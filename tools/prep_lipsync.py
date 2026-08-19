#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prep_lipsync.py — впаивает липсинк по реальной озвучке в сценарий перед рендером.

«Завод без рассинхрона»: речь в .anim размечается ПОДСКАЗКОЙ-комментарием и
обычным `speaks for`, который работает и сам по себе:

    //lip 1                      # это реплика VO-1
    freeman speaks for 3.2s      # запасной вариант (флэпы), если озвучки нет

Препроцессор для каждой пары ищет mp3 этой реплики (<parts>/vo-<N>.mp3), снимает
огибающую громкости (tools/lipsync.py) и ЗАМЕНЯЕТ строку `speaks for` на дорожку
из действий `lips` — рот открывается ровно там, где звук (амплитудный липсинк),
а тело держит позу (lips — overlay). Если mp3 нет — строка `speaks for` остаётся
как есть, так что сценарий рендерится всегда.

Использование:
    python3 tools/prep_lipsync.py scene.anim --parts videos/<id>-parts \
        -o scene.lipsynced.anim
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lipsync import extract_envelope, envelope_to_mouths  # noqa: E402

LIP = re.compile(r"^\s*//lip\s+(\d+)\s*$")

# ЗАКАДРОВАЯ РЕПЛИКА — та, которую герой не произносит в кадре НАМЕРЕННО: он
# может там вообще отсутствовать (титр-карта, план без него). У такой реплики
# нет и не должно быть `//lip`, и опознаётся она по ремарке в VO-таблице.
#
# Константа вынесена сюда и импортируется теми, кому нужна та же конвенция
# (tools/sverka.py). Разъехавшись, два инструмента начнут спорить об одном и
# том же ролике: один назовёт закадровую реплику браком, другой — нормой. Так
# уже случилось: гейт сверки уронил завод на `biznes-myshlenie-intro`, где
# VO-7 честно помечена «голос-диктор» и звучит над титр-картой.
NARRATOR = re.compile(r"голос[\s-]*диктор|диктор\w*\s+голос|за\s+кадром|закадр", re.I)
SPEAK = re.compile(r"^(\s*)(\S+)\s+speaks\s+for\s+([\d.]+)s\s*$")
# Строительные строки между маркером и речью: открытие блока, закрытие,
# комментарий, пустая. Через них маркер обязан ПЕРЕЖИТЬ до `speaks for`.
SCAFFOLD = re.compile(r"^\s*(together\s*\{|do\s*\{|\{|\}|//.*)?\s*$")
# Всё, что задаёт время внутри блока катов: `wait 1.0s`, `... over 0.55s`,
# `camera shake 0.3s`, `... for 0.2s`. Растягивается вместе с репликой.
TIMED = re.compile(r"\b(wait\s+|over\s+|shake\s+|for\s+)([\d.]+)s")

# Виземы Rhubarb → позы рига (rig.json: visA..visF). Расширенные G/H/X
# сводим к ближайшим базовым.
RHUBARB_MAP = {
    "A": "visA", "B": "visB", "C": "visC", "D": "visD",
    "E": "visE", "F": "visF", "G": "visB", "H": "visC", "X": "visA",
}


def rhubarb_bin():
    """Путь к бинарю Rhubarb Lip Sync (или None): $RHUBARB_BIN либо в PATH."""
    cand = os.environ.get("RHUBARB_BIN") or shutil.which("rhubarb")
    return cand if cand and os.path.exists(cand) else None


def gate_viseme(pose, prev_pose, dur, loud):
    """Гейт виземы по РЕАЛЬНОЙ громкости (loud = local RMS / peak, 0..1).

    Rhubarb метит рот по фонеме, без громкости → шёпот и крик дают один удар.
    Здесь громкость рулит акцентом: тихий «широкий» слог оседает в скромный рот
    (visB, без удара → жеста/сквоша нет — микро на шёпоте); громкий ударный слог
    получает _acc (удар → жест+сквош по огибающей mp3 — размашисто на крике).
    Средняя громкость оставляет базовый широкий рот (обычный акцент)."""
    if pose in ("visC", "visD", "visE"):
        if loud < 0.40:
            return "visB"                      # тихо → скромный рот, БЕЗ удара
        if (prev_pose in ("visA", "visB", "visF")
                and dur >= 0.08 and loud >= 0.58):
            return pose + "_acc"               # громкий ударный слог → удар
    return pose


