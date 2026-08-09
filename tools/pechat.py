#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pechat.py — ПЕЧАТЬ НА ШАГЕ, КОТОРЫЙ УЖЕ СДЕЛАН.

ЗАЧЕМ. Два шага завода делает ЧЕЛОВЕК, и машина не может их выполнить за него:

  · ВЫЧИТКА — понятна ли реплика на слух с первого раза (`VYCHITKA.md`);
  · МИЗАНСЦЕНЫ — не срезала ли фигуру мебель, туда ли смотрит жест
    (контактный лист `tools/mizanscena.py`).

Оба шага одинаково устроены: их можно пройти, а можно сказать, что прошёл.
Разницы в файле не остаётся никакой. Так и вышло: текст «Спорта» был вычитан по
черновику, потом шесть реплик переписали по разбору оригинала — и вычитку не
повторили. Выяснилось это только от прямого вопроса студии, а повторный прогон
нашёл три места из шести переписанных.

ЧТО ДЕЛАЕТ ЭТОТ ИНСТРУМЕНТ. Ставит в файл ПЕЧАТЬ — короткий хэш того самого
материала, который человек смотрел. Дальше гейт пересчитывает хэш по текущему
файлу и сверяет. Изменил текст после вычитки — печать протухла, и это ВИДНО,
без всякой внимательности.

Печать не доказывает, что человек читал внимательно. Она доказывает ровно одно:
что он читал ИМЕННО ЭТОТ текст, а не тот, что был три правки назад. Этого
достаточно — пропуск шага перестаёт быть бесследным.

ЧТО ИМЕННО ХЭШИРУЕТСЯ

  · вычитка — только произносимые реплики VO-таблицы, без ремарок, локаций,
    таймкодов и шапки. Правка ремарки вычитку не роняет: её слушатель не
    слышит. Правка слова — роняет;
  · мизансцены — только строки расстановки: `set:`, `place`, `scales`,
    `camera`. Переписал реплику — лист не протух; подвинул фигуру — протух.

Использование:
    python3 tools/pechat.py --vychitka examples/lektorij/sport-VO.md
    python3 tools/pechat.py --mizanscena examples/lektorij/sport.anim
    python3 tools/pechat.py --check examples/lektorij/sport-VO.md
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Реплика в VO-таблице: четвёртая колонка, текст в «ёлочках» до ремарки.
REPLIKA = re.compile(r"^\|\s*VO-?\d+\s*\|[^|]*\|[^|]*\|\s*«(.*?)»", re.M)
# Строки расстановки в раскадровке.
MIZAN = re.compile(r"^\s*(?:place\s+\w+\s+at\s*\([^)]*\)[^\n]*|"
                   r"\w+\s+scales\s+[\d.]+[^\n]*|"
                   r"camera\s+\w+[^\n]*|"
                   r"scene\s+\"[^\"]+\"\s*\([^)]*\)[^\n]*)$", re.M)

# Двоеточие в наших шапках стоит и внутри жирного, и снаружи — принимаем оба.
STAMP_VYCH = re.compile(r"\*\*ВЫЧИТКА(?:\s*\(реплики\s+([0-9a-f]{8})\))?\s*:?\*\*\s*:?")
STAMP_MIZ = re.compile(r"^//\s*МИЗАНСЦЕНЫ ПРОСМОТРЕНЫ:\s*([0-9a-f]{8})\s*$", re.M)


def _hash(parts):
    """Хэш по СОДЕРЖАНИЮ, а не по форматированию.

    Пробелы схлопываются, регистр не трогаем: «Штанга» и «штанга» — разные
    слова для слушателя, значит и для печати тоже.
    """
    norm = "\n".join(re.sub(r"\s+", " ", p).strip() for p in parts)
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:8]


def hash_vychitki(path):
    return _hash(REPLIKA.findall(Path(path).read_text(encoding="utf-8")))


def hash_mizanscen(path):
    return _hash(MIZAN.findall(Path(path).read_text(encoding="utf-8")))


def postavit_vychitku(path):
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    h = hash_vychitki(p)
    m = STAMP_VYCH.search(t)
    if not m:
        return None, ("в шапке нет строки «**ВЫЧИТКА:**» — сначала напиши, "
                      "ЧТО она нашла, потом ставь печать")
    t = t[:m.start()] + f"**ВЫЧИТКА (реплики {h}):**" + t[m.end():]
    p.write_text(t, encoding="utf-8")
    return h, None


def postavit_mizanscenu(path):
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    h = hash_mizanscen(p)
    m = STAMP_MIZ.search(t)
    stroka = f"//  МИЗАНСЦЕНЫ ПРОСМОТРЕНЫ: {h}"
    if m:
        t = t[:m.start()] + stroka + t[m.end():]
    else:
        # кладём последней строкой шапки, перед закрывающей чертой
        cherta = t.find("// ====", 60)
        konec = t.find("\n", t.rfind("// ===", 0, t.find("import ")))
        t = t[:konec] + "\n//\n" + stroka + t[konec:]
    p.write_text(t, encoding="utf-8")
    return h, None


def proverit(path):
    """[(имя, ок, что не так)] — обе печати, если файл их предполагает."""
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    out = []
    if p.name.endswith("-VO.md"):
        m = STAMP_VYCH.search(t)
        est = m.group(1) if m else None
        nado = hash_vychitki(p)
        out.append(("печать вычитки", est == nado,
                    "строки «ВЫЧИТКА:» нет вовсе" if not m else
                    ("печати нет: строка есть, но не сказано, ПО КАКОМУ тексту "
                     "читали — поставь `pechat.py --vychitka`") if not est else
                    f"печать {est}, а текст сейчас {nado} — реплики правили "
                    f"ПОСЛЕ вычитки. Перечитать заново и переставить печать"))
    if p.suffix == ".anim":
        m = STAMP_MIZ.search(t)
        est = m.group(1) if m else None
        nado = hash_mizanscen(p)
        out.append(("печать мизансцен", est == nado,
                    "в шапке нет строки «МИЗАНСЦЕНЫ ПРОСМОТРЕНЫ:» — собери "
                    "контактный лист, ПОСМОТРИ его и поставь печать" if not est
                    else f"печать {est}, а расстановка сейчас {nado} — фигуру "
                         f"двигали после того, как лист смотрели"))
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="Печать на пройденном шаге завода")
    ap.add_argument("--vychitka", metavar="VO.md")
    ap.add_argument("--mizanscena", metavar="FILE.anim")
    ap.add_argument("--check", nargs="+", metavar="FILE")
    a = ap.parse_args(argv)

    if a.vychitka:
        h, err = postavit_vychitku(a.vychitka)
        if err:
            print(f"  {err}", file=sys.stderr)
            return 1
        print(f"  печать вычитки: {h}")
    if a.mizanscena:
        h, err = postavit_mizanscenu(a.mizanscena)
        if err:
            print(f"  {err}", file=sys.stderr)
            return 1
        print(f"  печать мизансцен: {h}")
    if a.check:
        bad = 0
        print("\n  ПЕЧАТИ НА ШАГАХ, КОТОРЫЕ ДЕЛАЕТ ЧЕЛОВЕК\n")
        for f in a.check:
            for name, ok, why in proverit(f):
                print(f"    [{'OK  ' if ok else 'ПРОВАЛ'}] {Path(f).name}: {name}")
                if not ok:
                    bad += 1
                    print(f"             → {why}")
        if bad:
            print(f"\n  Печатей не сходится: {bad}. Шаг не пройден — "
                  f"на завод не отправлять.\n")
            return 1
        print("\n  Обе печати свежие: человек смотрел ровно этот материал.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
