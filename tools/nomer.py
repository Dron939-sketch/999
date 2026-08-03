#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nomer.py — НОМЕР КУРСА НА БАЛАХОНЕ.

ЗАЧЕМ. Ролики уходят в ленту инстаграма, где решение «смотреть или листать»
принимается за две секунды. Две секунды — это меньше, чем первая реплика, и
зацепить в них можно только КАРТИНКОЙ. Решение студии: у персонажа на балахоне,
справа на груди, стоит порядковый номер курса. Он читается мгновенно, работает
как серия («а, это шестой») и не требует ни слова.

ЧТО ДЕЛАЕТ. Рисует цифру белой тушью в рваном круге — так, как её нарисовали бы
на ткани, а не напечатали. Кладёт в `examples/assets/props/nomer-NN.svg`.

ПОЧЕМУ ПРОП, А НЕ ЧАСТЬ РИГА. Часть рига поехала бы за костями во всех позах, и
на профиле, полуспине и в наклоне цифра ползла бы по ткани. Номер нужен там, где
он работает, — в ПЕРВЫХ СЕКУНДАХ, на статичном общем плане. Ставится в сцене
рядом с фигурой и уезжает за кадр, когда персонаж начинает ходить.

БЕЛЫМ, А НЕ ЧЁРНЫМ: балахон — сплошное чёрное пятно, чёрная цифра на нём не
видна вообще. Проверено тем же правилом, что и рука в ПУСТОТЕ.

Использование:
    python3 tools/nomer.py 6
    python3 tools/nomer.py 6 --out examples/assets/props/nomer-06.svg
"""

import argparse
import sys
from pathlib import Path

TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="240" height="240">
  <defs>
    <filter id="ink" x="-15%" y="-15%" width="130%" height="130%">
      <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="1" seed="{seed}" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="4" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
  </defs>
  <!-- НОМЕР КУРСА «{num}» на балахон, справа на груди. Белая тушь: балахон —
       сплошное чёрное пятно, чёрная цифра на нём не читается вообще.
       Круг рваный и незамкнутый — метка от руки, а не печать. -->
  <g filter="url(#ink)">
    <circle cx="120" cy="120" r="86" fill="none" stroke="#f2f2ec" stroke-width="9"
            stroke-linecap="round" stroke-dasharray="470 60" transform="rotate(-24 120 120)"/>
    <text x="120" y="120" fill="#f2f2ec" font-family="Georgia, 'Times New Roman', serif"
          font-size="{size}" font-weight="700" text-anchor="middle"
          dominant-baseline="central">{num}</text>
  </g>
</svg>
'''


def main(argv):
    ap = argparse.ArgumentParser(description="Номер курса на балахон")
    ap.add_argument("number", help="порядковый номер курса, например 6")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    num = a.number.strip()
    if not num.isdigit():
        print("номер должен быть числом", file=sys.stderr)
        return 1
    # Двузначный номер в том же круге должен быть мельче, иначе вылезет за обводку.
    size = 132 if len(num) == 1 else 96
    out = Path(a.out) if a.out else Path("examples/assets/props") / f"nomer-{int(num):02d}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.format(num=num, size=size, seed=int(num) * 7 % 97),
                   encoding="utf-8")
    print(f"  {out}")
    print(f"  ставится в ПЕРВОЙ сцене, справа на груди:")
    print(f'      let nomer = prop("nomer", "../assets/props/{out.name}") at (0.53, 0.62) layer 9')
    print(f"      nomer scales 0.30")
    print(f"  и уезжает за кадр, как только персонаж пойдёт: nomer moves-to (-1.5, 1.5) over 0.01s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
