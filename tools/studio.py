#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
studio.py — «завод» Лектория: одна команда → готовый ролик со звуком.

Оркестратор всего конвейера. По манифесту продакшенов (tools/productions.json)
для каждого ролика последовательно:

  1) КАРТИНКИ  — генерит недостающие иллюстрации по текстовым промтам
                 (tools/image_gen.py, Nano Banana / image API). Опционально.
  2) РЕНДЕР    — движок animdsl рендерит НЕМОЙ ролик (.anim → mp4/png).
  3) ОЗВУЧКА   — Fish Audio по VO-сценарию (tools/voiceover.py) → mp3. Опц.
  4) СВЕДЕНИЕ  — ffmpeg подмешивает голос к видео (tools/compose_video.sh)
                 → финальный mp4 со звуком.

Любой шаг, у которого нет ключа/инструмента, аккуратно пропускается с
понятным логом — конвейер не падает, а отдаёт что смог (немой mp4 как минимум).

Ключи берутся ТОЛЬКО из окружения (в CI — из GitHub Secrets), никогда из кода:
  * FISH_AUDIO_API_KEY   — озвучка (обязателен для звука);
  * FISH_AUDIO_VOICE_ID  — голос Фреди (reference_id), желателен;
  * IMAGE_API_KEY        — генерация картинок (Nano Banana / провайдер), опц.;
  * IMAGE_API_PROVIDER   — gemini|openai|... (по умолчанию gemini).

Использование:
    python3 tools/studio.py                 # все продакшены из манифеста
    python3 tools/studio.py pereproshivka-intro   # только один (по id)
    python3 tools/studio.py --engine ./target/release/animdsl
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DEFAULT_MANIFEST = TOOLS / "productions.json"
DEFAULT_ENGINE = ROOT / "target" / "release" / "animdsl"


def log(msg):
    print(msg, flush=True)


def have_ffmpeg():
    from shutil import which
    return which("ffmpeg") is not None


def run(cmd, **kw):
    log("  $ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def step_images(prod, out_dir):
    """Генерит объявленные картинки (если задан IMAGE_API_KEY)."""
    images = prod.get("images", [])
    if not images:
        return
    if not os.environ.get("IMAGE_API_KEY"):
        log("  [картинки] IMAGE_API_KEY не задан — пропуск генерации "
            f"({len(images)} шт., будут использованы существующие ассеты).")
        return
    gen = TOOLS / "image_gen.py"
    for img in images:
        dst = ROOT / img["out"]
        if dst.exists() and not img.get("force"):
            log(f"  [картинки] уже есть: {img['out']} — пропуск.")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(gen), "-o", str(dst), "--prompt", img["prompt"]]
        if img.get("wrap_svg"):
            cmd += ["--wrap-svg", str(ROOT / img["wrap_svg"])]
        if img.get("size"):
            cmd += ["--size", img["size"]]
        try:
            run(cmd)
        except subprocess.CalledProcessError as e:
            log(f"  [картинки] не удалось сгенерить {img['out']}: {e} — пропуск.")


# ВЕРТИКАЛЬНЫЙ ФОРМАТ — ВТОРОЙ КАДР, А НЕ ОБРЕЗКА. Ролики живут в двух местах:
# горизонталь для сайта и YouTube, вертикаль для ленты. Обрезать горизонталь по
# бокам нельзя: у нас фигура ходит по трети кадра влево-вправо (хук справа,
# добивка слева — это режиссура, а не украшение), и обрезка выбрасывает её из
# кадра ровно на ударных репликах.
#
# Поэтому вертикаль РЕНДЕРИТСЯ ЗАНОВО из того же сценария другим размером кадра.
# Одна поправка обязательна: `scales` и вся карта фигуры отсчитываются от ВЫСОТЫ
# кадра, а в вертикали высота больше в 3.16 раза — фигура вылезла бы за кадр.
# Компенсация ставится прямо в config через подмену строки `height`, а рост
# сущностей делится на отношение высот.
VERTICAL = (720, 1280)


def _vertical_source(src_anim):
    """Сценарий, пересчитанный под вертикальный кадр. Возвращает путь или None."""
    src = Path(src_anim)
    text = src.read_text(encoding="utf-8")
    m = re.search(r"width:\s*(\d+)\s*\n\s*height:\s*(\d+)", text)
    if not m:
        return None
    w0, h0 = int(m.group(1)), int(m.group(2))
    k = VERTICAL[1] / h0                       # во столько раз выше кадр
    out = text.replace(m.group(0), f"width: {VERTICAL[0]}\n    height: {VERTICAL[1]}")
    # рост фигур: `x scales N` и `x scales N over ...` — делим на k
    out = re.sub(r"(\b\w+ scales )([\d.]+)",
                 lambda mm: f"{mm.group(1)}{round(float(mm.group(2)) / k, 4)}", out)
    dst = src.with_name(f".{src.stem}.vert.anim")
    dst.write_text(out, encoding="utf-8")
    return dst


