#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vectorize.py — ХУДОЖНИК завода: растр → SVG для движка.

Два разных дела, которые раньше делались одним и тем же способом:

  ОБВОДКА (trace) — растровый рисунок превращается в НАСТОЯЩИЕ векторные пути.
      Нужна всему рисованному: сгенерённым картинкам, сканам, кадрам-референсам.
      Вектор не мылится на сверхкрупе, а сверхкрупных планов в роликах теперь
      много. Делает VTracer (MIT, github.com/visioncortex/vtracer) — обводка
      1024×1024 занимает около 0.2с.

  ВСТАВКА (embed) — растр заворачивается в SVG как <image> с data-URI.
      Единственно верна для ФОТО: обводить фотографию значит превращать её в
      кашу из пятен, а фотореализм в наших роликах — приём («фото-шок»),
      а не полуфабрикат.

Раньше `raster_to_svg.py` умел только вставку и назывался так, будто умеет
обводку. Из-за этого любая сгенерённая картинка попадала в кадр растром.

Выбор режима — ЗАМЕР, а не догадка по имени файла. Меряется доля «плоских»
пикселей (сосед отличается меньше чем на 6 из 255): у рисованной туши это
0.64–0.69, у фотографии — 0.22. Порог 0.45 стоит посередине этого разрыва.
Замер печатается, режим можно задать руками — `--mode trace|embed`.

Использование:
    python3 tools/vectorize.py in.png out.svg               # режим по замеру
    python3 tools/vectorize.py in.png out.svg --mode trace
    python3 tools/vectorize.py in.png out.svg --size 1280x720
    python3 tools/vectorize.py in.png --measure             # только замер
"""

import argparse
import base64
import struct
import sys
from pathlib import Path

# Доля плоских пикселей, выше которой картинка считается рисованной.
# Замер по нашим ассетам: тушь 0.64–0.69, фото 0.22 (см. шапку).
FLAT_INK_MIN = 0.45
# Сосед отличается меньше чем на столько из 255 — пиксель «плоский».
FLAT_EPS = 6.0

# Параметры обводки под канон: плоская тушь, few flat tones, мягкие кривые.
# `color_precision` намеренно низкий — рисунок и так живёт в 3–4 тонах, а
# высокая точность плодит сотни почти одинаковых путей и раздувает файл.
TRACE_DEFAULTS = dict(
    colormode="color",
    color_precision=4,
    mode="spline",
    filter_speckle=8,
    corner_threshold=60,
    length_threshold=4.0,
    splice_threshold=45,
    path_precision=3,
)

# Магические байты. Расширению верить нельзя: в репозитории лежат ассеты
# `NanoBanana_*.png`, которые на деле JPEG, и обе прежние обёртки выбирали mime
# по расширению — то есть встраивали JPEG, объявив его PNG.
MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF8", "gif"),
    (b"RIFF", "webp"),          # RIFF....WEBP
    (b"BM", "bmp"),
]


def real_format(path):
    """Настоящий формат по сигнатуре файла, а не по расширению."""
    head = Path(path).read_bytes()[:12]
    for sig, name in MAGIC:
        if head.startswith(sig):
            if name == "webp" and head[8:12] != b"WEBP":
                continue
            return name
    return None


def png_size(data):
    """Размер PNG из IHDR (big-endian u32 по смещению 16)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    return None


