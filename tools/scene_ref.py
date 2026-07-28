#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scene_ref.py — инвентаризация КАДРА оригинала: что в нём есть кроме персонажа.

Персонажем занимаются face_ref/proportions. Но у Фримена кадр почти никогда
не пустой: земля со штриховкой, линия горизонта, градиент неба, частицы,
цветовой акцент в чёрно-белом, массовка из одинаковых фигурок, знаки на полу.
Наши сцены при этом часто стоят на голом однотонном поле — персонаж хорош,
а кадр пуст.

Этот инструмент считает по кадрам, НАСКОЛЬКО кадр населён, и в каких долях
кадров встречается каждый признак. Величина принимается только по развёртке
на десятках кадров — одиночный кадр уже дважды уводил студию не туда.

Признаки:
  * horizon    — есть ли выраженная горизонтальная граница яркости (линия
                 земли). Считаем по резкому скачку средней яркости строк;
  * ground_tex — фактура нижней трети: доля «краевых» пикселей. Гладкая
                 заливка даёт около нуля, штриховка-паутина — заметную долю;
  * sky_grad   — перепад яркости по вертикали в верхней половине (градиент
                 неба против плоской заливки);
  * particles  — число мелких изолированных пятен, контрастных фону (снег,
                 пепел, стая);
  * color      — доля пикселей с заметной насыщенностью (цветовой акцент
                 в монохромном кадре — фирменный приём);
  * ink_share  — доля чернил в кадре (насколько кадр вообще заполнен).

Использование:
    python3 tools/scene_ref.py оригинал.mp4 --sweep 2 52 1.0
    python3 tools/scene_ref.py наш.mp4 --sweep 1 40 1.0
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


def load_rgb(path, at=None):
    p = Path(path)
    if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
        return np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)
    out = Path(tempfile.mkdtemp()) / "f.png"
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if at is not None:
        cmd += ["-ss", str(at)]
    cmd += ["-i", str(p), "-vframes", "1", str(out)]
    subprocess.run(cmd, check=True)
    return np.asarray(Image.open(out).convert("RGB"), dtype=np.int16)


def edges(g):
    e = np.zeros_like(g, dtype=np.float32)
    e[1:-1, 1:-1] = (np.abs(g[1:-1, 2:] - g[1:-1, :-2])
                     + np.abs(g[2:, 1:-1] - g[:-2, 1:-1]))
    return e


def measure(rgb):
    g = rgb.mean(2).astype(np.float32)
    h, w = g.shape
    rows = g.mean(1)
    # горизонт: самый резкий скачок средней яркости строк в средней трети кадра
    band = rows[int(h * 0.25):int(h * 0.85)]
    jump = float(np.abs(np.diff(band)).max()) if band.size > 1 else 0.0
    # фактура земли: доля «краевых» пикселей в нижней трети
    low = edges(g[int(h * 0.66):])
    ground_tex = float((low > 22).mean())
    # градиент неба: перепад средней яркости по верхней половине
    top = rows[:int(h * 0.5)]
    sky_grad = float(top.max() - top.min()) if top.size else 0.0
    # частицы: мелкие пятна, контрастные локальному фону
    small = g[::2, ::2]
    med = float(np.median(small))
    spot = np.abs(small - med) > 45
    # считаем «зёрна» грубо: изолированные пиксели после прореживания
    particles = int(spot.sum())
    # цвет: максимальный разброс каналов
    sat = (rgb.max(2) - rgb.min(2))
    color = float((sat > 30).mean())
    ink_share = float((g < 90).mean())
    return {"horizon": jump, "ground_tex": ground_tex, "sky_grad": sky_grad,
            "particles": particles, "color": color, "ink_share": ink_share}


NAMES = {
    "horizon": "горизонт (скачок яркости)",
    "ground_tex": "фактура земли, доля",
    "sky_grad": "градиент неба",
    "particles": "частиц (пятен)",
    "color": "цветной акцент, доля",
    "ink_share": "заполненность чернилами",
}
# порог «признак присутствует» — подобран так, чтобы пустое однотонное поле
# не считалось населённым кадром
PRESENT = {"horizon": 6.0, "ground_tex": 0.02, "sky_grad": 12.0,
           "particles": 400, "color": 0.005, "ink_share": 0.04}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--sweep", nargs=3, type=float, required=True,
                    metavar=("T0", "T1", "STEP"))
    a = ap.parse_args(argv)

    t0, t1, st = a.sweep
    rows, t = [], t0
    while t <= t1:
        try:
            rows.append(measure(load_rgb(a.video, t)))
        except Exception:
            pass
        t += st
    if not rows:
        raise SystemExit("не удалось прочитать ни одного кадра")

    print(f"\n  ИНВЕНТАРЬ КАДРА: {Path(a.video).name}  ({len(rows)} кадров)")
    print(f"  {'признак':<28}{'медиана':>10}{'есть в % кадров':>18}")
    for k, name in NAMES.items():
        v = np.array([r[k] for r in rows], dtype=float)
        share = 100.0 * (v > PRESENT[k]).mean()
        print(f"  {name:<28}{np.median(v):>10.3f}{share:>17.0f}%")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
