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
  3а) ХРОНОМЕТРАЖ — `speaks for` и таймкоды VO переписываются по фактической
                 длине готовых реплик (tools/hronometrazh.py). Идёт сразу за
                 озвучкой и до липсинка: единственный момент, когда mp3 уже
                 есть, а сценарий ещё не отрендерен.
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


def step_hronometrazh(prod, parts_dir):
    """Переписать `speaks for` в СЦЕНАРИИ по фактической длине озвучки.

    ЕДИНСТВЕННЫЙ МОМЕНТ, КОГДА ЭТО ВОЗМОЖНО: mp3 уже синтезированы, сценарий
    ещё не отрендерен. До озвучки фактических длительностей не существует, а
    после рендера они уже никому не нужны.

    Автор пишет `speaks for` по мерке 0.36 с на слово — другого способа у него
    нет. Синтез на конкретной реплике длиннее расчёта на 0.2–0.45 с, и от этого
    числа считается всё остальное: каты и жесты соседней ветки `do{}`, гейт
    тишины, таймкоды VO-таблицы. Рот-то `prep_lipsync` откроет по звуку — врёт
    окружение реплики. Здесь сценарий становится тем, чем притворялся.

    Правка идёт В ИСХОДНЫЙ ФАЙЛ, а не во временную копию: смысл в том, чтобы
    раскадровка перестала врать, а не чтобы соврала тише. Прогон завода
    возвращает файл изменённым — CI дозаливает его в ветку.
    """
    src = ROOT / prod["anim"]
    cmd = [sys.executable, str(TOOLS / "hronometrazh.py"), str(src),
           "--parts", str(parts_dir)]
    if prod.get("vo"):
        cmd += ["--vo", str(ROOT / prod["vo"])]
    try:
        run(cmd)
    except subprocess.CalledProcessError as e:
        # Мягко: сценарий останется с расчётными числами, и завод соберёт ролик
        # ровно как собирал раньше — растяжку в prep_lipsync никто не отменял.
        log(f"  [хронометраж] не сработал ({e}) — `speaks for` остаётся расчётным.")


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
        # SFX ПРИЖИМАЕТСЯ ГОЛОСОМ (sidechain), а не просто стоит тише.
        #
        # Замечание студии: «появляются посторонние шумы, из-за которых не
        # слышно». Претензия подтвердилась замером: при `volume=0.75` дорожка
        # SFX шла на -26.7 LUFS против -22.4 LUFS у голоса — всего 4 LU
        # разницы. Для подложки под речь это не подложка, а второй голос:
        # разборчивость держится, когда фон сидит на 12-18 LU ниже.
        #
        # Просто убавить громкость мало: половина звуков в этих роликах
        # работает В ПАУЗАХ — «гул обрывается», «щёлкает замок», обрыв в
        # чёрное. Прижмёшь их насмерть — исчезнет и то, ради чего они
        # ставились. Поэтому компрессор с боковой цепью: пока звучит голос,
        # фон уходит вниз на ~8:1, в паузе возвращается за треть секунды.
        # Голос при этом не трогается вообще — он идёт в микс как есть и
        # только служит ключом.
        #
        # ЧИСЛА ПОДОБРАНЫ ЗАМЕРОМ на готовой дорожке «Дистанции». Виноваты были
        # три места, а не вся дорожка: кухня (гул холодильника, шелест бумаг,
        # калькулятор) шла на -12.6 dB при голосе -7.2 dB, эхо зала -20.4 dB,
        # шаги в финале -21.1 dB; всё остальное честно сидело на -36 dB. После
        # прижатия кухня уходит на -18.4 и -33.1 dB, то есть на 11-26 dB ниже
        # речи. Пробовал жёстче (0.5 / 8:1 / 350 мс) — фон становится совсем
        # неслышным и в паузах тоже; выбран средний вариант.
        run(["ffmpeg", "-y", "-v", "error", "-i", str(voice_mp3), "-i", str(sfx_mp3),
             "-filter_complex",
             "[0]asplit=2[v][key];"
             "[1]volume=0.6[s];"
             "[s][key]sidechaincompress=threshold=0.03:ratio=6:"
             "attack=5:release=250[duck];"
             "[v][duck]amix=inputs=2:duration=longest:normalize=0",
             "-b:a", "160k", str(mixed)])
        audio = mixed

    # МУЗЫКАЛЬНАЯ ВРЕЗКА. Ролик может кончаться песней: персонаж включает
    # кассетник, и дальше играет кусок трека. Описывается в манифесте:
    #     "music": {"file": "трек.mp3", "at": 62.0, "duration": 12.0,
    #               "start": 0.0, "volume": 0.9, "fade_out": 1.5}
    # `at` — секунда РОЛИКА, где музыка вступает (щелчок клавиши), `start` —
    # с какой секунды берётся сам трек. Кусок вырезается, задерживается на
    # `at` и подмешивается третьим входом: голос и SFX не трогаются, а музыка
    # приходит ровно туда, где нажали кнопку.
    music = prod.get("music")
    if music and (ROOT / music["file"]).exists():
        src = ROOT / music["file"]
        # «ПОСЛЕ РЕЧИ» — НЕ ЧИСЛО, А ПРАВИЛО. Секунду вступления считали руками
        # по рендеру, и она устаревала при первой же правке хронометража: в
        # ролике-презентации сцены подросли на паузы для ходьбы, голос вытянулся
        # до 112.8 с, а музыка осталась на 103.5 — и последние девять секунд
        # монолога играли ПОД песню. Теперь можно написать `"at": "after-voice"`
        # (плюс `gap`), и сборщик сам возьмёт длину готовой озвучки: музыка
        # физически не может начаться раньше, чем персонаж договорит.
        at_raw = music.get("at", 0.0)
        if isinstance(at_raw, str) and at_raw.startswith("after-voice"):
            gap = float(music.get("gap", 1.5))
            at = (media_duration(voice_mp3) if have_voice else 0.0) + gap
            log(f"  [музыка] вступает после речи: {at:.1f} c "
                f"(озвучка {media_duration(voice_mp3):.1f} c + пауза {gap} c)")
        else:
            at = float(at_raw)
        dur = float(music.get("duration", 12.0))
        start = float(music.get("start", 0.0))
        vol = float(music.get("volume", 0.9))
        fade = float(music.get("fade_out", 1.5))
        piece = Path(video_mp4).with_name(Path(video_mp4).stem + "-music.mp3")
        # Вырезаем кусок с затуханием в хвосте: обрыв на полуноте читается
        # как технический сбой, а не как точка.
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start}", "-t", f"{dur}",
             "-i", str(src),
             "-af", f"volume={vol},afade=t=out:st={max(dur - fade, 0):.2f}:d={fade}",
             "-b:a", "192k", str(piece)])
        with_music = Path(video_mp4).with_name(Path(video_mp4).stem + "-mixmus.mp3")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(audio), "-i", str(piece),
             "-filter_complex",
             f"[1]adelay={int(at * 1000)}|{int(at * 1000)}[m];"
             f"[0][m]amix=inputs=2:duration=longest:normalize=0",
             "-b:a", "192k", str(with_music)])
        audio = with_music
        log(f"  [музыка] {src.name}: {dur:.0f} с с {start:.0f}-й секунды трека, "
            f"вступает на {at:.0f}-й секунде ролика")
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


