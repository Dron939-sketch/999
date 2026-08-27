#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
podol.py — ГЕЙТ ПОДОЛА: накладка не задирает плащ, ноги не «дышат».

ЗАМЕЧАНИЕ СТУДИИ: «движения ломанные, ноги удлиняются почему-то, когда двигает
руками». Замер подтвердил и назвал механизм.

ЧТО ПРОИСХОДИТ. Ступни стоят на месте, а ПОДОЛ ПЛАЩА уезжает вверх. Ноги видны
ровно от подола до ступней, поэтому сдвиг подола на тринадцать пикселей при
росте в пятьсот двадцать — это пятая часть длины ног. Внутри одной реплики
накладок две-четыре, и на каждой смене ноги то вытягиваются, то поджимаются:
это и читается как ломаное движение.

ОТКУДА. Плащ висит на ТОРСЕ, а ноги крепятся к тазу. Поза, поворачивающая торс,
тянет плащ за собой, ноги остаются на месте. У `v_upor` торс повёрнут на
пятнадцать градусов — подол уезжает на тринадцать пикселей. Физически плащ при
повороте корпуса так не задирается.

ПОЧЕМУ НЕ СПИСОК ЗАПРЕЩЁННЫХ ИМЁН. Торс двигают пятьдесят пять поз из двухсот
трёх, и они стоят накладками в тридцати пяти роликах из тридцати девяти.
Запретить все — значит запретить половину пластики. Мерить надо СВОЙСТВО, как
у гейта осанки: на сколько уехал подол при неподвижных ступнях.

ПОРОГ СНЯТ С КАТАЛОГА. Медиана сдвига по ходовым накладкам — два пикселя из
пятисот двадцати; пятёрка слоёв даёт четыре-шесть; один выброс, `v_upor`, даёт
тринадцать. Порог — ДЕСЯТАЯ ЧАСТЬ ВИДИМОЙ ДЛИНЫ НОГ (около шести пикселей на
стенде): всё, что ниже, глаз не ловит, выброс отсекается с запасом.

ЧТО НЕ ПРОВЕРЯЕТСЯ. Слои шага (`shag_*`) двигают силуэт ПО ЗАМЫСЛУ: при шаге
одна ступня отрывается, и подол честно качается. Их гейт пропускает.

Использование:
    python3 tools/podol.py examples/lektorij/lebed.anim
    python3 tools/podol.py --pozy v_upor obvinil     # разовый замер поз
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from karta import render                              # noqa: E402
import numpy as np                                    # noqa: E402

BASE = "calm"
DOLYA_NOG = 0.10          # доля видимой длины ног, выше которой сдвиг заметен
OVERLAY = re.compile(r'^\s*\w+\s+overlays\s+"([^"]+)"', re.M)
IMPORT = re.compile(r'import\s+character\s+\S+\s+from\s+"([^"]+)"')
SHAG = re.compile(r"^shag_")


def tochki(rig_dir, poza):
    """(подол, ступни) в пикселях кадра на стенде.

    Подол ищется снизу вверх по ширине силуэта: ноги — две тонкие палки, и
    ширина на них много меньше, чем на плаще. Первая строка, где силуэт
    расширяется, и есть кромка подола.
    """
    g = render(rig_dir, poza, 0.60, 0.90)
    ink = g < 90
    ys, _ = np.nonzero(ink)
    if not len(ys):
        return None
    top, bot = int(ys.min()), int(ys.max())
    shir = ink.sum(1)
    mx = int(shir[top:bot + 1].max())
    y = bot
    while y > top and shir[y] < mx * 0.30:
        y -= 1
    return y, bot


def main(argv):
    ap = argparse.ArgumentParser(description="Гейт подола: ноги не «дышат»")
    ap.add_argument("anim", nargs="?")
    ap.add_argument("--pozy", nargs="*", help="замерить названные позы и выйти")
    a = ap.parse_args(argv)

    rig = str(ROOT / "examples/assets/characters/freeman_rig")
    base = tochki(rig, BASE)
    if base is None:
        print("эталон не отрисовался", file=sys.stderr)
        return 1
    b_hem, b_bot = base
    nogi = b_bot - b_hem
    porog = max(3, int(nogi * DOLYA_NOG))

    if a.pozy:
        for p in a.pozy:
            t = tochki(rig, p)
            if t:
                print(f"  {p:22} подол {t[0] - b_hem:+3} пикс "
                      f"({abs(t[0] - b_hem) / nogi * 100:4.0f}% длины ног)")
        return 0

    if not a.anim:
        raise SystemExit("укажи .anim или --pozy")
    src = Path(a.anim)
    text = src.read_text(encoding="utf-8")
    m = IMPORT.search(text)
    if m:
        rig = str((src.parent / m.group(1)).resolve())
        base = tochki(rig, BASE)
        b_hem, b_bot = base
        nogi = b_bot - b_hem
        porog = max(3, int(nogi * DOLYA_NOG))

    sloi = sorted({p for p in OVERLAY.findall(text) if not SHAG.match(p)})
    bed = []
    for p in sloi:
        t = tochki(rig, p)
        if t is None:
            continue
        d = t[0] - b_hem
        if abs(d) > porog:
            bed.append((p, d, abs(d) / nogi * 100))

    if bed:
        print(f"  ПОДОЛ УЕЗЖАЕТ, НОГИ «ДЫШАТ» (порог {porog} пикс = "
              f"{DOLYA_NOG * 100:.0f}% длины ног):")
        for p, d, pct in sorted(bed, key=lambda x: -abs(x[1])):
            print(f"    · {p}: подол {d:+d} пикс — это {pct:.0f}% видимой длины "
                  f"ног. Ступни на месте, значит ноги на этой смене "
                  f"{'вытянутся' if d < 0 else 'поджмутся'}")
        print("  Плащ висит на торсе: поза, поворачивающая корпус, тянет подол "
              "за собой. Взять слой, который торс не трогает.")
        return 1
    print(f"  подол: все {len(sloi)} накладок держат кромку в пределах "
          f"{porog} пикс ({DOLYA_NOG * 100:.0f}% длины ног)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
