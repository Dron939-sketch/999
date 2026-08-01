#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sverka.py — ГЕЙТ СООТВЕТСТВИЯ: сценарий и раскадровка говорят об одном.

VO-файл и `.anim` — два документа об одном ролике, и связаны они ОДНИМИ
НОМЕРАМИ: реплика `| VO-4 |` в таблице озвучки и маркер `//lip 4` в раскадровке
обязаны быть одним и тем же. По этим номерам prep_lipsync подставляет mp3 в
речевые блоки. Никакой другой связи между файлами нет.

ЧЕМ ЭТО ОПАСНО. Стоит вписать реплику в таблицу и забыть маркер — и все
следующие реплики поедут на слот назад: под четвёртую картинку ляжет пятый
голос. Ролик соберётся, липсинк сойдётся, длина совпадёт, гейты речи и пауз
промолчат — потому что каждый по отдельности видит согласованную картину.
Заметно только ухом и только на готовом файле, и то не сразу: смещение на одну
реплику читается как «странная режиссура», а не как поломка.

Ловушка не гипотетическая. В этой сессии число реплик менялось дважды —
одиннадцать, потом десять, — и оба раза маркеры пришлось перенумеровывать
руками. Прогон по каталогу нашёл уже разъехавшийся ролик: у
`biznes-myshlenie-intro` шесть маркеров против семи реплик.

ЧТО ПРОВЕРЯЕТСЯ:
  · маркеров ровно столько же, сколько реплик в VO-таблице;
  · номера идут подряд с единицы, без дыр и без повторов.

Второе не придирка: `//lip 3` дважды подряд означает, что одна реплика уедет
в два разных блока, а другая не прозвучит вовсе.

Использование:
    python3 tools/sverka.py examples/lektorij/foo.anim
    python3 tools/sverka.py --all
"""

import argparse
import glob
import re
import sys
from pathlib import Path

LIP = re.compile(r"^\s*//lip\s+(\d+)\s*$", re.M)


def vo_path(anim):
    return Path(anim).with_name(Path(anim).stem + "-VO.md")


def check(anim):
    """Список расхождений между раскадровкой и сценарием озвучки."""
    vo = vo_path(anim)
    if not vo.exists():
        return []                       # ролик без озвучки — сверять нечего
    nums = [int(n) for n in LIP.findall(Path(anim).read_text(encoding="utf-8"))]
    reps = [l for l in vo.read_text(encoding="utf-8").splitlines()
            if l.startswith("| VO-")]
    bad = []
    if len(nums) != len(reps):
        bad.append(f"маркеров `//lip` {len(nums)}, а реплик в {vo.name} {len(reps)} — "
                   f"голоса поедут по слотам, и каждая следующая реплика ляжет "
                   f"не под свою картинку")
    if nums != list(range(1, len(nums) + 1)):
        dup = sorted({n for n in nums if nums.count(n) > 1})
        gaps = sorted(set(range(1, max(nums) + 1)) - set(nums)) if nums else []
        why = []
        if dup:
            why.append(f"повторяются: {dup}")
        if gaps:
            why.append(f"пропущены: {gaps}")
        bad.append("номера маркеров не идут подряд с единицы"
                   + (" (" + "; ".join(why) + ")" if why else f": {nums}"))
    return bad


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    files = a.files or (sorted(glob.glob("examples/**/*.anim", recursive=True))
                        if a.all else [])
    if not files:
        raise SystemExit("нечего проверять: укажи файл или --all")

    print("\n  СЦЕНАРИЙ И РАСКАДРОВКА — ОДНИ НОМЕРА\n")
    worst = 0
    for f in files:
        bad = check(f)
        if not vo_path(f).exists():
            continue
        if not bad:
            print(f"    [OK] {Path(f).name}: номера сходятся")
            continue
        worst = 1
        print(f"    [ПРОВАЛ] {Path(f).name}")
        for b in bad:
            print(f"      {b}")
    print("\n  Реплика и маркер связаны только номером: другой связи между "
          "\n  VO-таблицей и раскадровкой нет. Сдвиг на один слот собирается "
          "\n  без единой ошибки и слышен только на готовом файле.\n"
          if worst else "\n  Реплики и маркеры на своих местах.\n")
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
