#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
turn.py — РАЗВОРОТ ФИГУРЫ СЧИТАЕТСЯ, А НЕ ПОДБИРАЕТСЯ.

Позы разворота (три четверти, профиль, полуспина, спина) я собирал руками:
каждое число — на глаз, каждая правка ломала соседнее. Плечо уезжало за
силуэт, нога вылезала из-под подола, дальняя рука пропадала в чёрном. Всё это
не вкусовые вопросы, а геометрия: у поворота вокруг вертикальной оси есть
формула, и из неё следует ВСЁ — что укоротится, что удлинится, что поднимется,
насколько сузится силуэт и куда уедет глаз.

Модель. Фигура — коробка шириной W и глубиной D, голова — цилиндр радиуса R,
глаза сидят на его окружности под углом ±φ от направления «вперёд».

  ширина силуэта       half(θ) = √((W/2)²cos²θ + (D/2)²sin²θ)
        фигура в плане — ЭЛЛИПС, а не коробка. Формула коробки
        (W/2·cos + D/2·sin) даёт на 45° силуэт ШИРЕ, чем анфас (259 против
        248) — у коробки на косом ракурсе действительно видно два борта сразу,
        у округлого тела нет. Первая версия модели считала по коробке, и
        полуповорот выходил толще анфаса.

  гнездо руки/ноги     x(θ) = x₀·cos θ
        всё, что отстоит от оси на x₀, проецируется в x₀·cos θ. Поэтому НОГИ
        НЕ ВЫЛЕЗАЮТ ЗА ПОДОЛ ни при каком угле: и гнездо, и подол сжимаются
        одним и тем же косинусом, а гнездо изначально внутри. Раньше подол
        сжимался, а гнёзда — нет, отсюда ноги «мимо» юбки.

  ближе/дальше         k(θ) = 1 ± k·sin θ
        слабая перспектива: ближняя половина крупнее, дальняя мельче. Отсюда
        разная длина ног, разный размер кистей и наклон плечевой дуги.

  глаз на голове       x = R·sin(α+θ),  ширина ∝ |cos(α+θ)|
        глаз едет к кромке и сплющивается по мере ухода за край; когда
        cos(α+θ) ≤ 0, глаз за головой и гасится. Ничего не надо решать
        отдельно «в профиль виден один глаз» — это следствие.

  ГОЛОВА ПОЧТИ НЕ СУЖАЕТСЯ. Замер оригинала: маска H/W 1.60–1.65 на 22 кадрах
  с одним видимым глазом — столько же, сколько анфас. Яйцо в плане круглое, а
  круг с любой стороны выглядит одинаково. Наши прежние 0.72 ширины в профиль
  были ошибкой: мы сужали голову как доску.

Использование:
    python3 tools/turn.py --list                 # какие позы сгенерирует
    python3 tools/turn.py --write                # записать в rig.json
