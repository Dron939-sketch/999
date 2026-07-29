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

РЕЗУЛЬТАТ ПЕРВОГО ПРОГОНА: подгонка удалась, приёмщик разворота — нет.

Числа взяты: маска 0.420 → 0.293 (цель 0.287), плечи 0.306 → 0.205 (цель
0.234), капюшон ушёл — голова встала НА плечи, а не в них. Побочно улучшился
разворот: три четверти 0.805 → 0.86, что впервые совпало и с болваном (0.846), и
с эллиптической моделью.

Но `turnaround.py --check` провалился на двух условиях, и правку пришлось
откатить:

  · МАКУШКА ГУЛЯЕТ на 9.2% роста (норма ≤3%), хуже всего на 135° (−0.087);
  · СПИНА: высота маски 0.50 — на нижней границе полосы купола 0.50..0.75.

Причина понятна: множитель применён РАВНОМЕРНО ко всем 18 позам, задающим свой
масштаб головы, — включая позы спины и полуспины. А они устроены иначе: там
стоит `head_back` со своими масштабами (0.80/1.40) и своими посадками, и общий
множитель ломает их посадку, а не просто уменьшает голову.

ЧТО ОСТАЛОСЬ СДЕЛАТЬ. Позы спины/полуспины надо править отдельно: пересчитать
их посадку под новый размер головы, а не умножать масштаб. Это 6 поз из 124
(`spina`, `polu_spina`, `spina_oglyadka`, `spina_ponuro` и их варианты).
Остальные 112 правку принимают.

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
    for pose in d["poses"].values():
        h = pose.get("bones", {}).get("head")
        if h and "scale" in h:
            h["scale"] = [round(h["scale"][0] * kx, 4),
                          round(h["scale"][1] * ky, 4)]
            touched += 1
    RIG_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return touched


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
    for step in range(6):
        H, mh, sh = measure()
        if abs(mh - TARGET_MASK_H) < 0.004:
            print(f"  голова: сошлось за {step} шаг(ов), маска {mh:.3f}")
            break
        k = (TARGET_MASK_H / mh) ** 0.55      # мягкий шаг: цель движется
        n = scale_head(k, k)
        print(f"  голова шаг {step+1}: маска {mh:.3f} -> множитель {k:.4f} "
              f"(скелет + {n} поз)")
    else:
        print(f"  голова: за 6 шагов не сошлось, осталось {mh:.3f}")

    # 2. ПЛЕЧИ — свип с прямым замером.
    best = None
    for dy in (0, 10, 20, 30, 40, 55, 70):
        restore_torso_only(dy)
        _, _, s = measure()
        d = abs(s - TARGET_SHOULDER) if s else 9
        print(f"  плечи dy={dy:3}: линия {s:.3f}  расхождение {d:+.3f}")
        if best is None or d < best[0]:
            best = (d, dy, s)
    restore_torso_only(best[1])
    H, mh, sh = measure()
    print(f"\n  выбран сдвиг плеч dy={best[1]}")
    print(f"  ПОСЛЕ: рост {H}px  маска {mh:.3f} (цель {TARGET_MASK_H})  "
          f"плечи {sh:.3f} (цель {TARGET_SHOULDER})\n")
    return 0


def restore_torso_only(dy):
    """Вернуть исходный torso.svg и применить к нему сдвиг dy."""
    b = TORSO.with_suffix(TORSO.suffix + ".fitbak")
    shutil.copy(b, TORSO)
    if dy:
        shift_shoulders(dy)


if __name__ == "__main__":
    raise SystemExit(main())
