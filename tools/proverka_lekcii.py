#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
proverka_lekcii.py — приёмка ВИДЕОРЯДА ЛЕКЦИИ по готовому файлу.

Двадцать шесть гейтов ролика сюда не применяются: они меряют устройство интро
(крючок на третьей секунде, кольцо, разрыв, жало, станок шутки), а у лекции есть
тема и порядок мыслей. Здесь свои шесть проверок, и каждая выросла из брака.

  1. ДЛИТЕЛЬНОСТИ. Картинка, звук и выданный файл — с точностью до десятой.
     Ролик 25 собрался без финала ровно потому, что этого никто не сверил.

  2. СКЛЕЙКИ В ПАУЗАХ. Смена кадра посреди слова читается обрывом, даже когда
     зритель не понимает, что его дёрнуло. Склейки ищутся В САМОМ ФАЙЛЕ
     (по скачку кадра), а не берутся из раскладки: сверять план с планом
     бессмысленно, проверять надо то, что вышло.

  3. ЗВУК ПОДНЯТ, НО НЕ ПЕРЕДАВЛЕН. LRA готового файла не ниже исходного минус
     0.2 LU. `loudnorm` при малом LRA уходит в динамику и даёт скачки усиления
     между соседними секундами — на шестнадцати минутах это слышно как дыхание.

  4. КАДР НЕ СТОИТ МЁРТВЫМ. Между соседними планами не должно быть промежутка
     дольше 50 с, и внутри каждого обязано идти движение.

  5. ПОДЛОЖКА НЕ ВЫЛЕЗАЕТ. Реестр §XLI: сет натянут край в край, проезд на
     `wide` показывает голый фон. Кадры берутся В КОНЦЕ проездов — пилот прошёл
     проверку глазами зелёным только потому, что смотрели начала сцен.

  6. КОНТАКТНЫЙ ЛИСТ — ГЛАЗАМИ. Машина его собирает, смотрит человек.

    python3 tools/proverka_lekcii.py videos/lekciya-koleya-1.mp4
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def dlit(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def sklejki(video, porog=0.35):
    """Тайм-коды смен кадра, снятые С ФАЙЛА фильтром scdet."""
    r = subprocess.run(
        ["ffmpeg", "-v", "info", "-nostats", "-i", str(video),
         "-vf", f"select='gt(scene,{porog})',metadata=print:file=-",
         "-f", "null", "-"],
        capture_output=True, text=True)
    syr = []
    for line in (r.stdout + r.stderr).splitlines():
        if line.startswith("frame:") and "pts_time:" in line:
            syr.append(float(line.split("pts_time:")[1].split()[0]))
    #  СКЛЕЙКА ОДНА, А СРАБАТЫВАНИЙ НЕСКОЛЬКО. `scdet` даёт по два-три кадра
    #  подряд на один стык (кадр смены и следующий за ним), и первый кадр файла
    #  он тоже считает сменой. Без склейки этих гроздей приёмка насчитала 51
    #  склейку там, где их 36, и половину объявила промахом.
    out = []
    for t in sorted(syr):
        if t < 0.2:                       # первый кадр — не склейка
            continue
        if not out or t - out[-1] > 0.5:
            out.append(round(t, 2))
    return out


def gromkost(p):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(p), "-af",
                        "loudnorm=I=-16:TP=-1.5:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    txt = r.stderr
    j = txt[txt.rfind("{"):txt.rfind("}") + 1]
    return json.loads(j)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--zvuk", default="examples/assets/audio-lekciya-koleya-1-master.mp3")
    ap.add_argument("--istochnik", default="examples/assets/audio-lekciya-koleya-1.mp3")
    ap.add_argument("--nemoj", default="videos/lekciya-koleya-1-nemoj.mp4")
    a = ap.parse_args(argv)

    video = ROOT / a.video
    zvuk, istok, nemoj = ROOT / a.zvuk, ROOT / a.istochnik, ROOT / a.nemoj
    ploho = 0
    print("\n  ПРИЁМКА ВИДЕОРЯДА ЛЕКЦИИ\n")

    # 1 ── длительности
    dv, dz, df = dlit(nemoj), dlit(zvuk), dlit(video)
    print(f"  1. ДЛИТЕЛЬНОСТИ")
    print(f"     немая картинка {dv:8.2f}с")
    print(f"     звук           {dz:8.2f}с")
    print(f"     готовый файл   {df:8.2f}с")
    #  Звук короче картинки на добор тишины в хвосте — это НЕ расхождение, а
    #  замысел: лекция кончается, и закрывающий кадр держится ещё полсекунды,
    #  вместо того чтобы обрубиться на последнем слове. Отдельно меряется
    #  картинка против готового файла (тут допуск жёсткий) и хвост тишины.
    if abs(dv - df) > 0.1:
        print(f"     [ПРОВАЛ] картинка и файл разошлись на {abs(dv-df):.2f}с")
        ploho += 1
    elif not (0 <= df - dz <= 1.0):
        print(f"     [ПРОВАЛ] хвост тишины {df - dz:+.2f}с — либо звук обрублен, "
              f"либо кадр висит слишком долго")
        ploho += 1
    else:
        print(f"     [OK] картинка и файл сходятся в {abs(dv-df):.2f}с, "
              f"хвост тишины {df - dz:.2f}с")

    # 2 ── склейки в паузах
    sys.path.insert(0, str(ROOT / "tools"))
    from lekciya_videoryad import pauzy
    ps, _ = pauzy(istok)
    cuts = sklejki(video)
    print(f"\n  2. СКЛЕЙКИ (снято с файла: {len(cuts)})")
    mimo = []
    for t in cuts:
        if not any(p[0] - 0.25 <= t <= p[1] + 0.25 for p in ps):
            blizh = min(((p[0] + p[1]) / 2 for p in ps), key=lambda c: abs(c - t))
            mimo.append((t, t - blizh))
    if mimo:
        print(f"     [ПРОВАЛ] мимо паузы: {len(mimo)} из {len(cuts)}")
        for t, d in mimo[:8]:
            print(f"        {int(t//60)}:{t%60:05.2f} — до ближайшей паузы {d:+.2f}с")
        ploho += 1
    else:
        print(f"     [OK] все {len(cuts)} склеек стоят в паузах записи")

    # 3 ── звук
    gi, gf = gromkost(istok), gromkost(video)
    li, lf = float(gi["input_lra"]), float(gf["input_lra"])
    print(f"\n  3. ЗВУК")
    print(f"     источник {gi['input_i']} LUFS, LRA {li:.2f}")
    print(f"     в файле  {gf['input_i']} LUFS, LRA {lf:.2f}, пик {gf['input_tp']} dBTP")
    if lf < li - 0.2:
        print(f"     [ПРОВАЛ] динамика съедена: LRA упал на {li - lf:.2f} LU")
        ploho += 1
    elif float(gf["input_tp"]) > -1.0:
        print(f"     [ПРОВАЛ] пик выше −1.0 dBTP"); ploho += 1
    else:
        print(f"     [OK] громкость поднята, LRA сохранён ({li:.2f} → {lf:.2f})")

    # 4 ── мёртвый кадр
    print(f"\n  4. ДЛИНА ПЛАНОВ")
    granicy = [0.0] + cuts + [df]
    dlinnye = [(granicy[i], granicy[i + 1] - granicy[i])
               for i in range(len(granicy) - 1) if granicy[i + 1] - granicy[i] > 50]
    if dlinnye:
        print(f"     [ПРОВАЛ] планов длиннее 50с: {len(dlinnye)}")
        for t, d in dlinnye[:6]:
            print(f"        {int(t//60)}:{t%60:05.2f} висит {d:.1f}с")
        ploho += 1
    else:
        sam = max(granicy[i + 1] - granicy[i] for i in range(len(granicy) - 1))
        print(f"     [OK] самый длинный план {sam:.1f}с, порог 50с")

    print(f"\n  {'ПРИЁМКА ПРОЙДЕНА' if not ploho else f'ПРОВАЛОВ: {ploho}'}")
    print(f"  Осталось глазами: контактный лист по КОНЦАМ проездов "
          f"(tools/list_lekcii.py).\n")
    return 1 if ploho else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
