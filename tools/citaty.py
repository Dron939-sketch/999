#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
citaty.py — ГЕЙТ: комментарий в раскадровке цитирует реплику, которой больше нет.

ЗАЧЕМ. У каждого `//lip N` в раскадровке стоят комментарии вида

    freeman overlays "klin"        // «не вам»

Это цитата из реплики VO-N: она объясняет, ЗАЧЕМ здесь именно этот слой, и по
ней раскадровку читают как партитуру. Реплики правятся часто — на вычитке, на
замечании студии, на замере хронометража, — а комментарии остаются старыми.
Через три правки комментарий начинает описывать текст, которого в ролике нет,
и раскадровка тихо превращается в художественную литературу.

Заметить это глазом нельзя: файл на девятьсот строк, цитат в нём под сотню, и
все выглядят правдоподобно. Поймали руками ровно один раз — комментарий
`// «каждый по трём случаям»` пережил реплику, которую переписали, потому что
рассказчик в ней обобщал.

КАК ПРОВЕРЯЕТСЯ. Из цитаты берутся слова длиннее трёх букв; если ни одного из
них нет в реплике с тем же номером — цитата оторвалась. Знаки ударения (U+0301)
снимаются с обеих сторон, регистр и пунктуация не учитываются. Проверка нарочно
мягкая: комментарий имеет право сокращать и перефразировать, он не обязан
совпадать дословно. Ловится только полный отрыв.

Использование:
    python3 tools/citaty.py examples/lektorij/logika.anim
    python3 tools/citaty.py --all
"""

import argparse
import glob
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def bez_udareniy(x):
    x = unicodedata.normalize("NFD", x)
    return "".join(c for c in x if c != "\u0301")


def slova(x):
    return re.sub(r"[^\w ]", " ", bez_udareniy(x).lower(), flags=re.U).split()


def repliki(vo_path):
    """{номер: набор слов реплики} из VO-таблицы."""
    out = {}
    for line in Path(vo_path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| VO-(\d+) \|", line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        quoted = [c for c in cells if "\u00ab" in c and "\u00bb" in c]
        if not quoted:
            continue
        # ЁЛОЧКИ БЫВАЮТ ВЛОЖЕННЫМИ: «Курс «Теории личности». Двадцать линз…».
        # Нежадный поиск обрывает реплику на первой внутренней кавычке, и всё,
        # что дальше, начинает считаться отсутствующим. Берём от ПЕРВОЙ « до
        # ПОСЛЕДНЕЙ » в ячейке.
        cell = quoted[0]
        text = cell[cell.index("\u00ab") + 1 : cell.rindex("\u00bb")]
        out[int(m.group(1))] = set(slova(text))
    return out


def proverit(anim_path, vo_path):
    rep = repliki(vo_path)
    src = Path(anim_path).read_text(encoding="utf-8")
    parts = re.split(r"//lip (\d+)\n", src)
    bad = []
    for i in range(1, len(parts), 2):
        n = int(parts[i])
        body = parts[i + 1]
        end = body.find("\n    }")
        body = body[: end if end > 0 else 600]
        # ТОЛЬКО ХВОСТОВЫЕ КОММЕНТАРИИ, а не строки-абзацы. Цитата реплики
        # всегда стоит ПОСЛЕ кода: `freeman overlays "klin"  // «не вам»`.
        # Отдельная строка `//  «НЕ stern: та трогает рот»` — это прозаический
        # разбор в шапке блока, он цитирует не реплику, а сам себя, и попадал в
        # улов ложно.
        for citata in re.findall(r"\S[^\n]*?//\s*\u00ab([^\u00bb]{4,})\u00bb", body):
            w = [x for x in slova(citata) if len(x) > 3]
            if w and not any(x in rep.get(n, ()) for x in w):
                bad.append((n, citata))
    return bad, len(rep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("anim", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    pary = []
    if a.all:
        for f in sorted(glob.glob(str(ROOT / "examples" / "**" / "*.anim"), recursive=True)):
            vo = Path(f).with_name(Path(f).stem + "-VO.md")
            if vo.exists():
                pary.append((f, vo))
    else:
        for f in a.anim:
            vo = Path(f).with_name(Path(f).stem + "-VO.md")
            if not vo.exists():
                print(f"  [ПРОПУСК] {Path(f).name}: нет VO-сценария рядом")
                continue
            pary.append((f, vo))

    print("\n  ЦИТАТЫ В РАСКАДРОВКЕ — ЖИВЫ ЛИ РЕПЛИКИ, НА КОТОРЫЕ ОНИ ССЫЛАЮТСЯ\n")
    plohih = 0
    for anim, vo in pary:
        bad, n = proverit(anim, vo)
        if bad:
            plohih += len(bad)
            print(f"    [ПРОВАЛ] {Path(anim).name}: маркеров {n}, оторвавшихся цитат {len(bad)}")
            for num, c in bad:
                print(f"        lip {num}: \u00ab{c}\u00bb \u2014 таких слов в реплике VO-{num} нет")
        else:
            print(f"    [OK] {Path(anim).name}: маркеров {n}, все цитаты живы")
    if plohih:
        print("\n  Комментарий описывает текст, которого в ролике нет. Раскадровку")
        print("  читают как партитуру — она обязана совпадать с тем, что звучит.")
        return 1
    print("\n  Раскадровка говорит о ролике правду.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
