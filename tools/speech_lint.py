#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
speech_lint.py — ГЕЙТ РЕЧЕВЫХ БЛОКОВ: что можно и чего нельзя делать, пока
персонаж говорит.

Три ошибки, пойманные на живых роликах. Все три выглядят одинаково —
«лицо не соответствует озвучке», — но причины разные.

1. СМЕНА ПОЛНОЙ ПОЗЫ ВНУТРИ РЕПЛИКИ. Липсинк идёт слоем поверх позы тела, а
   полная поза слои СБРАСЫВАЕТ (renderer::resolve_effective_pose): базой
   становится она. В момент такой смены рот прыгает на рот позы и держится до
   следующего флэпа. Жест внутри реплики нужен — но он обязан быть СЛОЕМ
   (`overlays`), а полные позы ставятся МЕЖДУ репликами.

2. СЛОЙ С РТОМ ВНУТРИ РЕПЛИКИ. Слои накапливаются по порядку, и последний
   выигрывает: мимика, положенная посреди речи, перебивает рот до следующего
   флэпа. Флэш-морда (`flash_*`) — приём на 2 кадра, её ставят ДО или ПОСЛЕ
   реплики. А вот слой БЕЗ рта (жест рукой, наклон головы) внутри реплики
   законен и нужен: тело живёт, речь не страдает — гейт такие пропускает,
   сверяясь с ригом.

3. НЕОБЪЯВЛЕННАЯ РЕПЛИКА. `speaks for` без маркера `//lip N` перед ним не
   получит настоящей озвучки: prep_lipsync ищет mp3 по номеру. Рот будет
   молотить флэпы, пока голос говорит своё, — и это самый заметный
   рассинхрон из трёх.

Использование:
    python3 tools/speech_lint.py examples/lektorij/foo.anim
    python3 tools/speech_lint.py --all           # все .anim в examples
