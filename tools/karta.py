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

Карта принадлежит ПЕРСОНАЖУ, а не движку: она лежит в его `rig.json` в поле
`karta`, и по ней компилятор таймлайна кадрирует планы. Поэтому правило
работает для любого персонажа в кадре, а не только для Фримена — новому ригу
достаточно один раз снять карту с ключом `--write`.

Использование:
    python3 tools/karta.py                              # Фримен: замер + печать
    python3 tools/karta.py --rig examples/assets/characters/fredi_rig
    python3 tools/karta.py --rig <папка> --pose idle --write   # записать в rig.json
    python3 tools/karta.py --all --check                # сверить все риги
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "target" / "release" / "animdsl"

# Эталон берётся из САМОГО РИГА (поле `karta` в rig.json) — не из этого файла.
# Так карта не может разойтись с тем, чем пользуется движок: `--check` меряет
# заново и сверяет с тем, что записано у персонажа.
TOL = 0.012
RIGS = "examples/assets/characters"

STAND = """import character hero from "{rig}"
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
    place hero at (0.5, {y}) facing front
    hero scales {s}
    hero pose "{pose}"
{props_off}    camera wide
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


def render(rig_dir, pose, y, s):
    d = Path(tempfile.mkdtemp())
    src = ROOT / "examples" / "lektorij" / "_karta_stand.anim"
    rel = os.path.relpath(Path(rig_dir).resolve(), src.parent)
    # ПРЕДМЕТЫ СНИМАЮТСЯ НА СТЕНДЕ. Трость свисает ниже подошв, цилиндр ездит с
    # головой — по ним «ступни» и «макушка» мерятся не по фигуре, и рост с
    # кадрированием уезжают. Риг объявляет накладку `bez_predmetov`; у кого её
    # нет, стенд остаётся прежним.
    poses = json.loads((Path(rig_dir) / "rig.json").read_text(encoding="utf-8")).get("poses", {})
    off = '    hero overlays "bez_predmetov"\n' if "bez_predmetov" in poses else ""
    src.write_text(STAND.format(rig=rel, pose=pose, y=y, s=s, props_off=off),
                   encoding="utf-8")
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


def one_rig(rig_dir, pose, scale, do_check, do_write):
    y = 0.20
    m = measure(render(rig_dir, pose, y, scale), y, scale)

    # ВТОРОЙ ЗАХОД С ПОДБОРОМ РОСТА. `scales` НЕ сопоставим между персонажами:
    # движок делит на `height` из рига, и при одном и том же `scales 0.9`
    # Фримен занимает 0.58 кадра, а Фреди — 0.28. У мелкой фигуры голова
    # выходит в 19 пикселей, и глаза меряются как пятна 1x2 — мусор. Поэтому
    # первый замер нужен только чтобы узнать рост, а настоящий делается на
    # масштабе, при котором фигура заполняет кадр.
    full = abs(m["crown"]) + m["feet"]
    if full > 1e-6:
        want = 0.70 / full
        if abs(want - scale) / scale > 0.15:
            scale = round(want, 3)
            m = measure(render(rig_dir, pose, y, scale), y, scale)
    rig_json = Path(rig_dir) / "rig.json"
    stored = json.loads(rig_json.read_text(encoding="utf-8")).get("karta")

    print(f"\n  КАРТА ФИГУРЫ — {Path(rig_dir).name}, поза «{pose}», scales {scale}")
    print("  (доли кадра НА ЕДИНИЦУ `scales`, отсчёт от якоря сущности)\n")
    bad = 0
    for k, name in NAMES.items():
        v = m[k]
        line = f"    {name:<34}{v:+8.4f}"
        if stored and k in stored:
            d = abs(v - stored[k])
            line += f"   в риге {stored[k]:+.4f}"
            if do_check and d > TOL:
                line += f"   ← РАСХОЖДЕНИЕ {d:.4f}"
                bad += 1
        elif not stored:
            line += "   карты в риге НЕТ"
        print(line)
    print("\n    глаза (ширина×высота в px стенда, смещение от якоря):")
    for w, h, dx, dy in m["_eyes"]:
        print(f"      {w:>3}×{h:<3}  h/w {h/w:.2f}   dx {dx:+.4f}  dy {dy:+.4f}")
    print(f"\n  Перевод в сцену: элемент на уровне глаз — "
          f"y = якорь {m['eyes']:+.4f}·scales,\n"
          f"  предмет на полу — y = якорь {m['feet']:+.4f}·scales,\n"
          f"  полный рост {abs(m['crown']) + m['feet']:.3f}·scales "
          f"(в общий план целиком влезает при scales ≤ "
          f"{0.86 / (abs(m['crown']) + m['feet']):.2f}).\n"
          f"  Промах, замеренный по КАДРУ крупного плана, делить на зум плана.\n")

    if do_write:
        doc = json.loads(rig_json.read_text(encoding="utf-8"))
        vals = {}
        for k in NAMES:
            v = m[k]
            if v != v:      # NaN: замер не нашёл величину (у Фреди глаза не
                            # тёмные пятна на белой маске, а часть рисунка).
                v = m["crown"] + (m["chin"] - m["crown"]) * 0.5
                print(f"  ! {NAMES[k]}: замером не взято, пишу середину головы "
                      f"{v:+.4f} — планы от этого не зависят, но предметы "
                      f"«на уровне глаз» для этого персонажа ставить нельзя.")
            vals[k] = round(v, 4)
        doc["karta"] = vals
        rig_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"  Карта записана в {rig_json}\n")
    if do_check and not stored:
        print("  У рига НЕТ карты: планы для него считаются по историческим\n"
              "  постоянным, подобранным под другого персонажа. Снять картой:\n"
              f"  python3 tools/karta.py --rig {rig_dir} --write\n")
        return 1
    if do_check and bad:
        print(f"  РАСХОЖДЕНИЙ: {bad}. Фигуру правили, а карту в риге не обновили —\n"
              f"  движок кадрирует планы по устаревшим числам.\n")
        return 1
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default=str(ROOT / RIGS / "freeman_rig"))
    ap.add_argument("--all", action="store_true",
                    help="все риги в examples/assets/characters")
    ap.add_argument("--pose", default="",
                    help="по умолчанию — поза `measure` рига, иначе `idle`")
    ap.add_argument("--scale", type=float, default=0.90)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true",
                    help="записать замеренную карту в rig.json персонажа")
    a = ap.parse_args(argv)

    if a.all:
        dirs = sorted(d for d in (ROOT / RIGS).iterdir()
                      if (d / "rig.json").exists())
    else:
        dirs = [Path(a.rig)]

    bad = 0
    for d in dirs:
        bad += one_rig(d, a.pose or "idle", a.scale, a.check, a.write)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
