#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sockets.py — КРЕПЛЕНИЯ РУК И НОГ ПРОВЕРЯЮТСЯ СЧЁТОМ, А НЕ ГЛАЗАМИ.

Каждый раз, когда мы меняли ширину плаща или рост, где-нибудь отрывалась рука:
гнездо оставалось на прежнем месте, силуэт уезжал, и на одном кадре это было
видно, а на сорока других — нет. Смотреть все позы глазами нельзя: их 122, и
руки в них подняты, вытянуты, заведены за спину.

Проверка чисто геометрическая, рендер не нужен. Для каждой позы:

  · берётся ДЕЙСТВУЮЩИЙ рисунок плаща (поза может подменить torso на
    torso_side или torso_34) и его масштаб в этой позе;
  · контур рисунка переводится в систему кости `torso`: (x−110)·sx, (y−16)·sy;
  · берётся ДЕЙСТВУЮЩЕЕ гнездо руки/ноги (поза может его переопределить);
  · на высоте гнезда меряются кромки силуэта, и считается, насколько гнездо
    внутри — в долях полуширины на этой высоте.

  запас 1.0  — гнездо на оси фигуры;
  запас 0.0  — гнездо ровно на кромке;
  запас < 0  — ГНЕЗДО СНАРУЖИ: рука растёт из воздуха.

Порог. Гнездо на самой кромке — ещё не отрыв: плечевой пучок нарисован вокруг
гнезда и перекрывает стык. Но запас меньше −0.08 уже виден как щель, поэтому
это провал. Зеркальные позы (отрицательный torso.scale.x) проверяются по
модулю: зеркало не меняет отношения гнезда к силуэту.

    python3 tools/sockets.py            # только провалы
    python3 tools/sockets.py --all      # все позы
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG_DIR = ROOT / "examples/assets/characters/freeman_rig"
FAIL = -0.08

SOCKETS = {
    "upper_arm_left": "плечо L",
    "upper_arm_right": "плечо R",
    "thigh_left": "бедро L",
    "thigh_right": "бедро R",
}


# --- плоский разбор svg-контура ---------------------------------------------
def _tokens(d):
    out = []
    for c, n in re.findall(r"([MmCcLlZzHhVvSsQqAa])|(-?\d*\.?\d+(?:[eE]-?\d+)?)", d):
        out.append(c if c else float(n))
    return out


def flatten(d, steps=20):
    st = _tokens(d)
    pts, cur, start, cmd, i = [], (0.0, 0.0), (0.0, 0.0), None, 0
    while i < len(st):
        if isinstance(st[i], str):
            cmd = st[i]; i += 1
            if cmd in "Zz":
                cur = start; pts.append(cur)
            continue
        rel, C = cmd.islower(), cmd.upper()
        if C == "M":
            x, y = st[i], st[i + 1]; i += 2
            if rel: x += cur[0]; y += cur[1]
            cur = (x, y); start = cur; pts.append(cur); cmd = "l" if rel else "L"
        elif C == "L":
            x, y = st[i], st[i + 1]; i += 2
            if rel: x += cur[0]; y += cur[1]
            cur = (x, y); pts.append(cur)
        elif C == "H":
            x = st[i]; i += 1
            if rel: x += cur[0]
            cur = (x, cur[1]); pts.append(cur)
        elif C == "V":
            y = st[i]; i += 1
            if rel: y += cur[1]
            cur = (cur[0], y); pts.append(cur)
        elif C == "C":
            x1, y1, x2, y2, x, y = st[i:i + 6]; i += 6
            if rel:
                x1 += cur[0]; y1 += cur[1]; x2 += cur[0]; y2 += cur[1]
                x += cur[0]; y += cur[1]
            p = cur
            for k in range(1, steps + 1):
                s = k / steps; u = 1 - s
                pts.append((u ** 3 * p[0] + 3 * u * u * s * x1 + 3 * u * s * s * x2 + s ** 3 * x,
                            u ** 3 * p[1] + 3 * u * u * s * y1 + 3 * u * s * s * y2 + s ** 3 * y))
            cur = (x, y)
        elif C == "Q":
            x1, y1, x, y = st[i:i + 4]; i += 4
            if rel: x1 += cur[0]; y1 += cur[1]; x += cur[0]; y += cur[1]
            p = cur
            for k in range(1, steps + 1):
                s = k / steps; u = 1 - s
                pts.append((u * u * p[0] + 2 * u * s * x1 + s * s * x,
                            u * u * p[1] + 2 * u * s * y1 + s * s * y))
            cur = (x, y)
        else:
            i += 1
    return pts


_CACHE = {}


def _xform(attrs):
    """(sx, sy, tx, ty) из transform группы; поддержаны translate и scale."""
    sx = sy = 1.0
    tx = ty = 0.0
    m = re.search(r"translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)", attrs)
    if m:
        tx, ty = float(m.group(1)), float(m.group(2))
    m = re.search(r"scale\(\s*([-\d.]+)(?:[ ,]+([-\d.]+))?\s*\)", attrs)
    if m:
        sx = float(m.group(1))
        sy = float(m.group(2)) if m.group(2) else sx
    return sx, sy, tx, ty


