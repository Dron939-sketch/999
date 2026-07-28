#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
proportions.py — замер ПРОПОРЦИЙ фигуры в единицах ширины лицевой маски.

Единица — ширина БЕЛОГО ЯДРА маски (само лицо, без чёрной обводки). Раньше
единицей был габарит маски вместе с обводкой, и это тихо ломало весь замер:
стоило сделать обводку честно тонкой, как единица уменьшалась и «ухудшались»
все строки таблицы, хотя фигура не менялась. Ядро — величина, которая от
толщины карандаша не зависит.

Эталон НЕ зашит числами: он меряется той же функцией с кадра оригинала
(`--ref`). Пока обе стороны считаются одним кодом, спор «а по какой линейке»
невозможен.

Использование:
    python3 tools/proportions.py наш.png --ref "оригинал.mp4" --at-ref 30
    python3 tools/proportions.py наш.png            # просто числа, без сверки
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from face_ref import find_face, load_gray  # noqa: E402

TOL = 0.15  # ±15% — в пределах разброса ручного рисунка

NAMES = {
    "mask_hw":    "маска высота/ширина",
    "fig_h":      "высота фигуры",
    "max_w":      "макс ширина (руки)",
    "torso_top":  "ширина корпуса у плеч",
    "torso_max":  "ширина корпуса в широком месте",
    "flare":      "разлёт корпуса (низ/верх)",
    "head_share": "доля головы в росте",
}


def ink_threshold(g):
    """Порог «чернил» по Оцу.

    Фиксированный порог годится только для нашего стенда с белым полем: у
    оригинала фон — тёмно-серый и целиком уходил в «чернила», после чего
    замер мерил декорацию (ширина корпуса выходила во весь кадр).
    """
    # Оцу здесь не годится: на кадре оригинала пол светлее фона, и порог
    # уезжает между полом и всем остальным — серый фон уходит в «чернила»
    # и замер начинает мерить декорацию. Персонаж же всегда САМОЕ ТЁМНОЕ
    # пятно кадра, поэтому берём середину между самым тёмным и медианой.
    dark = float(np.percentile(g, 1))
    mid = float(np.median(g))
    return int((dark + mid) / 2)


def longest_run(row):
    best = cur = 0
    for v in row:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def measure(g, floor=None, box=None):
    """box — «y0,y1,x0,x1»: рамка вокруг фигуры на кадре со сценой.

    У оригинала фигура стоит не на пустом поле: в чернила попадают горизонт,
    штриховка пола, снег. Без рамки замер меряет декорацию, а не персонажа.
    floor — Y, ниже которого фигура закрыта землёй и её нельзя учитывать.
    """
    if box:
        y0, y1, x0, x1 = box
        g = g[y0:y1, x0:x1]
        floor = None if floor is None else floor - y0
    ink = g < ink_threshold(g)
    box = find_face(g)
    if box is None:
        raise SystemExit("лицевой маски не нашёл: контур разомкнут или кадр обрезан")
    my0, my1, mx0, mx1 = box
    u = float(mx1 - mx0 + 1)

    rows = np.where(ink.any(1))[0]
    fig_top = min(rows.min(), my0)
    fig_bot = rows.max() if floor is None else min(rows.max(), floor)
    fig_h = fig_bot - fig_top + 1

    max_w = max(
        (np.where(ink[y])[0].max() - np.where(ink[y])[0].min() + 1)
        for y in range(fig_top, fig_bot + 1) if ink[y].any()
    )
    # Корпус меряем СПЛОШНЫМ отрезком чернил в строке, а не габаритом:
    # габарит ловит руки, фон и горизонт, сплошной отрезок — только массу.
    # Верх корпуса — сразу под подбородком; «широкое место» — максимум по
    # всей длине массы (у оригинала это подол, трапеция расширяется книзу).
    span = max(fig_bot - my1, 1)
    runs = [(y, longest_run(ink[y]))
            for y in range(my1 + int(span * 0.03), my1 + int(span * 0.95))]
    t_top = float(np.median([r for _, r in runs[:max(len(runs) // 8, 1)]]))
    # «широкое место» — только там, где это ещё масса корпуса. Ниже подола
    # остаются ноги (отрезок схлопывается), а на уровне кистей руки сливаются
    # с телом в один длинный отрезок — 90-й процентиль гасит этот выброс.
    body = [r for _, r in runs if r >= t_top * 0.6]
    t_max = float(np.percentile(body, 90)) if body else 0.0

    return {
        "mask_hw": (my1 - my0 + 1) / u,
        "fig_h": fig_h / u,
        "max_w": max_w / u,
        "torso_top": t_top / u,
        "torso_max": t_max / u,
        "flare": t_max / max(t_top, 1e-6),
        "head_share": (my1 - my0 + 1) / fig_h,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("frame", help="наш кадр (стенд examples/lektorij/proportion-probe.anim)")
    ap.add_argument("--ref", help="кадр или ролик оригинала")
    ap.add_argument("--at", type=float)
    ap.add_argument("--at-ref", type=float)
    ap.add_argument("--floor", type=int,
                    help="Y линии земли на кадре ЭТАЛОНА (ниже неё фигура закрыта)")
    ap.add_argument("--ref-box", help="рамка вокруг фигуры эталона: y0,y1,x0,x1")
    a = ap.parse_args(argv)

    ours = measure(load_gray(a.frame, a.at))
    if not a.ref:
        print("\n  ПРОПОРЦИИ (единица — ширина белого ядра маски)")
        for k, n in NAMES.items():
            print(f"  {n:<28}{ours[k]:>8.2f}")
        print()
        return 0

    box = tuple(int(v) for v in a.ref_box.split(",")) if a.ref_box else None
    ref = measure(load_gray(a.ref, a.at_ref if a.at_ref is not None else a.at),
                  floor=a.floor, box=box)
    print(f"\n  ПРОПОРЦИИ (единица — ширина белого ядра маски)\n"
          f"  {'параметр':<28}{'наш':>8}{'оригинал':>10}{'расх.':>8}")
    bad = 0
    for k, n in NAMES.items():
        o, r = ours[k], ref[k]
        if k in ("fig_h", "head_share", "max_w") and a.floor is not None:
            print(f"  {n:<28}{o:>8.2f}{'—':>10}{'':>8}  эталон обрезан полом")
            continue
        d = abs(o - r) / max(abs(r), 1e-6)
        bad += d > TOL
        print(f"  {n:<28}{o:>8.2f}{r:>10.2f}{d*100:>7.0f}%  "
              f"{'OK' if d <= TOL else 'РАСХОЖДЕНИЕ'}")
    print(f"\n  итог: {len(NAMES) - bad}/{len(NAMES)} в допуске ±{int(TOL*100)}%\n")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
