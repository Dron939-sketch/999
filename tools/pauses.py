#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pauses.py — ГЕЙТ ТИШИНЫ: между репликами не должно быть дыр.

Замечание студии: «слишком длинные паузы после реплик». На слух это ловится
только на готовом ролике, а в сценарии не видно вовсе — и не потому, что автор
невнимателен, а потому, что ДЫРУ НЕ ПИШУТ РУКАМИ. Она набегает сама, двумя
способами, и оба невидимы в тексте `.anim`:

  1. СЦЕНА ДЛИННЕЕ СВОЕГО СОДЕРЖИМОГО. Движок берёт
     `scene.duration.max(actual)` — объявленная длительность не обрезает сцену,
     а ДОБИВАЕТ её застывшим кадром. Объявил 16s, набрал действий на 12 — в
     ролик уехали четыре секунды неподвижной картинки.

  2. ВЕТКА `do{}` ДЛИННЕЕ РЕПЛИКИ. `together` идёт по самой длинной ветке.
     Если жесты и шаги в `do{}` занимают двенадцать секунд, а `speaks for`
     семь — пять секунд персонаж молча доигрывает движение. Ровно так и вышло
     на проходе вдоль стола: `moves-to over 6.4s` плюс семь `wait 0.8s` дали
     ветку вдвое длиннее речи.

ЧТО МЕРЯЕТСЯ. `animdsl timing` отдаёт границы всех речевых блоков. Гейт берёт
промежутки между соседними блоками и хвост после последнего. Пауза — приём, и
короткая пауза обязана быть; предмет проверки — та, которую никто не заказывал.

ПОРОГИ. Между репликами 2.5 с: драматическая пауза в наших роликах нигде не
превышает полутора секунд, склейка добавляет ещё около секунды, и всё, что
длиннее, — уже не приём.

ХВОСТ СЧИТАЕТСЯ БЕЗ ТИТРОВ, и это не поблажка. Печать с логотипом — содержимое
кадра: там происходит событие, зритель на него смотрит. Считать её тишиной —
всё равно что считать тишиной последний план. Поэтому финальная сцена без
реплик из хвоста вычитается, а меряется то, что осталось: сколько секунд
персонаж молча доигрывает уход. Порог 3.0 с — два шага и стойка.

Первая версия гейта мерила хвост до конца файла с порогом 4.5 с. Порог был взят
из головы и смешивал две разные вещи; ролик, подрезанный под него, терял печать,
а не тишину.

Использование:
    python3 tools/pauses.py examples/lektorij/foo.anim
    python3 tools/pauses.py --all
"""

import argparse
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "target" / "release" / "animdsl"

GAP_MAX = 2.5       # секунд тишины между репликами
TAIL_MAX = 3.0      # секунд молчаливого доигрывания после последнего слова
                    # (титры-без-реплик не в счёт — см. шапку)

SCENE = re.compile(r'^\s*scene\s+"([^"]+)"\s*\(duration:\s*([\d.]+)s', re.M)
LIP = re.compile(r'^\s*//lip\s+\d+', re.M)


def credits_len(path):
    """Длительность финальной сцены, если в ней нет ни одной реплики.

    Печать с логотипом — событие в кадре, а не молчание, и в хвост её
    записывать нельзя. Опознаётся структурно: последняя сцена файла, в которой
    не стоит ни одного `//lip`. Список имён вести не нужно.
    """
    s = Path(path).read_text(encoding="utf-8")
    scenes = list(SCENE.finditer(s))
    if not scenes:
        return 0.0
    last = scenes[-1]
    return 0.0 if LIP.search(s[last.end():]) else float(last.group(2))


def blocks(path):
    r = subprocess.run([str(ENGINE), "timing", str(path)],
                       capture_output=True, check=True)
    return json.loads(r.stdout.decode())


def check(path):
    d = blocks(path)
    b = d.get("blocks", [])
    if len(b) < 2:
        return [], 0.0
    bad = []
    for p, q in zip(b, b[1:]):
        gap = q["start"] - p["end"]
        if gap > GAP_MAX:
            bad.append((p["index"], gap,
                        "сцена длиннее содержимого или ветка do{} длиннее реплики"))
    tail = d["total"] - b[-1]["end"] - credits_len(path)
    if tail > TAIL_MAX:
        bad.append((b[-1]["index"], tail,
                    "молчаливый хвост после последнего слова (титры не в счёт)"))
    return bad, d["total"]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    files = a.files or (sorted(glob.glob("examples/**/*.anim", recursive=True))
                        if a.all else [])
    if not files:
        raise SystemExit("нечего проверять: укажи файл или --all")

    print("\n  ТИШИНА МЕЖДУ РЕПЛИКАМИ\n")
    worst = 0
    for f in files:
        try:
            bad, total = check(f)
        except subprocess.CalledProcessError:
            print(f"    [ПРОПУСК] {Path(f).name}: движок не собрал таймлайн")
            continue
        if not bad:
            print(f"    [OK] {Path(f).name}: дыр нет ({total:.1f} с)")
            continue
        worst = 1
        print(f"    [ПРОВАЛ] {Path(f).name} ({total:.1f} с)")
        for idx, gap, why in bad:
            print(f"      после реплики {idx}: {gap:.1f} с — {why}")

    if worst:
        print("\n  Дыру не пишут руками, она набегает сама: сцена добивается "
              "\n  застывшим кадром до объявленной длительности, а `together` "
              "\n  идёт по самой длинной ветке. Сверь `duration:` сцены с суммой "
              "\n  её действий и `do{}` — со `speaks for`.\n")
    else:
        print("\n  Все паузы — приём, а не недосмотр.\n")
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
