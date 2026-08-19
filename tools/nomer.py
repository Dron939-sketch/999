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

ПРОП — ВРЕМЕННОЕ РЕШЕНИЕ, И ОНО УЖЕ ПОКАЗАЛО СВОЙ ПРЕДЕЛ. Проп стоит в
координатах КАДРА, а не на фигуре: как только персонаж двигается, метка остаётся
на месте и «съезжает с балахона на картинку» — так это и увидела студия. Пока
ролик держит номер только на статичном общем плане в первые секунды, это
работает; в подписи-кольце уже нет.

ПРАВИЛЬНОЕ РЕШЕНИЕ — ЧАСТЬ РИГА, привязанная к кости торса: тогда метка едет
вместе с тканью и не требует ручной подгонки в каждой сцене. Это следующая
работа, и она не косметическая — в риге появится новая деталь и правило для
профильных поз (на спине номера быть не должно).

БЕЛЫМ, А НЕ ЧЁРНЫМ: балахон — сплошное чёрное пятно, чёрная цифра на нём не
видна вообще. Проверено тем же правилом, что и рука в ПУСТОТЕ.

Использование:
    python3 tools/nomer.py 6
    python3 tools/nomer.py 6 --out examples/assets/props/nomer-06.svg
"""

import argparse
import sys
from pathlib import Path


# ЦИФРЫ — КОНТУРАМИ, А НЕ ТЕКСТОМ. Первая версия рисовала номер элементом
# <text>, и в готовом ролике круг оказался ПУСТЫМ: движок не грузит шрифты
# (fontdb в рендерере нет), а usvg без шрифтов молча выбрасывает текст. Никакой
# ошибки при этом не появляется — просто цифры нет.
#
# Поэтому каждая цифра нарисована ломаными и дугами в коробке 100×140 с началом
# в (0,0). Рисунок нарочно угловатый: это метка на ткани, а не типографика.
GLYPHS = {
    "0": "M50 4 C18 4 8 34 8 70 C8 106 18 136 50 136 C82 136 92 106 92 70 C92 34 82 4 50 4 Z",
    "1": "M22 34 L54 6 L54 136",
    "2": "M10 36 C10 12 34 4 52 4 C78 4 92 22 92 44 C92 78 22 96 10 136 L92 136",
    "3": "M12 24 C24 8 44 4 56 4 C80 4 92 20 92 38 C92 58 74 70 52 70 C78 70 96 82 96 104 C96 124 78 136 54 136 C34 136 16 128 8 112",
    "4": "M70 136 L70 4 L8 96 L96 96",
    "5": "M88 6 L26 6 L18 62 C30 54 42 50 56 50 C82 50 96 68 96 92 C96 118 76 136 52 136 C32 136 16 128 8 114",
    "6": "M84 12 C74 6 62 4 52 4 C24 4 10 30 10 76 C10 116 26 136 52 136 C76 136 92 118 92 96 C92 74 76 58 52 58 C32 58 14 70 10 88",
    "7": "M8 6 L94 6 L44 136",
    "8": "M52 66 C28 66 12 52 12 34 C12 14 30 4 52 4 C74 4 92 14 92 34 C92 52 76 66 52 66 Z M52 66 C80 66 98 82 98 104 C98 124 78 136 52 136 C26 136 6 124 6 104 C6 82 24 66 52 66 Z",
    "9": "M20 128 C30 134 42 136 52 136 C80 136 94 110 94 64 C94 24 78 4 52 4 C28 4 12 22 12 44 C12 66 28 82 52 82 C72 82 90 70 94 52",
}

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
    <g transform="translate({tx} {ty}) scale({sc})" fill="none" stroke="#f2f2ec"
       stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{paths}</g>
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
    missing = [c for c in num if c not in GLYPHS]
    if missing:
        print(f"нет контура для цифры {missing[0]}", file=sys.stderr)
        return 1
    # Ширина цифры 100, зазор 18. Двузначный номер ужимаем, чтобы влез в круг.
    step = 118
    paths = "".join(
        f'<path d="{GLYPHS[c]}" transform="translate({i * step} 0)"/>'
        for i, c in enumerate(num))
    w = len(num) * 100 + (len(num) - 1) * 18
    sc = 0.86 if len(num) == 1 else 0.62
    tx = 120 - (w * sc) / 2
    ty = 120 - (140 * sc) / 2
    sw = 16 if len(num) == 1 else 20
    out = Path(a.out) if a.out else Path("examples/assets/props") / f"nomer-{int(num):02d}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.format(num=num, seed=int(num) * 7 % 97, paths=paths,
                                   tx=round(tx, 1), ty=round(ty, 1),
                                   sc=round(sc, 3), sw=sw), encoding="utf-8")
    print(f"  {out}")
    print(f"  ставится в ПЕРВОЙ сцене, справа на груди:")
    print(f'      let nomer = prop("nomer", "../assets/props/{out.name}") at (0.53, 0.62) layer 9')
    print(f"      nomer scales 0.30")
    print(f"  и уезжает за кадр, как только персонаж пойдёт: nomer moves-to (-1.5, 1.5) over 0.01s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
