#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ink_metrics.py — измерение ФАКТУРЫ рисунка: чем и как проведена линия.

Пропорции мы уже сверяем (compare_ref.py). Этот инструмент отвечает на другой
класс вопросов: какой «карандаш» у оригинала и насколько рваный у него край.
Всё считается из пикселей, без оценок на глаз.

Метрики:
  * stroke_px   — медианная ТОЛЩИНА линии в пикселях (и в долях ширины кадра,
                  чтобы сравнивать кадры разного разрешения);
  * stroke_var  — разброс толщины (0 = ровная «векторная» линия, выше = живая
                  линия с нажимом, как от кисти/карандаша);
  * roughness   — РВАНОСТЬ края: во сколько раз реальный контур длиннее своей
                  сглаженной версии. 1.0 = идеально гладкий вектор;
  * edge_soft   — мягкость края: доля полутоновых пикселей на границе
                  (0 = жёсткая двухтоновая заливка, выше = размытие/антиалиас);
  * tones       — сколько уровней яркости реально занято (двухтон или полутона);
  * contour_wobble — на сколько пикселей УЕЗЖАЕТ контур между соседними
                  рисунками (только для видео). Это и есть «боил» оригинала —
                  прямое целевое значение для нашего line-boil.

Использование:
    python3 tools/ink_metrics.py кадр.png
    python3 tools/ink_metrics.py ролик.mp4 --at 8        # + contour_wobble
    python3 tools/ink_metrics.py наш.mp4 --ref оригинал.mp4 --at 8
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

INK = 100        # порог «чернил»
PAPER = 190      # порог «бумаги»


def load_gray(path, at=None):
    p = Path(path)
    if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
        return np.asarray(Image.open(p).convert("L"), dtype=np.uint8)
    out = Path(tempfile.mkdtemp()) / "f.png"
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if at is not None:
        cmd += ["-ss", str(at)]
    cmd += ["-i", str(p), "-vframes", "1", str(out)]
    subprocess.run(cmd, check=True)
    return np.asarray(Image.open(out).convert("L"), dtype=np.uint8)


def run_lengths(row):
    """Длины непрерывных отрезков True в булевом ряду."""
    out, n = [], 0
    for v in row:
        if v:
            n += 1
        elif n:
            out.append(n); n = 0
    if n:
        out.append(n)
    return out


def stroke_widths(ink, max_w=60):
    """Толщины штрихов: длины чёрных отрезков по строкам и столбцам.

    Берём только «тонкие» отрезки (< max_w) — иначе в статистику попадут
    сплошные заливки тела, а нас интересует именно ЛИНИЯ.
    """
    runs = []
    h, w = ink.shape
    for y in range(0, h, 3):
        runs += [r for r in run_lengths(ink[y]) if 1 < r < max_w]
    for x in range(0, w, 3):
        runs += [r for r in run_lengths(ink[:, x]) if 1 < r < max_w]
    return np.array(runs) if runs else np.array([0])


def roughness(ink):
    """Рваность края: периметр контура / периметр его сглаженной версии."""
    e = np.zeros_like(ink)
    e[1:-1, 1:-1] = ink[1:-1, 1:-1] & (
        ~ink[:-2, 1:-1] | ~ink[2:, 1:-1] | ~ink[1:-1, :-2] | ~ink[1:-1, 2:]
    )
    per = e.sum()
    # сглаживаем маску боксом 5×5 и снова считаем периметр
    k = 5
    pad = np.pad(ink.astype(np.float32), k // 2, mode="edge")
    sm = np.zeros_like(ink, dtype=np.float32)
    for dy in range(k):
        for dx in range(k):
            sm += pad[dy:dy + ink.shape[0], dx:dx + ink.shape[1]]
    smooth = (sm / (k * k)) > 0.5
    es = np.zeros_like(smooth)
    es[1:-1, 1:-1] = smooth[1:-1, 1:-1] & (
        ~smooth[:-2, 1:-1] | ~smooth[2:, 1:-1] | ~smooth[1:-1, :-2] | ~smooth[1:-1, 2:]
    )
    per_s = max(es.sum(), 1)
    return per / per_s


def contour_wobble(path, at, window=4.0, step=2):
    """Насколько уезжает контур между соседними рисунками (боил оригинала).

    Считаем долю пикселей, поменявших класс (чернила↔бумага) от длины контура:
    это средний сдвиг края в пикселях.
    """
    d = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-t", str(window),
                    "-i", str(path), str(d / "f_%03d.png")], check=True)
    files = sorted(d.glob("f_*.png"))
    if len(files) < step + 1:
        return None
    vals = []
    prev = None
    # На двойках соседние кадры — ДУБЛИ (разница 0), поэтому сравниваем через
    # `step`: только там, где рисунок реально перерисован.
    files = files[::step]
    for f in files:
        g = np.asarray(Image.open(f).convert("L"), dtype=np.uint8)
        ink = g < INK
        if prev is not None:
            changed = np.logical_xor(ink, prev).sum()
            e = np.zeros_like(ink)
            e[1:-1, 1:-1] = ink[1:-1, 1:-1] & (
                ~ink[:-2, 1:-1] | ~ink[2:, 1:-1] | ~ink[1:-1, :-2] | ~ink[1:-1, 2:]
            )
            per = max(e.sum(), 1)
            vals.append(changed / per)
        prev = ink
    return float(np.median(vals)) if vals else None


def measure(path, at=None, label=""):
    g = load_gray(path, at)
    ink = g < INK
    m = {}
    sw = stroke_widths(ink)
    m["stroke_px"] = float(np.median(sw))
    m["stroke_var"] = float(np.std(sw) / max(np.median(sw), 1e-6))
    m["roughness"] = float(roughness(ink))
    edge = (g >= INK) & (g <= PAPER)
    m["edge_soft"] = float(edge.sum() / max(ink.sum(), 1))
    hist = np.histogram(g, bins=32, range=(0, 255))[0]
    m["tones"] = int((hist > g.size * 0.002).sum())
    if Path(path).suffix.lower() == ".mp4":
        wob = contour_wobble(path, at or 5)
        if wob is not None:
            m["contour_wobble"] = wob
    return m


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="наш кадр/ролик")
    ap.add_argument("--ref", help="кадр/ролик оригинала для сравнения")
    ap.add_argument("--at", type=float, default=None)
    ap.add_argument("--at-ref", type=float, default=None,
                    help="таймкод эталона, если план в другом месте ролика")
    a = ap.parse_args(argv)

    ours = measure(a.target, a.at)
    ref = measure(a.ref, a.at_ref if a.at_ref is not None else a.at) if a.ref else None

    names = {
        "stroke_px": "толщина линии, px",
        "stroke_var": "разброс толщины",
        "roughness": "рваность края",
        "edge_soft": "мягкость края",
        "tones": "число тонов",
        "contour_wobble": "дрожь контура, px",
    }
    if ref:
        print(f"\n  ФАКТУРА РИСУНКА\n  {'метрика':<20}{'наш':>9}{'оригинал':>11}{'расх.':>9}")
        for k, n in names.items():
            if k in ours and k in ref:
                o, r = ours[k], ref[k]
                d = abs(o - r) / max(abs(r), 1e-6) * 100
                print(f"  {n:<20}{o:>9.2f}{r:>11.2f}{d:>8.0f}%  {'OK' if d <= 25 else 'РАСХОЖДЕНИЕ'}")
    else:
        print(f"\n  ФАКТУРА: {a.target}")
        for k, n in names.items():
            if k in ours:
                print(f"  {n:<20}{ours[k]:>9.2f}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
