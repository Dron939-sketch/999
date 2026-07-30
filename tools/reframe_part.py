#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reframe_part.py — переложить рисунок части в ДРУГУЮ рамку с другим пивотом.

Зачем. Пивот в риге принадлежит КОСТИ, а не рисунку. Пока у кости один рисунок,
это незаметно; у плаща их три (анфас, три четверти, профиль), и стоило снять
анфас со скульптуры в новую рамку 335x521 с пивотом [162,30], как два
подменяемых ракурса поехали: их рамка 220x392 с пивотом [110,16], и якорь
попадал к правому краю. На экране это видно только на тех ракурсах, куда
давно никто не смотрел.

Развороты можно было бы тоже снять со скульптуры (`view_deg` в stl_to_rig.py),
и это пробовалось. Не подошло: плащ скульптуры — почти тело вращения, в профиль
он выходит 0.9 анфасной ширины, и поворот перестаёт читаться. Подлинный лист
разворотов даёт профиль 0.70, три четверти 0.86 — плащ у Фримена ПЛОСКИЙ, это
графика. Рисованные ракурсы это знают; их и оставляем, только перекладываем в
общую рамку и растягиваем до новой длины плаща.

Растяжение РАЗНОЕ по осям, и это не произвол: по вертикали плащ вырос сильнее
(новый рисунок длиннее), по горизонтали слабее. Один общий множитель сделал бы
профиль на 18% шире полосы приёмки.

Использование:
    python3 tools/reframe_part.py вход.svg выход.svg \
        --old-pivot 110 16 --frame 335 521 162 30 --scale 1.42 1.635
"""

import argparse
import re
import sys
from pathlib import Path


def reframe(src_txt, old_pivot, frame, scale):
    W, H, px, py = frame
    sx, sy = scale
    opx, opy = old_pivot
    body = re.sub(r"^.*?<svg[^>]*>", "", src_txt, flags=re.S)
    body = re.sub(r"</svg>\s*$", "", body)
    # Порядок важен: сперва рисунок ставится пивотом в начало координат, потом
    # растягивается, и только потом переносится в новый пивот. Иначе растяжение
    # уводит сам пивот.
    tx = px - opx * sx
    ty = py - opy * sy
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}">\n'
            f'  <!-- ПЕРЕЛОЖЕНО в общую рамку плаща инструментом\n'
            f'       tools/reframe_part.py: пивот кости [{px},{py}], растяжение\n'
            f'       {sx}x{sy}. Рисунок внутри — прежний, обведённый с листа\n'
            f'       разворотов; правится он, а не эта обёртка. -->\n'
            f'  <g transform="translate({tx:.2f},{ty:.2f}) scale({sx},{sy})">'
            f'{body}</g>\n</svg>\n')


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--old-pivot", nargs=2, type=float, required=True)
    ap.add_argument("--frame", nargs=4, type=float, required=True)
    ap.add_argument("--scale", nargs=2, type=float, required=True)
    a = ap.parse_args(argv)
    txt = Path(a.src).read_text(encoding="utf-8")
    out = reframe(txt, a.old_pivot, [int(v) for v in a.frame[:2]] + list(a.frame[2:]),
                  a.scale)
    Path(a.dst).write_text(out, encoding="utf-8")
    print(f"{a.dst}: рамка {int(a.frame[0])}x{int(a.frame[1])}, "
          f"пивот [{a.frame[2]:.0f},{a.frame[3]:.0f}], растяжение {a.scale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