# Кости ТЕЛА. Всё, что держит силуэт: руки, ноги, корпус. Лицо (глаза, рот,
# бровь) в силуэт не входит — оно живёт внутри белой маски, а не по контуру.
BODY_BONES = frozenset((
    "torso", "cloak",
    "upper_arm_left", "forearm_left", "hand_left",
    "upper_arm_right", "forearm_right", "hand_right",
    "thigh_left", "shin_left", "thigh_right", "shin_right",
))


def anim_code(text):
    """Текст сценария без комментариев.

    Гейты ищут `pose "…"` регуляркой, а в шапках сценариев и в пояснениях к
    правкам те же слова стоят в тексте — комментарий с примером «пиши не
    `pose "wide"`, а `overlays`» честно ловился как дефект. Разметку `//lip N`
    читают другие приёмщики по сырому тексту, здесь она не нужна.
    """
    return re.sub(r"//[^\n]*", "", text)


def _rig_poses(rig_dir=None):
    rig = Path(rig_dir) if rig_dir else ROOT / "examples/assets/characters/freeman_rig"
    f = rig / "rig.json"
    if not f.exists():
        return {}
    return json.loads(f.read_text(encoding="utf-8"))["poses"]


def is_face_pose(name, poses):
    """Поза, которая НЕ называет ни одной кости тела — чистая мимика (cel лица).

    Таких в риге 54 из 124: все `hero_*`, `flash_*`, `smug`, `stern`, `doubt`,
    `angry`, `sad`, визимы. Они меняют только глаза/рот/бровь.
    """
    bones = set(poses.get(name, {}).get("bones", {}))
    return bool(bones) and not (bones & BODY_BONES)


def body_signature(name, poses):
    """Отпечаток ТЕЛА позы. Одинаковый отпечаток — одинаковый силуэт в кадре."""
    bones = poses.get(name, {}).get("bones", {})
    body = {k: bones[k] for k in sorted(set(bones) & BODY_BONES)}
    # Мимическая поза тела не называет — движок подставит дефолт рига, то есть
    # ОДНУ И ТУ ЖЕ стойку: руки вдоль тела, плечи ровно, анфас.
    return "DEFAULT" if not body else json.dumps(body, sort_keys=True)


