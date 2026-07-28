#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_ref.py — машинный компаратор «наш кадр ↔ кадр оригинала».

Зачем: взгляд (человека или vision-модели) хорошо ловит «что-то не так», но
плохо даёт числа. Все самые ценные находки этой сессии пришли от замеров:
пропорция маски (0.61 у оригинала против 1.25 у нас), дёрганье (4.39 → 2.04),
разрыв кисти (offset 114 против 102). Этот инструмент считает такие метрики
сам — и говорит, где расхождение.

Метрики (все — безразмерные, не зависят от крупности плана):
  * mask_wh      — W/H белой маски лица (форма головы);
  * mask_share   — доля маски в силуэте (насколько голова крупная);
  * ink_share    — доля «чернил» в кадре (плотность силуэта);
  * contour      — относительная толщина контура маски (доля краевых пикселей);
  * jitter       — средняя покадровая разница (только для видео).

ВАЖНО про сопоставимость кадров: метрики плотности/контура сравнивают КАДР
целиком, поэтому берите планы схожей крупности и с похожим фоном. Форма маски
(mask_wh) — самая устойчивая метрика, она не зависит ни от крупности, ни от
фона, если маска отделяется от фона по яркости (снимайте на тёмном поле).

Использование:
    # кадр против кадра
    python3 tools/compare_ref.py --ours our.png --ref orig.png
    # видео против видео (добавит jitter)
    python3 tools/compare_ref.py --ours our.mp4 --ref orig.mp4 --at 8 --window 6
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

WHITE = 190          # порог «белого» (маска лица)
DARK = 70            # порог «чернил» (силуэт)


def frame_from(path, at=None):
    """PNG отдаём как есть; из видео вынимаем кадр на секунде `at`."""
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


def biggest_blob_bbox(mask, step=2):
    """Габариты крупнейшей связной области (4-связность, с шагом для скорости)."""
    from collections import deque
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best = (0, None)
    for y in range(0, h, step):
        for x in range(0, w, step):
            if not mask[y, x] or seen[y, x]:
                continue
            q = deque([(y, x)]); seen[y, x] = True
            xs, ys = [x], [y]
            while q:
                cy, cx = q.popleft()
                for dy, dx in ((step, 0), (-step, 0), (0, step), (0, -step)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx)); xs.append(nx); ys.append(ny)
            if len(xs) > best[0]:
                best = (len(xs), (min(xs), max(xs), min(ys), max(ys)))
    return best


def metrics(gray, label):
    white = gray > WHITE
    ink = gray < DARK
    size, bbox = biggest_blob_bbox(white)
    m = {"label": label}
    if bbox:
        x0, x1, y0, y1 = bbox
        w, h = max(x1 - x0, 1), max(y1 - y0, 1)
        m["mask_wh"] = w / h
        m["mask_share"] = size * 4 / max(ink.sum(), 1)
    m["ink_share"] = ink.mean()
    # контур: доля пикселей, у которых сосед другого класса (грубая оценка
    # «жирности» линии относительно площади фигуры)
    edge = np.zeros_like(ink)
    edge[1:-1, 1:-1] = ink[1:-1, 1:-1] & (
        ~ink[:-2, 1:-1] | ~ink[2:, 1:-1] | ~ink[1:-1, :-2] | ~ink[1:-1, 2:]
    )
    m["contour"] = edge.sum() / max(ink.sum(), 1)
    return m


def jitter(path, at, window):
    """Средняя покадровая разница — «дрожь» картинки."""
    d = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-t", str(window),
                    "-i", str(path), "-vf", "scale=320:180", str(d / "f_%03d.png")],
                   check=True)
    files = sorted(d.glob("f_*.png"))
    if len(files) < 2:
        return None
    arr = [np.asarray(Image.open(f).convert("L"), dtype=np.float32) for f in files]
    return float(np.mean([np.mean(np.abs(arr[i] - arr[i - 1])) for i in range(1, len(arr))]))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True, help="наш кадр (png) или ролик (mp4)")
    ap.add_argument("--ref", required=True, help="кадр/ролик оригинала")
    ap.add_argument("--at", type=float, default=None, help="секунда кадра (для видео)")
    ap.add_argument("--window", type=float, default=6.0, help="окно для замера дрожи")
    a = ap.parse_args(argv)

    ours = metrics(frame_from(a.ours, a.at), "НАШ")
    ref = metrics(frame_from(a.ref, a.at), "ОРИГИНАЛ")

    print("\n  СРАВНЕНИЕ С ОРИГИНАЛОМ")
    print(f"  {'метрика':<14}{'наш':>10}{'оригинал':>12}{'расхождение':>14}")
    for key, name, tol in (
        ("mask_wh", "форма маски", 0.10),
        ("mask_share", "голова/силуэт", 0.25),
        ("ink_share", "плотность", 0.30),
        ("contour", "толщина линии", 0.30),
    ):
        if key not in ours or key not in ref:
            continue
        o, r = ours[key], ref[key]
        rel = abs(o - r) / max(abs(r), 1e-6)
        flag = "OK" if rel <= tol else "РАСХОЖДЕНИЕ"
        print(f"  {name:<14}{o:>10.3f}{r:>12.3f}{rel*100:>12.0f}%  {flag}")

    if Path(a.ours).suffix.lower() == ".mp4" and Path(a.ref).suffix.lower() == ".mp4":
        jo = jitter(a.ours, a.at or 5, a.window)
        jr = jitter(a.ref, a.at or 5, a.window)
        if jo and jr:
            print(f"  {'дрожь кадра':<14}{jo:>10.2f}{jr:>12.2f}"
                  f"{abs(jo-jr)/jr*100:>12.0f}%")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
