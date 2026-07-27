#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
karta.py — КАРТА ФИГУРЫ: где на экране оказывается то, что мы задали в сцене.

Зачем. Художник рисует «очки на глазах» и видит результат сразу. У нас между
замыслом и экраном стоит четыре системы координат, и ошибка в любой даёт
«очки не на глазах», «нога мимо окурка», «макушка срезана»:

    1. КООРДИНАТЫ ЧАСТИ   — внутри своего svg (viewBox), пиксели рисунка;
    2. КООРДИНАТЫ КОСТИ   — offset от пивота РОДИТЕЛЬСКОЙ кости; масштаб кости
                            наследуется детьми (поэтому плащ отделён от оси);
    3. МИРОВЫЕ            — доли кадра [0..1], в них пишется `place`/`moves-to`;
    4. ЭКРАННЫЕ           — пиксели готового кадра: мир × зум камеры.

Ловушка, которая стоила двух правок подряд: промах ВИДЕН в экранных пикселях,
а ЗАДАЁТСЯ в мировых. На крупном плане (зум 2.75) промах в 39 экранных
пикселей — это 14 мировых. Кто правит «на глаз по кадру», всегда перелетает.

Что делает инструмент. Рендерит замерный стенд и печатает ФАКТИЧЕСКУЮ карту:
где относительно якоря сущности оказались макушка, глаза, подбородок, ступни и
центр белого ядра — в долях кадра НА ЕДИНИЦУ `scales`. Эти числа и есть
переводчик «человеческого» замысла в наши координаты; из них считаются
кадрирование планов (src/timeline `frame_shot`) и посадка любого предмета.

Числа НЕ зашиты: поза, плащ и рост менялись десяток раз, и всякая зашитая
константа протухала молча. Меряем заново — и сверяем с KARTA.md.

Использование:
    python3 tools/karta.py                       # замерить и напечатать карту
    python3 tools/karta.py --pose lunge          # карта в конкретной позе
    python3 tools/karta.py --check               # сверить с эталоном KARTA.md
"""

import argparse
import json
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "target" / "release" / "animdsl"

# Эталон карты (доли кадра на единицу `scales`, якорь = 0). Держится здесь и в
# KARTA.md; --check сверяет замер с этими числами.
# Замер позы «idle» — она и есть отсчётная. Другие позы двигают голову и ноги
# на сотые доли: это НОРМА, а не расхождение, поэтому предметы, обязанные
# держаться тела, делаются костью (см. KARTA.md), а не подгонкой по числу.
KARTA = {
    "crown": -0.1733,     # макушка
    "eyes": -0.0630,      # центр глаз
    "chin": 0.0433,       # низ белого ядра
    "feet": 0.4144,       # ступни
    "mask_dx": -0.0239,   # центр белого ядра левее якоря (в долях ШИРИНЫ)
    "mask_w": 0.1422,     # ширина белого ядра (в долях ВЫСОТЫ кадра)
}
TOL = 0.012

STAND = """import character freeman from "../assets/characters/freeman_rig"
config {{
    width: 1000
    height: 1000
    fps: 24
    background: #e9eae4
    film-grain: 0.0
    vignette: 0.0
    line-boil: 0.0
    on-twos: 1
    form-shadow: 0.0
    ground-shadow: 0.0
    rim-light: 0.0
}}
scene "karta" (duration: 1s) {{
    place freeman at (0.5, {y}) facing front
    freeman scales {s}
    freeman pose "{pose}"
    camera wide
    wait 1s
}}
"""


def label(mask):
    """4-связные компоненты без scipy (его нет в окружении завода)."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    parent = [0]
    cur = 0

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for y in range(h):
        row = mask[y]
        for x in np.flatnonzero(row):
            up = lab[y - 1, x] if y and mask[y - 1, x] else 0
            lf = lab[y, x - 1] if x and row[x - 1] else 0
            if up and lf:
                lab[y, x] = min(up, lf)
                ra, rb = find(up), find(lf)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
            elif up or lf:
                lab[y, x] = up or lf
            else:
                cur += 1
                parent.append(cur)
                lab[y, x] = cur
    remap = np.zeros(cur + 1, np.int32)
    for i in range(1, cur + 1):
        remap[i] = find(i)
    return remap[lab]