def lint_chehov(prod):
    """Приёмщик РУЖЬЯ ЧЕХОВА: заявленное обязано выстрелить. (hard, soft).

    Закон драматургии №5 (`DRAMATURGIYA.md`): предмет, попавший в кадр и ничего
    не сделавший, — не деталь, а шум. Зритель держит его во внимании и не
    получает выплаты, и это прямой вычет из напряжения, а не нейтральный ноль.
    У нас закон буквален: локация — вещдок, все предметы в ней заряжены
    (`PRODAZHA.md` §2).

    Гейт структурный, без словарей: проп объявлен через `let` и ни разу не
    получает действия (`moves-to`, `rotates`, `scales`, `fades-to`, `shows`,
    `hides`). Ложных тревог такой счёт не даёт — потому и hard.
    """
    anim = ROOT / prod.get("anim", "")
    if not anim.exists():
        return [], []
    lines = anim_code(anim.read_text(encoding="utf-8")).split("\n")
    declared, used = {}, set()
    for i, l in enumerate(lines):
        m = re.search(r"let (\w+) = (prop|text)\(", l)
        if m:
            declared[m.group(1)] = m.group(2)
            continue
        m = re.match(r"\s*(\w+)\s+(moves-to|rotates|scales|fades-to|shows|hides)\b", l)
        if m:
            used.add(m.group(1))
    hard = []
    for name, kind in declared.items():
        if name not in used:
            what = "предмет" if kind == "prop" else "слово"
            hard.append(f"{prod['id']}: {what} «{name}» объявлен и ни разу не "
                        f"действует — ружьё висит и не стреляет. Либо заряди его "
                        f"движением, либо убери из сценария (DRAMATURGIYA.md §5)")
    return hard, []


# Гротескные морды: рисованный экстремум лица. Бьют по закону правды и
# преувеличения (DRAMATURGIYA.md §9) — только ПОСЛЕ узнаваемой бытовой детали.
# Две подряд обесценивают обе: зритель не успевает вернуться к норме, и вторая
# читается не как удар, а как манера.
GROTESK = ("flash_", "hero_", "grotesque", "gore")


def lint_grotesk(prod):
    """Приёмщик ГРОТЕСКА: не идут ли экстремумы лица очередью. (hard, soft)."""
    anim = ROOT / prod.get("anim", "")
    if not anim.exists():
        return [], []
    soft, run, first, prev_flash = [], 0, "", False
    for line in anim_code(anim.read_text(encoding="utf-8")).split("\n"):
        m = re.search(r"\bwait\s+([\d.]+)s", line)
        if m and float(m.group(1)) > 0.25:
            run, first, prev_flash = 0, "", False
            continue
        m = re.search(r'(?:pose|overlays)\s+"([a-z_0-9]+)"', line)
        if not m:
            continue
        name = m.group(1)
        if any(name.startswith(g) or name == g for g in GROTESK):
            # ФЛЭШ-ОЧЕРЕДЬ — ОДИН УДАР, А НЕ ТРИ. Морды `flash_*` держатся по
            # 0.08с и подряд читаются как единственная вспышка; считать их
            # порознь значит ругаться на приём, а не на дефект.
            flash = name.startswith("flash_")
            if not (flash and prev_flash):
                run += 1
                first = first or name
            prev_flash = flash
            if run == 4:
                soft.append(f"{prod['id']}: гротеск идёт очередью — «{first}» и "
                            f"ещё три подряд без спокойного кадра между ними. "
                            f"Преувеличение работает после узнавания, а не "
                            f"поверх другого преувеличения (DRAMATURGIYA.md §9)")
                run = 0
        else:
            run, prev_flash = 0, False
    return [], soft


def lint_imena_poz(prod, rig_dir=None):
    """Приёмщик ИМЁН: названа поза, которой в риге нет. (hard, soft).

    Движок на такое НЕ РУГАЕТСЯ: `rig.poses.get(&ev.pose)?` возвращает None,
    поза молча становится пустой, и фигура падает в дефолт рига. Опечатка
    выглядит на экране ровно как «персонаж зачем-то встал по стойке смирно».
    Так в двух роликах жил `pose "skeptic"` — в риге он называется
    `hero_skeptic`, и обе сцены на этом месте теряли и лицо, и жест.
    """
    anim = ROOT / prod.get("anim", "")
    poses = _rig_poses(rig_dir)
    if not anim.exists() or not poses:
        return [], []
    used = re.findall(r'(?:pose|overlays)\s+"([a-z_0-9]+)"',
                      anim_code(anim.read_text(encoding="utf-8")))
    bad = sorted({u for u in used if u not in poses})
    return [f"{prod['id']}: позы «{n}» нет в риге — движок молча поставит "
            f"дефолтную стойку" for n in bad], []


