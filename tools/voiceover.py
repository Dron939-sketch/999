#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voiceover.py — генерация озвучки через Fish Audio по VO-сценарию.

Читает сценарий озвучки (examples/lektorij/*-VO.md), берёт из таблицы реплики
с таймкодами, синтезирует каждую через Fish Audio API и собирает единый
«дубль»: дорожку, где каждая реплика стоит на своём таймкоде (паузы — тишина).
Результат кладётся рядом с видео (videos/<имя>-voice.mp3).

Требования:
  * переменная окружения FISH_AUDIO_API_KEY — ключ API Fish Audio;
  * опционально FISH_AUDIO_VOICE_ID — reference_id голоса Фреди
    (если не задан — голос Fish Audio по умолчанию);
  * ffmpeg в PATH (сборка дорожки).

Использование:
    python3 tools/voiceover.py examples/lektorij/pereproshivka-intro-VO.md \
        -o videos/pereproshivka-intro-voice.mp3
"""

import argparse
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

API_URL = "https://api.fish.audio/v1/tts"
# Frederick — источник правды по озвучке (голос Фреди). Если задан токен, реплики
# синтезирует он (ключ Fish не покидает сервер Frederick) и кэширует mp3 у себя.
# `or` (не default-аргумент): пустой секрет FREDERICK_TTS_URL приходит как ""
# — get(..., default) вернул бы "", а нам нужен дефолтный адрес.
FREDERICK_BASE = (os.environ.get("FREDERICK_TTS_URL") or "https://ffred-ddd989.amvera.io").rstrip("/")
FREDERICK_TOKEN = os.environ.get("FREDERICK_ADMIN_TOKEN") or ""

# Ударения в VO-сценариях размечены знаком U+0301 сразу после ударной гласной
# («уже́», «три сло́ва»). По умолчанию они уходят в синтез КАК ЕСТЬ: без них
# движок ставит ударение по своей модели и путает омографы, а контекста
# реплики у него нет. Аварийный тумблер на случай, если движок начнёт читать
# знак вслух: VO_NO_ACCENTS=1 срезает разметку перед отправкой, а сценарий
# при этом остаётся источником правды и править его не надо.
ACCENT = "́"
STRIP_ACCENTS = (os.environ.get("VO_NO_ACCENTS") or "").strip() not in ("", "0")


def for_synthesis(text):
    """Текст реплики в том виде, в каком он уходит в синтез."""
    return text.replace(ACCENT, "") if STRIP_ACCENTS else text


def parse_vo_table(md_path):
    """Достаёт из VO-таблицы (| VO-n | 0:02.5–0:05.7 | «текст» |) реплики.

    Возвращает список (start_seconds, text).
    """
    rows = []
    with open(md_path, encoding="utf-8") as f:
        for line in f:
            m = re.match(
                r"\|\s*VO-\d+\s*\|\s*(\d+):(\d+(?:\.\d+)?)\s*[–-]\s*[\d:.]+\s*\|(.+)\|",
                line,
            )
            if not m:
                continue
            start = int(m.group(1)) * 60 + float(m.group(2))
            # Реплика — ВСЕГДА ПОСЛЕДНЯЯ колонка строки. Раньше бралось всё
            # после таймкода, и служебные колонки («Бит формулы»: ХУК, ПУЛЕМЁТ,
            # РАЗВОРОТ…) уезжали в синтез — их слышно в ролике. Режем по «|».
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # РЕПЛИКА — ЯЧЕЙКА В ЁЛОЧКАХ, А НЕ ПОСЛЕДНЯЯ. Раньше бралась
            # последняя, и это молча ломалось, стоило сценаристу добавить
            # колонку справа: в ролике-презентации пятой колонкой шла
            # «Локация / ход», и голос честно зачитал вслух режиссёрские
            # ремарки — «пустое поле, идёт слева направо». Текст реплики у нас
            # всегда в «ёлочках», по ним и опознаём.
            quoted = [c for c in cells if "«" in c and "»" in c]
            # ПЕРВАЯ ячейка в ёлочках, а не последняя. Реплика стоит в таблице
            # ЛЕВЕЕ служебных колонок, и это единственное, на что можно
            # опереться. `quoted[-1]` держался, пока ёлочки встречались ровно
            # один раз за строку, — и сломался в тот день, когда режиссёрская
            # колонка «Локация / ход» получила своё закавыченное слово: у
            # реплики-презентации синтез честно произнёс «зал, у „по́лок“»
            # вместо названия площадки. Ошибка молчаливая: mp3 есть, липсинк
            # сходится, в ролике звучит не тот текст.
            # Гейт на этот случай — в tools/script_lint.py: строка с двумя
            # закавыченными ячейками валит сценарий ДО синтеза.
            cell = quoted[0] if quoted else (cells[-1] if cells else m.group(3))
            # Колонка «Бит формулы» (ХУК / ПУЛЕМЁТ / РАЗВОРОТ / ВЗЛЁТ / ЖАЛО),
            # если она есть — подсказка для интонации: у оригинала подача
            # меняется ПО БИТАМ, а не только по ремарке режиссёра.
            ci = cells.index(cell) if cell in cells else len(cells) - 1
            beat = cells[ci - 1] if ci >= 1 else ""
            # Ремарка *(...)* — режиссура реплики (темп/громкость/шёпот).
            rm = re.search(r"\*\(([^)]*)\)\*", cell)
            remark = rm.group(1).lower() if rm else ""
            text = re.sub(r"\*\([^)]*\)\*", "", cell).strip()
            text = text.strip("«»«» \t")
            if text:
                # бит подмешиваем к ремарке — direct_line читает оба источника
                rows.append((start, text, (remark + " " + beat.lower()).strip()))
    return rows


def tts_via_frederick(text):
    """Одна реплика → mp3-байты через Frederick (голос Фреди, кэш на сервере)."""
    req = urllib.request.Request(
        f"{FREDERICK_BASE}/api/tts/video/say",
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Admin": FREDERICK_TOKEN},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def list_fish_voices(api_key):
    """Печатает голоса аккаунта Fish: reference_id + название.

    Нужен, чтобы найти FISH_AUDIO_VOICE_ID своего голоса (например, Фримена)
    и положить его в секреты. Тот же id виден в URL модели: fish.audio/m/<id>/
    """
    req = urllib.request.Request(
        "https://api.fish.audio/model?self=true&page_size=50",
        headers={"Authorization": f"Bearer {api_key}"}, method="GET",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    items = data.get("items", data if isinstance(data, list) else [])
    if not items:
        print("В аккаунте Fish не найдено собственных моделей голоса.")
        return
    print(f"Голоса аккаунта ({len(items)}):")
    for it in items:
        vid = it.get("_id") or it.get("id") or "?"
        title = it.get("title") or it.get("name") or "(без названия)"
        print(f"  {vid}  —  {title}")
    print("\nПоложи нужный id в секрет FISH_AUDIO_VOICE_ID (Settings → "
          "Secrets and variables → Actions).")


def fetch_fish_voices(api_key):
    """Список моделей голоса аккаунта: [(id, название), ...] (пусто при сбое)."""
    try:
        req = urllib.request.Request(
            "https://api.fish.audio/model?self=true&page_size=50",
            headers={"Authorization": f"Bearer {api_key}"}, method="GET",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — молча падать нельзя, но и рушить нечего
        print(f"    [fish] список голосов недоступен ({e})")
        return []
    items = data.get("items", data if isinstance(data, list) else [])
    out = []
    for it in items:
        vid = it.get("_id") or it.get("id")
        title = it.get("title") or it.get("name") or ""
        if vid:
            out.append((vid, title))
    return out


def resolve_voice_id(api_key, explicit):
    """Голос по умолчанию — ФРИМЕН, без всяких id в секретах.

    Порядок: явный FISH_AUDIO_VOICE_ID → поиск в аккаунте модели, название
    которой содержит «freeman»/«фримен» (регистр не важен; искомое имя можно
    сменить через FISH_VOICE_NAME) → первая своя модель аккаунта → сток Fish.
    """
    if explicit:
        return explicit, "секрет FISH_AUDIO_VOICE_ID"
    wanted = (os.environ.get("FISH_VOICE_NAME") or "freeman").lower()
    voices = fetch_fish_voices(api_key)
    if not voices:
        return None, "сток Fish (список голосов не получен)"
    aliases = [wanted, "фримен", "фриман", "freeman"]
    for vid, title in voices:
        low = (title or "").lower()
        if any(a in low for a in aliases):
            return vid, f"свой голос «{title}» (найден по названию)"
    vid, title = voices[0]
    return vid, f"первый свой голос «{title}» (Фримена в аккаунте не нашлось)"


def tts_fish_audio(text, api_key, voice_id=None, model=None):
    """Одна реплика → mp3-байты через Fish Audio (прямой путь завода).

    `model` — заголовок выбора движка Fish (s2 — новее и живее s1; решение
    студии). Если модель недоступна на аккаунте, откат на дефолтную.
    Если модель недоступна на аккаунте, запрос повторяется без заголовка,
    чтобы озвучка не падала целиком.
    """
    payload = {"text": text, "format": "mp3"}
    if voice_id:
        payload["reference_id"] = voice_id
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if model:
        headers["model"] = model
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"),
        headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()
    except Exception as e:
        if not model:
            raise
        print(f"    [fish] модель {model} не принята ({e}) — повтор на дефолтной")
        headers.pop("model", None)
        req = urllib.request.Request(
            API_URL, data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()


def _mp3_duration(path):
    """Длительность mp3 в секундах через ffprobe (0.0 при ошибке)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except Exception:
        return 0.0


BASE_TEMPO = re.compile(r"^\s*(?:\*\*)?ТЕМП(?:\*\*)?\s*:?\s*\*?\*?\s*([\d.]+)",
                        re.I | re.M)


def script_tempo(md_path):
    """Базовый темп ролика из шапки VO: строка «**ТЕМП:** 1.12».

    ПОДАЧА — СВОЙСТВО СЦЕНАРИЯ, А НЕ НАСТРОЙКА СБОРЩИКА. Ремарки задают темп
    ОТДЕЛЬНОЙ реплики относительно соседних, и общий разгон ими не выразить:
    пришлось бы дописывать «быстрее» в каждую строку, а через ролик забыть в
    одной. Одно число в шапке разгоняет весь монолог и живёт рядом с текстом,
    к которому относится, — там же, где сквозная мысль и конфликт.
    """
    try:
        m = BASE_TEMPO.search(Path(md_path).read_text(encoding="utf-8"))
    except OSError:
        return 1.0
    return float(m.group(1)) if m else 1.0


def direct_line(mp3_bytes, remark, base=1.0):
    """Режиссура реплики по ремарке из VO-таблицы: темп/громкость/шёпот.

    Обрабатываем готовый mp3 ffmpeg'ом — API не трогаем. Ключевые слова:
    шёпот/тихо → тише и мягче; медленно/с расстановкой → темп вниз;
    жёстко/в упор → чуть громче и плотнее; финал → медленно и весомо.

    `base` — общий темп ролика из шапки сценария. Ремарка правит подачу
    ОТНОСИТЕЛЬНО него: «медленно» на разогнанном ролике всё равно быстрее
    обычного, и это верно — медленно тут значит «медленнее соседних», а не
    «медленно вообще».
    """
    if not shutil.which("ffmpeg"):
        return mp3_bytes
    if not remark and abs(base - 1.0) < 0.005:
        return mp3_bytes
    af = []
    tempo = 1.0          # копим ОДИН множитель темпа (см. ниже про кламп)
    r = remark
    # --- ШЁПОТ / ТИХО: тише, мягче, чуть ближе к уху -----------------------
    if any(k in r for k in ("шёпот", "шепот", "тихо", "тише")):
        af += ["volume=0.66", "lowpass=f=6500", "highpass=f=120"]
    # --- КРИК / ЯРОСТЬ: громче, плотнее, чуть быстрее ----------------------
    if any(k in r for k in ("крик", "кричи", "ярост", "зло", "злее", "рявк")):
        af += ["volume=1.32",
               "acompressor=threshold=-20dB:ratio=4:attack=3:release=60"]
        tempo *= 1.05
    # --- ЖЁСТКО / В УПОР: плотный нажим без крика --------------------------
    if any(k in r for k in ("жёстко", "жестко", "в упор", "оскал")):
        af += ["volume=1.18",
               "acompressor=threshold=-18dB:ratio=3:attack=5:release=80"]
    # --- РУБЛЕНО / МЕХАНИЧЕСКИ (пулемёт): суше, ровнее и БЫСТРЕЕ ------------
    # 1.04 был почти неслышен: перечисление шло тем же темпом, что и
    # рассуждение, и приём пропадал. Пулемёт обязан отличаться на слух —
    # 1.12 (потолок вклада ремарки) поверх базового темпа ролика даёт
    # очередь, после которой пауза бьёт.
    if any(k in r for k in ("рублен", "механич", "пулемёт", "пулемет")):
        af.append("acompressor=threshold=-16dB:ratio=2.5")
        tempo *= 1.12
    # --- ПРЕЗРЕНИЕ / УХМЫЛКА: медленнее, вальяжно ---------------------------
    if any(k in r for k in ("презрен", "ухмыл", "фамильярн", "дерзк")):
        tempo *= 0.96
    # --- ТЕПЛО / ДОСТОИНСТВО (взлёт): мягче и медленнее ---------------------
    if any(k in r for k in ("тепл", "достоинств", "взлёт", "взлет")):
        af += ["lowpass=f=11000", "volume=0.95"]
        tempo *= 0.94
    # --- МЕДЛЕННО / ФИНАЛ / ЖАЛО: весомо ------------------------------------
    if any(k in r for k in ("медленн", "расстановк", "финал", "весом", "жало")):
        tempo *= 0.93
    # --- СПОКОЙНО / ДИКТОР --------------------------------------------------
    if any(k in r for k in ("спокойно", "диктор")):
        tempo *= 0.97
    # Кламп: несколько подсказок не должны складываться в кисель. Диапазон
    # ±12% — слышно как смена подачи, но дикция остаётся внятной.
    # Клампится ТОЛЬКО вклад ремарки; базовый темп ролика накладывается сверху,
    # иначе разогнанный монолог упирался бы в потолок на каждой второй реплике
    # и подача выравнивалась бы в одну доску.
    tempo = min(1.12, max(0.88, tempo)) * base
    # Общий потолок дикции. Поднимался дважды по замеру готовых роликов: на
    # 1.35 и пулемёт, и рассуждение упирались в него и звучали одинаково, а
    # разница между битами важнее последних процентов внятности. 1.58 — это
    # база 1.42 плюс вклад пулемёта; синтез на такой скорости ещё держит
    # согласные, но дальше поднимать нельзя.
    tempo = min(1.58, max(0.75, tempo))
    if abs(tempo - 1.0) > 0.005:
        af.append(f"atempo={tempo:.3f}")
    if not af:
        return mp3_bytes
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.mp3"); dst = os.path.join(td, "out.mp3")
        open(src, "wb").write(mp3_bytes)
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                            "-af", ",".join(af), "-c:a", "libmp3lame", "-q:a", "3", dst],
                           check=True)
            return open(dst, "rb").read()
        except subprocess.CalledProcessError:
            return mp3_bytes


def assemble_track(replicas, out_path, gap=0.15):
    """Собирает дубль: каждая реплика на своём таймкоде, но БЕЗ наложения —
    если озвучка длиннее зазора до следующей, следующая сдвигается вправо
    (стартует не раньше, чем предыдущая закончилась + короткая пауза)."""
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg не найден в PATH.")
    with tempfile.TemporaryDirectory() as td:
        inputs = []
        filters = []
        amix = []
        cursor = 0.0  # момент, раньше которого следующая реплика начаться не может
        for i, (start, mp3_bytes) in enumerate(replicas):
            p = os.path.join(td, f"r{i}.mp3")
            with open(p, "wb") as f:
                f.write(mp3_bytes)
            dur = _mp3_duration(p)
            place = max(start, cursor)          # не раньше конца предыдущей
            if place > start + 0.05:
                print(f"  ⚠ реплика {i+1} сдвинута {start:.1f}s→{place:.1f}s "
                      f"(предыдущая длиннее зазора) — раздвинь таймкоды в VO")
            cursor = place + dur + gap
            inputs += ["-i", p]
            delay_ms = int(place * 1000)
            filters.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
            amix.append(f"[a{i}]")
        filter_complex = (
            ";".join(filters)
            + f";{''.join(amix)}amix=inputs={len(amix)}:normalize=0[out]"
        )
        cmd = (
            ["ffmpeg", "-y", "-v", "error"]
            + inputs
            + ["-filter_complex", filter_complex, "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "3", out_path]
        )
        subprocess.run(cmd, check=True)


def assemble_by_timing(script, parts_dir, times_json, map_json, out_path):
    """Собрать дорожку по ФАКТИЧЕСКИМ временам движка (animdsl timing).

    Синхрон по конструкции: реплика ложится ровно туда, где движок открывает
    рот. Реплики без маркера (дикторские) ставятся с сохранением сдвига
    относительно предыдущей синхронизированной (по дельтам из VO.md).
    """
    import json as _json
    rows = parse_vo_table(script)                     # [(md_time, text, remark)]
    times = _json.load(open(times_json))["blocks"]    # [{"index","start","end"}]
    order = _json.load(open(map_json))                # [vo_n, ...] в порядке блоков
    n2block = {n: times[i]["start"] for i, n in enumerate(order) if i < len(times)}
    replicas = []
    placed = {}
    for i, (md_t, text, remark) in enumerate(rows, start=1):
        p = os.path.join(parts_dir, f"vo-{i}.mp3")
        if not os.path.isfile(p):
            continue
        if i in n2block:
            t = n2block[i]
        else:
            # дикторская: сдвиг от предыдущей размеченной по дельте VO.md
            prev = max((n for n in n2block if n < i), default=None)
            if prev is not None:
                prev_md = rows[prev - 1][0]
                t = n2block[prev] + (md_t - prev_md)
            else:
                t = md_t
        placed[i] = round(t, 2)
        replicas.append((t, open(p, "rb").read()))
    if not replicas:
        sys.exit("Нет частей vo-N.mp3 — сборка невозможна (сначала --parts-dir).")
    print(f"Сборка по временам движка: {placed}")
    assemble_track(replicas, out_path)


def main(argv):
    ap = argparse.ArgumentParser(description="Озвучка VO-сценария через Fish Audio")
    ap.add_argument("script", nargs="?", help="Путь к *-VO.md со сценарием")
    ap.add_argument("-o", "--output", help="Куда писать mp3")
    ap.add_argument("--parts-dir", help="Куда сохранить mp3 по репликам (vo-<N>.mp3) для липсинка")
    ap.add_argument("--no-assemble", action="store_true",
                    help="только сгенерить части (сборка позже по временам движка)")
    ap.add_argument("--assemble-only", action="store_true",
                    help="только собрать из готовых частей по --times-json/--map-json")
    ap.add_argument("--times-json", help="JSON от `animdsl timing` (фактические времена)")
    ap.add_argument("--map-json", help="карта блоков от prep_lipsync (map.json)")
    ap.add_argument("--list-voices", action="store_true",
                    help="показать голоса аккаунта Fish (их id → FISH_AUDIO_VOICE_ID)")
    args = ap.parse_args(argv)

    if args.list_voices:
        key = os.environ.get("FISH_AUDIO_API_KEY")
        if not key:
            sys.exit("Нужен FISH_AUDIO_API_KEY в окружении.")
        list_fish_voices(key)
        return 0
    if not args.script or not args.output:
        sys.exit("Нужны script и -o (или --list-voices).")

    if args.assemble_only:
        if not (args.parts_dir and args.times_json and args.map_json):
            sys.exit("--assemble-only требует --parts-dir, --times-json, --map-json")
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        assemble_by_timing(args.script, args.parts_dir, args.times_json,
                           args.map_json, args.output)
        print(f"OK: {args.output}")
        return 0

    # ОСНОВНОЙ путь — ПРЯМОЙ Fish Audio: студия клонировала свой голос и держит
    # его id в секрете FISH_AUDIO_VOICE_ID, поэтому ходить за озвучкой через
    # Frederick больше незачем — это лишнее звено, чужой кэш и чужой голос по
    # умолчанию. Frederick остаётся ЗАПАСНЫМ: включается, только если ключа
    # Fish нет вовсе. Переключить обратно можно переменной VOICE_VIA=frederick.
    api_key = os.environ.get("FISH_AUDIO_API_KEY")
    via = (os.environ.get("VOICE_VIA") or "").strip().lower()
    if via == "frederick":
        use_frederick = bool(FREDERICK_TOKEN)
    elif via == "fish":
        use_frederick = False
    else:
        use_frederick = not api_key and bool(FREDERICK_TOKEN)
    if not use_frederick and not api_key:
        sys.exit("Нет FISH_AUDIO_API_KEY (и нет запасного FREDERICK_ADMIN_TOKEN) — пропускаю озвучку.")
    voice_id = os.environ.get("FISH_AUDIO_VOICE_ID")
    voice_src = "запасной путь Frederick"
    if not use_frederick:
        voice_id, voice_src = resolve_voice_id(api_key, voice_id)

    base_tempo = script_tempo(args.script)
    if abs(base_tempo - 1.0) > 0.005:
        print(f"  темп ролика: ×{base_tempo:.2f} (шапка сценария)")
    rows = parse_vo_table(args.script)
    if not rows:
        sys.exit(f"В {args.script} не найдено реплик VO-таблицы.")
    fish_model = os.environ.get("FISH_AUDIO_MODEL") or "s2"
    if not use_frederick and not voice_id:
        print("!!! ВНИМАНИЕ: голос Фримена не найден в аккаунте Fish — озвучка "
              "пойдёт СТОКОВЫМ голосом. Проверь `--list-voices`; если модель "
              "названа иначе, задай FISH_VOICE_NAME или FISH_AUDIO_VOICE_ID.")
    src = (f"Frederick ({FREDERICK_BASE}) [запасной] — голос Фреди" if use_frederick
           else f"Fish напрямую, модель {fish_model}, голос: {voice_src}")
    print(f"Реплик: {len(rows)}; озвучка: {src}")

    if args.parts_dir:
        os.makedirs(args.parts_dir, exist_ok=True)
    replicas = []
    for i, (start, text, remark) in enumerate(rows, start=1):
        tag = f" [{remark}]" if remark else ""
        print(f"  {start:6.1f}s  {text[:56]}{tag}")
        spoken = for_synthesis(text)
        audio = (tts_via_frederick(spoken) if use_frederick
                 else tts_fish_audio(spoken, api_key, voice_id, fish_model))
        audio = direct_line(audio, remark, base_tempo)
        replicas.append((start, audio))
        # Сохранить реплику отдельным файлом для липсинка (prep_lipsync).
        if args.parts_dir:
            with open(os.path.join(args.parts_dir, f"vo-{i}.mp3"), "wb") as f:
                f.write(audio)

    if args.no_assemble:
        print("Части готовы (сборка отложена до animdsl timing).")
        return 0
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    assemble_track(replicas, args.output)
    print(f"OK: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