def step_render(src_anim, engine, out_mp4, vertical=False):
    """Немой рендер .anim → mp4. `vertical` — второй кадр 720×1280."""
    src = Path(src_anim)
    if not src.exists():
        raise FileNotFoundError(f"нет сценария: {src}")
    if vertical:
        vsrc = _vertical_source(src)
        if vsrc is None:
            log("  [вертикаль] в config нет width/height — вертикальный кадр пропущен.")
            return None
        src = vsrc
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    run([str(engine), "render", str(src), "-o", str(out_mp4)])
    return out_mp4


def step_voice(prod, out_voice, parts_dir):
    """Озвучка VO-сценария → mp3 + реплики по файлам (vo-<N>.mp3) для липсинка."""
    vo = prod.get("vo")
    if not vo:
        log("  [озвучка] VO-сценарий не задан — немой ролик.")
        return None
    if not (os.environ.get("FREDERICK_ADMIN_TOKEN") or os.environ.get("FISH_AUDIO_API_KEY")):
        log("  [озвучка] нет FISH_AUDIO_API_KEY (и запасного FREDERICK_ADMIN_TOKEN) — "
            "озвучка пропущена (секрет: Settings → Secrets and variables → Actions).")
        return None
    vo_path = ROOT / vo
    if not vo_path.exists():
        log(f"  [озвучка] нет VO-файла: {vo} — пропуск.")
        return None
    # Мягко: сбой озвучки НЕ рушит завод — просто немой ролик + лог причины.
    try:
        run([sys.executable, str(TOOLS / "voiceover.py"), str(vo_path),
             "-o", str(out_voice), "--parts-dir", str(parts_dir)])
        return out_voice
    except subprocess.CalledProcessError as e:
        log(f"  [озвучка] не удалась ({e}) — оставляю немой ролик. "
            "Проверь FISH_AUDIO_API_KEY / FISH_AUDIO_VOICE_ID (прямой путь Fish).")
        return None


def step_voice_parts(prod, parts_dir):
    """Сгенерить реплики по файлам (vo-<N>.mp3) БЕЗ сборки дорожки."""
    vo = prod.get("vo")
    if not vo:
        log("  [озвучка] VO-сценарий не задан — немой ролик.")
        return False
    if not (os.environ.get("FREDERICK_ADMIN_TOKEN") or os.environ.get("FISH_AUDIO_API_KEY")):
        log("  [озвучка] нет токенов — озвучка пропущена.")
        return False
    vo_path = ROOT / vo
    if not vo_path.exists():
        log(f"  [озвучка] нет VO-файла: {vo} — пропуск.")
        return False
    try:
        run([sys.executable, str(TOOLS / "voiceover.py"), str(vo_path),
             "-o", str(parts_dir / "_unused.mp3"), "--parts-dir", str(parts_dir),
             "--no-assemble"])
        return True
    except subprocess.CalledProcessError as e:
        log(f"  [озвучка] не удалась ({e}) — немой ролик.")
        return False


def step_assemble_voice(prod, prepped_anim, parts_dir, out_voice, engine):
    """Собрать голосовую дорожку по фактическим временам движка."""
    vo_path = ROOT / prod["vo"]
    times = Path(str(prepped_anim) + ".times.json")
    mapf = Path(str(prepped_anim) + ".map.json")
    try:
        with open(times, "w") as f:
            subprocess.run([str(engine), "timing", str(prepped_anim)],
                           check=True, stdout=f)
        run([sys.executable, str(TOOLS / "voiceover.py"), str(vo_path),
             "-o", str(out_voice), "--assemble-only",
             "--parts-dir", str(parts_dir),
             "--times-json", str(times), "--map-json", str(mapf)])
        return out_voice
    except subprocess.CalledProcessError as e:
        log(f"  [сборка голоса] не удалась ({e}) — немой ролик.")
        return None


def step_prep_lipsync(prod, parts_dir):
    """Впаять липсинк по звуку в сценарий (или флэп-фолбэк). Возвращает .anim для рендера.

    Пишем рядом с оригиналом (относительные import'ы разрешаются от папки .anim).
    """
    src = ROOT / prod["anim"]
    prepped = src.with_name(f".{src.stem}.lipsynced.anim")
    try:
        cmd = [sys.executable, str(TOOLS / "prep_lipsync.py"), str(src),
               "--parts", str(parts_dir), "-o", str(prepped)]
        if prod.get("vo"):
            cmd += ["--vo", str(ROOT / prod["vo"])]
        run(cmd)
        return prepped
    except subprocess.CalledProcessError as e:
        log(f"  [липсинк] препроцессор не сработал ({e}) — рендерю исходный сценарий.")
        return src


def step_sfx(prod, video_mp4, out_sfx, prepped_anim=None):
    """Синтезировать SFX-дорожку по таблице из VO.md (длина = длине видео).

    Тайм-коды в таблице проставлены по СЦЕНАРИЮ, а готовый ролик длиннее:
    диктор говорит не ровно столько, сколько заявлено. Поэтому кии переводятся
    на фактический монтаж по временам реплик из `animdsl timing` — тот же файл,
    по которому собирается голос. Без этого звук отъезжает от того, что он
    озвучивает: звон битого стекла звучал, когда очки ещё сидели на маске.
    """
    vo = prod.get("vo")
    if not vo or not (ROOT / vo).exists() or not have_ffmpeg():
        return None
    try:
        dur = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(video_mp4)],
            check=True, capture_output=True, text=True).stdout.strip()
        cmd = [sys.executable, str(TOOLS / "sfx.py"), str(ROOT / vo),
               "-o", str(out_sfx), "--duration", dur]
        times = Path(str(prepped_anim) + ".times.json") if prepped_anim else None
        if times and times.exists():
            cmd += ["--times-json", str(times)]
            mapf = Path(str(prepped_anim) + ".map.json")
            if mapf.exists():
                cmd += ["--map-json", str(mapf)]
        run(cmd)
        return out_sfx if Path(out_sfx).exists() else None
    except subprocess.CalledProcessError as e:
        log(f"  [sfx] синтез не удался ({e}) — без звуковых эффектов.")
        return None


