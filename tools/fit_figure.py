#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fit_figure.py — ОТКЛЮЧЁН. Скрипт, которым испортили персонажа.

ЧТО ОН ДЕЛАЛ. Сводил голову и плечи рига к «измеренным» долям роста: маску к
0.287, линию плеч к 0.234. Отработал ровно как задумано — итерации сошлись,
приёмщик разворота остался зелёным, планка взята. Результат: голова уменьшена
в 1.75 раза (0.375 → 0.257 роста), и персонаж перестал быть похож на себя.

ПОЧЕМУ. Цель 0.287 снята `tools/original_ref.py` со сломанным отбором кадров:
в замер лезли стол, слипшийся с плащом, нарисованная рамка вместо лица и
костёр рядом с фигурой. С починенным отбором оригинал даёт 0.344 при разбросе
0.289…0.381 — то есть ПОЛОСУ, а не число, и риг с его 0.375 лежал внутри неё.
Правка не требовалась вовсе. Подробности — в шапке `original_ref.py` и в
`RULES.md` рига.

ПОЧЕМУ ФАЙЛ НЕ УДАЛЁН. Механика в нём рабочая и небанальная: итеративный подбор
масштаба (доля меняется нелинейно, потому что уменьшая голову, уменьшаешь и
рост), свип пластины плеч с прямым замером на готовом кадре, отдельная посадка
затылка. Если однажды пропорции ДЕЙСТВИТЕЛЬНО понадобится править, это делается
так. Но запускать его можно только с целями, которые проверены глазами на
сравнении с оригиналом, — поэтому константы целей стёрты, а не оставлены
«на всякий случай».

ЧТОБЫ ВКЛЮЧИТЬ ОБРАТНО: задать TARGET_MASK_H и TARGET_SHOULDER своими числами,
и перед этим прогнать
    python3 tools/original_ref.py <видео> --sheet /tmp/sheet.png
и ПОСМОТРЕТЬ лист: что прибор принял за фигуру и за маску. Без этого листа
любое число отсюда — фантазия, выглядящая как замер.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from karta import ROOT, render  # noqa: E402
from turnaround import flood_background, label  # noqa: E402

RIG = ROOT / "examples/assets/characters/freeman_rig"
RIG_JSON = RIG / "rig.json"
TORSO = RIG / "torso.svg"

# ЦЕЛИ. Оба числа измерены, источники разные и независимые.
# ЦЕЛИ СТЁРТЫ НАМЕРЕННО — см. шапку. Прежние значения (0.287 и 0.234) увели
# персонажа за полосу оригинала; оставлять их закомментированными нельзя,
# раскомментируют.
TARGET_MASK_H = None
TARGET_SHOULDER = None

# Рисунки головы, которые НЕ подчиняются общему множителю: у них своя
# геометрия и свои условия приёмки (см. scale_head).
BACK_PARTS = {"head_back"}

# Спинные позы: множитель тот же (голова — один предмет, и сзади она обязана
# быть того же размера), но посадка своя, и её решает свип.
BACK_POSES = ("spina", "polu_spina")
CROWN_TOL = 0.010          # доля роста; у гейта разброс ≤0.03 на ВЕСЬ лист
SEAT_SWEEP = range(-10, 61, 2)   # свип посадки затылка, единицы рига

POSE = "calm"              # эталон анфаса (у idle опущена голова, см. turnaround)


def measure():
    """Замер готового кадра: (рост, доля маски по высоте, доля линии плеч)."""
    g = render(str(RIG), POSE, 0.62, 1.0)
    dark = g < 90
    ys = np.nonzero(dark)[0]
    top, H = int(ys.min()), int(ys.max() - ys.min() + 1)
    white = g > 200
    inner = white & ~flood_background(white)
    lab = label(inner)
    if not lab.max():
        return H, None, None
    best = max((int((lab == i).sum()), i) for i in range(1, lab.max() + 1))
    my, mx = np.nonzero(lab == best[1])
    mask_h = (my.max() - my.min() + 1) / H

    # ЛИНИЯ ПЛЕЧ — где ПЛАЩ выходит на полную ширину, и мерить надо БЕЗ РУК.
    # Первая версия брала самую широкую строку всего силуэта и выдала 0.748 —
    # это низ фигуры: с опущенными руками самое широкое место приходится на
    # кисти, а не на плечи. Цель 0.234 снята с плаща болвана, поэтому и здесь
    # нужен плащ. Убираем тонкие руки тем же прибором, что у приёмщика
    # разворота: заливаем внутренние дыры и размыкаем всё тоньше 12 пикселей.
    from turnaround import _fill_holes, _open_x, widest_run
    body = _open_x(_fill_holes(dark), 12)
    widths = np.array([widest_run(body, y, y + 1) for y in range(top, top + H)])
    full = widths.max()
    idx = np.flatnonzero(widths >= full * 0.92)
    shoulder = (idx.min()) / H if len(idx) else None
    return H, mask_h, shoulder


