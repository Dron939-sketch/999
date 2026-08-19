#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
walk.py — ХОДЬБА В ПРОФИЛЬ: шаговый цикл, речь на ходу, чистая остановка.

Позы шага раньше делал сам turn.py: брал ноги из анфасных `shag_*` и
подставлял их в профиль. Получался не шаг, а подёргивание — по трём причинам,
и все три чинятся здесь.

1. ОДНА НОГА. В профиле дальняя нога погашена масштабом [0,0] — правильно для
   руки (её корпус перекрывает целиком), неправильно для ноги: нога торчит
   НИЖЕ подола, прятать нечего. Фигура с одной ногой не шагает, а скользит
   боком. Шаг читается ТОЛЬКО парой в противофазе: одна впереди, другая
   позади, и на следующем кадре наоборот. Дальняя нога теперь живёт в самом
   профиле (turn.py), а здесь она получает свой поворот.

2. РУКИ НЕ ХОДЯТ. Мах руки — не украшение: при ходьбе плечевой пояс
   отрабатывает шаг, и без него фигура выглядит подвешенной за макушку.
   Ближняя рука машет в противофазе к ближней ноге, амплитуда 1.8 от базовой
   (мах меньше — не читается на общем плане), предплечье догоняет с обратным
   знаком в 0.9: локоть не заламывается.

3. РЕЧЬ НА ХОДУ ЛОМАЛА РОТ. Шаг — это смена ПОЛНОЙ позы, а полная поза
   сбрасывает наложенные слои (renderer::resolve_effective_pose), в том числе
   липсинк: рот прыгал на каждом шаге. Поэтому шаг существует ДВАЖДЫ:
     · полными позами `bok_*_levoj` / `bok_*_pravoj` — для молчаливой ходьбы;
     · слоями `shag_bok_levoj` / `shag_bok_pravoj` — для ходьбы С РЕЧЬЮ.
   Слой трогает только ноги и руку, рта не касается — липсинк остаётся
   хозяином рта, и персонаж говорит НА ХОДУ, а не между проходами.

ГОЛОВА К ЗРИТЕЛЮ. Профиль хорош для движения и плох для речи: сбоку от лица
видно один глаз и половину рта, говорящая фигура читается как отвернувшаяся.
Позы `bok_*_govorit` ставят корпус в профиль, а маску — в три четверти к
зрителю: тело идёт туда, куда идёт, лицо обращено к нам. Маска берётся
целиком из готового ракурса `chetvert_*` (там она уже выверена гейтом
разворота), меняется только посадка — она остаётся профильной, вынесенной
вперёд.

ОСТАНОВКА. Слои накапливаются, и брошенный слой шага остаётся на фигуре:
персонаж «доигрывает» полушаг уже стоя. Останавливать проход обязана ПОЛНАЯ
поза — она слои сбрасывает. Гейт `--check` ловит проходы, после которых
слой шага остался висеть.

Использование:
    python3 tools/walk.py            # что получится
    python3 tools/walk.py --write    # записать шаговые позы в rig.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = ROOT / "examples/assets/characters/freeman_rig/rig.json"

# ФАЗЫ ШАГА. Ключ — какая нога идёт вперёд; `near` это ближняя к зрителю нога
# (thigh_right/shin_right), `far` — дальняя (thigh_left/shin_left).
# Бедро и голень В ПРОТИВОФАЗЕ друг к другу: бедро выносит ногу, голень её
# догоняет. Без этого нога идёт прямой палкой и «раскидывается» в конце
# прохода — ровно то, на что жаловалась студия.
WALK = {
    "levoj":  dict(near=(18, -20), far=(-22, 16), arm=-24),
    "pravoj": dict(near=(-24, 18), far=(18, -18), arm=22),
}
# МАХ СЧИТАЕТСЯ ОТ ПОКОЯ, А НЕ ОТ НУЛЯ. Рука в профиле висит с поворотом 13°
# — вдоль заваленной вперёд кромки плаща, — и мах, отсчитанный от нуля, ронял
# её из этого положения в −43°: плечо выносило руку далеко перед корпусом, а
# кисть повисала в воздухе отдельным пятном. Качаем ВОКРУГ покоя.
# 1.0, а не 1.8: амплитуда 1.8 (±43°) на длинной руке даёт не шаг, а взмах
# семафора. ±24° от покоя — рука ходит вдоль корпуса, кисть не отрывается.
ARM_SWING = 1.0      # мах плеча к базовой амплитуде
FOREARM = -0.45      # предплечье догоняет плечо с обратным знаком

LEGS = ("thigh_right", "shin_right", "thigh_left", "shin_left")
ARMS = ("upper_arm_right", "forearm_right")