def step_mux(prod, video_mp4, voice_mp3, sfx_mp3, out_final):
    """Свести видео + голос + SFX → финальный mp4 (ffmpeg)."""
    have_voice = voice_mp3 is not None and Path(voice_mp3).exists()
    have_sfx = sfx_mp3 is not None and Path(sfx_mp3).exists()
    if not have_voice and not have_sfx:
        log("  [сведение] нет ни озвучки, ни SFX — финальный ролик = немой рендер.")
        return None
    if not have_ffmpeg():
        log("  [сведение] ffmpeg не найден — сведение пропущено "
            "(в CI ffmpeg ставится; локально установите ffmpeg).")
        return None
    # Голос + SFX премиксуются в одну дорожку (голос громче, SFX — подложка).
    audio = voice_mp3 if have_voice else sfx_mp3
    if have_voice and have_sfx:
        mixed = Path(video_mp4).with_name(Path(video_mp4).stem + "-mix.mp3")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(voice_mp3), "-i", str(sfx_mp3),
             "-filter_complex",
             "[0]volume=1.0[v];[1]volume=0.75[s];"
             "[v][s]amix=inputs=2:duration=longest:normalize=0",
             "-b:a", "160k", str(mixed)])
        audio = mixed
    cmd = ["bash", str(TOOLS / "compose_video.sh"),
           str(video_mp4), str(audio), str(out_final)]
    if prod.get("title"):
        cmd.append(prod["title"])
    run(cmd)
    return out_final


def _ffprobe(path, entries, select=None):
    cmd = ["ffprobe", "-v", "error", "-show_entries", entries,
           "-of", "default=nw=1:nk=1"]
    if select:
        cmd += ["-select_streams", select]
    cmd.append(str(path))
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def media_duration(path):
    try:
        return float(_ffprobe(path, "format=duration") or 0.0)
    except ValueError:
        return 0.0


def has_audio(path):
    return bool(_ffprobe(path, "stream=codec_type", select="a:0"))


def qc_production(prod, video_mp4, final_mp4, voice_expected, voice_produced):
    """Гейт качества. Возвращает (hard, soft) — списки сообщений.

    HARD = наш дефект (нет рендера, грубый рассинхрон, ПОТЕРЯ уже сгенеренного
    голоса в миксе) → должен ронять --strict.
    SOFT = внешний сбой (TTS недоступен → голос вообще не сгенерился) — НЕ наша
    вина, только предупреждение; здоровые файлы всё равно должны закоммититься.

    `voice_produced` снимает неоднозначность «нет звука»: если голосовая дорожка
    БЫЛА собрана (voice.mp3 существует), а в финале звука нет — это НАШ баг микса
    (step_mux потерял дорожку) → HARD; если голоса не было вовсе → внешний TTS → SOFT.
    Иначе гейт прощал бы собственные баги сборки под видом внешнего сбоя."""
    hard, soft = [], []
    if not Path(video_mp4).exists():
        hard.append(f"{prod['id']}: нет отрендеренного video ({Path(video_mp4).name})")
        return hard, soft
    if voice_expected and prod.get("vo"):
        if not have_ffmpeg():
            return hard, soft  # без ffprobe проверить нечем
        if not Path(final_mp4).exists() or not has_audio(final_mp4):
            if voice_produced:
                hard.append(f"{prod['id']}: голос СОБРАН (voice.mp3 есть), но в финале "
                            "нет звука — потеря дорожки в сведении (наш баг микса)")
            else:
                soft.append(f"{prod['id']}: заявлен vo, но голос не сгенерился "
                            "(вероятно недоступен TTS) — отдаём немой рендер")
        else:
            vd, ad = media_duration(video_mp4), media_duration(final_mp4)
            if vd > 0 and abs(ad - vd) / vd > 0.20:
                # Рассинхрон при СУЩЕСТВУЮЩЕМ звуке — дефект сборки. HARD.
                hard.append(f"{prod['id']}: рассинхрон длительностей "
                            f"video={vd:.1f}s vs final={ad:.1f}s (>20%)")
    return hard, soft