def scale_head(kx, ky):
    """Умножить масштаб кости head в скелете И в позах, задающих свой."""
    d = json.loads(RIG_JSON.read_text(encoding="utf-8"))

    def walk(n):
        if n["name"] == "head":
            s = n.get("scale", [1.0, 1.0])
            n["scale"] = [round(s[0] * kx, 4), round(s[1] * ky, 4)]
            return True
        return any(walk(c) for c in n.get("children", []))

    walk(d["skeleton"]["root"])
    touched = 0
    for name, pose in d["poses"].items():
        h = pose.get("bones", {}).get("head")
        if not (h and "scale" in h):
            continue
        # ПОЗЫ С ЧУЖИМ РИСУНКОМ ГОЛОВЫ — МИМО ОБЩЕГО МНОЖИТЕЛЯ.
        # `spina` и `polu_spina` берут `head_back` (обруч затылка), а не
        # `head.svg`. Множитель выводится из условия «маска head.svg = 0.287
        # роста» и к другой геометрии неприменим: первый прогон умножил и их,
        # из-за чего приёмщик разворота дал макушку, гуляющую на 9.2% роста, и
        # купол спины на нижней границе полосы. Их масштаб решается отдельно,
        # по своим условиям приёмки.
        if h.get("part") in BACK_PARTS:
            continue
        h["scale"] = [round(h["scale"][0] * kx, 4),
                      round(h["scale"][1] * ky, 4)]
        touched += 1
    RIG_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return touched


def scale_back(k):
    """Умножить масштаб `head_back` в спинных позах — обе оси, как спереди."""
    d = json.loads(RIG_JSON.read_text(encoding="utf-8"))
    n = 0
    for name in BACK_POSES:
        h = d["poses"][name]["bones"]["head"]
        h["scale"] = [round(h["scale"][0] * k, 4), round(h["scale"][1] * k, 4)]
        n += 1
    RIG_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return n


def seat_back(name, dy):
    """Посадить затылок: сдвинуть `offset` позы по вертикали на dy от базы."""
    d = json.loads(RIG_JSON.read_text(encoding="utf-8"))
    h = d["poses"][name]["bones"]["head"]
    base = h.setdefault("_seat_base", h["offset"][1])
    h["offset"] = [h["offset"][0], base + dy]
    RIG_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")


def drop_seat_marks():
    """Убрать служебное поле `_seat_base` из поз после свипа."""
    d = json.loads(RIG_JSON.read_text(encoding="utf-8"))
    for name in BACK_POSES:
        d["poses"][name]["bones"]["head"].pop("_seat_base", None)
    RIG_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")


def view(pose, front=None):
    """Ракурс глазами приёмщика: (макушка относительно анфаса, купол)."""
    import turnaround as T
    m = T.measure(render(str(RIG), pose, 0.60, 0.90))
    if front is None:
        return m
    fmh = front["mask"]["y1"] - front["mask"]["y0"]
    crown = (m["top"] - front["top"]) / front["h"]
    dome = (m["mask"]["y1"] - m["mask"]["y0"]) / fmh if m.get("mask") else 0.0
    return crown, dome


def fit_back(k):
    """Уменьшить затылок вместе с головой и заново посадить его на шею.

    Порядок важен: сначала множитель (размер), потом свип посадки (место).
    Наоборот не выйдет — посадка, подобранная под старый размер, после
    умножения снова уедет.
    """
    print(f"  затылок: множитель {k:.4f} на {scale_back(k)} позы")
    front = view(POSE)
    for name in BACK_POSES:
        best = None
        for dy in SEAT_SWEEP:
            seat_back(name, dy)
            crown, dome = view(name, front)
            if best is None or abs(crown) < abs(best[1]):
                best = (dy, crown, dome)
            if abs(crown) < CROWN_TOL:
                break
        seat_back(name, best[0])
        print(f"  {name:12s} посадка {best[0]:+3} → макушка {best[1]:+.3f} "
              f"купол {best[2]:.2f}")
    drop_seat_marks()


# Пластина плеч и дуга обтравки — те самые придуманные части. Сдвигаем обе на
# одну величину, иначе пластина вылезет из-под обтравки.
PLATE_RE = re.compile(r'(<path d="M58 96 C64 44 90 12 110 10 C130 12 156 44 '
                      r'162 96 C156 116 64 116 58 96 Z")')
CLIP_RE = re.compile(r'(<path d="M-4 66 C 12 26, 50 0, 96 -4\s+'
                     r'C 142 0, 180 26, 196 66 L 196 400 L -4 400 Z"/>)')


