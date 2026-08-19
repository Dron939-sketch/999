#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
posture.py — ГЕЙТ ОСАНКИ: персонаж не приседает и не садится в кадре.

Замечание студии повторялось трижды: «не должно быть нигде, где он сидит»,
«на корточки не садится — некрасиво в кадре». Каждый раз это чинилось руками:
находили позу, меняли на другую, через ролик всплывала соседняя. Проблема в
том, что «сидит» — это не имя позы, а ИЗМЕРИМОЕ СВОЙСТВО: у фигуры падает
макушка при неподвижных ступнях. Поза может называться как угодно —
`bow`, `hunch`, `za_golovu`, — важно, на сколько она роняет рост.

ЧТО МЕРЯЕТСЯ. Каждая поза, которую сценарий реально играет, снимается на том
же стенде, что и разворот (общий рендер, один масштаб, один якорь). Берём
высоту макушки над ступнями и делим на ту же высоту у эталона `calm`. Ниже
порога — фигура просела: колени согнулись, корпус ушёл вниз, и на экране это
читается приседанием независимо от того, что задумывал автор позы.

ПОЧЕМУ НЕ СПИСОК ЗАПРЕЩЁННЫХ ИМЁН. Список нужно пополнять руками, он не ловит
новые позы и врёт на старых: `sit` честно называет себя сидением и в роликах
не используется, а роняет фигуру `bow`, которая называется «поклон». Мерка
ловит обе и не требует ведения списка.

ПОРОГ. 0.92 — падение больше 8% роста. Пять процентов даёт естественная
сутулость и наклон головы (`think`, `hunch`), их запрещать нельзя: это
характер. Восемь и больше — уже подсев в коленях.

Использование:
    python3 tools/posture.py examples/lektorij/foo.anim
    python3 tools/posture.py --all
"""

import argparse
import glob
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from karta import ROOT, render                     # noqa: E402
import numpy as np                                 # noqa: E402

POSE = re.compile(r'^\s*\S+\s+(?:pose|overlays)\s+"([^"]+)"')
IMPORT = re.compile(r'import\s+character\s+(\S+)\s+from\s+"([^"]+)"')
BASE = "calm"
FLOOR = 0.92          # доля роста эталона, ниже которой поза считается присевшей


def height(rig_dir, pose):
    """Высота макушки над ступнями на стенде, в пикселях кадра."""
    g = render(rig_dir, pose, 0.60, 0.90)
    ink = g < 90
    ys, _ = np.nonzero(ink)
    if not len(ys):
        return None
    return int(ys.max() - ys.min() + 1)


def used_poses(path):
    """Позы, которые сценарий реально играет (и полные, и слои)."""
    names = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = POSE.match(line)
        if m and m.group(1) not in names:
            names.append(m.group(1))
    return names


def rig_of(path):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = IMPORT.search(line)
        if m:
            return (Path(path).parent / m.group(2)).resolve()
    return None


def check(path):
    rig = rig_of(path)
    if rig is None or not (rig / "rig.json").exists():
        return [], []
    base = height(rig, BASE)
    if not base:
        return [], []
    rows, bad = [], []
    for name in used_poses(path):
        h = height(rig, name)
        if h is None:
            continue
        r = h / base
        rows.append((name, r))
        if r < FLOOR:
            bad.append((name, r))
    return rows, bad


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)

    files = a.files
    if a.all or not files:
        files = sorted(glob.glob(str(ROOT / "examples/**/*.anim"), recursive=True))
        files = [f for f in files if not Path(f).name.startswith((".", "_"))]

    total = 0
    print("\n  ОСАНКА — рост позы к эталону «calm»\n")
    for f in files:
        rows, bad = check(f)
        if not rows:
            continue
        name = Path(f).name
        if bad:
            print(f"    {name}:")
            for pose, r in bad:
                print(f"      [ПРОВАЛ] «{pose}»: рост {r:.2f} эталона — "
                      f"фигура присела (порог {FLOOR})")
            total += len(bad)
        else:
            print(f"    [OK] {name}: {len(rows)} поз(ы), ни одна не роняет рост")
        if a.verbose:
            for pose, r in sorted(rows, key=lambda x: x[1]):
                print(f"        {pose:<24}{r:.2f}")
    if total:
        print(f"\n  Присевших поз: {total}. Почему это ошибка — в шапке файла.\n")
        return 1
    print("\n  Все позы держат рост.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