def lint_nosimoe(prod, rig_dir=None):
    """Приёмщик НОСИМОЙ ДЕТАЛИ: не пропала ли надетая вещь. (hard, soft).

    Очки — КОСТЬ, выключенная масштабом [0,0], и включают её только позы-двойники
    с суффиксом `_ochki` (KARTA.md §3). Полная поза без суффикса кость не
    называет, та падает в дефолт — и очки ИСЧЕЗАЮТ с маски посреди ролика.
    Слой (`overlays`) кладётся поверх последней полной позы и её очки сохраняет,
    поэтому жест телом после надевания ставится слоем, а не полной позой.

    Ловушка проверена на себе: в «Теориях личности» жест, добавленный полной
    позой, снимал с героя очки — весь смысл ролика — и ни один гейт этого не
    видел.
    """
    anim = ROOT / prod.get("anim", "")
    poses = _rig_poses(rig_dir)
    if not anim.exists() or not poses:
        return [], []
    lines = anim_code(anim.read_text(encoding="utf-8")).split("\n")
    worn, handoff, hard = False, False, []
    for line in lines:
        # СРЫВ ПО СЦЕНАРИЮ — не дефект. Деталь снимают, передав её пропу:
        # проп встаёт на место кости (`ochki shows`) и только потом гаснет
        # кость. Ровно так снимаются очки на взлёте «Теорий личности».
        if re.search(r"\bochki\s+shows\b", line):
            handoff = True
        m = re.search(r'(pose|overlays)\s+"([a-z_0-9]+)"', line)
        if not m:
            continue
        kind, name = m.group(1), m.group(2)
        if kind == "overlays":
            continue                       # слой базу не меняет
        if name.endswith("_ochki"):
            worn, handoff = True, False
        elif worn:
            if handoff:
                worn, handoff = False, False   # снято намеренно
                continue
            hard.append(f"{prod['id']}: после надетых очков стоит полная поза "
                        f"«{name}» без суффикса `_ochki` — кость очков выключится, "
                        f"и они пропадут с маски. Возьми двойник «{name}_ochki», "
                        f"поставь жест слоем `overlays \"{name}\"` или сними деталь "
                        f"явно через проп (KARTA.md §3)")
            worn = False                   # об одном месте — одно сообщение
    return hard, []


def lint_mimika(prod, rig_dir=None):
    """Приёмщик МИМИКИ: не стирает ли смена лица жест тела. (hard, soft).

    ГЛАВНЫЙ ИСТОЧНИК «НЕТ ДИНАМИКИ», и он не там, где искали.

    Замер движка (проверено рендером, `pose "v_upor"` → `pose "hero_rage"`):
    поза перекрывает названные кости, а ВСЕ ОСТАЛЬНЫЕ падают в дефолт рига —
    `interpolate_bone` берёт `bone.rotation`, а не значение прошлой позы. Значит
    каждая из 54 мимических поз, поставленная как `pose`, СТИРАЕТ жест тела:
    поднятая рука падает, корпус выпрямляется, фигура встаёт анфас по стойке
    смирно. Ролик, собранный на `hero_*`/`flash_*`/`smug`, стоит столбом при
    любом числе «разных поз» в монтаже — что студия и увидела глазами.

    Лечится без правок движка: в DSL уже есть `overlays`, который кладёт кости
    позы ПОВЕРХ удержанной (`resolve_effective_pose`, ветка overlay). Мимика
    через `overlays` меняет лицо и оставляет тело в жесте.

    Гейт ловит мимическую позу, поставленную как `pose` ПОСЛЕ позы с телом:
    именно там жест и теряется. Мимика после дефолтного тела (`calm`, `idle`)
    ничего не стирает и претензии не вызывает.
    """
    anim = ROOT / prod.get("anim", "")
    poses = _rig_poses(rig_dir)
    if not anim.exists() or not poses:
        return [], []
    seq = re.findall(r'(pose|overlays)\s+"([a-z_0-9]+)"',
                     anim_code(anim.read_text(encoding="utf-8")))
    hard, soft = [], []
    held = "DEFAULT"          # силуэт тела, который сейчас держит фигура
    held_name = "idle"
    for kind, name in seq:
        if kind == "overlays":
            continue          # слой тела не сбрасывает — это и есть верный путь
        if is_face_pose(name, poses):
            if held != "DEFAULT":
                hard.append(
                    f"{prod['id']}: мимика «{name}» поставлена как `pose` после "
                    f"«{held_name}» — жест тела стирается в стойку смирно. "
                    f"Пиши `overlays \"{name}\"`: лицо сменится, тело удержит "
                    f"жест (PRAVILA-DVIZHENIYA.md §5)")
                held, held_name = "DEFAULT", name
            continue
        held, held_name = body_signature(name, poses), name
    return hard, soft


# Кости рук и порог, за которым рука считается ПОДНЯТОЙ. Дефолт покоя — 30° и
# −29°: рука висит вдоль тела. 60° и выше — вынос в сторону или вперёд.
ARM_BONES = ("upper_arm_left", "upper_arm_right")
ARM_RAISED = 60.0
# Сколько СЕКУНД жест держится, пока это приём. Считать слоями нельзя: очередь
# флэш-морд — три слоя за четверть секунды, и по счёту слоёв она выглядела как
# забытая рука, хотя на экране это один удар. Держит время, а не число событий.
ARM_HELD_MAX_SEC = 6.0


