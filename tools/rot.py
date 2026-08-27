#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rot.py — ГЕЙТ: рот обязан ОТКРЫВАТЬСЯ.

ЗАЧЕМ. Липсинк на заводе собран из трёх независимо исправных частей: Rhubarb
размечает звук по фонемам, `prep_lipsync` переводит буквы в позы `visA..visF`,
движок эти позы честно подставляет. Каждая часть по отдельности работала — и
ролик «Этика» вышел с неподвижным ртом. Замер по готовому файлу: 24 кадра
подряд на самой быстрой реплике — одна и та же плоская линия.

Причина оказалась НЕ в разметке и НЕ в движке, а в риге. Визема B у Rhubarb —
«слегка приоткрытый рот», самая частая из всех: на замере одной реплики она
занимала 42% времени речи. В риге на неё была назначена деталь `mouth_m` —
штрих, то есть ЗАКРЫТЫЙ рот, внешне неотличимый от `mouth_closed` виземы A.
Вместе эти две «закрытые» виземы держали 67% времени, а после понижения
громкостным гейтом — 80%. Разметка менялась, картинка не менялась.

Ни один из тринадцати гейтов такого поймать не мог: они читают сценарий, а
дефект жил в SVG-детали, на которую сценарий даже не ссылается по имени.

ЧТО ПРОВЕРЯЕТСЯ.

1. У каждой виземы из `RHUBARB_MAP` в риге есть поза, и она задаёт деталь рта.
2. Виземы ОТКРЫТЫХ букв (всё, кроме A и X) нарисованы ОТКРЫТЫМ ртом: в SVG
   есть залитая фигура, а не только штрих. Штрих — это сомкнутые губы.
3. Базовые виземы A..F нарисованы РАЗНЫМИ деталями: если две из них ссылаются
   на один файл, рот между ними не меняется, сколько бы их ни чередовалось.
   Расширенные G/H/X к базовым сводятся НАМЕРЕННО и из этой мерки исключены.

Проверка нарочно грубая и текстовая — она ловит не «некрасиво», а «не видно».

Использование:
    python3 tools/rot.py                       # риг по умолчанию
    python3 tools/rot.py examples/assets/characters/freeman_rig
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from prep_lipsync import RHUBARB_MAP, ZAKRYTYE_BUKVY  # noqa: E402

RIG_PO_UMOLCHANIYU = ROOT / "examples/assets/characters/freeman_rig"

# Базовые буквы Rhubarb. G/H/X — расширенные, они сводятся к базовым намеренно,
# поэтому совпадение детали у них не дефект.
BAZOVYE = set("ABCDEF")

# Залитая фигура: `fill="#..."` у любого элемента, кроме служебного `fill="none"`.
ZALIVKA = re.compile(r'fill\s*=\s*"(?!none")#?[0-9a-zA-Z]', re.I)


def detal_otkryta(svg_path):
    """Деталь рта рисует ОТВЕРСТИЕ (залитая фигура), а не сомкнутые губы (штрих)."""
    try:
        src = svg_path.read_text(encoding="utf-8")
    except OSError:
        return None
    # Комментарии выкидываем: в них попадаются и `fill`, и разметочные заметки.
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    return bool(ZALIVKA.search(src))


def proverit(rig_dir):
    rig_dir = Path(rig_dir)
    rig = json.loads((rig_dir / "rig.json").read_text(encoding="utf-8"))
    poses = rig.get("poses", {})
    bed = []
    detali = {}

    for bukva, poza in sorted(RHUBARB_MAP.items()):
        p = poses.get(poza)
        if not p:
            bed.append(f"буква {bukva}: позы «{poza}» нет в риге")
            continue
        chast = p.get("bones", {}).get("mouth", {}).get("part")
        if not chast:
            bed.append(f"{poza} (буква {bukva}): поза не задаёт деталь рта")
            continue
        if bukva in BAZOVYE:
            detali.setdefault(chast, []).append((bukva, poza))

        if bukva in ZAKRYTYE_BUKVY:
            continue
        otkr = detal_otkryta(rig_dir / f"{chast}.svg")
        if otkr is None:
            bed.append(f"{poza} (буква {bukva}): нет файла {chast}.svg")
        elif not otkr:
            bed.append(
                f"{poza} (буква {bukva}) нарисована ЗАКРЫТЫМ ртом ({chast}.svg — "
                f"один штрих без заливки). Буква {bukva} у Rhubarb рот открывает")

    # Одна деталь на две буквы — рот между ними не меняется.
    for chast, kto in sorted(detali.items()):
        if len(kto) > 1:
            imena = ", ".join(f"{b}→{p}" for b, p in kto)
            bed.append(f"{chast}.svg назначен сразу на {imena} — "
                       f"между этими буквами рот не изменится")

    return bed


def main():
    rig = sys.argv[1] if len(sys.argv) > 1 else RIG_PO_UMOLCHANIYU
    bed = proverit(rig)
    if bed:
        print("  РОТ НЕ ОТКРЫВАЕТСЯ:")
        for b in bed:
            print(f"    · {b}")
        return 1
    print(f"  рот: {len(RHUBARB_MAP)} визем, открытые буквы открыты, "
          f"детали не дублируются")
    return 0


if __name__ == "__main__":
    sys.exit(main())
