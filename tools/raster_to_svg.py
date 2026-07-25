#!/usr/bin/env python3
"""Обернуть растровую картинку (PNG/JPG) в SVG с встроенным <image> (data-URI).

Так фотореалистичный фон грузится через обычный путь движка (resvg рисует
встроенный растр) — БЕЗ доработки движка. Персонаж (векторная тушь) ложится
сверху → парадокс «рисованный герой в фотомире».

Использование:
    python3 tools/raster_to_svg.py in.png out.svg [W H]
Если W/H не заданы — берутся из картинки.
"""
import sys, base64, struct, pathlib


def png_size(data: bytes):
    # IHDR: width/height — big-endian u32 по смещению 16.
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    return None


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    data = pathlib.Path(src).read_bytes()
    ext = pathlib.Path(src).suffix.lower().lstrip(".")
    mime = "png" if ext == "png" else "jpeg"
    if len(sys.argv) >= 5:
        w, h = int(sys.argv[3]), int(sys.argv[4])
    else:
        sz = png_size(data)
        w, h = sz if sz else (1280, 720)
    b64 = base64.b64encode(data).decode()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
        f'  <image x="0" y="0" width="{w}" height="{h}" '
        f'preserveAspectRatio="xMidYMid slice" '
        f'xlink:href="data:image/{mime};base64,{b64}"/>\n'
        f"</svg>\n"
    )
    pathlib.Path(dst).write_text(svg)
    print(f"wrote {dst}  ({w}x{h}, {len(b64)//1024} KB base64)")


if __name__ == "__main__":
    main()
