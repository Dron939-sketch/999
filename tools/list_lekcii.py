#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_lekcii.py — контактный лист видеоряда лекции ПО КОНЦАМ ПРОЕЗДОВ.

Обычный контактный лист берёт по кадру на сцену — как правило, из начала. Для
лекции это бесполезно: в начале сцены камера ещё стоит в центре, и весь брак
проездов невидим по построению. Именно так пилот прошёл проверку глазами
зелёным, имея на каждом ходе камеры серую полосу голой подложки (реестр §XLI).

Поэтому кадр берётся за секунду ДО конца плана — там, где камера уехала дальше
всего, и если подложка вылезет, то вылезет здесь.

    python3 tools/list_lekcii.py videos/lekciya-koleya-1.mp4
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--kolonok", type=int, default=4)
    a = ap.parse_args(argv)

    sys.path.insert(0, str(ROOT / "tools"))
    from lekciya_videoryad import razlozhit
    plany, _, _ = razlozhit()

    from PIL import Image, ImageDraw
    tw, th = 320, 180
    rows = (len(plany) + a.kolonok - 1) // a.kolonok
    sheet = Image.new("RGB", (a.kolonok * tw, rows * (th + 20)), (255, 255, 255))
    d = ImageDraw.Draw(sheet)

    tmp = Path("/tmp/_list_lekcii.png")
    for i, p in enumerate(plany):
        t = max(0.2, p["do"] - 1.0)          # конец проезда, до склейки
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}",
                        "-i", str(ROOT / a.video), "-frames:v", "1", str(tmp)],
                       check=True)
        x, y = (i % a.kolonok) * tw, (i // a.kolonok) * (th + 20)
        sheet.paste(Image.open(tmp).resize((tw - 4, th - 4)), (x + 2, y + 2))
        imya = "ФРИМЕН" if p["vid"] == "shov" else p["kadr"].replace("lek1-", "")
        d.text((x + 4, y + th + 3),
               f'{int(t//60)}:{t%60:04.1f} {imya}', fill=(0, 0, 0))

    out = a.out or "/tmp/kontakt-lekcii.png"
    sheet.save(out)
    print(f"  контактный лист по КОНЦАМ проездов: {out} ({len(plany)} планов)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
