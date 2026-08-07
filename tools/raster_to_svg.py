#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Обернуть растровую картинку в SVG с встроенным <image> (data-URI).

Так фотореалистичный фон грузится через обычный путь движка (resvg рисует
встроенный растр) — БЕЗ доработки движка. Персонаж (векторная тушь) ложится
сверху → парадокс «рисованный герой в фотомире».

ЭТО ВСТАВКА, А НЕ ОБВОДКА — и она верна только для ФОТО. Рисованному растру
(сгенерённая картинка, скан, кадр-референс) нужна настоящая векторизация:
вставленный растр мылится на сверхкрупе, а сверхкрупных планов в роликах
много. Обводка живёт в `tools/vectorize.py` (художник завода):

    python3 tools/vectorize.py in.png out.svg              # режим по замеру
    python3 tools/vectorize.py in.png out.svg --mode trace

Этот файл оставлен как есть, чтобы не рвать старые вызовы, и делегирует
художнику вставку.

Использование:
    python3 tools/raster_to_svg.py in.png out.svg [W H]
Если W/H не заданы — берутся из картинки.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vectorize import embed  # noqa: E402


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    size = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) >= 5 else None
    embed(src, dst, size)
    kb = Path(dst).stat().st_size / 1024
    print(f"wrote {dst} ({kb:.0f} КБ, вставка растром — "
          f"для рисунка нужен tools/vectorize.py --mode trace)")


if __name__ == "__main__":
    main()