def render(pose, y, s, w=1000):
    d = Path(tempfile.mkdtemp())
    src = ROOT / "examples" / "lektorij" / "_karta_stand.anim"
    src.write_text(STAND.format(pose=pose, y=y, s=s), encoding="utf-8")
    try:
        subprocess.run([str(ENGINE), "render", str(src), "--png-dir", str(d)],
                       check=True, capture_output=True)
    finally:
        src.unlink(missing_ok=True)
        (src.with_suffix(".mp4")).unlink(missing_ok=True)
    frames = sorted(d.glob("frame_*.png"))
    return np.asarray(Image.open(frames[len(frames) // 2]).convert("L"), np.uint8)


def measure(g, y_anchor, s):
    """Карта в долях кадра НА ЕДИНИЦУ `scales`, отсчёт от якоря сущности."""
    H, W = g.shape
    root_y = y_anchor * H
    root_x = 0.5 * W

    ink = g < 90
    ys, xs = np.where(ink)
    feet = ys.max()

    # белое ядро маски: белое, не связанное с рамкой кадра
    white = g > 200
    seen = np.zeros(white.shape, bool)
    q = deque([(0, 0)])
    seen[0, 0] = True
    while q:
        yy, xx = q.popleft()
        for ny, nx in ((yy - 1, xx), (yy + 1, xx), (yy, xx - 1), (yy, xx + 1)):
            if 0 <= ny < H and 0 <= nx < W and white[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    core = white & ~seen
    if not core.any():
        raise SystemExit("белого ядра маски не нашёл: обводка головы разомкнута "
                         "и белое перетекает в фон (было ровно так до правки "
                         "head.svg — щель на макушке)")
    # Ядро — САМАЯ КРУПНАЯ компонента, а не всё «белое не у рамки»: сглаживание
    # оставляет по кадру светлые крупинки, и габарит по ним растягивался вдвое.
    lab_core = label(core)
    ids, cnt = np.unique(lab_core[lab_core > 0], return_counts=True)
    core = lab_core == ids[cnt.argmax()]
    cy, cx = np.where(core)
    y0, y1, x0, x1 = cy.min(), cy.max(), cx.min(), cx.max()

    # глаза — тёмные пятна внутри ядра, выше трёх четвертей его высоты
    sub = ink[y0:y1 + 1, x0:x1 + 1]
    lab = label(sub)
    hh, ww = sub.shape
    eyes = []
    for i in np.unique(lab):
        if i == 0:
            continue
        by, bx = np.where(lab == i)
        if len(by) < sub.size * 0.002:
            continue
        if by.min() <= 1 or bx.min() <= 1 or by.max() >= hh - 2 or bx.max() >= ww - 2:
            continue
        if by.mean() / hh >= 0.72:          # это рот
            continue
        eyes.append((by.mean() + y0, bx.mean() + x0,
                     bx.max() - bx.min() + 1, by.max() - by.min() + 1))
    eye_y = float(np.median([e[0] for e in eyes])) if eyes else np.nan

    def fy(v):
        return (v - root_y) / H / s

    return {
        "crown": fy(y0), "eyes": fy(eye_y), "chin": fy(y1), "feet": fy(feet),
        "mask_dx": ((x0 + x1) / 2 - root_x) / W / s,
        "mask_w": (x1 - x0 + 1) / H / s,
        "_eyes": [(e[2], e[3], (e[1] - root_x) / W / s, (e[0] - root_y) / H / s)
                  for e in sorted(eyes, key=lambda e: e[1])],
    }


NAMES = {
    "crown": "макушка",
    "eyes": "центр глаз",
    "chin": "низ маски (подбородок)",
    "feet": "ступни",
    "mask_dx": "центр маски по X (доли ШИРИНЫ)",
    "mask_w": "ширина маски (доли ВЫСОТЫ)",
}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pose", default="idle")
    ap.add_argument("--scale", type=float, default=0.90)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)

    y = 0.20
    m = measure(render(a.pose, y, a.scale), y, a.scale)

    print(f"\n  КАРТА ФИГУРЫ — поза «{a.pose}», scales {a.scale}")
    print("  (доли кадра НА ЕДИНИЦУ `scales`, отсчёт от якоря сущности)\n")
    bad = 0
    for k, name in NAMES.items():
        v = m[k]
        line = f"    {name:<34}{v:+8.4f}"
        if k in KARTA:
            d = abs(v - KARTA[k])
            line += f"   эталон {KARTA[k]:+.4f}"
            if a.check and d > TOL:
                line += f"   ← РАСХОЖДЕНИЕ {d:.4f}"
                bad += 1
        print(line)
    print("\n    глаза (ширина×высота в px стенда, смещение от якоря):")
    for w, h, dx, dy in m["_eyes"]:
        print(f"      {w:>3}×{h:<3}  h/w {h/w:.2f}   dx {dx:+.4f}  dy {dy:+.4f}")
    print(f"\n  Перевод в сцену: элемент на уровне глаз ставится в "
          f"y = якорь {m['eyes']:+.4f}·scales,\n"
          f"  предмет на полу — в y = якорь {m['feet']:+.4f}·scales.\n"
          f"  Промах, замеренный по КАДРУ крупного плана, делить на зум плана —\n"
          f"  иначе правка перелетает во столько же раз.\n")
    if a.check and bad:
        print(f"  РАСХОЖДЕНИЙ С ЭТАЛОНОМ: {bad}. Либо правка фигуры не занесена\n"
              f"  в KARTA.md и frame_shot, либо что-то поехало.\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