def lint_sync(prod):
    """Статический линт синхрона голос↔рот. Возвращает (hard, soft).

    Ловит класс бага «Бизнес-мышления»: у продакшена есть VO, но в сцене нет
    машинных тегов //lip → синхрон завода не включается, голос кладётся по
    рукописным таймкодам и разъезжается с движением рта. Проверка статическая
    (без рендера/ключей), гоняется до сборки — падаем быстро.

    Легитимно: //lip меньше, чем реплик VO (дикторские строки поверх
    неговорящих планов — напр. титр). Нелегитимно: 0 тегов при говорящей сцене,
    дубли, ссылка на несуществующую реплику."""
    hard, soft = [], []
    vo = prod.get("vo")
    if not vo:
        return hard, soft
    anim = ROOT / prod.get("anim", "")
    vo_path = ROOT / vo
    if not anim.exists() or not vo_path.exists():
        return hard, soft  # отсутствие файлов ловит step_render/step_voice
    import re
    text = anim.read_text(encoding="utf-8")
    lips = [int(m.group(1)) for m in re.finditer(r"^\s*//lip\s+(\d+)\s*$", text, re.M)]
    n_speaks = len(re.findall(r"^\s*\S+\s+speaks\s+for\s", text, re.M))
    n_vo = len(re.findall(r"^\s*\|\s*VO-\d+\s*\|", vo_path.read_text(encoding="utf-8"), re.M))

    if n_speaks > 0 and not lips:
        hard.append(f"{prod['id']}: VO задан, но в сцене НЕТ ни одного //lip — "
                    f"синхрон не включится (голос ляжет по таймкодам и разъедется)")
    dups = {n for n in lips if lips.count(n) > 1}
    if dups:
        hard.append(f"{prod['id']}: дублируются //lip {sorted(dups)} — карта блоков сломается")
    over = [n for n in lips if n_vo and n > n_vo]
    if over:
        hard.append(f"{prod['id']}: //lip {sorted(set(over))} ссылаются на реплики "
                    f"сверх VO (в VO {n_vo} шт.)")
    if lips and n_speaks > len(lips):
        soft.append(f"{prod['id']}: {n_speaks - len(lips)} speaks-блок(ов) без //lip — "
                    f"озвучатся флэпами без синхрона")
    return hard, soft


# Кости рук и порог, за которым рука считается ПОДНЯТОЙ. Дефолт покоя — 30° и
# −29°: рука висит вдоль тела. 60° и выше — вынос в сторону или вперёд.
ARM_BONES = ("upper_arm_left", "upper_arm_right")
ARM_RAISED = 60.0


def lint_arms(prod, rig_dir=None):
    """Приёмщик РУК: не забыта ли поднятая рука в следующей позе. (hard, soft).

    ЛОВУШКА НАКЛАДЫВАЕМЫХ ПОЗ. Поза перекрывает ТОЛЬКО те кости, которые
    называет. `v_upor` поднимает левую руку на 92°, `raskryl` на 100°, `lunge`
    на 85° — а `smug`, `stern`, `doubt`, `calm_*` рук не называют вовсе. Значит
    после «в упор» персонаж уходит в следующую реплику С ТОРЧАЩЕЙ В СТОРОНУ
    РУКОЙ и стоит так, пока какая-нибудь поза руку не опустит.

    Это не описка в одном сценарии, а свойство рига, на которое наступает
    каждый, кто пишет монтаж. В «Мышлении» рука так провисела половину ролика,
    и заметил это не завод, а студия — глазами, на готовом видео.

    Гейт проходит по сценарию в порядке поз и считает, сколько ПОДРЯД идёт поз
    с унаследованной поднятой рукой. Одна-две — приём (жест держится через
    склейку). Три и больше — рука забыта.
    """
    anim = ROOT / prod.get("anim", "")
    rig = Path(rig_dir) if rig_dir else ROOT / "examples/assets/characters/freeman_rig"
    if not anim.exists() or not (rig / "rig.json").exists():
        return [], []
    poses = json.loads((rig / "rig.json").read_text(encoding="utf-8"))["poses"]
    seq = re.findall(r'pose\s+"([a-z_0-9]+)"', anim.read_text(encoding="utf-8"))
    hard, soft = [], []
    state = {b: None for b in ARM_BONES}       # угол, унаследованный от прошлой позы
    since = {b: 0 for b in ARM_BONES}          # сколько поз рука висит поднятой
    culprit = {b: "" for b in ARM_BONES}
    for name in seq:
        bones = poses.get(name, {}).get("bones", {})
        for b in ARM_BONES:
            if b in bones and "rotation" in bones[b]:
                ang = float(bones[b]["rotation"])
                state[b] = ang
                since[b] = 1 if abs(ang) >= ARM_RAISED else 0
                culprit[b] = name if abs(ang) >= ARM_RAISED else ""
            elif state[b] is not None and abs(state[b]) >= ARM_RAISED:
                since[b] += 1                  # поза руку не назвала — рука висит
                if since[b] >= 4:
                    # ПРЕДУПРЕЖДЕНИЕ, А НЕ ЗАПРЕТ — И ЭТО ОСОЗНАННО.
                    # Гейт написан раньше, чем починены ролики: забытая рука
                    # живёт в шести из семи, включая эталон. Жёстким он уронил
                    # ЗАВОД ЦЕЛИКОМ и не отдал ни одного ролика — то есть
                    # старый дефект перевесил всю новую работу. Гейт, который
                    # останавливает линию из-за давно существующей болезни,
                    # вреднее самой болезни: он не чинит, а только не даёт
                    # выпускать. Станет жёстким, когда все шесть будут чисты.
                    soft.append(
                        f"{prod['id']}: {b} поднята в позе «{culprit[b]}» "
                        f"({abs(state[b]):.0f}°) и не опущена — уже {since[b]} поз "
                        f"подряд, к позе «{name}». Опусти явно или возьми позу, "
                        f"которая называет руки.")
                    since[b] = 0               # об одном месте — одно сообщение
    return hard, soft


