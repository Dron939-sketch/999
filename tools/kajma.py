#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kajma.py — СВЕТЛАЯ КАЙМА ПО РУКАМ И КИСТЯМ.

ЗАМЕЧАНИЕ СТУДИИ: «чёрное на чёрном не видно, поэтому если надо делай иногда
руки белыми или белый контур».

ЧТО БЫЛО. Плащ чёрный, руки чёрные. Пока рука вынесена в сторону, она читается
на фоне локации; как только жест идёт ПЕРЕД корпусом — а перед корпусом идёт
половина жестов, — кисть пропадает целиком. Зритель видит, что персонаж что-то
делает, но не видит, что именно.

ПОЧЕМУ НЕ «СДЕЛАТЬ РУКИ БЕЛЫМИ». Это уже пробовали на профильных руках
(`arm_out_*`) и откатили: белая рука на светлом поле становится прозрачной
проволочкой, а гейт разворота считает профиль на 15% уже нормы, потому что
мерит силуэт по ТУШИ. Работает только два слоя — чёрная тушь снизу, светлая
кайма по её краю сверху.

КАК СДЕЛАНО ЗДЕСЬ. Кайма не дорисовывается руками по каждому пути: у кисти
пять налегающих друг на друга кусков, и обводка каждого дала бы белые линии
ВНУТРИ ладони — пальцы расчертило бы как решётку. Вместо этого рисунок
печатается дважды: сначала его силуэт, раздутый на 1.6 и залитый цветом бумаги,
затем поверх — он же тушью. Светлое остаётся видно ровно по внешнему краю.
Раздутием занимается feMorphology, поэтому приём одинаково работает и на
заливках (кисти), и на штрихах (рукав-щетина), и не зависит от того, из чего
сложена фигура.

ЧЕГО КАЙМА НЕ ЛОМАЕТ. Тушь остаётся на месте и не сдвигается ни на пиксель,
поэтому все мерки, которые читают силуэт по тёмному (масштаб, разворот, подол,
осанка, запас), видят ровно то же, что видели. Кайма светлая — в ink она не
попадает.

Использование:
    python3 tools/kajma.py --dry-run
    python3 tools/kajma.py
    python3 tools/kajma.py --check    # деталь без каймы роняет приёмку
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = ROOT / "examples/assets/characters/freeman_rig"

BUMAGA = "#eef1ec"
RADIUS = 1.6

# Кисти и передние руки. Профильные (`arm_out_*`) уже с каймой, сделанной
# вручную по одному пути, — их не трогаем.
CELI = ["hand_*.svg", "forearm_*.svg", "upper_arm_*.svg"]

FILTR = (
    f'<filter id="kajma" x="-50%" y="-50%" width="200%" height="200%">'
    f'<feMorphology in="SourceAlpha" operator="dilate" radius="{RADIUS}" '
    f'result="tolshche"/>'
    f'<feFlood flood-color="{BUMAGA}" result="bumaga"/>'
    f'<feComposite in="bumaga" in2="tolshche" operator="in"/>'
    f"</filter>"
)

METKA = 'id="kajma"'
KOMM = (
    "\n<!-- СВЕТЛАЯ КАЙМА (tools/kajma.py). Ниже рисунок напечатан дважды:\n"
    "     первый проход — раздутый силуэт цветом бумаги, второй — он же тушью\n"
    "     поверх. На чёрном плаще кисть читается каймой, на светлом поле —\n"
    "     тушью. Правится не здесь, а в kajma.py: он пересобирает все файлы. -->"
)

KOMMENT = re.compile(r"<!--.*?-->", re.S)


def perepisat(text):
    if METKA in text:
        return None                      # кайма уже стоит
    m = re.search(r"</defs>", text)
    if not m:
        return None
    golova, telo = text[: m.end()], text[m.end():]
    hvost = telo.rfind("</svg>")
    risunok, konec = telo[:hvost], telo[hvost:]

    golova = golova[: m.start()] + FILTR + golova[m.start():]
    # В нижнем проходе комментарии не нужны — они уже есть в верхнем.
    tenj = KOMMENT.sub("", risunok).strip()
    return (golova + KOMM
            + f'\n<g filter="url(#kajma)">{tenj}</g>\n'
            + risunok.rstrip() + "\n" + konec)


def main(argv):
    ap = argparse.ArgumentParser(description="Светлая кайма по рукам и кистям")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="упасть, если у детали каймы нет")
    a = ap.parse_args(argv)

    fajly = sorted({f for g in CELI for f in RIG.glob(g)})

    if a.check:
        golye = [f.name for f in fajly
                 if METKA not in f.read_text(encoding="utf-8")]
        if golye:
            print("  ДЕТАЛЬ БЕЗ СВЕТЛОЙ КАЙМЫ — на чёрном плаще пропадёт:")
            for n in golye:
                print(f"    · {n}")
            print("  Прогнать `python3 tools/kajma.py` (реестр §XXXIV).")
            return 1
        print(f"  кайма: все {len(fajly)} деталей рук и кистей обшиты")
        return 0
    tronuto = 0
    for f in fajly:
        novoe = perepisat(f.read_text(encoding="utf-8"))
        if novoe is None:
            print(f"  · {f.name}: кайма уже стоит")
            continue
        tronuto += 1
        print(f"  + {f.name}")
        if not a.dry_run:
            f.write_text(novoe, encoding="utf-8")
    print(f"\n  {'показано' if a.dry_run else 'обшито'}: {tronuto} из "
          f"{len(fajly)} файлов")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
