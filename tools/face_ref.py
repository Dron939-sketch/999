#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
face_ref.py — сверка ЛИЦА с оригиналом: форма маски, глаза, рот.

Зачем отдельный инструмент. `proportions.py` меряет габариты фигуры, и по ним
можно быть «в допуске», оставаясь непохожим: узнают персонажа по ЛИЦУ, а не по
отношению роста к ширине торса. Именно здесь и жил разрыв «цифры сходятся —
сходства не видно»: габарит маски совпадал, а внутри неё контур съедал пятую
часть ширины, глаза были узкими щелями вместо круглых пятен, рта не было.

Что считает (всё — в долях ширины БЕЛОГО ЯДРА маски, чтобы не зависеть от
плана и разрешения):
  * ядро H/W        — форма самой маски (белое пятно без чёрной обводки);
  * контур/ядро     — во сколько маска «одета» в обводку. Толстая обводка
                      превращает лицо в шлем с прорезью;
  * глаза           — ширина/высота и h/w каждого: у оригинала глаз почти
                      КРУГЛЫЙ (h/w ≈ 1.2–1.4), не «капля»;
  * позиции         — центры глаз и рта в % от габарита маски;
  * рот             — есть ли он вообще и какой ширины.

Использование:
    python3 tools/face_ref.py наш_кадр.png --ref кадр_оригинала.png
    python3 tools/face_ref.py наш_кадр.png --ref орig.mp4 --at-ref 14
    ... --side-by-side out.png     # картинка «оригинал | наш» в один рост
"""

import argparse
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

WHITE = 200
INK = 90


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


def blobs(mask, min_frac):
    """Связные компоненты крупнее min_frac от площади кадра."""
    lab = np.zeros(mask.shape, np.int32)
    out, cur = [], 0
    h, w = mask.shape
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or lab[sy, sx]:
                continue
            cur += 1
            q = deque([(sy, sx)])
            lab[sy, sx] = cur
            pts = []
            while q:
                y, x = q.popleft()
                pts.append((y, x))
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = cur
                        q.append((ny, nx))
            if len(pts) > mask.size * min_frac:
                out.append(np.array(pts))
    return out


def find_face(g):
    """Белое ядро маски: крупнейшее белое пятно, не касающееся края кадра."""
    h, w = g.shape
    cands = [
        b for b in blobs(g > WHITE, 0.002)
        if b[:, 0].min() > 0 and b[:, 1].min() > 0
        and b[:, 0].max() < h - 1 and b[:, 1].max() < w - 1
    ]
    if not cands:
        return None
    b = max(cands, key=len)
    return b[:, 0].min(), b[:, 0].max(), b[:, 1].min(), b[:, 1].max()


def ring_thickness(g, box):
    """Толщина обводки: от края белого ядра наружу, пока идут чернила.

    Меряем по ВЕРХУ маски — сбоку и снизу к обводке примыкает чёрное тело,
    и замер убегает в плащ.
    """
    y0, _, x0, x1 = box
    cx = (x0 + x1) // 2
    n, y = 0, y0 - 1
    while y >= 0 and g[y, cx] < INK:
        n += 1
        y -= 1
    return n


def features(g, box):
    """Глаза и рот — тёмные пятна внутри габарита маски, слева направо."""
    y0, y1, x0, x1 = box
    W, H = x1 - x0 + 1, y1 - y0 + 1
    inner = g[y0:y1 + 1, x0:x1 + 1] < INK
    # обводка входит в габарит углами — отбрасываем всё, что липнет к рамке
    out = []
    for b in blobs(inner, 0.004):
        by, bx = b[:, 0], b[:, 1]
        if by.min() <= 1 or bx.min() <= 1 or by.max() >= H - 2 or bx.max() >= W - 2:
            continue
        bw, bh = bx.max() - bx.min() + 1, by.max() - by.min() + 1
        out.append({
            "w": 100 * bw / W, "h": 100 * bh / H, "hw": bh / bw,
            "cx": 100 * bx.mean() / W, "cy": 100 * by.mean() / H,
        })
    return sorted(out, key=lambda f: f["cx"])


def report(g, name):
    box = find_face(g)
    if box is None:
        raise SystemExit(f"{name}: белого ядра маски не нашёл")
    y0, y1, x0, x1 = box
    W, H = x1 - x0 + 1, y1 - y0 + 1
    ring = ring_thickness(g, box)
    print(f"\n  {name}")
    print(f"    ядро маски {W}×{H}px, H/W = {H/W:.2f}")
    print(f"    обводка {ring}px = {100*ring/W:.0f}% ширины маски")
    for f in features(g, box):
        print(f"    пятно {f['w']:.0f}%×{f['h']:.0f}% маски, h/w={f['hw']:.2f}, "
              f"центр ({f['cx']:.0f}%, {f['cy']:.0f}%)")
    return box


def crop_face(g, box, margin=0.22):
    y0, y1, x0, x1 = box
    m = int(max(y1 - y0, x1 - x0) * margin)
    return Image.fromarray(g[max(y0 - m, 0):y1 + m, max(x0 - m, 0):x1 + m])


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--ref")
    ap.add_argument("--at", type=float)
    ap.add_argument("--at-ref", type=float)
    ap.add_argument("--side-by-side", help="куда положить картинку «оригинал | наш»")
    a = ap.parse_args(argv)

    ours = load_gray(a.target, a.at)
    box_o = report(ours, f"НАШ  {Path(a.target).name}")
    if a.ref:
        ref = load_gray(a.ref, a.at_ref if a.at_ref is not None else a.at)
        box_r = report(ref, f"ОРИГИНАЛ  {Path(a.ref).name}")
        if a.side_by_side:
            H = 480
            imgs = []
            for g, b in ((ref, box_r), (ours, box_o)):
                im = crop_face(g, b)
                imgs.append(im.resize((int(im.width * H / im.height), H), Image.LANCZOS))
            gap = 40
            out = Image.new("L", (sum(i.width for i in imgs) + gap * 3, H + gap * 2), 255)
            x = gap
            for im in imgs:
                out.paste(im, (x, gap))
                x += im.width + gap
            out.save(a.side_by_side)
            print(f"\n  сравнение: {a.side_by_side} (слева оригинал, справа наш)")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
