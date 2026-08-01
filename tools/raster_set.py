#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
raster_set.py — ГОТОВАЯ КАРТИНКА СТАНОВИТСЯ ЛОКАЦИЕЙ.

Студия присылает сгенерированные фоны в PNG, а движок грузит только SVG:
`import set` разбирает файл через usvg и на растре падает с «provided data has
not an UTF-8 encoding». Обходной путь известен и надёжен — растр кладётся
ВНУТРЬ svg элементом `<image>` с data-URI. usvg такой файл разбирает, resvg
рисует, и локация ведёт себя как любая другая: кадрируется, принимает тень,
слушается карты поверхностей.

ЧТО ДЕЛАЕТ ИНСТРУМЕНТ, кроме обёртки:
  · КАДРИРУЕТ ПОД 16:9. Генератор отдаёт квадрат; полоса берётся по центру со
    сдвигом вниз (пола в кадре нужно больше, чем неба). Прижимать к нижней
    кромке нельзя — срезает то, ради чего локацию и рисовали: крону дерева,
    верх камня, окно в комнате;
  · СНИМАЕТ НАРИСОВАННУЮ РАМКУ. Генератор часто обводит кадр — в ролике такая
    рамка читается «картина на стене», а не локация. Ищется по строкам и
    столбцам, где тёмного больше 60% длины;
  · КВАНТУЕТ ПАЛИТРУ. Рисунок в две краски держится в 12 цветах, и файл
    худеет втрое — в svg он поедет в base64, где каждый байт становится
    четырьмя.

ЧЕГО ИНСТРУМЕНТ НЕ ДЕЛАЕТ: не пишет `*.surfaces.json`. Линию пола он снять не
может — автомат ищет, где начинается сплошное светлое поле, а у комнаты стена
и пол одинаково светлые, и порог срабатывает у самой кромки. Карта ставится
руками по рисунку, и без неё `place ... on floor` молча не работает.

Использование:
    python3 tools/raster_set.py вход.png examples/assets/sets/имя.svg
    python3 tools/raster_set.py вход.png ... --no-crop   # кадр уже 16:9
"""

import argparse
import base64
import io
import sys
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    sys.exit("нужны Pillow и numpy")


def strip_frame(im, thr=110, share=0.6):
    """Срезать нарисованную рамку по краю кадра."""
    a = np.array(im.convert("L"))
    h, w = a.shape
    dark = a < thr
    rows = [i for i, v in enumerate(dark.sum(1)) if v > share * w]
    cols = [i for i, v in enumerate(dark.sum(0)) if v > share * h]
    top = max([r for r in rows if r < h * 0.12], default=-1) + 1
    bot = min([r for r in rows if r > h * 0.88], default=h)
    left = max([c for c in cols if c < w * 0.12], default=-1) + 1
    right = min([c for c in cols if c > w * 0.88], default=w)
    return im.crop((left, top, right, bot))


def to_169(im, drop=0.55, fit="width"):
    """Кадр 16:9 из квадрата. Два разных способа, и выбор между ними — смысловой.

    `fit="width"` — берём горизонтальную полосу во всю ширину. Годится, когда
    композиция лежит в середине по высоте: комната, поле, склон.

    `fit="height"` — вписываем ВСЮ высоту и режем бока. Нужен, когда картинка
    построена по вертикали и её края несут смысл: у ночной кухни сверху лампа,
    снизу пол, и полоса во всю ширину выбрасывает либо источник света, либо
    место, где стоит персонаж. Из квадрата 16:9 забирает 44% высоты — это
    слишком много, чтобы решать вслепую.
    """
    w, h = im.size
    if fit == "height":
        tw = int(h * 16 / 9)
        if tw <= w:
            return im.crop(((w - tw) // 2, 0, (w - tw) // 2 + tw, h))
        # картинка у́же нужного — добираем полосой сверху/снизу, иначе никак
        th = int(w * 9 / 16)
        top = int((h - th) * drop)
        return im.crop((0, top, w, top + th))
    th = int(w * 9 / 16)
    if th <= h:
        top = int((h - th) * drop)
        return im.crop((0, top, w, top + th))
    tw = int(h * 16 / 9)
    return im.crop(((w - tw) // 2, 0, (w - tw) // 2 + tw, h))


def wrap(png_bytes, w=1280, h=720, note=""):
    b64 = base64.b64encode(png_bytes).decode()
    head = f"  <!-- {note} -->\n" if note else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n{head}'
            f'  <image x="0" y="0" width="{w}" height="{h}" '
            f'xlink:href="data:image/png;base64,{b64}"/>\n</svg>\n')


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--no-crop", action="store_true")
    ap.add_argument("--no-frame-strip", action="store_true")
    ap.add_argument("--drop", type=float, default=0.55,
                    help="доля запаса по высоте, уходящая наверх (0 — прижать к верху)")
    ap.add_argument("--fit", choices=("width", "height"), default="width",
                    help="width — полоса во всю ширину; height — вписать всю высоту, срезать бока")
    ap.add_argument("--colors", type=int, default=12)
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)

    im = Image.open(a.src).convert("RGB")
    if not a.no_frame_strip:
        im = strip_frame(im)
    if not a.no_crop:
        im = to_169(im, a.drop, a.fit)
    im = im.resize((1280, 720), Image.LANCZOS)
    q = im.quantize(colors=a.colors, method=Image.MEDIANCUT)
    buf = io.BytesIO()
    q.save(buf, format="PNG", optimize=True)

    dst = Path(a.dst)
    dst.write_text(wrap(buf.getvalue(), note=a.note), encoding="utf-8")
    png = dst.with_suffix(".png")
    q.save(png, optimize=True)
    print(f"  {dst.name}: {dst.stat().st_size // 1024} КБ "
          f"(растр {png.stat().st_size // 1024} КБ рядом, как исходник)")
    print(f"  НЕ ЗАБЫТЬ: {dst.stem}.surfaces.json с линией пола — "
          f"без неё `on floor` молча не работает и фигура левитирует.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