def rhubarb_track(mp3):
    """mp3 → [(поза, длительность)] через фонемный Rhubarb (None при сбое).

    Rhubarb ест wav/ogg — конвертируем ffmpeg'ом; распознаватель phonetic
    языконезависим (наш текст — русский). Выход: JSON mouthCues (A..X).
    Виземы гейтятся реальной огибающей громкости (gate_viseme).
    """
    rb = rhubarb_bin()
    if not rb or not shutil.which("ffmpeg"):
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            wav = os.path.join(td, "line.wav")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", "16000", "-ac", "1", wav],
                check=True,
            )
            res = subprocess.run(
                [rb, "-r", "phonetic", "-f", "json", "--machineReadable", wav],
                check=True, capture_output=True, text=True,
            )
        cues = json.loads(res.stdout).get("mouthCues", [])
        # Огибающая громкости этой же реплики — гейт акцентов по силе голоса.
        hop = 0.05
        try:
            env = extract_envelope(mp3, hop)
            peak = max(env) or 1.0
        except Exception:
            env, peak = [], 1.0

        def loud_at(t):
            if not env:
                return 1.0
            return env[min(int(t / hop), len(env) - 1)] / peak

        track = []
        prev_pose = "visA"
        for c in cues:
            start = float(c["start"])
            dur = float(c["end"]) - start
            pose = RHUBARB_MAP.get(c["value"], "visA")
            pose = gate_viseme(pose, prev_pose, dur, loud_at(start + dur * 0.5))
            prev_pose = pose.replace("_acc", "")
            if track and track[-1][0] == pose:
                track[-1] = (pose, track[-1][1] + dur)
            elif dur > 0:
                track.append((pose, dur))
        return track or None
    except Exception as e:  # noqa: BLE001 — любой сбой → честный фолбэк на RMS
        print(f"  [rhubarb] не сработал ({e}) — амплитудный липсинк.")
        return None