"""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = ROOT / "examples/assets/characters/freeman_rig/rig.json"

# --- обмеры фигуры (в единицах torso.svg; сняты с рига и рендера) -----------
W = 248.0          # ширина плаща анфас (191 · масштаб кости 1.3)
D = 118.0          # глубина: ширина профильного рисунка torso_side
K = 0.16           # сила слабой перспективы (ближе крупнее)
EYE_PHI = 38.0     # угол глаза от направления «вперёд», градусов
DROP = 12.0        # насколько ближнее плечо опускается на полном профиле

SOCK_ARM = {"upper_arm_left": -125.0, "upper_arm_right": 79.0}
SOCK_LEG = {"thigh_left": -77.0, "thigh_right": 37.0}
EYE_X = {"eye_left": -33.0, "eye_right": 20.0}
EYE_SCALE = {"eye_left": (0.9, 1.07), "eye_right": (0.85, 1.0)}

# рисунок плаща по углу: у каждого своя нарисованная ширина
CLOAKS = [(30.0, None, W), (65.0, "torso_34", 155.0), (180.0, "torso_side", D)]


def half_width(deg):
    t = math.radians(deg)
    return math.hypot(W / 2 * math.cos(t), D / 2 * math.sin(t))


def cloak_for(deg):
    """Какой рисунок плаща и с каким масштабом даёт нужную ширину силуэта."""
    a = abs(deg) if abs(deg) <= 90 else 180 - abs(deg)
    for lim, part, drawn in CLOAKS:
        if a <= lim:
            return part, half_width(deg) * 2 / drawn
    return "torso_side", half_width(deg) * 2 / D


def turn_pose(name, deg, blank_face=False, head_tilt=0.0, head_squash=1.0):
    """Кости одной позы разворота. deg>0 — фигура повёрнута ВПРАВО."""
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    d = 1 if deg >= 0 else -1
    near = 1 + K * abs(s)          # ближняя половина
    far = 1 - K * abs(s)           # дальняя
    bones = {}

    part, sc = cloak_for(deg)
    bones["cloak"] = {"scale": [round(sc * (1 if deg >= 0 else -1), 3), 1.0]}
    if part:
        bones["cloak"]["part"] = part

    # голова: ширина почти не меняется (в плане круг), садится глубже к профилю
    bones["head"] = {
        "scale": [round(1.05 * (0.97 + 0.03 * abs(c)), 3),
                  round(1.05 * head_squash, 3)],
        "offset": [round(6 * s), round(66 + 40 * abs(s))],
        "rotation": round(head_tilt + 9 * s, 1),
    }
    if abs(deg) > 100:                       # затылок: черт лица нет
        blank_face = True
    if abs(deg) > 35:                        # плечо перекрывает низ головы
        bones["head"]["z_order"] = 1

    for eye, x0 in EYE_X.items():
        if blank_face:
            bones[eye] = {"scale": [0, 0]}
            continue
        # плановый угол глаза: знак по стороне головы
        alpha = math.radians((-EYE_PHI if x0 < 0 else EYE_PHI) + deg)
        vis = math.cos(alpha)
        if vis <= 0.12:                      # ушёл за голову
            bones[eye] = {"scale": [0, 0]}
            continue
        sx, sy = EYE_SCALE[eye]
        R = 46.0                             # радиус головы в плане
        bones[eye] = {
            "offset": [round(R * math.sin(alpha)), -121],
            "scale": [round(sx * vis, 3), round(sy, 3)],
        }
    bones["mouth"] = ({"scale": [0, 0]} if blank_face else
                      {"offset": [round(-22 * c + 30 * s), -56],
                       "scale": [round(max(0.35, abs(c)), 3), 1.0]})

    # руки: гнездо по косинусу, размер и высота по близости
    for arm, x0 in SOCK_ARM.items():
        is_near = (x0 > 0) == (deg >= 0)
        k = near if is_near else far
        fore = arm.replace("upper_arm", "forearm")
        # гнездо — на 62% полуширины, а не на краю: дуга плеч срезала углы, и
        # у самой кромки плеча под гнездом уже нет (замер CAMERA.md).
        hw = half_width(deg)
        bones[arm] = {
            "offset": [round((hw * 0.62) * (1 if x0 > 0 else -1)),
                       round((3 if x0 < 0 else 13) + DROP * s * (1 if is_near else -1))],
            "scale": [round(k, 3), round(k, 3)],
            "z_order": 4 if is_near else 1,
        }
        # локоть гнётся ТОЛЬКО к лицу: рука не складывается назад
        bones[fore] = {"rotation": round(34 * d * (1 if is_near else 0.6), 1)}

    # ноги: гнездо тем же косинусом — потому и не вылезают за подол
    for th, x0 in SOCK_LEG.items():
        is_near = (x0 > 0) == (deg >= 0)
        k = near if is_near else far
        sh = th.replace("thigh", "shin")
        bones[th] = {"offset": [round(x0 * c), round(172 - 8 * abs(s) * (0 if is_near else 1))],
                     "scale": [0.9, round(k, 3)]}
        bones[sh] = {"scale": [0.9, round(k, 3)]}
    return {"name": name, "transition_duration": 0.3, "bones": bones}


POSES = [
    ("chetvert_pravo", 45), ("chetvert_levo", -45),
    ("bok_pravo", 90), ("bok_levo", -90),
    ("polu_spina", 135), ("spina", 180),
]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)

    print(f"  {'поза':<18}{'угол':>6}{'полуширина':>12}{'плащ':>14}")
    for name, deg in POSES:
        part, sc = cloak_for(deg)
        print(f"  {name:<18}{deg:>6}{half_width(deg):>12.1f}"
              f"{(part or 'анфас') + f' ×{sc:.2f}':>14}")
    if not a.write:
        return 0

    rig = json.loads(RIG.read_text(encoding="utf-8"))
    for name, deg in POSES:
        p = turn_pose(name, deg,
                      head_tilt=(6 if abs(deg) > 100 else 0),
                      head_squash=(0.88 if abs(deg) > 100 else 1.0))
        rig["poses"][name] = p
    # шаг в профиль: профиль + ноги из шага
    for base, deg in (("bok_pravo", 90), ("bok_levo", -90)):
        for step in ("shag_levoj", "shag_pravoj"):
            q = json.loads(json.dumps(rig["poses"][base]))
            q["name"] = f"{base}_{step.split('_')[1]}"
            for leg in ("thigh_left", "thigh_right", "shin_left", "shin_right"):
                src = rig["poses"][step]["bones"].get(leg)
                if src:
                    keep = q["bones"].get(leg, {})
                    m = dict(src)
                    m["offset"] = keep.get("offset", m.get("offset"))
                    m["scale"] = keep.get("scale", m.get("scale"))
                    q["bones"][leg] = m
            rig["poses"][q["name"]] = q
    RIG.write_text(json.dumps(rig, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  записано поз разворота: {len(POSES) + 4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