# ПОКОЙ КАДРА. Три источника дрожи складываются, а считали их порознь: контур
# (`line-boil`), увод кадра (`gate-weave`) и мерцание (`film-flicker`). Каждый
# по отдельности «еле заметен», вместе — рябь, которую студия увидела как
# «персонаж корявый и трясётся». Ориентиры покоя из PRAVILA-DVIZHENIYA.md §2.
BOIL_LIMITS = {"line-boil": 0.6, "gate-weave": 0.4, "film-flicker": 0.03}
MAX_SECONDS = 60.0          # потолок длины ролика, задан студией


def lint_pokoy(prod):
    """Приёмщик ПОКОЯ: не трясётся ли кадр. (hard, soft)."""
    anim = ROOT / prod.get("anim", "")
    if not anim.exists():
        return [], []
    text = anim.read_text(encoding="utf-8")
    soft = []
    for key, lim in BOIL_LIMITS.items():
        m = re.search(rf"{key}:\s*([\d.]+)", text)
        if m and float(m.group(1)) > lim:
            soft.append(f"{prod['id']}: {key} = {m.group(1)} при пороге покоя "
                        f"{lim} — на удержанном рисунке это тремор, а не "
                        f"рукотворность (PRAVILA-DVIZHENIYA.md §2)")
    return [], soft


def lint_dlina(prod, final_mp4):
    """Приёмщик ДЛИНЫ: ролик длиннее потолка. (hard, soft)."""
    if not Path(final_mp4).exists() or not have_ffmpeg():
        return [], []
    try:
        d = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(final_mp4)],
            check=True, capture_output=True, text=True).stdout.strip())
    except Exception:                                        # noqa: BLE001
        return [], []
    if d > MAX_SECONDS:
        return [], [f"{prod['id']}: {d:.1f}с при потолке {MAX_SECONDS:.0f}с — "
                    f"режь текст и паузы между сценами"]
    return [], []


def lint_propy(prod):
    """Приёмщик ПРЕДМЕТОВ: бег задом и исчезновение посреди плана. (hard, soft).

    Крыса в «Перепрошивке» бежала справа налево, нарисованная смотрящей вправо,
    и пропадала на середине пути: `hides` стоял сразу после `moves-to`, а план
    длился дольше. Оба дефекта видны в тексте сценария, но их никто не искал.
    """
    anim = ROOT / prod.get("anim", "")
    if not anim.exists():
        return [], []
    lines = anim.read_text(encoding="utf-8").split("\n")
    # Отрицательный масштаб — и есть разворот пропа: у пропов нет `facing`,
    # флип делается знаком (см. render_svg_to_pixmap, flip_bg). Помечаем такие
    # предметы, иначе гейт ругается на ПРАВИЛЬНО развёрнутую крысу.
    pos, soft, flipped = {}, [], set()
    for i, l in enumerate(lines):
        m = re.search(r"let (\w+) = prop\([^)]*\) at \(([\d.]+),", l)
        if m:
            pos[m.group(1)] = float(m.group(2))
            continue
        m = re.search(r"(\w+) scales\s+-[\d.]+", l)
        if m:
            flipped.add(m.group(1))
            continue
        m = re.search(r"(\w+) moves-to \((-?[\d.]+),", l)
        if m and m.group(1) in pos:
            x0, x1 = pos[m.group(1)], float(m.group(2))
            if x1 < x0 - 0.05 and m.group(1) not in flipped:
                soft.append(f"{prod['id']}: «{m.group(1)}» едет ВЛЕВО "
                            f"({x0:.2f}→{x1:.2f}), а пропы не разворачиваются — "
                            f"предмет поедет задом (PRAVILA-DVIZHENIYA.md §6)")
            pos[m.group(1)] = x1
            # `hides` сразу следом — предмет растворяется посреди плана
            nxt = next((x.strip() for x in lines[i + 1:i + 3] if x.strip()), "")
            if nxt == f"{m.group(1)} hides" and 0.0 <= x1 <= 1.0:
                soft.append(f"{prod['id']}: «{m.group(1)}» прячется в точке "
                            f"{x1:.2f} — это ВНУТРИ кадра, зритель увидит, как "
                            f"предмет растворяется (§7)")
    return [], soft


# ПЛОТНОСТЬ ЖЕСТА. В риге 124 позы, а в монтаже крутится полтора десятка — и
# именно отсюда «нет динамики», а не из настроек рендера. Порог снят с
# «Перепрошивки» и «Тюрьмы» (32 и 30 поз в минуту), где движение читается;
# «Мышление» с шестнадцатью выглядит стоячим.
# Считается ДВА числа, и оба важны: сколько смен позы в минуту (движение) и
# сколько РАЗНЫХ поз (разнообразие). Двадцать смен между тремя позами — это
# не жестикуляция, а тик.
POSES_PER_MIN = 26
DISTINCT_MIN = 14