def lint_arms(prod, rig_dir=None):
    """Приёмщик ЗАБЫТОЙ РУКИ — теперь по тому конструкту, где она возможна.

    ЧТО БЫЛО НЕ ТАК. Прошлая версия гейта считала, что `pose` наследует кости
    прошлой позы, и потому поднятая рука висит через весь монтаж. Проверено
    рендером (`calm → point → smug → stern`): рука ВНИЗУ уже на «smug». Позы
    кости не наследуют — неназванная кость падает в дефолт рига. Гейт дал
    двенадцать ложных тревог и один раз уронил завод целиком.

    ГДЕ ДЕФЕКТ ЖИВЁТ НА САМОМ ДЕЛЕ. Наследует `overlays`: слой кладётся поверх
    последней ПОЛНОЙ позы, и если та подняла руку, рука останется поднятой,
    пока не придёт новая полная поза. Ровно этим `overlays` и ценен — жест
    держится через смену лица, — и ровно поэтому за длиной удержания нужен
    присмотр: жест, простоявший больше шести секунд без единой полной позы, это
    уже не жест, а забытая рука.
    """
    anim = ROOT / prod.get("anim", "")
    poses = _rig_poses(rig_dir)
    if not anim.exists() or not poses:
        return [], []
    soft = []
    state = {b: 0.0 for b in ARM_BONES}     # угол, который держит база
    since = {b: 0.0 for b in ARM_BONES}     # СЕКУНДЫ, что рука висит поднятой
    culprit = {b: "" for b in ARM_BONES}
    for line in anim_code(anim.read_text(encoding="utf-8")).split("\n"):
        # Время идёт по `wait Ns` и `speaks for Ns` — тем же операторам, что
        # двигают курсор в движке.
        m = re.search(r"\b(?:wait|speaks for)\s+([\d.]+)s", line)
        if m:
            dt = float(m.group(1))
            for b in ARM_BONES:
                if abs(state[b]) >= ARM_RAISED:
                    since[b] += dt
            continue
        m = re.search(r'(pose|overlays)\s+"([a-z_0-9]+)"', line)
        if not m:
            continue
        kind, name = m.group(1), m.group(2)
        bones = poses.get(name, {}).get("bones", {})
        for b in ARM_BONES:
            if b in bones and "rotation" in bones[b]:
                state[b] = float(bones[b]["rotation"])
                since[b] = 0.0
                culprit[b] = name if abs(state[b]) >= ARM_RAISED else ""
            elif kind == "pose":
                state[b], since[b] = 0.0, 0.0  # полная поза руку опускает в дефолт
            elif since[b] >= ARM_HELD_MAX_SEC:
                soft.append(
                    f"{prod['id']}: {b} поднята в позе «{culprit[b]}» "
                    f"({abs(state[b]):.0f}°) и держится уже {since[b]:.1f}с "
                    f"подряд, к «{name}» — жест превратился в забытую руку. "
                    f"Поставь полную позу телом или слой, называющий руки.")
                since[b] = 0.0                 # об одном месте — одно сообщение
    return [], soft


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
    # У КОГО ЕСТЬ ПЕРЁД. «Ехать задом» может только предмет, у которого перёд
    # нарисован: крыса, фигура, рука. Дверь, очки, кабель, кардиограмма, слово
    # переднего края не имеют, и требовать от них разворота — ложная тревога.
    # Первая версия гейта этого не различала и кричала на семь предметов из
    # восьми; ровно так гейты и теряют доверие.
    #
    # Признак берётся из рисунка, а не из сцены: перёд — свойство файла.
    FRONTED = ("rat", "prisoner", "hand-point", "giant-hand")
    # Разворот: `facing left` в объявлении (грамматика пропов) либо
    # отрицательный масштаб — исторический способ до появления `facing`.
    pos, soft, flipped, fronted = {}, [], set(), set()
    for i, l in enumerate(lines):
        m = re.search(r'let (\w+) = prop\("[^"]*",\s*"([^"]*)"\)(.*)', l)
        if m:
            name, path, tail = m.group(1), m.group(2), m.group(3)
            mp = re.search(r"at \(([\d.]+),", tail)
            if mp:
                pos[name] = float(mp.group(1))
            if any(k in Path(path).name for k in FRONTED):
                fronted.add(name)
            if re.search(r"\bfacing\s+left\b", tail):
                flipped.add(name)
            continue
        m = re.search(r"(\w+) scales\s+-[\d.]+", l)
        if m:
            flipped.add(m.group(1))
            continue
        m = re.search(r"(\w+) moves-to \((-?[\d.]+),", l)
        if m and m.group(1) in pos:
            x0, x1 = pos[m.group(1)], float(m.group(2))
            if (x1 < x0 - 0.05 and m.group(1) in fronted
                    and m.group(1) not in flipped):
                soft.append(f"{prod['id']}: «{m.group(1)}» едет ВЛЕВО "
                            f"({x0:.2f}→{x1:.2f}), а рисунок смотрит вправо — "
                            f"предмет поедет задом. Объяви его `facing left` "
                            f"(PRAVILA-DVIZHENIYA.md §6)")
            pos[m.group(1)] = x1
            # `hides` сразу следом — предмет растворяется посреди плана
            nxt = next((x.strip() for x in lines[i + 1:i + 3] if x.strip()), "")
            if nxt == f"{m.group(1)} hides" and 0.0 <= x1 <= 1.0:
                soft.append(f"{prod['id']}: «{m.group(1)}» прячется в точке "
                            f"{x1:.2f} — это ВНУТРИ кадра, зритель увидит, как "
                            f"предмет растворяется (§7)")
    return [], soft


