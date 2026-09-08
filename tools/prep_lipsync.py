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

ЖЕСТЫ САЖАЮТСЯ НА СЛОВА. Второе дело препроцессора, кроме рта. Соседний с
речью блок `do` держит режиссуру реплики: наезды, каты, смены позы. Его паузы
писались до озвучки, поэтому раньше блок просто растягивался в то же число раз,
на какое разъехалась речь, — жест оставался на своей ДОЛЕ реплики. Этого мало:
синтез каждый раз распределяет паузы иначе, и доля, снятая с прошлой дорожки,
уезжает от слова на 0.1–0.15 реплики (на «Философии» это 0.6с на фразе
«Утро. Работа. Лента. Так надо.» — обвис приходился на «Ленту»). Поэтому после
растяжки каждая смена позы подтягивается к ближайшему НАЧАЛУ СЛОВА, если оно
ближе 0.35с; дальше не тянем — значит, режиссёр метил в другое слово.

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


# Начало жеста ловится на СЛОВЕ, а не на секунде: см. ниже `speech_onsets`
# и `retime_block`. Порог «тише десятой доли пика» и минимальная тишина в 60мс
# подобраны по нашим репликам Fish: слоги внутри слова тише не проваливаются,
# а межсловная пауза проваливается всегда.
ONSET_REL = 0.10          # доля пика, ниже которой считаем, что звука нет
ONSET_GAP_S = 0.06        # столько тишины должно быть ПЕРЕД началом слова
ONSET_MIN_SEP_S = 0.12    # ближе этого два начала не различаем — это один слог
SNAP_TOL_S = 0.35         # дальше этого к слову не тянем — значит, метили не туда


def speech_onsets(mp3, hop_s=0.01):
    """Начала слов и слогов в реплике (секунды от её начала).

    Двумя способами сразу, и это не перестраховка. Первый — выход из тишины:
    надёжен, но во фразе, сказанной на одном дыхании, тишины между словами нет
    вовсе. На «Смысл жизни — третья кнопка сверху» такой поиск нашёл РОВНО ОДНО
    начало — первое, — и жест не к чему было притягивать.

    Второй — подъём громкости (половинчатая разность огибающей с порогом от
    скользящего среднего). Он ловит начало слога и внутри слитной речи, где
    громкость проваливается на согласном, но до тишины не доходит.

    Точность здесь нужна не фонетическая: жест должен попасть в слово, а не в
    середину гласной. Ошибка в пределах согласного эту задачу решает.
    """
    try:
        env = extract_envelope(mp3, hop_s)
    except Exception:                                        # noqa: BLE001
        return []
    if not env or max(env) <= 0:
        return []
    peak = max(env)
    cand = []

    # 1) выход из тишины
    thr = peak * ONSET_REL
    gap = max(1, int(ONSET_GAP_S / hop_s))
    quiet = gap
    for i, v in enumerate(env):
        if v > thr:
            if quiet >= gap:
                cand.append(i)
            quiet = 0
        else:
            quiet += 1

    # 2) подъём громкости внутри слитной речи
    flux = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    win = max(3, int(0.25 / hop_s))
    for i, f in enumerate(flux):
        lo, hi = max(0, i - win), min(len(flux), i + win + 1)
        local = sum(flux[lo:hi]) / (hi - lo)
        if f > max(local * 1.8, peak * 0.02) and env[i + 1] > peak * 0.18:
            if f >= max(flux[max(0, i - 2):min(len(flux), i + 3)]):
                cand.append(i + 1)

    # слить близкие: два подъёма ближе 0.12с — это один слог, а не два слова
    sep = max(1, int(ONSET_MIN_SEP_S / hop_s))
    out, last = [], -10 ** 9
    for i in sorted(set(cand)):
        if i - last >= sep:
            out.append(i * hop_s)
            last = i
    return out