"""

import argparse
import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

IMPORT = re.compile(r'import\s+character\s+(\S+)\s+from\s+"([^"]+)"')
LIP = re.compile(r"^\s*//lip\s+(\d+)\s*$")
#  ДОСЛОВНО ИЗ `prep_lipsync.py`: через какие строки маркер переживает путь до
#  речи. Держать копию рискованно, но импортировать хуже — гейт обязан работать
#  и когда сборщика в дереве нет. Расхождение этих двух выражений и есть та
#  щель, из-за которой ролик 25 собрался без финала: если правите здесь,
#  правьте и там.
SCAFFOLD = re.compile(r"^\s*(together\s*\{|do\s*\{|\{|\}|//.*)?\s*$")
SPEAK = re.compile(r"^\s*(\S+)\s+speaks\s+for\s+([\d.]+)s\s*$")
LIPS = re.compile(r"^\s*(\S+)\s+lips\s+")
POSE = re.compile(r"^\s*(\S+)\s+pose\s+\"([^\"]+)\"")
OVERLAY = re.compile(r"^\s*(\S+)\s+overlays\s+\"([^\"]+)\"")
OPEN_BLOCK = re.compile(r"\{\s*$")
CLOSE_BLOCK = re.compile(r"^\s*\}\s*$")


def mouth_layers(path, lines):
    """Имена поз, которые трогают рот, — по ригам, импортированным сценарием.

    Слой без рта внутри реплики безвреден (жест живёт, речь не страдает), и
    запрещать его было бы вредно: тело замерло бы на каждой фразе.
    """
    import json
    names = set()
    for line in lines:
        m = IMPORT.search(line)
        if not m:
            continue
        rig_path = (Path(path).parent / m.group(2) / "rig.json").resolve()
        if not rig_path.exists():
            continue
        rig = json.loads(rig_path.read_text(encoding="utf-8"))
        for pose_name, pose in rig.get("poses", {}).items():
            if "mouth" in pose.get("bones", {}):
                names.add(pose_name)
    return names


def check(path):
    """→ (список нарушений, число проверенных реплик)"""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    with_mouth = mouth_layers(path, lines)
    bad, spoken = [], 0

    # Реплика живёт внутри `together { ... }`: речь и каты идут параллельно.
    # Ищем блок together, внутри него — speaks/lips, и смотрим, что ещё там.
    i = 0
    while i < len(lines):
        if "together" in lines[i] and OPEN_BLOCK.search(lines[i]):
            depth, j, body = 1, i + 1, []
            while j < len(lines) and depth > 0:
                if OPEN_BLOCK.search(lines[j]):
                    depth += 1
                if CLOSE_BLOCK.match(lines[j]):
                    depth -= 1
                    if depth == 0:
                        break
                body.append((j + 1, lines[j]))
                j += 1
            talks = any(SPEAK.match(t) or LIPS.match(t) for _, t in body)
            if talks:
                spoken += 1
                # Маркер ищем и ПЕРЕД блоком, и ВНУТРИ него: сценаристы ставят
                # его там, где начинается сама речь, а речь часто лежит внутри
                # `do { ... }`. Первая версия смотрела только шапку и объявляла
                # размеченные реплики немаркированными — гейт обязан ловить
                # ошибку, а не расположение комментария.
                # МАРКЕР ИЩЕТСЯ ТЕМ ЖЕ ПРАВИЛОМ, ЧТО У СБОРЩИКА, а не «шесть
                # строк назад».
                #
                # Здесь стояло `lines[i-6:i+1]` — просто шесть строк вверх, что
                # угодно между ними. `prep_lipsync` же держит маркер только
                # через СТРОИТЕЛЬНЫЕ строки (скобки, `together {`, комментарии,
                # пустые) и сбрасывает его на любой другой — на `overlays`, на
                # `wait`. Правила разошлись, и в эту щель прошёл ролик 25: чтобы
                # убрать слой с ртом из речи, мимика была поднята ВЫШЕ блока, и
                # встала между маркером и речью. Гейт видел маркер в шести
                # строках и молчал; сборщик маркер терял.
                #
                # Цена расхождения — не липсинк, а весь ролик. Реплика без
                # блока не попадает в карту, голос ставится по ПЛАНОВОЙ дельте
                # от предыдущей размеченной, и на четырёх репликах из семи он
                # уехал ЗА следующую: VO-28 «Поздравляю, это и есть халитоз»
                # легло на 78.5с, а VO-29 «Только настоящий» — на 77.0с, то
                # есть подтверждение зазвучало после своей же добивки. Плюс
                # картинка осталась на своих 162с против 137с голоса, и
                # сведение обрезало ей хвост: ролик кончился без финала.
                # Ни один из двадцати пяти гейтов не упал.
                head, k, skipped = None, i - 1, 0
                while k >= 0 and skipped < 6:
                    if LIP.match(lines[k]):
                        head = lines[k]
                        break
                    if not SCAFFOLD.match(lines[k]):
                        break
                    skipped += 1
                    k -= 1
                if head is None and not any(LIP.match(t) for _, t in body):
                    bad.append((i + 1, "маркер //lip N не привязан к реплике: "
                                       "между ним и речью стоит строка, на "
                                       "которой prep_lipsync маркер сбрасывает "
                                       "(любая, кроме скобок, комментариев и "
                                       "пустых). Озвучка к реплике не "
                                       "привяжется, а голос встанет по плановой "
                                       "дельте — и может уехать за следующую "
                                       "реплику. Подними строку ВЫШЕ маркера"))
                for ln, t in body:
                    m = POSE.match(t)
                    if m:
                        bad.append((ln, f"полная поза «{m.group(2)}» ВНУТРИ "
                                        f"реплики — сбрасывает липсинк, рот "
                                        f"прыгнет; поставь её между репликами "
                                        f"или сделай слоем (overlays)"))
                    m = OVERLAY.match(t)
                    if m and m.group(2) in with_mouth:
                        bad.append((ln, f"слой «{m.group(2)}» ВНУТРИ реплики "
                                        f"трогает рот — перебьёт липсинк до "
                                        f"следующего флэпа; ставь до или после"))
            i = j
        i += 1
    return bad, spoken


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)

    files = a.files
    if a.all or not files:
        files = sorted(glob.glob(str(ROOT / "examples/**/*.anim"), recursive=True))
        files = [f for f in files if not Path(f).name.startswith(".")]

    total = 0
    print("\n  РЕЧЬ И ЛИЦО\n")
    for f in files:
        bad, spoken = check(f)
        if not spoken:
            continue
        name = Path(f).name
        if bad:
            print(f"    {name}: реплик {spoken}, нарушений {len(bad)}")
            for ln, msg in bad:
                print(f"      [ПРОВАЛ] строка {ln}: {msg}")
            total += len(bad)
        else:
            print(f"    [OK] {name}: реплик {spoken}, рот ведёт только речь")
    if total:
        print(f"\n  Нарушений: {total}. Почему это ошибки — в шапке этого файла.\n")
        return 1
    print("\n  Все речевые блоки чисты.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
