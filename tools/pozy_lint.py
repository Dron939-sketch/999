#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pozy_lint.py — ПОЗА, КОТОРАЯ ПОВТОРЯЕТ СОСЕДНЮЮ, БИБЛИОТЕКУ НЕ ПОПОЛНЯЕТ.

Требование студии: поз должно быть МНОГО, чтобы не повторяться, и чтобы зрителю
было ДОХОДЧИВО. Эти два требования тянут в разные стороны, и без мерки второе
проигрывает первому: наплодить имён легко, а каждое новое имя, читающееся как
уже существующее, делает библиотеку хуже — автор верит, что взял другой жест,
а в кадре тот же.

Так уже было. В риге 162 позы, из них 36 не использованы НИ РАЗУ, и часть — не
потому, что забыты, а потому, что дублируют соседние. Библиотека мимики
хранит два таких приговора, вынесенных ГЛАЗОМ: `ruki_skrestil` «рендерилась как
hips», `schitaet` «читается пятном». Оба верны, оба стоили работы, и оба можно
было получить машиной за минуту.

ЧТО МЕРЯЕТСЯ. Каждая поза снимается на том же стенде, что осанка и разворот
(один масштаб, один якорь), и приводится к силуэту — чёрному пятну фигуры.
Дальше считается IoU (пересечение к объединению) каждой пары. Это ровно то, что
видит зритель: у Фримена плащ — сплошная заливка, лицо — белая маска, и жест
существует в кадре только тем, что ТОРЧИТ из силуэта.

ПОЧЕМУ IoU, А НЕ «РАЗНЫЕ УГЛЫ КОСТЕЙ». Углы врут в обе стороны. Рука, поднятая
на 30°, и она же на 45° дают разные числа и один силуэт: обе внутри плаща.
А `vdal` и `palec_vverh` отличаются одним суставом и читаются как совершенно
разные высказывания. Мерить надо там, где живёт дефект, — в кадре.

ПОРОГИ СНЯТЫ С БИБЛИОТЕКИ. У пар, которые студия и авторы считают РАЗНЫМИ,
IoU держится ниже ~0.80; пара `zakrylsya`/`hips`, которую библиотека прямо
называет спорной, даёт 0.59 и оставлена сознательно. Порог 0.88 — выше него
пара неразличима на глаз, и это уже не два жеста, а один с двумя именами.

ЗЕРКАЛА СЧИТАЮТСЯ РАЗНЫМИ И ЭТО НЕ ПОБЛАЖКА. `vdal` вправо и `vdal_l` влево
дают низкий IoU честно — силуэт другой. Для зрителя это тоже разные жесты:
смена стороны читается как новый удар, и ровно этим лечится «повторяется».

Использование:
    python3 tools/pozy_lint.py                    # все жестовые позы
    python3 tools/pozy_lint.py --new palec_vverh vdal_l   # только эти против всех
    python3 tools/pozy_lint.py --face             # мимические слои, не силуэт
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from karta import ROOT, render                            # noqa: E402

RIG_DIR = ROOT / "examples/assets/characters/freeman_rig"
RIG = RIG_DIR / "rig.json"

# Кости тела: поза, которая их не трогает, силуэта не меняет и здесь не судится
# (мимику меряют глазами и по смыслу, а не по пятну).
BODY_BONES = frozenset((
    "torso", "cloak",
    "upper_arm_left", "forearm_left", "hand_left",
    "upper_arm_right", "forearm_right", "hand_right",
    "thigh_left", "shin_left", "thigh_right", "shin_right",
))
VISEMES = frozenset(("visA", "visB", "visC", "visD", "visE", "visF",
                     "visC_acc", "visD_acc", "visE_acc", "talk", "gab"))

BLIZKO = 0.88        # выше — пара неразличима, это один жест с двумя именами
POHOZHE = 0.82       # выше — стоит посмотреть глазами

# Стенд: те же числа, что у гейта осанки, — один масштаб и один якорь на все
# позы, иначе силуэты несравнимы.
STAND_Y, STAND_S = 0.60, 0.90


def poses(rig=RIG):
    return json.loads(Path(rig).read_text(encoding="utf-8"))["poses"]


def gesture_names(p):
    """Позы, которые двигают ТЕЛО, — только их и судим по силуэту."""
    return sorted(n for n, v in p.items()
                  if n not in VISEMES and set(v.get("bones", {})) & BODY_BONES)


def silhouette(name):
    """Силуэт позы на стенде: булева маска чернил."""
    return np.asarray(render(str(RIG_DIR), name, STAND_Y, STAND_S)) < 200


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def main(argv):
    ap = argparse.ArgumentParser(
        description="Ищет позы, неразличимые по силуэту")
    ap.add_argument("--new", nargs="*", default=None,
                    help="проверить только эти позы против всех остальных")
    ap.add_argument("--porog", type=float, default=POHOZHE,
                    help=f"печатать пары выше этого IoU (по умолчанию {POHOZHE})")
    args = ap.parse_args(argv)

    p = poses()
    names = gesture_names(p)
    print(f"\n  СИЛУЭТЫ: ПОЗА НЕ ДОЛЖНА ПОВТОРЯТЬ СОСЕДНЮЮ\n")
    print(f"  снимаю {len(names)} жестовых поз на стенде "
          f"(мимика силуэта не трогает и здесь не судится)…")
    masks = {}
    for i, n in enumerate(names, 1):
        try:
            masks[n] = silhouette(n)
        except SystemExit as e:
            print(f"    ✗ {n}: {e}")
        if i % 20 == 0:
            print(f"    …{i}/{len(names)}")

    check = [n for n in (args.new or names) if n in masks]
    pairs = []
    for a in check:
        for b in masks:
            if a >= b and not args.new:
                continue
            if a == b:
                continue
            v = iou(masks[a], masks[b])
            if v >= args.porog:
                pairs.append((v, a, b))
    pairs.sort(reverse=True)

    hard = [x for x in pairs if x[0] >= BLIZKO]
    for v, a, b in pairs:
        mark = "✗ ОДНО И ТО ЖЕ" if v >= BLIZKO else "· похоже"
        print(f"    {mark:16} {a:18} ~ {b:18} IoU {v:.3f}")
    if not pairs:
        print("    ✓ неразличимых пар нет — каждая поза читается своим силуэтом.")
    print(f"\n  Пар выше {BLIZKO}: {len(hard)}; выше {args.porog}: {len(pairs)}.")
    if hard:
        print("  Поза, повторяющая соседнюю, библиотеку не пополняет — она\n"
              "  пополняет кладбище неиспользуемых имён (RABOTA §XII).")
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