def retime_block(lines, k, onsets):
    """Растянуть блок `do` в k раз и посадить жесты на начала слов.

    Растяжка одна сохраняет ДОЛЮ реплики, на которой стоит жест, и этого мало:
    синтез каждый раз распределяет паузы чуть иначе, и доля, снятая с прошлой
    дорожки, уезжает от слова на 0.1–0.15 реплики. Поэтому после растяжки
    каждый жест подтягивается к ближайшему началу слова, если оно ближе
    SNAP_TOL_S. Дальше — не трогаем: значит, метили не в это слово, и лучше
    оставить как поставил режиссёр, чем притянуть к чужому.
    """
    # где в блоке стоят жесты: строка со сменой позы или появлением предмета
    gesture = [bool(re.search(r'\bpose\s+"|\b\w+\s+shows\b', ln)) for ln in lines]
    out, t, moved = [], 0.0, 0
    for i, ln in enumerate(lines):
        m = re.search(r"\b(wait\s+)([\d.]+)s", ln)
        if m:
            new = float(m.group(2)) * k
            # следующая содержательная строка — жест? тогда время его прихода
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and gesture[j] and onsets:
                want = t + new
                near = min(onsets, key=lambda o: abs(o - want))
                if abs(near - want) <= SNAP_TOL_S:
                    adj = max(0.02, new + (near - want))
                    if abs(adj - new) > 0.01:
                        moved += 1
                    new = adj
            t += new
            ln = ln[:m.start()] + f"{m.group(1)}{round(new, 2)}s" + ln[m.end():]
            out.append(ln)
            continue
        # прочие длительности (наезд, тряска) просто тянутся вместе с речью
        out.append(TIMED.sub(
            lambda mm: f"{mm.group(1)}{round(float(mm.group(2)) * k, 2)}s", ln))
    return out, moved


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
    # ПОРОГИ СНИЖЕНЫ: 0.40/0.58 → 0.26/0.44. С голосом Fish (сжатая динамика)
    # до 58% пика дотягивали единицы слогов, и слой «говорящего тела» в
    # движке почти не включался: замер доли силуэта, меняющейся между кадрами,
    # дал 0.03 на озвучке против 0.20 на флэп-фолбэке и ~0.10 у оригинала.
    # Ролик с настоящим голосом выходил МЕРТВЕЕ ролика с болванкой.
    if pose in ("visC", "visD", "visE"):
        if loud < 0.26:
            return "visB"                      # тихо → скромный рот, БЕЗ удара
        if (prev_pose in ("visA", "visB", "visF")
                and dur >= 0.08 and loud >= 0.44):
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
    stretch = None   # (коэффициент, отступ блока `do`, начала слов реплики)
    depth = None     # глубина скобок внутри растягиваемого `do`
    buf = []         # строки блока `do`: пересчитываются целиком на закрытии
    snapped = 0      # сколько жестов подтянуто к началу слова
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
            k, blk_indent, onsets = stretch
            if depth is None:
                if re.match(rf"^{blk_indent}do\s*\{{\s*$", line):
                    depth, buf = 1, []
                    out.append(line)
                    continue
                if line.strip() and not line.strip().startswith("//"):
                    stretch = None      # соседнего блока катов нет
            else:
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    # БЛОК ЗАКРЫЛСЯ — только теперь его можно пересчитать: чтобы
                    # посадить жест на слово, надо видеть, что стоит ПОСЛЕ паузы,
                    # а построчный проход этого не знает.
                    fixed, moved = retime_block(buf, k, onsets)
                    out.extend(fixed)
                    snapped += moved
                    stretch, depth, buf = None, None, []
                else:
                    buf.append(line)
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
                    # Блок пересчитываем ВСЕГДА, даже при k≈1: растяжка — не
                    # единственная его работа, жесты ещё надо посадить на слова.
                    stretch, depth = (k, indent, speech_onsets(mp3)), None
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
    return "\n".join(out) + "\n", subbed, fell, order, snapped


def main(argv):
    ap = argparse.ArgumentParser(description="Впаять липсинк в .anim перед рендером")
    ap.add_argument("anim")
    ap.add_argument("--parts", help="каталог с vo-<N>.mp3 (нет → везде флэпы)")
    ap.add_argument("--vo", help="VO-сценарий: по нему отличаем дикторские реплики "
                                 "от забытых при разметке")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args(argv)

    text = open(args.anim, encoding="utf-8").read()
    result, subbed, fell, order, snapped = process(text, args.parts)

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
                if re.search(r"голос[\s-]*диктор|диктор\w*\s+голос|за\s+кадром|закадр", line, re.I):
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
    print(f"OK: {args.output} — липсинк по звуку: {subbed}, флэп-фолбэк: {fell}; "
          f"жестов посажено на слово: {snapped}; карта блоков: {order}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
