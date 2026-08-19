#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mouth_ownership.py — РОТ ПРИНАДЛЕЖИТ РЕЧИ, А НЕ ПОЗЕ ТЕЛА.

Зачем. Липсинк кладётся СЛОЕМ поверх позы тела (renderer::resolve_effective_
pose), а полная поза этот слой СБРАСЫВАЕТ: базой становится она сама. Пока рот
задавали и позы тела, и липсинк, они дрались за одну кость — на каждой смене
позы посреди реплики рот прыгал на рот позы и держался до следующего флэпа.
Со стороны это читается ровно так, как сказал режиссёр: «лицо и рот не всегда
соответствуют озвучке».

Правило завода: **у поз, которые двигают ТЕЛО, кости `mouth` быть не должно**.
Рот ведут только речь (виземы/флэпы) и мимические слои, которые тела не
касаются. Исключение одно и оно про рисунок, а не про мимику: ракурсы со спины
и в профиль подменяют САМ РИСУНОК рта (`mouth_side`) или прячут его (scale 0) —
там кость обязана остаться, иначе на профиле будет анфасный рот.

Что делает скрипт:
    --check   гейт: печатает нарушителей и выходит с кодом 1
    --fix     снимает `mouth` у поз тела (кроме исключений) и переписывает риг

Использование:
    python3 tools/mouth_ownership.py --check
    python3 tools/mouth_ownership.py --fix
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = ROOT / "examples/assets/characters/freeman_rig/rig.json"

# Кости тела: если поза трогает хоть одну, это поза тела, а не мимика.
BODY = {
    "upper_arm_left", "upper_arm_right", "forearm_left", "forearm_right",
    "thigh_left", "thigh_right", "shin_left", "shin_right",
    "torso", "cloak", "hand_left", "hand_right",
}
# Рисунки рта, которые ставит РАКУРС, а не мимика: их снимать нельзя.
VIEW_PARTS = {"mouth_side", "mouth_34"}


def offenders(rig):
    """Позы тела, которые лезут в рот мимикой. → [(имя, что стоит)]"""
    bad = []
    for name, pose in rig.get("poses", {}).items():
        bones = pose.get("bones", {})
        if not set(bones) & BODY:
            continue                      # мимический слой — ему рот положен
        track = bones.get("mouth")
        if track is None:
            continue
        if track.get("part") in VIEW_PARTS:
            continue                      # ракурсный рисунок рта
        if track.get("scale") == [0, 0]:
            continue                      # рот спрятан (спина) — это не мимика
        bad.append((name, track.get("part") or "<без part>"))
    return sorted(bad)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default=str(RIG))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args(argv)

    path = Path(a.rig)
    rig = json.loads(path.read_text(encoding="utf-8"))
    bad = offenders(rig)

    if a.fix:
        for name, _ in bad:
            rig["poses"][name]["bones"].pop("mouth", None)
        path.write_text(json.dumps(rig, ensure_ascii=False, indent=4) + "\n",
                        encoding="utf-8")
        print(f"  снят рот у {len(bad)} поз тела — рот теперь ведёт только речь")
        return 0

    print("\n  РОТ И ПОЗЫ ТЕЛА\n")
    if not bad:
        print("    [OK] ни одна поза тела не спорит с липсинком за рот\n")
        return 0
    for name, part in bad:
        print(f"    [ПРОВАЛ] поза тела «{name}» ставит рот {part}")
    print(f"\n  Нарушителей: {len(bad)}. Чинится: "
          f"python3 tools/mouth_ownership.py --fix")
    print("  Почему это ошибка — в шапке этого файла.\n")
    return 1 if a.check else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