# ПЛОТНОСТЬ ЖЕСТА. Меряется по ТЕЛУ, а не по именам поз, и это разные числа.
#
# Первая версия гейта считала `pose "…"` в тексте — и хвалила монтаж, который в
# кадре стоял столбом. Причина в замере движка: мимическая поза тела не
# называет, движок ставит телу дефолт рига, и десять подряд «разных» hero-морд
# дают ОДИН силуэт. У «Теорий личности» 21 разное имя позы — и 10 разных тел,
# почти половина событий возвращает фигуру в одну и ту же стойку смирно.
#
# Считается ДВА числа, и оба по силуэту: сколько раз тело реально меняется в
# минуту и сколько РАЗНЫХ тел за ролик. Двадцать смен между тремя силуэтами —
# это не жестикуляция, а тик. Пороги сняты с «Перепрошивки» и «Тюрьмы», где
# движение читается.
BODY_CHANGES_PER_MIN = 18
DISTINCT_BODIES_MIN = 9
# Доля событий, оставляющих тело в дефолтной стойке. Выше — фигура анфас с
# висящими руками бóльшую часть хронометража; ровно это студия и назвала
# «нет динамики».
DEFAULT_BODY_SHARE_MAX = 0.35


def hronometrazh_anim(anim, engine=None):
    """Фактическая длина таймлайна сценария в секундах (`animdsl timing`).

    СУММА `duration:` — НЕ ХРОНОМЕТРАЖ, И ЭТО НЕ МЕЛОЧЬ. У говорящей сцены
    объявленная длительность — ПОЛ, а не цель: с тех пор как это стало
    правилом (`pauses.py`), она равна `1s` независимо от того, сколько сцена
    идёт на самом деле. Ролик на 78 секунд объявляет шесть.

    Любая мерка, делящая на эту сумму, врёт во столько же раз. Ровно это и
    случилось с приёмщиком динамики: на четырёх новейших роликах знаменатель
    занижен в десять-тринадцать раз, и «смены силуэта в минуту» выходили за
    400 при норме 18 — гейт не мог провалиться в принципе.

    Длину берём у движка тем же способом, что `pauses.py`: он единственный
    знает, сколько сцена идёт по содержимому. Движка нет — возвращаем None,
    и звать нас будут с честной оговоркой, а не с выдуманным числом.
    """
    eng = Path(engine or DEFAULT_ENGINE)
    if not eng.exists():
        return None
    try:
        out = subprocess.run([str(eng), "timing", str(anim)],
                             capture_output=True, check=True).stdout
        return float(json.loads(out)["total"])
    except Exception:                                        # noqa: BLE001
        return None


def lint_dinamika(prod, rig_dir=None):
    """Приёмщик ДИНАМИКИ: меняется ли СИЛУЭТ ТЕЛА, а не только лицо. (hard, soft)."""
    anim = ROOT / prod.get("anim", "")
    poses = _rig_poses(rig_dir)
    if not anim.exists() or not poses:
        return [], []
    text = anim_code(anim.read_text(encoding="utf-8"))
    seq = re.findall(r'(pose|overlays)\s+"([a-z_0-9]+)"', text)
    # ХРОНОМЕТРАЖ У ДВИЖКА, А НЕ ИЗ ОБЪЯВЛЕНИЙ. Разбор — в шапке
    # hronometrazh_anim. Без движка мерить нечем: считать по `duration:`
    # значит печатать зелёное там, где не измерено.
    secs = hronometrazh_anim(anim)
    if secs is None or secs < 5 or not seq:
        return [], []

    # Проигрываем сценарий так же, как движок: `pose` задаёт тело целиком
    # (мимическая — дефолтом), `overlays` перекрывает только названные кости.
    sigs, held = [], "DEFAULT"
    for kind, name in seq:
        bones = poses.get(name, {}).get("bones", {})
        body = {k: bones[k] for k in sorted(set(bones) & BODY_BONES)}
        if kind == "overlays":
            if not body:
                continue                       # слой мимики силуэт не трогает
            held = f"{held}+{json.dumps(body, sort_keys=True)}"
        else:
            held = body_signature(name, poses)
        sigs.append(held)

    if not sigs:
        return [], []
    changes = sum(1 for a, b in zip(sigs, sigs[1:]) if a != b)
    per_min = 60.0 * changes / secs
    share = sum(1 for s in sigs if s == "DEFAULT") / len(sigs)
    soft = []
    if per_min < BODY_CHANGES_PER_MIN:
        soft.append(f"{prod['id']}: {per_min:.0f} смен СИЛУЭТА в минуту при норме "
                    f"{BODY_CHANGES_PER_MIN} — фигура стоит столбом. Живое движение "
                    f"это НАМЕРЕННЫЕ жесты на ударах реплик (PRAVILA-DVIZHENIYA.md §4)")
    if len(set(sigs)) < DISTINCT_BODIES_MIN:
        soft.append(f"{prod['id']}: разных силуэтов {len(set(sigs))} при норме "
                    f"{DISTINCT_BODIES_MIN} (имён поз {len({n for _, n in seq})}) — "
                    f"в риге 70 поз с телом, монтаж их не видит")
    if share > DEFAULT_BODY_SHARE_MAX:
        soft.append(f"{prod['id']}: {share * 100:.0f}% событий оставляют тело в "
                    f"дефолтной стойке при потолке {DEFAULT_BODY_SHARE_MAX * 100:.0f}% "
                    f"— это и есть «анфас с висящей рукой». Мимику через `overlays`, "
                    f"жест телом на каждый удар")
    return [], soft


