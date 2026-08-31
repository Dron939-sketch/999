#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fit_figure.py — СВЕСТИ ГОЛОВУ И ПЛЕЧИ по измеренным числам.

ЗАЧЕМ. Детали рига обведены с ПОДЛИННЫХ кадров, но с РАЗНЫХ: маска — с крупного
плана (`maxresdefault (3).jpg`, фигура занимает 94% высоты кадра), плащ — с
другого, более общего (`maxresdefault (4).jpg`). Их относительный размер в риге
ничем не задан: каждую деталь сняли в своём масштабе и собрали на глаз. Отсюда
голова в 0.420 роста вместо фримановских 0.287 — при том, что сам рисунок маски
подлинный и трогать его не надо. Не согласована СБОРКА.

Второе: плечи в `torso.svg` ПРИДУМАНЫ. В файле написано «верх СРЕЗАН… выше
среза стоит простая пластина плеч»; замер подтверждает — обводка покрывает
y 2.7..427, всё выше y≈40 синтетика. Линия плеч — единственная часть плаща,
которую никто не обводил, и её подогнали под большую голову. Поэтому уменьшение
головы БЕЗ правки плеч даёт лицо в капюшоне (проверено, откатывал).

ЧТО ДЕЛАЕТ СКРИПТ. Две правки, обе по измеренным величинам:

  1. МАСШТАБ ГОЛОВЫ до 0.287 роста — замер `tools/original_ref.py` по 35 кадрам
     оригинала с целой фигурой. Множитель ищется ИТЕРАЦИЯМИ, а не формулой:
     уменьшая голову, мы уменьшаем и рост фигуры, поэтому доля меняется
     нелинейно. Правится и скелет, и 18 поз, задающих свой масштаб головы.

  2. ЛИНИЯ ПЛЕЧ на 0.234 роста — замер по 3D-болвану, чей плащ построен лофтом
     по обводке подлинного кадра. Пластина плеч и дуга обтравки `clipPath`
     сдвигаются вниз; сдвиг подбирается свипом с замером, потому что связь
     между координатой в рисунке и долей роста готовой фигуры проходит через
     масштабы кости, позы и камеры.

ПОЧЕМУ СВИП, А НЕ ФОРМУЛА. Я пробовал считать: путь от координаты в `torso.svg`
до доли роста на кадре идёт через `scale(1,1.58)` в рисунке, масштаб кости
`cloak` (1.092), масштаб позы и рост, который сам зависит от размера головы.
Каждое звено — возможность ошибиться на множитель, и такую ошибку не видно:
результат выглядит правдоподобным. Свип с прямым замером на готовом кадре
короче и не врёт.

  3. ПОСАДКА СПИННЫХ ПОЗ — отдельным шагом, и без него всё разваливалось.
     `spina` и `polu_spina` берут другой рисунок (`head_back`, обруч затылка) и
     стоят ЗА плащом (`z_order` 1). Две прошлые попытки провалили гейт с
     противоположных сторон: умножить их общим множителем — макушка гуляла на
     9.2% роста, ИСКЛЮЧИТЬ их — на 21.1%, а купол затылка раздувался до 1.35
     анфасной маски. Ни то ни другое не работает, потому что задача тут не
     «масштаб», а ПОСАДКА: голова уменьшилась, и её надо заново посадить на
     шею. Множитель даёт размер, посадку решает свип `offset` с замером.

ЧТО ЗАМЕР ПОКАЗАЛ ПРО ЗАТЫЛОК (это и было главным непониманием). Со спины низ
купола прижат ВОРОТНИКОМ: сдвигай голову как хочешь, нижняя кромка белого стоит
на кромке плаща. Значит высота купола не свободна — она равна расстоянию от
макушки до воротника, а макушку держит первое условие приёмки. Отсюда вывод,
который сначала выглядел тупиком: на 180° купол задан геометрией плаща, и
единственный рычаг — опустить линию плеч, что правка №2 и делает.

На 135° прибор показал обратное: низ купола ехал вместе с головой (526..598 →
575..648), то есть там кромка своя, не воротник. Поэтому полуспина решается
посадкой, и решается сразу: сдвиг `offset` вниз на ~28 единиц ставит макушку
вровень с анфасом, не трогая купол.

ЧТО ПОЛУЧАЕТСЯ. Маска 0.420 → 0.293 роста (цель 0.287), линия плеч 0.306 →
0.214 (цель 0.234), капюшон ушёл — голова встала НА плечи, а не в них. Купол
затылка 0.57 на спине и 0.61 на полуспине — обе внутри полосы 0.50..0.75.
Побочно улучшился разворот: три четверти 0.805 → 0.86, что впервые совпало и с
болваном (0.846), и с эллиптической моделью.

Использование:
    python3 tools/fit_figure.py --dry      # только замер, ничего не менять
    python3 tools/fit_figure.py            # применить правки
    python3 tools/fit_figure.py --restore  # вернуть из бэкапа

ПОСЛЕ ПРИМЕНЕНИЯ ОБЯЗАТЕЛЬНО: `python3 tools/turnaround.py --check`. Гейт
жёсткий и роняет завод; без этой проверки правка выглядит удачной и ломает
ракурсы, которых в анфасном кадре не видно.
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
TARGET_MASK_H = 0.287      # доля роста; original_ref.py, 35 кадров оригинала
TARGET_SHOULDER = 0.234    # доля роста; glb_turn.py по болвану с обводки

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