def mp3_duration(path):
    """Длина файла в секундах (None, если ffprobe недоступен)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            check=True, capture_output=True, text=True).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001
        return None


def fit_to_audio(track, mp3):
    """ГЛАВНЫЙ ИНВАРИАНТ: дорожка рта длится РОВНО столько же, сколько её звук.

    На нём держится весь синхрон завода. Движок откладывает речевой блок по
    сумме `lips ... for`, а сборщик голоса ставит реплику на время этого блока.
    Если дорожка короче своего mp3, блок в движке короче звука — и КАЖДАЯ
    следующая реплика уезжает на разницу. Ошибка накапливается: в тюрьме за
    девять реплик набежало 24 секунды, картинка кончалась на 47-й, а голос шёл
    до 71-й.

    Ловилось это только человеком, потому что по отдельности всё «работало»:
    Rhubarb отдавал разметку, движок её честно откладывал, сборщик честно
    сдвигал реплики и честно предупреждал «предыдущая длиннее зазора».

    Недобор добиваем закрытым ртом в конец — начало реплики остаётся точным,
    вся погрешность уходит в хвост. Перебор подрезаем с конца.
    """
    dur = mp3_duration(mp3)
    if not dur or not track:
        return track
    total = sum(d for _, d in track)
    delta = dur - total
    if abs(delta) < 0.02:
        return track
    if delta > 0:
        track = track + [("visA", delta)]
    else:
        left = -delta
        while track and left > 1e-6:
            pose, d = track[-1]
            if d > left + 1e-6:
                track[-1] = (pose, d - left)
                left = 0.0
            else:
                left -= d
                track.pop()
    if abs(delta) > dur * 0.05:
        print(f"  ⚠ {os.path.basename(mp3)}: разметка рта разошлась со звуком на "
              f"{delta:+.2f}s из {dur:.2f}s — выровнял, но стоит проверить.")
    return track


def lips_track_lines(entity, mp3, indent, fps=11.0):
    # Сначала фонемы (Rhubarb): рот артикулирует слоги. Фолбэк — RMS-огибающая.
    track = rhubarb_track(mp3)
    src = "фонемы" if track else "амплитуда"
    if not track:
        hop = 1.0 / fps
        track = envelope_to_mouths(extract_envelope(mp3, hop), hop)
    track = fit_to_audio(track, mp3)
    # ДОРОЖКА ОБЁРНУТА В `do { }` — иначе она схлопывается.
    #
    # Речь с катами внутри мы пишем как `together { speaks; do { камеры } }`.
    # Препроцессор подменял строку `speaks` СПИСКОМ строк `lips`, и каждая из
    # них становилась ОТДЕЛЬНОЙ ветвью together — а ветви стартуют
    # ОДНОВРЕМЕННО. Сто ртов реплики играли в один и тот же миг: речевой блок
    # выходил длиной в один рот, губы дёргались и замирали, а сборщик голоса,
    # который ставит реплику на время блока, честно сдвигал каждую следующую —
    # так набегали те самые 24 секунды звука поверх последнего кадра.
    #
    # `do { }` делает список ОДНОЙ последовательной ветвью: рты идут друг за
    # другом, длина блока равна длине звука, каты в соседней ветви идут
    # параллельно, как и задумано.
    out = [f"{indent}// липсинк {os.path.basename(mp3)} ({len(track)} ртов, {src})",
           f"{indent}do {{"]
    # Округляем НАКОПИТЕЛЬНО: каждый рот дотягивается до общей сетки, поэтому
    # сумма выведенных длительностей равна длине звука с точностью до 0.01с, а
    # не уползает на 0.005 за каждый рот.
    acc, printed = 0.0, 0.0
    for pose, dur in track:
        acc += dur
        step = round(acc - printed, 2)
        if step <= 0:
            continue
        printed += step
        out.append(f'{indent}    {entity} lips "{pose}" for {step}s')
    out.append(f"{indent}}}")
    return out


def process(text, parts_dir):
    out, pending, subbed, fell, skipped = [], None, 0, 0, 0
    order = []  # номера vo-N в порядке появления речевых блоков в файле
    stretch = None   # (коэффициент, отступ блока `do`) для соседних катов
    depth = None     # глубина скобок внутри растягиваемого `do`
    for line in text.splitlines():
        # РАСТЯЖКА СОСЕДНЕГО БЛОКА КАТОВ. Реплика пишется так:
        #
        #     together {
        #         freeman speaks for 6.5s     ← заявленная длительность
        #         do { camera ...; wait 2.2s; camera ...; wait 2.0s; camera ... }
        #     }
        #
        # `speaks for` заменяется дорожкой рта РЕАЛЬНОЙ длины, а соседний `do`
        # остаётся прежним. Когда диктор говорит дольше заявленного, каты
        # заканчиваются на середине реплики и камера СТОИТ до её конца: в
        # «Теориях личности» так вышел неподвижный план на 12.2 секунды при
        # среднем плане 1.7. Поэтому паузы соседнего блока умножаются на то
        # же отношение, на какое разъехалась речь, — каты остаются там же по
        # ДОЛЕ реплики, где их поставил режиссёр.
        if stretch is not None:
            k, blk_indent = stretch
            if depth is None:
                if re.match(rf"^{blk_indent}do\s*\{{\s*$", line):
                    depth = 1
                    out.append(line)
                    continue
                if line.strip() and not line.strip().startswith("//"):
                    stretch = None      # соседнего блока катов нет
            else:
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    stretch, depth = None, None
                else:
                    line = TIMED.sub(
                        lambda mm: f"{mm.group(1)}{round(float(mm.group(2)) * k, 2)}s",
                        line)
                    out.append(line)
                    continue
        m = LIP.match(line)
        if m:
            pending, skipped = int(m.group(1)), 0  # запомнить номер, маркер убрать
            continue
        s = SPEAK.match(line)
        if s and pending is not None:
            indent, entity, dur = s.group(1), s.group(2), s.group(3)
            mp3 = os.path.join(parts_dir or "", f"vo-{pending}.mp3")
            if parts_dir and os.path.isfile(mp3) and os.path.getsize(mp3) > 0:
                out.extend(lips_track_lines(entity, mp3, indent))
                subbed += 1
                real, declared = mp3_duration(mp3), float(dur)
                if real > 0 and declared > 0.05:
                    k = round(real / declared, 4)
                    if abs(k - 1.0) > 0.02:
                        stretch, depth = (k, indent), None
            else:
                out.append(line)  # запасной путь: обычные флэпы
                fell += 1
            order.append(pending)
            pending, skipped = None, 0
            continue
        # МАРКЕР ПЕРЕЖИВАЕТ СТРОИТЕЛЬНЫЕ СТРОКИ.
        #
        # Раньше `pending` сбрасывался ЛЮБОЙ строкой, которая не `speaks for`.
        # А каты внутри реплики мы пишем так:
        #
        #     //lip 1
        #     together {
        #         freeman speaks for 3.0s
        #
        # — следом за маркером идёт `together {`, маркер обнулялся, и речь
        # уходила на обобщённые флэпы. Молча: в логе стояло честное
        # «карта блоков: []», но никто не читал. В итоге липсинк по звуку
        # не работал в ТРЁХ роликах из пяти озвученных — во всех, где есть
        # каты внутри реплик, то есть в самых проработанных.
        #
        # Пропускаем только строительные строки и не больше шести подряд,
        # чтобы забытый маркер не прилип к речи через полсцены.
        if pending is not None and SCAFFOLD.match(line) and skipped < 6:
            skipped += 1
            out.append(line)
            continue
        pending, skipped = None, 0
        out.append(line)
    return "\n".join(out) + "\n", subbed, fell, order


def main(argv):
    ap = argparse.ArgumentParser(description="Впаять липсинк в .anim перед рендером")
    ap.add_argument("anim")
    ap.add_argument("--parts", help="каталог с vo-<N>.mp3 (нет → везде флэпы)")
    ap.add_argument("--vo", help="VO-сценарий: по нему отличаем дикторские реплики "
                                 "от забытых при разметке")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args(argv)

    text = open(args.anim, encoding="utf-8").read()
    result, subbed, fell, order = process(text, args.parts)

    # СВЕРКА: все ли синтезированные реплики нашли себе речевой блок в сцене.
    # Голос собирается по VO-таблице целиком, а рот открывается только там, где
    # в сцене стоит `speaks`. Если реплика озвучена, но в сцене её никто не
    # произносит, зритель слышит голос при закрытом рте — и никакая метрика
    # этого не ловила. В «Перепрошивке» так молча висели две реплики из десяти.
    if args.parts and os.path.isdir(args.parts):
        have = sorted(int(m.group(1)) for f in os.listdir(args.parts)
                      if (m := re.match(r"vo-(\d+)\.mp3$", f)))
        # ДИКТОРСКИЕ реплики звучат за кадром НАМЕРЕННО — герой в этот момент
        # может вообще отсутствовать в кадре (в «Перепрошивке» VO-5 и VO-6 идут
        # над сценой с книгой, где его нет). Отличаем их по ремарке: «голос
        # диктора», «за кадром», «закадр». Всё остальное без `//lip` — забыто.
        narrator = set()
        if args.vo and os.path.isfile(args.vo):
            for i, line in enumerate(
                    l for l in open(args.vo, encoding="utf-8")
                    if re.match(r"\s*\|\s*VO-?\d", l)):
                if NARRATOR.search(line):
                    narrator.add(i + 1)
        lost = [n for n in have if n not in order and n not in narrator]
        if lost:
            print(f"  ⚠ озвучены, но в сцене не произносятся: "
                  f"{', '.join('VO-' + str(n) for n in lost)} — "
                  f"голос будет звучать при закрытом рте. Добавь `//lip N` + "
                  f"`speaks`, убери реплику из VO или пометь её ремаркой "
                  f"«голос диктора», если она задумана закадровой.")
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(result)
    # Карта «речевой блок № → номер vo-N» для сборки голоса по фактическим
    # временам движка (animdsl timing) — синхрон по конструкции.
    with open(args.output + ".map.json", "w", encoding="utf-8") as f:
        json.dump(order, f)
    print(f"OK: {args.output} — липсинк по звуку: {subbed}, флэп-фолбэк: {fell}; карта блоков: {order}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