def lint_dinamika(prod):
    """Приёмщик ДИНАМИКИ: часто ли и разнообразно ли меняются позы. (hard, soft)."""
    anim = ROOT / prod.get("anim", "")
    if not anim.exists():
        return [], []
    text = anim.read_text(encoding="utf-8")
    seq = re.findall(r'pose\s+"([a-z_0-9]+)"', text)
    secs = sum(float(x) for x in re.findall(r"duration:\s*(\d+)s", text))
    if secs < 5 or not seq:
        return [], []
    per_min = 60.0 * len(seq) / secs
    soft = []
    if per_min < POSES_PER_MIN:
        soft.append(f"{prod['id']}: {per_min:.0f} смен позы в минуту при норме "
                    f"{POSES_PER_MIN} — фигура стоит столбом. Живое движение это "
                    f"НАМЕРЕННЫЕ жесты на ударах реплик (PRAVILA-DVIZHENIYA.md §4)")
    if len(set(seq)) < DISTINCT_MIN:
        soft.append(f"{prod['id']}: разных поз {len(set(seq))} при норме "
                    f"{DISTINCT_MIN} — в риге их 124, монтаж их не видит")
    return [], soft


def lint_turnaround(prods):
    """Приёмщик РАЗВОРОТА: одна ли это фигура на всех ракурсах. (hard, soft).

    Развороты жили в риге непроверенными, пока ролики шли анфасом: профиль
    схлопнулся вдвое против замера листа, на профиле и полуспине фигура
    проседала, глаза со стороны затылка исчезали не там, где надо. Ни одна
    метрика этого не ловила — смотрели глазом на контрольную картинку.

    Гейт меряет замером и делит нарушения по ответственности: ракурс, который
    хоть один ролик манифеста РЕАЛЬНО играет, роняет прогон; ракурс, лежащий
    на полке, идёт предупреждением. Иначе выбор был бы между «всё или ничего»:
    сломанный профиль запрещал бы выпуск ролика, снятого анфасом.
    """
    used = set()
    for prod in prods:
        anim = ROOT / prod.get("anim", "")
        if anim.exists():
            used |= set(re.findall(r'pose\s+"([a-z_0-9]+)"',
                                   anim.read_text(encoding="utf-8")))
    try:
        sys.path.insert(0, str(TOOLS))
        import turnaround
    except Exception as e:                                   # noqa: BLE001
        return [], [f"гейт разворота не запустился ({e})"]
    out = io.StringIO()
    with redirect_stdout(out):
        code = turnaround.report(str(ROOT / "examples/assets/characters/freeman_rig"),
                                 True, turnaround.angles_of(sorted(used)))
    for line in out.getvalue().splitlines():
        if line.strip():
            log("  " + line.rstrip())
    return ([] if code == 0 else ["разворот: нарушения на ракурсах, которые "
                                  "играют ролики — см. таблицу выше"]), []


def lint_location(prod):
    """Приёмщик локаций: проверяет сеты продакшена на «готовность». (hard, soft).

    Пропускает локацию к съёмке, только если надписи в порядке:
    - ЯЗЫК: текст на стенах — русский по умолчанию (кириллица). Латинские слова
      (2+ буквы подряд) выносятся как замечание, если в манифесте не задан
      "allow_latin": true (напр. бренд/аббревиатура). SOFT — на утверждение.
    - ЧИТАЕМОСТЬ: оценка ширины строки не должна вылезать за кадр (обрезка
      текста = нечитаемо). SOFT.
    Геометрию берём из <text ...>content</text> сета."""
    import re
    hard, soft = [], []
    anim = ROOT / prod.get("anim", "")
    if not anim.exists():
        return hard, soft
    allow_latin = bool(prod.get("allow_latin"))
    text = anim.read_text(encoding="utf-8")
    sets = re.findall(r'import\s+set\s+\w+\s+from\s+"([^"]+)"', text)
    for rel in sets:
        svg_path = (anim.parent / rel).resolve()
        if not svg_path.exists():
            continue
        svg = svg_path.read_text(encoding="utf-8")
        W = 1280
        mv = re.search(r'viewBox="0 0 (\d+)', svg)
        if mv:
            W = int(mv.group(1))
        # НАСЛЕДОВАНИЕ ОТ ГРУППЫ. text-anchor, font-size и font-family в SVG
        # наследуются: у нас заголовки карточек лежат в <g text-anchor="middle">
        # с голыми <text> внутри. Проверка читала только атрибуты самого <text>,
        # считала якорь «start» и объявляла вылет на строках, которые стоят по
        # центру с запасом в двести пикселей. Держим стек групп и разрешаем
        # атрибуты как SVG: своё перебивает унаследованное.
        stack = [{}]
        for m in re.finditer(r'<g\b([^>]*)>|</g>|<text\b([^>]*)>(.*?)</text>',
                             svg, re.S):
            tok = m.group(0)
            if tok.startswith("<g"):
                inh = dict(stack[-1])
                inh.update(dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1) or "")))
                stack.append(inh)
                continue
            if tok == "</g>":
                if len(stack) > 1:
                    stack.pop()
                continue
            attrs = dict(stack[-1])
            attrs.update(dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(2) or "")))
            content = re.sub(r"\s+", " ", m.group(3)).strip()
            if not content:
                continue
            if not allow_latin and re.search(r"[A-Za-z]{2,}", content):
                soft.append(f"{prod['id']}: {svg_path.name}: нерусский текст "
                            f"«{content}» (русский по умолчанию; задай allow_latin)")
            fs = float(attrs.get("font-size", 12))
            x = float(attrs.get("x", 0))
            approx_w = len(content) * fs * 0.6
            # `x` — ЯКОРЬ, а не левый край: при "middle" строка растёт в обе
            # стороны, при "end" — влево. Ложные тревоги приёмщика опаснее
            # молчания: они приучают пролистывать список, и настоящий вылет
            # уедет вместе с ними.
            anchor = attrs.get("text-anchor", "start")
            left = (x - approx_w / 2 if anchor == "middle"
                    else x - approx_w if anchor == "end" else x)
            if left < -8 or left + approx_w > W + 8:
                soft.append(f"{prod['id']}: {svg_path.name}: строка «{content}» "
                            f"вылезает за кадр (обрезка → нечитаемо)")
    return hard, soft


