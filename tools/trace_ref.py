#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trace_ref.py — «копирка»: обводит подлинный кадр Мистера Фримена в точные
вектор-части рига (potrace), вместо ручного подбора путей на глаз.

Метод (наложение/обводка). Маска и фон почти одной яркости — различает
только ЧЁРНАЯ ТУШЬ, поэтому работаем по ней:
  * dark = тёмная тушь (порог)
  * ЯЙЦО-МАСКА = область, до которой светлый фон НЕ дотягивается от границы
    кропа лица (внутренность замкнутой обводки-яйца)
  * ГЛАЗА/РОТ = тёмные пятна, ЗАМКНУТЫЕ внутри яйца (не связаны с границей)
Каждый регион: crop→resize битмапа под размер части→potrace→группу вставляем
КАК ЕСТЬ (её transform уже в пиксельных координатах ресайза), только
перекрашиваем. Никакого ручного пересчёта путей — значит без багов.

Использование:
    python3 tools/trace_ref.py <ref.jpg> --out-dir <dir> [--head-box L T R B]
      [--dark 100] [--scale 0.5]
"""
import argparse, subprocess, sys, re, tempfile, os
from collections import deque
import numpy as np
from PIL import Image


def dilate(m, r=1):
    out = m.copy()
    for _ in range(r):
        s = out.copy()
        s[1:, :] |= out[:-1, :]; s[:-1, :] |= out[1:, :]
        s[:, 1:] |= out[:, :-1]; s[:, :-1] |= out[:, 1:]
        out = s
    return out


def erode(m, r=1):
    return ~dilate(~m, r)


def fill_from_border(passable):
    H, W = passable.shape
    seen = np.zeros_like(passable, bool)
    dq = deque()
    def push(y, x):
        if passable[y, x] and not seen[y, x]:
            seen[y, x] = True; dq.append((y, x))
    for x in range(W):
        push(0, x); push(H - 1, x)
    for y in range(H):
        push(y, 0); push(y, W - 1)
    while dq:
        y, x = dq.popleft()
        if y > 0: push(y - 1, x)
        if y < H - 1: push(y + 1, x)
        if x > 0: push(y, x - 1)
        if x < W - 1: push(y, x + 1)
    return seen


def potrace_group(mask_bool, turd=2):
    """Битмап (True=тушь) → строка '<g ...>…</g>' от potrace в пикс-координатах
    самого битмапа (WxH). Плюс возвращает (W, H)."""
    H, W = mask_bool.shape
    bits = np.packbits(mask_bool.astype(np.uint8), axis=1)
    with tempfile.TemporaryDirectory() as td:
        pbm = os.path.join(td, "in.pbm"); svg = os.path.join(td, "out.svg")
        with open(pbm, "wb") as f:
            f.write(f"P4\n{W} {H}\n".encode()); f.write(bits.tobytes())
        subprocess.run(["potrace", "-s", "-t", str(turd), "-a", "1.2",
                        "-o", svg, pbm], check=True)
        s = open(svg).read()
    m = re.search(r'(<g\b.*?</g>)', s, re.S)
    return (m.group(1) if m else ""), (W, H)


def trace_region(mask_bool, target_vb, fill, stroke=None, sw=0, ink=False,
                 turd=2, margin=0.06):
    """Регион → SVG-часть в ФИКСИРОВАННОМ viewBox target_vb=(TW,TH), фигура
    вписана по аспекту и отцентрирована (pivot'ы рига остаются валидны).
    Обводка ставится на саму группу potrace (в её 10x-системе)."""
    TW, TH = target_vb
    ys, xs = np.where(mask_bool)
    if len(ys) == 0:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sub = mask_bool[y0:y1, x0:x1]
    h, w = sub.shape
    avail_w, avail_h = TW * (1 - 2*margin), TH * (1 - 2*margin)
    sc = min(avail_w / w, avail_h / h)
    rw, rh = max(2, round(w * sc)), max(2, round(h * sc))
    big = np.array(Image.fromarray((sub * 255).astype(np.uint8))
                   .resize((rw, rh), Image.NEAREST)) > 127
    g, (gw, gh) = potrace_group(big, turd=turd)
    g = re.sub(r'fill="#000000"', f'fill="{fill}"', g)
    if stroke:
        # potrace-группа масштабирована на 0.1 → stroke-width в её системе = sw*10
        g = g.replace('stroke="none"',
                      f'stroke="{stroke}" stroke-width="{sw*10:.1f}" '
                      f'stroke-linejoin="round"')
    offx, offy = (TW - gw) / 2, (TH - gh) / 2
    placed = f'<g transform="translate({offx:.2f},{offy:.2f})">{g}</g>'
    if ink:
        defs = ('<defs><filter id="ink" x="-25%" y="-25%" width="150%" height="150%">'
                '<feTurbulence type="fractalNoise" baseFrequency="0.014" numOctaves="1" '
                'seed="4" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" '
                'scale="2.2" xChannelSelector="R" yChannelSelector="G"/></filter></defs>')
        inner = f'{defs}<g filter="url(#ink)">{placed}</g>'
    else:
        inner = placed
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TW} {TH}" '
           f'width="{TW}" height="{TH}">\n{inner}\n</svg>\n')
    return svg


def label_components(mask):
    H, W = mask.shape
    lab = np.zeros((H, W), np.int32); cur = 0; out = []
    for sy in range(H):
        for sx in range(W):
            if mask[sy, sx] and lab[sy, sx] == 0:
                cur += 1; dq = deque([(sy, sx)]); lab[sy, sx] = cur; pts = []
                while dq:
                    y, x = dq.popleft(); pts.append((y, x))
                    for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny, nx = y+dy, x+dx
                        if 0<=ny<H and 0<=nx<W and mask[ny,nx] and lab[ny,nx]==0:
                            lab[ny,nx]=cur; dq.append((ny,nx))
                ys = np.array([p[0] for p in pts]); xs = np.array([p[1] for p in pts])
                out.append((cur, ys, xs))
    return lab, out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("ref"); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--head-box", nargs=4, type=int, default=None)
    ap.add_argument("--dark", type=int, default=100)
    ap.add_argument("--scale", type=float, default=0.5)
    a = ap.parse_args(argv)

    gray = np.array(Image.open(a.ref).convert("L"))
    if a.scale != 1.0:
        H0, W0 = gray.shape
        gray = np.array(Image.fromarray(gray).resize(
            (int(W0 * a.scale), int(H0 * a.scale)), Image.LANCZOS))
    H, W = gray.shape
    if a.head_box:
        L, T, R, B = (int(round(v * a.scale)) for v in a.head_box)
    else:
        L, T, R, B = int(W*0.32), int(H*0.03), int(W*0.68), int(H*0.48)
    crop = gray[T:B, L:R]
    dark = crop < a.dark
    ch, cw = crop.shape

    # Обводка-яйцо может быть разомкнута (тонкий/светлый подбородок) → заливка
    # утекает. Дилатируем тушь на пару px, ЧТОБЫ ЗАМКНУТЬ контур, считаем
    # яйцо, затем эродируем обратно к исходной кромке.
    darkD = dilate(dark, 2)
    egg = erode(~fill_from_border(~darkD), 2)   # цельная маска-яйцо
    enclosed = dark & ~fill_from_border(dark)   # глаза+рот (замкнутые тёмные)

    os.makedirs(a.out_dir, exist_ok=True)

    head_svg = trace_region(egg, (160, 200), "#eef1ec", stroke="#0e0e0e", sw=4.5,
                            ink=True, turd=8)
    if head_svg:
        open(os.path.join(a.out_dir, "head_traced.svg"), "w").write(head_svg)

    lab, comps = label_components(enclosed)
    feats = []
    for c, ys, xs in comps:
        area = len(xs)
        if area < 0.001 * ch * cw:
            continue
        feats.append(dict(lab=c, cx=xs.mean(), cy=ys.mean(),
                          w=xs.max()-xs.min()+1, h=ys.max()-ys.min()+1, area=area))
    feats.sort(key=lambda f: -f["area"])
    eyes = sorted([f for f in feats if f["h"] >= f["w"]*0.75][:2], key=lambda f: f["cx"])
    mouth = next((f for f in feats if f not in eyes and f["w"] > f["h"]
                  and f["cy"] > ch*0.4), None)

    for f, nm in zip(eyes, ("eye_left_traced.svg", "eye_right_traced.svg")):
        svg = trace_region(lab == f["lab"], (48, 60), "#0e0e0e", turd=2)
        if svg: open(os.path.join(a.out_dir, nm), "w").write(svg)
    if mouth:
        svg = trace_region(lab == mouth["lab"], (44, 30), "#0e0e0e", turd=2)
        if svg: open(os.path.join(a.out_dir, "mouth_smile_traced.svg"), "w").write(svg)

    print(f"OK → {a.out_dir}  (eyes={len(eyes)}, mouth={'yes' if mouth else 'no'})")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
