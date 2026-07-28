#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
motion_ref.py — снять ФИЗИКУ ДВИЖЕНИЯ с подлинного ролика.

Копирка по одному кадру даёт форму (`trace_ref.py`). Копирка по
ПОСЛЕДОВАТЕЛЬНОСТИ кадров даёт то, что формой не берётся: на скольких кадрах
держится один рисунок, как разгоняется и тормозит фигура, перелетает ли она
цель и на сколько кадров подол запаздывает за корпусом. Это и есть «физика»,
которую иначе приходится подбирать на глаз.

Что считает:

  * hold        — сколько кадров держится ОДИН рисунок. Рисованная анимация
                  живёт на двойках-тройках; если у нас каждый кадр новый, глаз
                  читает это как компьютер, а не как руку;
  * speed       — профиль скорости центра масс: доля времени в разгоне, на
                  полке и в торможении. Ровная скорость = механика;
  * overshoot   — перелетает ли фигура конечную точку и возвращается ли.
                  Без перелёта движение «приклеенное»;
  * hem_lag     — на сколько кадров низ силуэта запаздывает за верхом.
                  Ткань не может двигаться одновременно с телом;
  * squash      — размах отношения ширины к высоте маски: живой рисунок
                  сжимается и растягивается на ударах.

Использование:
    python3 tools/motion_ref.py оригинал.mp4 --at 26 --window 6
    python3 tools/motion_ref.py наш.mp4 --at 12 --window 6 --ref оригинал.mp4 --at-ref 26
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


def frames(path, at, window, width=320):
    d = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-t", str(window),
                    "-i", str(path), "-vf", f"scale={width}:-2", str(d / "f_%04d.png")],
                   check=True)
    out = []
    for f in sorted(d.glob("f_*.png")):
        g = np.asarray(Image.open(f).convert("L"), dtype=np.float32)
        out.append(g)
    return out


def ink_mask(g):
    thr = (np.percentile(g, 1) + np.median(g)) / 2
    return g < thr


def analyse(fs, fps):
    n = len(fs)
    if n < 6:
        raise SystemExit("слишком короткий отрезок")

    # ── hold: соседние кадры почти идентичны => это ДУБЛЬ одного рисунка
    # Дубль отличается от нового рисунка на порядок, но не на ноль: видео
    # сжато, и даже точная копия кадра даёт шум кодека. Поэтому порог берём
    # от МЕДИАНЫ разниц, а не от максимума — максимум задаёт один сильный
    # взмах и топит все остальные переходы.
    diffs = np.array([np.abs(fs[i] - fs[i - 1]).mean() for i in range(1, n)])
    novel = diffs > np.median(diffs) * 1.6
    holds, run = [], 1
    for is_new in novel:
        if is_new:
            holds.append(run); run = 1
        else:
            run += 1
    holds.append(run)
    hold = float(np.median(holds)) if holds else 1.0

    masks = [ink_mask(g) for g in fs]
    cx, cy, asp, low = [], [], [], []
    for m in masks:
        ys, xs = np.where(m)
        if xs.size == 0:
            cx.append(np.nan); cy.append(np.nan); asp.append(np.nan); low.append(np.nan)
            continue
        cx.append(xs.mean()); cy.append(ys.mean())
        asp.append((xs.max() - xs.min() + 1) / max(ys.max() - ys.min() + 1, 1))
        cut = ys.min() + (ys.max() - ys.min()) * 0.72     # нижняя треть силуэта
        lo = xs[ys >= cut]
        low.append(lo.mean() if lo.size else np.nan)
    cx = np.array(cx); low = np.array(low); asp = np.array(asp)

    # ── speed: профиль скорости центра масс
    v = np.abs(np.diff(cx))
    v = v[~np.isnan(v)]
    if v.size < 4:
        return {"hold": hold, "speed": None, "overshoot": None,
                "hem_lag": None, "squash": None}
    vmax = v.max() if v.max() > 0 else 1.0
    accel = float((v > vmax * 0.25).mean())          # доля времени в движении
    # ── overshoot: заходит ли центр за финальное положение и возвращается
    fin = np.nanmean(cx[-3:])
    beyond = np.nanmax(np.abs(cx - fin))
    travel = np.nanmax(cx) - np.nanmin(cx)
    overshoot = float(0.0 if travel < 1e-6 else
                      max(0.0, (beyond - abs(np.nanmean(cx[:3]) - fin)) / travel))

    # ── hem_lag: корреляция низа силуэта с верхом при сдвиге на k кадров
    top = cx - np.nanmean(cx)
    bot = low - np.nanmean(low)
    best_k, best_r = 0, -2.0
    for k in range(0, 7):
        a = top[:len(top) - k] if k else top
        b = bot[k:]
        ok = ~np.isnan(a) & ~np.isnan(b)
        if ok.sum() < 5:
            continue
        r = float(np.corrcoef(a[ok], b[ok])[0, 1])
        if r > best_r:
            best_r, best_k = r, k
    squash = float(np.nanmax(asp) - np.nanmin(asp))
    return {"hold": hold, "speed": accel, "overshoot": overshoot,
            "hem_lag": best_k, "squash": squash, "fps": fps}


NAMES = {
    "hold": ("кадров на один рисунок", "двойки-тройки = рука, единицы = компьютер"),
    "speed": ("доля времени в движении", "1.0 = едет всегда, ровно и механически"),
    "overshoot": ("перелёт цели", "0 = движение приклеенное, без инерции"),
    "hem_lag": ("запаздывание низа, кадров", "0 = ткань движется как доска"),
    "squash": ("размах сжатия силуэта", "0 = жёсткая фигура без удара"),
}


def probe(path, at, window):
    fps = 24.0
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v",
                              "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0",
                              str(path)], capture_output=True, text=True).stdout.strip()
        a, b = out.split("/")[:2]
        fps = float(a) / float(b)
    except Exception:
        pass
    return analyse(frames(path, at, window), fps)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--at", type=float, required=True)
    ap.add_argument("--window", type=float, default=6.0)
    ap.add_argument("--ref")
    ap.add_argument("--at-ref", type=float)
    a = ap.parse_args(argv)

    ours = probe(a.video, a.at, a.window)
    ref = probe(a.ref, a.at_ref if a.at_ref is not None else a.at, a.window) if a.ref else None

    hdr = f"  {'величина':<30}{'наш':>9}"
    if ref:
        hdr += f"{'оригинал':>11}"
    print(f"\n  ФИЗИКА ДВИЖЕНИЯ\n{hdr}")
    for k, (name, hint) in NAMES.items():
        o = ours.get(k)
        line = f"  {name:<30}{'—' if o is None else f'{o:>9.2f}'}"
        if ref:
            r = ref.get(k)
            line += f"{'—' if r is None else f'{r:>11.2f}'}"
        print(line)
        print(f"  {'':<30}{hint}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