def image_size(path):
    """Размер картинки. Pillow, если он есть; иначе только PNG из заголовка."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except ImportError:
        return png_size(Path(path).read_bytes())
    except Exception:                                        # noqa: BLE001
        return None


def measure(path):
    """(доля плоских пикселей, число тонов). None, если мерить нечем."""
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((256, 256))
        q = (np.asarray(im) // 32).reshape(-1, 3)
        tones = len(np.unique(q, axis=0))
        g = np.asarray(im.convert("L"), dtype=np.float32)
    d = (np.abs(np.diff(g, axis=1))[:-1, :] + np.abs(np.diff(g, axis=0))[:, :-1])
    return float((d < FLAT_EPS).mean()), int(tones)


def pick_mode(path):
    """«trace» для рисунка, «embed» для фото. (режим, пояснение)."""
    m = measure(path)
    if m is None:
        return "embed", "нет Pillow/numpy — мерить нечем, беру безопасную вставку"
    flat, tones = m
    if flat >= FLAT_INK_MIN:
        return "trace", f"плоских пикселей {flat:.2f} ≥ {FLAT_INK_MIN} — рисунок"
    return "embed", f"плоских пикселей {flat:.2f} < {FLAT_INK_MIN} — фото"


def embed(src, dst, size=None):
    """Растр в SVG как <image> с data-URI. Для фото."""
    data = Path(src).read_bytes()
    fmt = real_format(src) or "png"
    if size:
        w, h = size
    else:
        w, h = image_size(src) or (1280, 720)
    b64 = base64.b64encode(data).decode("ascii")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
           f'  <image x="0" y="0" width="{w}" height="{h}" '
           f'preserveAspectRatio="xMidYMid slice" '
           f'xlink:href="data:image/{fmt};base64,{b64}"/>\n</svg>\n')
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(svg, encoding="utf-8")
    return "embed"


def trace(src, dst, size=None, **opts):
    """Обводка растра в настоящие векторные пути (VTracer).

    VTracer выбирает декодер по расширению, а в репозитории лежат «PNG»,
    которые на деле JPEG. Поэтому при несовпадении сначала перекодируем во
    временный файл с честным расширением — иначе обводка падает с
    «No image file found», хотя файл на месте.
    """
    try:
        import vtracer
    except ImportError:
        print("  [художник] нет модуля vtracer (pip install vtracer) — "
              "падаю на вставку растром.", file=sys.stderr)
        return embed(src, dst, size)

    src = Path(src)
    fmt = real_format(src)
    work, tmp = src, None
    if fmt and not src.suffix.lower().lstrip(".").replace("jpg", "jpeg") == fmt:
        try:
            from PIL import Image
            tmp = Path(dst).with_suffix(f".src.{fmt}")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(src) as im:
                im.convert("RGB").save(tmp)
            work = tmp
        except Exception as e:                               # noqa: BLE001
            print(f"  [художник] расширение врёт ({src.suffix} ≠ {fmt}) и "
                  f"перекодировать не вышло ({e}) — вставка растром.",
                  file=sys.stderr)
            return embed(src, dst, size)

    cfg = dict(TRACE_DEFAULTS)
    cfg.update({k: v for k, v in opts.items() if v is not None})
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    try:
        vtracer.convert_image_to_svg_py(str(work.resolve()), str(Path(dst).resolve()), **cfg)
    except Exception as e:                                   # noqa: BLE001
        print(f"  [художник] обводка не удалась ({e}) — вставка растром.",
              file=sys.stderr)
        return embed(src, dst, size)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()

    if size:
        _refit(dst, size)
    return "trace"


def _refit(dst, size):
    """Подогнать обведённый SVG под кадр.

    VTracer пишет width/height в пикселях исходника и НЕ пишет viewBox. Просто
    подменить width/height нельзя: пути остаются в координатах исходника и
    рисуются 1:1 в углу кадра. Поэтому исходный размер переезжает в viewBox —
    он и задаёт систему координат путей, — а width/height становятся размером
    кадра. `slice` тянет рисунок по кадру, как это делала вставка растром.
    """
    import re
    w, h = size
    p = Path(dst)
    svg = p.read_text(encoding="utf-8")
    m = re.search(r'<svg[^>]*?\bwidth="([\d.]+)"[^>]*?\bheight="([\d.]+)"', svg)
    if not m:
        return
    sw, sh = m.group(1), m.group(2)
    head_end = svg.index(">", svg.index("<svg"))
    head = svg[svg.index("<svg"):head_end]
    for attr in ("width", "height", "viewBox", "preserveAspectRatio"):
        head = re.sub(rf'\s{attr}="[^"]*"', "", head)
    head += (f' width="{w}" height="{h}" viewBox="0 0 {sw} {sh}"'
             f' preserveAspectRatio="xMidYMid slice"')
    p.write_text(svg[:svg.index("<svg")] + head + svg[head_end:], encoding="utf-8")


def convert(src, dst, mode="auto", size=None, **opts):
    """Растр → SVG выбранным (или замеренным) способом. Возвращает режим."""
    if mode == "auto":
        mode, why = pick_mode(src)
        print(f"  [художник] {Path(src).name}: {why} → {mode}")
    return trace(src, dst, size, **opts) if mode == "trace" else embed(src, dst, size)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Художник: растр → SVG для движка")
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--mode", choices=("auto", "trace", "embed"), default="auto")
    ap.add_argument("--size", help="WxH кадра, например 1280x720")
    ap.add_argument("--colors", type=int, help="точность цвета обводки (1–8)")
    ap.add_argument("--speckle", type=int, help="отсекать пятна мельче N пикселей")
    ap.add_argument("--measure", action="store_true", help="только замер, без записи")
    a = ap.parse_args(argv)

    if a.measure:
        m = measure(a.src)
        if m is None:
            return print("нет Pillow/numpy — мерить нечем") or 1
        flat, tones = m
        mode, why = pick_mode(a.src)
        fmt = real_format(a.src)
        print(f"{a.src}\n  формат по сигнатуре: {fmt} (расширение: {Path(a.src).suffix})"
              f"\n  плоских пикселей: {flat:.2f}   тонов: {tones}\n  вердикт: {mode} — {why}")
        return 0

    if not a.dst:
        return print("нужен путь назначения (или --measure)") or 1
    size = tuple(int(x) for x in a.size.lower().split("x")) if a.size else None
    used = convert(a.src, a.dst, a.mode, size,
                   color_precision=a.colors, filter_speckle=a.speckle)
    kb = Path(a.dst).stat().st_size / 1024
    print(f"OK: {a.dst} ({used}, {kb:.0f} КБ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