def outline(part):
    """Контур рисунка плаща в координатах его viewBox.

    Группы с transform обязаны учитываться: обводки подола и щетины у нас
    трассированные, они лежат в группе `translate(...) scale(0.1,-0.1)`. Без
    учёта трансформы контур torso.svg уезжал до x=2071 при viewBox шириной
    220, кромки считались по мусору, и проверка «проваливала» бёдра там, где
    они на самом деле глубоко внутри силуэта.
    """
    if part in _CACHE:
        return _CACHE[part]
    txt = (RIG_DIR / f"{part}.svg").read_text(encoding="utf-8")
    txt = re.sub(r"<clipPath.*?</clipPath>", "", txt, flags=re.S)
    txt = re.sub(r"<defs>.*?</defs>", "", txt, flags=re.S)

    pts = []
    pos = 0
    stack = []          # (конец группы, sx, sy, tx, ty) — накопленная трансформа
    for m in re.finditer(r"<g([^>]*)>|</g>|<path[^>]*\sd=\"([^\"]+)\"", txt):
        tok = m.group(0)
        if tok.startswith("<g"):
            sx, sy, tx, ty = _xform(m.group(1))
            if stack:
                psx, psy, ptx, pty = stack[-1]
                stack.append((psx * sx, psy * sy, ptx + psx * tx, pty + psy * ty))
            else:
                stack.append((sx, sy, tx, ty))
        elif tok == "</g>":
            if stack:
                stack.pop()
        else:
            sx, sy, tx, ty = stack[-1] if stack else (1.0, 1.0, 0.0, 0.0)
            pts += [(x * sx + tx, y * sy + ty) for x, y in flatten(m.group(2))]
    _CACHE[part] = pts
    return pts


def edges_at(pts, y):
    """Кромки контура на высоте y — ПО ПЕРЕСЕЧЕНИЯМ ОТРЕЗКОВ, а не по точкам.

    Полоска «все точки в ±8 по y» зависит от того, как густо лёг контур: на
    рваном подоле вершины зубцов редкие, и на иной высоте в полоску попадал
    один-единственный зубец. Полуширина выходила ~0, запас улетал в −6839, и
    проверка «проваливала» сидячую позу, где бёдра на самом деле внутри.
    Пересечения отрезков от густоты не зависят.
    """
    xs = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if (y1 - y) * (y2 - y) <= 0 and y1 != y2:
            t = (y - y1) / (y2 - y1)
            xs.append(x1 + t * (x2 - x1))
    return (min(xs), max(xs)) if xs else None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="печатать все позы, не только провалы")
    a = ap.parse_args(argv)

    rig = json.loads((RIG_DIR / "rig.json").read_text(encoding="utf-8"))

    # значения по умолчанию из скелета
    defaults, pivots = {}, {}

    def walk(n):
        defaults[n["name"]] = n
        for c in n.get("children", []):
            walk(c)

    walk(rig["skeleton"]["root"])
    cloak_pivot = defaults["cloak"]["pivot"]
    cloak_def = defaults["cloak"]

    rows, bad = [], 0
    for name, pose in sorted(rig["poses"].items()):
        b = pose["bones"]
        cb = b.get("cloak", {})
        part = cb.get("part") or cloak_def.get("part")
        sx, sy = cb.get("scale") or cloak_def["scale"]
        pts = outline(part)
        for bone, label in SOCKETS.items():
            pb = b.get(bone, {})
            if pb.get("scale") == [0, 0]:
                continue                       # кость погашена — крепить нечего
            ox, oy = pb.get("offset") or defaults[bone]["offset"]
            # высота гнезда в системе рисунка плаща
            y_draw = oy / sy + cloak_pivot[1] if sy else cloak_pivot[1]
            e = edges_at(pts, y_draw)
            if not e:
                continue                       # выше или ниже рисунка — не про плащ
            # ЗНАК МАСШТАБА УЧИТЫВАЕТСЯ: у зеркального плаща (sx<0) кромки
            # меняются местами. Раньше стоял abs(), и проверка мерила
            # незеркальный силуэт — на полуспине это давало ложный провал.
            left = (e[0] - cloak_pivot[0]) * sx
            right = (e[1] - cloak_pivot[0]) * sx
            if left > right:
                left, right = right, left
            half = (right - left) / 2
            mid = (right + left) / 2
            if half < 1e-6:
                continue                       # контур на этой высоте вырожден
            # запас = насколько гнездо не доходит до кромки, в долях полуширины
            slack = 1.0 - abs(ox - mid) / half
            rows.append((name, label, part, round(ox, 1), round(slack, 3)))
            if slack < FAIL:
                bad += 1

    print(f"  {'поза':<26}{'кость':<9}{'плащ':<12}{'гнездо':>8}{'запас':>8}")
    for name, label, part, ox, slack in rows:
        if a.all or slack < FAIL:
            mark = "  ПРОВАЛ" if slack < FAIL else ""
            print(f"  {name:<26}{label:<9}{part:<12}{ox:>8}{slack:>8.2f}{mark}")
    print(f"\n  проверено креплений: {len(rows)}, снаружи силуэта: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