def run_planka(prod, engine, render_sec, final_mp4):
    """Гонит tools/qc_metrics.py на эталоне и переводит результат в (hard, soft).

    HARD-метрики планки (длина плана, скорость рендера, golden-frame diff) идут в
    общий hard-бакет → под --strict роняют прогон (не взяли планку = красный).
    loudness — soft (чинится нормализом, не дефект картинки). Голдены лежат в
    tests/golden/<id>; их обновление — отдельной командой (--update-golden),
    не на каждом прогоне, иначе diff бессмыслен."""
    hard, soft = [], []
    anim = ROOT / prod["anim"]
    golden_dir = ROOT / "tests" / "golden" / prod["id"]
    out_json = ROOT / "videos" / f".{prod['id']}.planka.json"
    cmd = [sys.executable, str(TOOLS / "qc_metrics.py"),
           "--anim", str(anim), "--engine", str(engine),
           "--golden-dir", str(golden_dir),
           "--render-sec", f"{render_sec:.1f}", "--json", str(out_json)]
    if final_mp4 and Path(final_mp4).exists():
        cmd += ["--final", str(final_mp4)]
    try:
        run(cmd)
    except subprocess.CalledProcessError as e:
        soft.append(f"{prod['id']}: планка не измерена ({e})")
        return hard, soft
    try:
        data = json.loads(Path(out_json).read_text(encoding="utf-8"))
    except Exception:
        soft.append(f"{prod['id']}: планка — нет отчёта JSON")
        return hard, soft
    for name, m in data.get("metrics", {}).items():
        if m.get("pass"):
            continue
        msg = (f"{prod['id']}: планка «{name}» = {m.get('value')} "
               f"(цель {m.get('target', '?')})")
        (hard if m.get("kind") == "hard" else soft).append(msg)
    return hard, soft


def build_one(prod, engine, videos_dir, voice_expected=False):
    pid = prod["id"]
    log(f"\n=== ПРОДАКШЕН: {pid} — {prod.get('desc', '')}")
    video_mp4 = videos_dir / f"{pid}.mp4"
    voice_mp3 = videos_dir / f"{pid}-voice.mp3"
    final_mp4 = videos_dir / f"{pid}-final.mp4"
    parts_dir = videos_dir / f"{pid}-parts"

    # Порядок: картинки → озвучка ЧАСТЯМИ → липсинк по звуку в сцену →
    # ФАКТИЧЕСКИЕ времена речи из движка (animdsl timing) → сборка голосовой
    # дорожки по этим временам (синхрон по конструкции) → рендер → SFX → микс.
    step_images(prod, videos_dir)
    parts_ok = step_voice_parts(prod, parts_dir)
    src_anim = step_prep_lipsync(prod, parts_dir)
    voice = step_assemble_voice(prod, src_anim, parts_dir, voice_mp3, engine) if parts_ok else None
    import time as _time
    _t0 = _time.monotonic()
    step_render(src_anim, engine, video_mp4)
    render_sec = _time.monotonic() - _t0
    # Вертикаль — тот же сценарий другим кадром. Отдельный файл, отдельная
    # сборка звука не нужна: дорожка та же, различается только картинка.
    # ВЕРТИКАЛЬ ВЫКЛЮЧЕНА ПО УМОЛЧАНИЮ. Пересчёт сценария работает (кадр
    # 720×1280, рост фигур поделён на отношение высот — проверено), но сам
    # рендер вертикального кадра на порядок медленнее горизонтального:
    # локация 1280×720 в кадре 720×1280 растягивается по большей стороне и
    # растрируется в 2278×1280 КАЖДЫЙ кадр, кэш пиксмапов такого не держит.
    # Включать в прогон в таком виде нельзя — раннер встанет. Включается
    # переменной VERTICAL=1, пока причина не найдена и не устранена.
    video_vert = videos_dir / f"{pid}-vert.mp4"
    if (os.environ.get("VERTICAL") or "").strip() not in ("", "0"):
        try:
            step_render(src_anim, engine, video_vert, vertical=True)
        except Exception as e:                              # noqa: BLE001
            log(f"  [вертикаль] рендер не удался ({e}) — только горизонталь.")
            video_vert = None
    else:
        video_vert = None
    sfx = step_sfx(prod, video_mp4, videos_dir / f"{pid}-sfx.mp3", src_anim)
    step_mux(prod, video_mp4, voice, sfx, final_mp4)
    if video_vert is not None and Path(video_vert).exists():
        step_mux(prod, video_vert, voice, sfx, videos_dir / f"{pid}-vert-final.mp4")

    made = []
    for p in (video_mp4, voice_mp3, final_mp4):
        if p.exists():
            mb = p.stat().st_size / 1048576
            made.append(f"{p.name} ({mb:.1f}МБ)")
            if p.suffix == ".mp4" and mb > 95:
                log(f"  [!] {p.name} = {mb:.0f}МБ — превысит лимит GitHub (>100МБ), "
                    "снизь битрейт/длительность.")
    log(f"  → готово: {', '.join(made)}")

    voice_produced = voice is not None and Path(voice).exists()
    hard, soft = qc_production(prod, video_mp4, final_mp4, voice_expected, voice_produced)
    dh, ds = lint_dlina(prod, final_mp4)          # приёмщик длины
    hard += dh
    soft += ds

    # Планка Фримена: на эталонных продакшенах (флаг "planka") гоняем машинные
    # метрики Рубежа 2 — средняя длина плана / скорость рендера / golden-frame /
    # громкость. Без этого правки движения проверяются только глазами.
    if prod.get("planka"):
        ph, ps = run_planka(prod, engine, render_sec, final_mp4)
        hard += ph
        soft += ps

    for e in hard:
        log(f"  [QC-HARD] {e}")
    for e in soft:
        log(f"  [QC-soft] {e}")
    return hard, soft


