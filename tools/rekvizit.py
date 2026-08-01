#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rekvizit.py — ГЕЙТ РЕКВИЗИТА: вещь не появляется на персонаже сама.

Замечание студии: «шляпу, которая появляется, убери». Цилиндр возникал на одну
реплику и пропадал — и это не ошибка сценария, а ловушка рига. Поза
`confident` среди прочих костей ставила `hat` и `cane`. Имя позы про это не
говорит ни слова, а слои накапливаются: стоило где-нибудь написать
`overlays "confident"`, и персонаж молча надевал цилиндр, брал трость, а на
следующей полной позе всё исчезало.

ПОЧЕМУ ЭТО ЛОВУШКА, А НЕ ОПЕЧАТКА. Автор сценария выбирает позу по НАЗВАНИЮ:
нужен уверенный жест — пишет `confident`. Проверить, какие кости она трогает,
можно только открыв `rig.json` и прочитав тридцать строк. Цилиндр приехал в
ЧЕТЫРЕ ролика подряд, и ни разу его никто не заказывал.

ПРАВИЛО. Реквизит носит только та поза, которая объявляет его ИМЕНЕМ. Риг
хранит карту `props`: какая кость какой суффикс требует — `glasses` → `ochki`,
`hat` и `cane` → `cilindr`. Очки этому правилу подчинялись всегда (`v_upor`
против `v_upor_ochki`), цилиндр — нет. Теперь подчиняются оба, и добавить
третью вещь можно, не трогая инструмент: строка в карте, суффикс в имени.

ПОЧЕМУ НЕ ГЕЙТ «ПОЗА НЕ ДОБАВЛЯЕТ ЧАСТЕЙ». Пробовал: эталон `calm` держит
четыре кости, любая осмысленная поза добавляет руки, голову и ноги, и такая
проверка ругается на сто двадцать поз из ста тридцати. Ловить надо не
добавление вообще, а добавление ВЕЩИ — предмета, который зритель считает
костюмом и заметит его исчезновение.

Использование:
    python3 tools/rekvizit.py                 # проверить риг
    python3 tools/rekvizit.py --rig путь
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = ROOT / "examples" / "assets" / "characters" / "freeman_rig"

# Запасная карта на случай рига без секции `props`: без неё гейт молча
# пропускал бы всё и создавал ложное спокойствие.
FALLBACK = {"hat": "cilindr", "cane": "cilindr", "glasses": "ochki"}


def offenders(rig):
    """Позы, которые несут вещь, не объявив её именем."""
    props = rig.get("props") or FALLBACK
    out = []
    for name, pose in rig.get("poses", {}).items():
        for bone in pose.get("bones", {}):
            mark = props.get(bone)
            if mark and mark not in name:
                out.append((name, bone, mark))
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default=str(RIG))
    a = ap.parse_args(argv)

    rig = json.loads((Path(a.rig) / "rig.json").read_text(encoding="utf-8"))
    bad = offenders(rig)

    print("\n  РЕКВИЗИТ — ВЕЩЬ ОБЪЯВЛЕНА ИМЕНЕМ ПОЗЫ\n")
    if not bad:
        props = rig.get("props") or FALLBACK
        print(f"    [OK] ни одна поза не надевает вещь тайком "
              f"(под присмотром: {', '.join(sorted(set(props)))})\n")
        return 0
    for name, bone, mark in bad:
        print(f"    [ПРОВАЛ] поза «{name}» ставит «{bone}» — "
              f"в имени нет «{mark}»")
    print("\n  Либо убрать вещь из позы, либо завести отдельную позу с "
          "\n  суффиксом в имени: автор сценария выбирает позу по названию и "
          "\n  в rig.json не заглядывает.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