def shift_shoulders(dy):
    """Опустить пластину плеч и дугу обтравки на dy единиц рисунка."""
    s = TORSO.read_text(encoding="utf-8")
    plate = ('<path transform="translate(0,%g)" d="M58 96 C64 44 90 12 110 10 '
             'C130 12 156 44 162 96 C156 116 64 116 58 96 Z"' % dy)
    s2, n1 = PLATE_RE.subn(plate, s, count=1)
    clip = ('<path d="M-4 %g C 12 %g, 50 %g, 96 %g C 142 %g, 180 %g, 196 %g '
            'L 196 400 L -4 400 Z"/>' % (66 + dy, 26 + dy, 0 + dy, -4 + dy,
                                         0 + dy, 26 + dy, 66 + dy))
    s3, n2 = CLIP_RE.subn(clip, s2, count=1)
    if not (n1 and n2):
        sys.exit(f"не нашёл пластину ({n1}) или дугу ({n2}) в torso.svg — "
                 f"файл менялся, свип применять нельзя")
    TORSO.write_text(s3, encoding="utf-8")


def backup():
    for p in (RIG_JSON, TORSO):
        b = p.with_suffix(p.suffix + ".fitbak")
        if not b.exists():
            shutil.copy(p, b)


def restore():
    n = 0
    for p in (RIG_JSON, TORSO):
        b = p.with_suffix(p.suffix + ".fitbak")
        if b.exists():
            shutil.copy(b, p)
            n += 1
    print(f"восстановлено файлов: {n}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Свести голову и плечи по замерам")
    ap.add_argument("--dry", action="store_true", help="только замер")
    ap.add_argument("--restore", action="store_true", help="вернуть из бэкапа")
    args = ap.parse_args(argv)

    if args.restore:
        restore()
        return 0

    if TARGET_MASK_H is None or TARGET_SHOULDER is None:
        sys.exit("fit_figure отключён: цели не заданы. Прочитай шапку файла — "
                 "прошлые цели были сняты сломанным прибором и увели персонажа "
                 "за полосу оригинала. Новые задавать только после\n"
                 "  python3 tools/original_ref.py <видео> --sheet /tmp/sheet.png\n"
                 "и просмотра листа глазами.")

    H, mh, sh = measure()
    print(f"\n  ДО: рост {H}px  маска {mh:.3f} роста  плечи {sh:.3f} роста")
    print(f"  цели: маска {TARGET_MASK_H:.3f}, плечи {TARGET_SHOULDER:.3f}\n")
    if args.dry:
        return 0

    backup()

    # 1. ГОЛОВА — итерациями. Уменьшая голову, уменьшаем рост, поэтому доля
    # меняется нелинейно и одной формулой не берётся.
    total = 1.0
    for step in range(8):
        H, mh, sh = measure()
        if abs(mh - TARGET_MASK_H) < 0.007:
            print(f"  голова: сошлось за {step} шаг(ов), маска {mh:.3f}")
            break
        k = (TARGET_MASK_H / mh) ** 0.55      # мягкий шаг: цель движется
        total *= k
        n = scale_head(k, k)
        print(f"  голова шаг {step+1}: маска {mh:.3f} -> множитель {k:.4f} "
              f"(накопл. {total:.4f}, скелет + {n} поз)")
    else:
        print(f"  голова: за 8 шагов не сошлось, осталось {mh:.3f}")

    # 2. ПЛЕЧИ — свип с прямым замером, грубый и уточняющий.
    # ШАГ В ЕДИНИЦУ, А НЕ В ДЕСЯТЬ: замер линии плеч разрывен. Между dy=37 и
    # dy=38 она прыгает с 0.214 на 0.283, потому что «самая широкая строка»
    # перескакивает с плеча на другую часть плаща. Грубый свип такую ступеньку
    # проскакивает и выбирает соседнюю точку, которая вдвое дальше от цели.
    def sweep(vals):
        best = None
        for dy in vals:
            restore_torso_only(dy)
            _, _, s = measure()
            d = abs(s - TARGET_SHOULDER) if s else 9
            if best is None or d < best[0]:
                best = (d, dy, s)
        return best

    coarse = sweep(range(0, 71, 10))
    best = min(coarse, sweep(range(max(coarse[1] - 9, 0), coarse[1] + 10)))
    restore_torso_only(best[1])
    print(f"  плечи: сдвиг dy={best[1]} → линия {best[2]:.3f} "
          f"(цель {TARGET_SHOULDER})")

    # 3. ЗАТЫЛОК — после плеч: низ купола на спине прижат воротником, а
    # воротник только что переехал.
    fit_back(total)

    H, mh, sh = measure()
    print(f"\n  ПОСЛЕ: рост {H}px  маска {mh:.3f} (цель {TARGET_MASK_H})  "
          f"плечи {sh:.3f} (цель {TARGET_SHOULDER})\n")
    print("  Теперь обязательно: python3 tools/turnaround.py --check\n")
    return 0


def restore_torso_only(dy):
    """Вернуть исходный torso.svg и применить к нему сдвиг dy."""
    b = TORSO.with_suffix(TORSO.suffix + ".fitbak")
    shutil.copy(b, TORSO)
    if dy:
        shift_shoulders(dy)


if __name__ == "__main__":
    raise SystemExit(main())