def lint_hodba(prods):
    """Приёмщик ХОДЬБЫ: проход обязан закрываться полной позой.

    Слои накапливаются и живут до следующей ПОЛНОЙ позы, поэтому брошенный
    слой шага остаётся висеть на фигуре: она стоит с разведёнными ногами и
    «доигрывает полушаг». Разбор — в шапке tools/walk.py.
    """
    sys.path.insert(0, str(TOOLS))
    import walk
    files = [str(ROOT / p["anim"]) for p in prods if (ROOT / p["anim"]).exists()]
    return [f"{Path(p).name}:{ln} — {msg}" for p, ln, msg in walk.check_anim(files)], []


def lint_osanka(prods):
    """Приёмщик ОСАНКИ: персонаж не приседает.

    SOFT, и намеренно: гейт РЕНДЕРИТ каждую сыгранную позу на стенде, а это
    десятки прогонов движка. На раннере это минуты, и ронять из-за них весь
    завод дороже, чем один некрасивый кадр. Ловить всё равно надо — замечание
    «на корточки не садится» приходило трижды. Разбор — в шапке
    tools/posture.py.
    """
    sys.path.insert(0, str(TOOLS))
    import posture
    out = []
    for prod in prods:
        anim = ROOT / prod["anim"]
        if not anim.exists():
            continue
        try:
            _, bad = posture.check(str(anim))
        except Exception as e:  # noqa: BLE001 — стенд может не собраться, это не повод падать
            out.append(f"{anim.name}: осанка не измерена ({e})")
            continue
        for pose, r in bad:
            out.append(f"{anim.name}: поза «{pose}» роняет рост до {r:.2f} "
                       f"эталона — фигура приседает")
    return [], out


def lint_sverka(prods):
    """Приёмщик СООТВЕТСТВИЯ: номера реплик и маркеров совпадают.

    HARD. Реплика `| VO-4 |` и маркер `//lip 4` связаны ТОЛЬКО номером; другой
    связи между сценарием и раскадровкой нет. Сдвиг на один слот собирается без
    единой ошибки — липсинк сходится, длина совпадает, — и слышен лишь на
    готовом файле. Разбор — в шапке tools/sverka.py.
    """
    sys.path.insert(0, str(TOOLS))
    import sverka
    out = []
    for prod in prods:
        anim = ROOT / prod["anim"]
        if not anim.exists():
            continue
        out += [f"{anim.name}: {b}" for b in sverka.check(str(anim))]
    return out, []


def lint_rekvizit(prods):
    """Приёмщик РЕКВИЗИТА: вещь не появляется на персонаже сама.

    HARD. Цилиндр, возникающий на одну реплику и пропадающий, — брак, который
    зритель замечает мгновенно, а автор сценария не видит вовсе: позу выбирают
    по названию, а не по списку костей. Проверка идёт по ригу, поэтому одна на
    все ролики. Разбор — в шапке tools/rekvizit.py.
    """
    sys.path.insert(0, str(TOOLS))
    import rekvizit
    rig = json.loads((ROOT / "examples/assets/characters/freeman_rig/rig.json")
                     .read_text(encoding="utf-8"))
    return [f"риг: поза «{n}» надевает «{b}», не объявив это именем "
            f"(нужен суффикс «{m}»)" for n, b, m in rekvizit.offenders(rig)], []


def lint_tishina(prods):
    """Приёмщик ТИШИНЫ: между репликами не должно быть дыр.

    SOFT, и намеренно. Гейт меряет ТАЙМЛАЙН СЦЕНАРИЯ, а в ролик уходит
    таймлайн после липсинка: `speaks for` подменяется реальной длиной mp3, и
    дыра может как вырасти, так и схлопнуться. Ронять из-за расчётной оценки
    весь завод нельзя — но и не считать её нельзя тоже: замечание «слишком
    длинные паузы после реплик» пришло с готового ролика, где дыра в пять
    секунд набежала сама. Разбор — в шапке tools/pauses.py.
    """
    sys.path.insert(0, str(TOOLS))
    import pauses
    out = []
    for prod in prods:
        anim = ROOT / prod["anim"]
        if not anim.exists():
            continue
        try:
            bad, _ = pauses.check(str(anim))
        except Exception as e:  # noqa: BLE001 — таймлайн может не собраться
            out.append(f"{anim.name}: тишина не измерена ({e})")
            continue
        for idx, gap, why in bad:
            out.append(f"{anim.name}: после реплики {idx} — {gap:.1f} с тишины ({why})")
    return [], out


