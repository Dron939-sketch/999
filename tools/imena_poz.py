#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
imena_poz.py — ПОЗА, КОТОРОЙ В РИГЕ НЕТ, НЕ ЛОМАЕТ НИЧЕГО. И В ЭТОМ БЕДА.

Движок на такое НЕ РУГАЕТСЯ: `rig.poses.get(&ev.pose)` возвращает None, слой
молча становится пустым, и фигура падает в дефолтную стойку рига. Опечатка
выглядит на экране ровно как «персонаж зачем-то встал по стойке смирно», и
понять причину по картинке нельзя — жест просто не сыграл.

ПОЧЕМУ ЭТО ОТДЕЛЬНЫЙ ГЕЙТ, А НЕ СТРОЧКА В `studio.py`. Проверка там была и
работает: строгий линт синхрона валит прогон ДО рендера. Но валит он НА ЗАВОДЕ,
через восемь минут после пуша, потратив сборку движка и слот прогона, — а в
ветке в это время нельзя запускать следующий ролик. Ровно это и случилось с
`otkaz`: слой `vopros_ruka` был выдуман на ходу, все двенадцать локальных
гейтов прошли чисто, и цена опечатки составила один прогон завода.

Проверка стоит доли секунды и читает те же два файла, что и завод. Её место —
до пуша, рядом с остальными.

Использование:
    python3 tools/imena_poz.py examples/lektorij/otkaz.anim
    python3 tools/imena_poz.py --all
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from studio import _rig_poses, anim_code   # noqa: E402  (общий источник правды)


def rigi(anim: Path):
    """Риги, объявленные САМИМ файлом.

    Без этого гейт врёт: демо `the-last-barista.anim` живёт на процедурных
    персонажах (`assets/characters/procedural/*.json`), поз рига Фримена там
    нет и быть не должно, — а проверка против одного захардкоженного рига
    выдавала на нём двенадцать «отсутствующих» имён подряд. Гейт, который
    врёт, перестают читать (`KONVEJER.md` §5.3).
    """
    puti = re.findall(r'import\s+character\s+\w+\s+from\s+"([^"]+)"',
                      anim_code(anim.read_text(encoding="utf-8")))
    out = []
    for rel in puti:
        d = (anim.parent / rel).resolve()
        out.append(d.parent if d.suffix == ".json" else d)
    return out


def proveryaem(anim: Path, poses):
    used = re.findall(r'(?:pose|overlays)\s+"([a-z_0-9]+)"',
                      anim_code(anim.read_text(encoding="utf-8")))
    return sorted({u for u in used if u not in poses})


def pohozhie(name, poses, skolko=3):
    """Что автор, скорее всего, имел в виду: соседи по началу или по хвосту."""
    koren = name.split("_")[0]
    hvost = name.split("_")[-1]
    blizkie = [p for p in poses
               if p.startswith(koren) or p.endswith(hvost) or koren in p]
    return sorted(blizkie, key=len)[:skolko]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true", help="все *.anim в examples/")
    a = ap.parse_args(argv)

    puti = [Path(f) for f in a.files]
    if a.all:
        puti = sorted((ROOT / "examples").rglob("*.anim"))
    if not puti:
        print("нечего проверять: укажи .anim или --all")
        return 2

    bed = 0
    for p in puti:
        if not p.exists():
            continue
        #  ПОЗЫ БЕРУТСЯ ИЗ ТЕХ РИГОВ, КОТОРЫЕ НАЗВАЛ САМ ФАЙЛ. Процедурные
        #  персонажи rig.json не имеют — по ним проверять нечего, и молчание
        #  тут честнее выдуманного провала.
        poses = {}
        for rig in rigi(p):
            poses.update(_rig_poses(rig) or {})
        if not poses:
            continue
        bad = proveryaem(p, poses)
        if not bad:
            print(f"    [OK] {p.name}: все имена поз есть в риге")
            continue
        bed += len(bad)
        print(f"    [ПРОВАЛ] {p.name}: поз нет в риге — {len(bad)}")
        for n in bad:
            sosedi = pohozhie(n, poses)
            podskazka = f" — может быть, {', '.join(sosedi)}?" if sosedi else ""
            print(f"      «{n}» движок молча заменит дефолтной стойкой{podskazka}")

    if bed:
        print("\n  Жест не сыграет, и по картинке этого не понять.")
        return 1
    print("\n  Все названные позы существуют.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