def main(argv):
    ap = argparse.ArgumentParser(description="Завод Лектория: ролики со звуком")
    ap.add_argument("only", nargs="?", help="id одного продакшена (иначе — все)")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--engine", default=str(DEFAULT_ENGINE))
    ap.add_argument("--videos", default=str(ROOT / "videos"))
    ap.add_argument("--strict", action="store_true",
                    help="ненулевой выход, если QC-гейт нашёл немой/рассинхронный ролик")
    args = ap.parse_args(argv)
    strict = args.strict or bool(os.environ.get("QC_STRICT"))

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    prods = manifest["productions"]
    if args.only:
        prods = [p for p in prods if p["id"] == args.only]
        if not prods:
            sys.exit(f"нет продакшена с id={args.only}")

    engine = Path(args.engine)
    if not engine.exists():
        sys.exit(f"движок не собран: {engine} (cargo build --release)")
    videos_dir = Path(args.videos)
    videos_dir.mkdir(parents=True, exist_ok=True)

    log(f"Завод: {len(prods)} продакшен(ов); движок {engine}; "
        f"ffmpeg={'есть' if have_ffmpeg() else 'нет'}; "
        f"озвучка={'вкл' if (os.environ.get('FREDERICK_ADMIN_TOKEN') or os.environ.get('FISH_AUDIO_API_KEY')) else 'выкл'}; "
        f"картинки={'вкл' if os.environ.get('IMAGE_API_KEY') else 'выкл'}")
    voice_expected = bool(
        os.environ.get("FREDERICK_ADMIN_TOKEN") or os.environ.get("FISH_AUDIO_API_KEY")
    )
    # Пред-линт синхрона (статический, до рендера — падаем быстро на баге //lip).
    all_hard, all_soft = [], []
    for prod in prods:
        h, s = lint_sync(prod)
        all_hard += h
        all_soft += s
        lh, ls = lint_location(prod)      # приёмщик локаций
        all_hard += lh
        all_soft += ls
        ah, asf = lint_arms(prod)         # приёмщик рук
        all_hard += ah
        all_soft += asf
        ph, ps = lint_pokoy(prod)         # приёмщик покоя кадра
        all_hard += ph
        all_soft += ps
        rh, rs = lint_propy(prod)         # приёмщик предметов
        all_hard += rh
        all_soft += rs
        dh, ds = lint_dinamika(prod)      # приёмщик динамики
        all_hard += dh
        all_soft += ds
    th, ts = lint_turnaround(prods)       # приёмщик разворота (один на риг)
    all_hard += th
    all_soft += ts
    for e in all_hard:
        log(f"  [LINT-HARD] {e}")
    for e in all_soft:
        log(f"  [LINT-soft] {e}")
    if all_hard and strict:
        log("\nЛинт синхрона строгий → падаем ДО рендера (не жжём раннер на разъезде).")
        return 1

    for prod in prods:
        h, s = build_one(prod, engine, videos_dir, voice_expected)
        all_hard += h
        all_soft += s
    log("\nЗавод отработал.")
    if all_soft:
        log(f"\nQC soft ({len(all_soft)}) — внешние сбои, файлы всё равно отданы:")
        for e in all_soft:
            log(f"  - {e}")
    if all_hard:
        log(f"\nQC HARD ({len(all_hard)}) — дефекты сборки:")
        for e in all_hard:
            log(f"  - {e}")
        if strict:
            # ВАЖНО: даже при hard-fail здоровые файлы уже записаны; шаг CI
            # «Commit videos» стоит под if: always() и закоммитит их. Ненулевой
            # выход помечает прогон красным, но не стирает готовое.
            log("QC-гейт строгий → красный прогон (дефект сборки).")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