def step_bones(base, phase):
    """Кости шага поверх базового профиля: ноги + ближняя рука."""
    w = WALK[phase]
    b = {}
    for bone, rot in (("thigh_right", w["near"][0]), ("shin_right", w["near"][1]),
                      ("thigh_left", w["far"][0]), ("shin_left", w["far"][1])):
        src = dict(base["bones"].get(bone, {}))
        src["rotation"] = rot
        b[bone] = src
    up = dict(base["bones"].get("upper_arm_right", {}))
    rest_up = up.get("rotation", 0)
    up["rotation"] = round(rest_up + w["arm"] * ARM_SWING, 1)
    b["upper_arm_right"] = up
    fore = dict(base["bones"].get("forearm_right", {}))
    rest_fore = fore.get("rotation", 0)
    fore["rotation"] = round(rest_fore + w["arm"] * FOREARM, 1)
    b["forearm_right"] = fore
    return b


def to_viewer(base, quarter):
    """Профиль корпусом, маска — в три четверти к зрителю.

    Из `chetvert_*` берём саму маску (размер, глаза, рот), из профиля —
    ПОСАДКУ: голова остаётся вынесенной вперёд, как ей и положено на этом
    ракурсе. Рот приходит фронтальный (`mouth_34`), и это главное: липсинк
    подменяет часть рта своими виземами, а профильный `mouth_side` виземами
    не бывает — говорящий профиль всегда молотил одной дугой.
    """
    q = json.loads(json.dumps(base))
    head = json.loads(json.dumps(quarter["bones"]["head"]))
    head.pop("part", None)                       # анфасная маска, не head_side
    head["offset"] = list(base["bones"]["head"]["offset"])
    head["z_order"] = 5
    q["bones"]["head"] = head
    for bone in ("eye_left", "eye_right", "mouth"):
        q["bones"][bone] = json.loads(json.dumps(quarter["bones"][bone]))
    return q


def build(rig):
    P = rig["poses"]
    made = {}
    for side in ("pravo", "levo"):
        base = P.get(f"bok_{side}")
        quarter = P.get(f"chetvert_{side}")
        if not base or not quarter:
            continue
        # 1. молчаливая ходьба: полные позы
        for phase in WALK:
            q = json.loads(json.dumps(base))
            q["name"] = f"bok_{side}_{phase}"
            q["bones"].update(step_bones(base, phase))
            made[q["name"]] = q
        # 2. речь на ходу: тот же корпус, маска к зрителю
        talk = to_viewer(base, quarter)
        talk["name"] = f"bok_{side}_govorit"
        made[talk["name"]] = talk
        for phase in WALK:
            q = json.loads(json.dumps(talk))
            q["name"] = f"bok_{side}_govorit_{phase}"
            q["bones"].update(step_bones(base, phase))
            made[q["name"]] = q

    # 3. ШАГ СЛОЕМ — один на оба направления. Зеркало живёт в кости `torso`
    #    (масштаб по x со знаком минус), а слой её не трогает: те же повороты
    #    ног и руки работают в обе стороны.
    base = P.get("bok_pravo")
    if base:
        for phase in WALK:
            made[f"shag_bok_{phase}"] = {
                "name": f"shag_bok_{phase}",
                "transition_duration": 0.12,
                "bones": step_bones(base, phase),
            }
    return made


def check_anim(paths):
    """Проходы, после которых слой шага остался висеть на фигуре."""
    import re
    bad = []
    layer = re.compile(r'^\s*(\S+)\s+overlays\s+"(shag_bok_\w+)"')
    full = re.compile(r'^\s*(\S+)\s+pose\s+"')
    for p in paths:
        lines = Path(p).read_text(encoding="utf-8").splitlines()
        pending = {}                      # сущность → строка последнего слоя шага
        for i, t in enumerate(lines, 1):
            m = layer.match(t)
            if m:
                pending[m.group(1)] = i
                continue
            m = full.match(t)
            if m:
                pending.pop(m.group(1), None)
        for who, ln in pending.items():
            bad.append((p, ln, f"«{who}»: слой шага не снят полной позой — "
                               f"фигура доигрывает полушаг стоя"))
    return bad


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", nargs="*", metavar="ANIM")
    a = ap.parse_args(argv)

    if a.check is not None:
        import glob
        files = a.check or sorted(glob.glob(str(ROOT / "examples/**/*.anim"),
                                            recursive=True))
        bad = check_anim(files)
        print("\n  ОСТАНОВКА ПОСЛЕ ПРОХОДА\n")
        for p, ln, msg in bad:
            print(f"    [ПРОВАЛ] {Path(p).name}:{ln}: {msg}")
        if bad:
            print(f"\n  Нарушений: {len(bad)}.\n")
            return 1
        print("    [OK] проходы закрыты полной позой\n")
        return 0

    rig = json.loads(RIG.read_text(encoding="utf-8"))
    made = build(rig)
    if a.write:
        rig["poses"].update(made)
        RIG.write_text(json.dumps(rig, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print("  ШАГОВЫЙ ЦИКЛ\n")
    for name in sorted(made):
        kind = "слой" if name.startswith("shag_") else "поза"
        print(f"    {kind}  {name}")
    print(f"\n  {'записано' if a.write else 'посчитано'}: {len(made)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