def lint_rech(prods):
    """Приёмщик РЕЧИ И ЛИЦА: рот обязан принадлежать озвучке.

    Два разных дефекта, оба читаются как «лицо не соответствует голосу», и оба
    ловятся до рендера, а не глазами на готовом ролике:
      · в РИГЕ — поза тела, которая сама ставит рот (спорит с липсинком);
      · в СЦЕНАРИИ — полная поза или мимический слой внутри реплики.
    Разбор причин — в шапках tools/mouth_ownership.py и tools/speech_lint.py.
    """
    # HARD — то, что ломает синхрон наверняка: рот в позе тела и полная поза
    # внутри реплики. SOFT — исторический долг старых роликов: ракурсные и
    # мимические слои внутри реплик. Их тоже надо вычистить, но ронять из-за
    # них ВЕСЬ завод нельзя: ролики сняты и живут, а правка каждого — отдельная
    # режиссёрская работа, а не механическая замена.
    sys.path.insert(0, str(TOOLS))
    hard, soft = [], []
    import mouth_ownership, speech_lint
    rig = json.loads((ROOT / "examples/assets/characters/freeman_rig/rig.json")
                     .read_text(encoding="utf-8"))
    for name, part in mouth_ownership.offenders(rig):
        hard.append(f"риг: поза тела «{name}» ставит рот {part} — "
                    f"спорит с липсинком (tools/mouth_ownership.py --fix)")
    for prod in prods:
        anim = ROOT / prod["anim"]
        if not anim.exists():
            continue
        bad, _ = speech_lint.check(str(anim))
        for ln, msg in bad:
            line = f"{anim.name}:{ln} — {msg}"
            (soft if "трогает рот" in msg else hard).append(line)
    return hard, soft


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

    # Порядок: картинки → озвучка ЧАСТЯМИ → ХРОНОМЕТРАЖ ПО ФАКТУ (`speaks for`
    # в раскадровке = реальная длина mp3) → липсинк по звуку в сцену →
    # ФАКТИЧЕСКИЕ времена речи из движка (animdsl timing) → сборка голосовой
    # дорожки по этим временам (синхрон по конструкции) → рендер → SFX → микс.
    #
    # ХРОНОМЕТРАЖ СТОИТ ПЕРЕД ЛИПСИНКОМ И ЭТО НЕ ПОРЯДОК РАДИ ПОРЯДКА. Обе
    # правки считают одно и то же отношение «факт / объявлено»: хронометраж
    # выпрямляет им сценарий, липсинк — подменяет рот. Поменяй их местами — и
    # липсинк растянет каты под старое число, а хронометраж следом растянет их
    # ещё раз под новое. Пройдя в этом порядке, второй видит k = 1.00 и не
    # трогает ничего.
    step_images(prod, videos_dir)
    parts_ok = step_voice_parts(prod, parts_dir)
    if parts_ok:
        step_hronometrazh(prod, parts_dir)
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
        nh, ns = lint_imena_poz(prod)     # приёмщик имён поз
        all_hard += nh
        all_soft += ns
        oh, os_ = lint_nosimoe(prod)      # приёмщик носимой детали (очки)
        all_hard += oh
        all_soft += os_
        ch, cs = lint_chehov(prod)        # приёмщик ружья Чехова
        all_hard += ch
        all_soft += cs
        gh, gs = lint_grotesk(prod)       # приёмщик гротеска (очередь морд)
        all_hard += gh
        all_soft += gs
        ah, asf = lint_mimika(prod)       # приёмщик мимики (жест не стирается)
        all_hard += ah
        all_soft += asf
        rh2, rs2 = lint_arms(prod)        # приёмщик забытой руки (по слоям)
        all_hard += rh2
        all_soft += rs2
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
    rch, rcs = lint_rech(prods)           # приёмщик речи и лица (липсинк)
    all_hard += rch
    all_soft += rcs
    hh, hs = lint_hodba(prods)            # приёмщик ходьбы (слой шага не брошен)
    all_hard += hh
    all_soft += hs
    oh, os_ = lint_osanka(prods)          # приёмщик осанки (не приседает)
    all_hard += oh
    all_soft += os_
    tih, tis = lint_tishina(prods)        # приёмщик тишины (дыры между репликами)
    all_hard += tih
    all_soft += tis
    rkh, rks = lint_rekvizit(prods)       # приёмщик реквизита (шляпа не сама)
    all_hard += rkh
    all_soft += rks
    svh, svs = lint_sverka(prods)         # приёмщик соответствия (номера реплик)
    all_hard += svh
    all_soft += svs
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
