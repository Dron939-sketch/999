#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pyl.py — ЧТО НА ЗАВОДЕ ПЫЛИТСЯ: наработки, которыми никто не пользуется.

ЗАЧЕМ. Требование студии: «проверь весь завод, чтобы все наработки были
использованы, а не пылились». Ревизия руками нашла много и займёт полдня в
следующий раз — а пыль копится сама, без чьей-либо ошибки: инструмент пишут
под задачу, задача уходит, вызов из конвейера никто не ставит.

Отчёт считает четыре кучи и по каждой печатает ИМЕНА, а не число:

  1. ПОЗЫ РИГА, не поставленные ни в один ролик. Виземы (`visA`…`visF`)
     из счёта исключены — их ставит липсинк, а не автор.
  2. ВОЗМОЖНОСТИ ДВИЖКА: действия DSL и приёмы камеры, которые движок умеет,
     а ролики не берут. Читается из `DSL.md`, чтобы список не разъезжался с
     тем, что реально поддержано.
  3. СТАНКИ ШУТОК из `BANK-SHUTOK.md`, ни разу не названные в шапках VO.
  4. ИНСТРУМЕНТЫ `tools/*.py`, которых не вызывает ни конвейер, ни другой
     инструмент, ни CI. Часть из них — цеховая оснастка под руку (рисовать
     позы, снимать мерки с оригинала), и это законно; отчёт не приговор, а
     список к разговору.

ПОЧЕМУ ЭТО НЕ ГЕЙТ. Пыль не брак: неиспользованная поза ничего не ломает.
Гейтом идёт `rost.py` — он требует, чтобы КАЖДЫЙ ролик брал что-то из этих
куч. Отчёт же показывает, из чего выбирать, и растёт ли куча.

Использование:
    python3 tools/pyl.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VIZEMA = re.compile(r"^vis[A-Z]")
POZA = re.compile(r'^\s*\w+\s+(?:pose|overlays)\s+"([^"]+)"', re.M)
CAM = re.compile(r"^\s*camera\s+([a-z-]+)", re.M)
DSL_ACT = re.compile(r"^####\s+([a-z][a-z-]+)\s*$", re.M)
DSL_SHOT = re.compile(r"^\|\s*`([a-z][a-z-]+)`\s*\|", re.M)
STANOK = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.M)


def animy():
    return sorted(ROOT.glob("examples/**/*.anim"))


def kucha_poz():
    rig = ROOT / "examples/assets/characters/freeman_rig/rig.json"
    if not rig.exists():
        return None
    vse = set(json.loads(rig.read_text(encoding="utf-8")).get("poses", {}))
    vse = {p for p in vse if not VIZEMA.match(p)}
    use = set()
    for a in animy():
        use |= set(POZA.findall(a.read_text(encoding="utf-8")))
    return vse, sorted(vse - use)


def kucha_dvizhka():
    dsl = (ROOT / "DSL.md").read_text(encoding="utf-8")
    #  Действия — заголовки «#### <глагол>» в разделе Actions; приёмы камеры —
    #  первая колонка таблицы Shot Types. Оба списка берутся из документа, а не
    #  переписываются сюда: переписанный список устаревает молча.
    #  Срез до СЛЕДУЮЩЕГО раздела верхнего уровня. Без границы в список
    #  действий попадают заголовки из «Character Definition» (`face`, `hair`,
    #  `outfit`) — это поля JSON-персонажа, а не глаголы сцены, и отчёт врал.
    nach = dsl.index("### Actions")
    kon = dsl.index("\n## ", nach)
    deystviya = {a for a in DSL_ACT.findall(dsl[nach:kon])}
    shot = dsl[dsl.index("#### Shot Types"):]
    plany = set(DSL_SHOT.findall(shot[:shot.index("```")]))

    ud, up = set(), set()
    for a in animy():
        t = a.read_text(encoding="utf-8")
        up |= set(CAM.findall(t))
        for d in deystviya:
            if re.search(rf"^\s*\w+\s+{re.escape(d)}\b", t, re.M):
                ud.add(d)
    return sorted(deystviya - ud), sorted(plany - up)


def kucha_shutok():
    bank = (ROOT / "BANK-SHUTOK.md").read_text(encoding="utf-8")
    stanki = {n: name for n, name in STANOK.findall(bank)}
    nazvany = set()
    for vo in ROOT.glob("examples/**/*-VO.md"):
        t = vo.read_text(encoding="utf-8")
        m = re.search(r"^\*\*ШУТКА[^\n]*\n(?:[^\n]*\n)*?", t, re.M)
        golova = t[m.start():m.start() + 600] if m else ""
        for n, name in stanki.items():
            if re.search(rf"станок\s*{n}\b", golova, re.I) or name.lower() in golova.lower():
                nazvany.add(n)
    return [(n, s) for n, s in sorted(stanki.items(), key=lambda x: int(x[0]))
            if n not in nazvany]


def kucha_instrumentov():
    tools = sorted(p.stem for p in (ROOT / "tools").glob("*.py"))
    korpus = {}
    for f in list(ROOT.glob("tools/*.py")) + list(ROOT.glob(".github/workflows/*.yml")):
        korpus[f.name] = f.read_text(encoding="utf-8", errors="ignore")
    #  Вызов ищется как ИМЯ МОДУЛЯ в чужом файле: и `python3 tools/x.py`, и
    #  `import x`, и `from x import …` дают одно и то же вхождение.
    #  Документация считается отдельно. Инструмент, который никто не вызывает,
    #  но который ОПИСАН в методичке, — это цеховая оснастка под руку, и её
    #  место законно. Пыль — то, что не вызывается И нигде не описано: про
    #  такой инструмент через полгода не вспомнит никто, включая автора.
    doki = {str(f): f.read_text(encoding="utf-8", errors="ignore")
            for f in ROOT.rglob("*.md")
            if ".git" not in f.parts and "target" not in f.parts}
    nikto, rukami = [], []
    for t in tools:
        if any(re.search(rf"\b{re.escape(t)}\b", txt)
               for name, txt in korpus.items() if name != f"{t}.py"):
            continue
        (rukami if any(re.search(rf"\b{re.escape(t)}\b", txt)
                       for txt in doki.values()) else nikto).append(t)
    return nikto, rukami


def main():
    print("\n  ЧТО ПЫЛИТСЯ НА ЗАВОДЕ\n")

    p = kucha_poz()
    if p:
        vse, ni = p
        print(f"  ПОЗЫ РИГА — не поставлены ни в один ролик: {len(ni)} из {len(vse)}")
        print(f"    {', '.join(ni)}\n")

    da, dp = kucha_dvizhka()
    print(f"  ДВИЖОК — действия DSL, ни разу не взятые: {len(da)}")
    print(f"    {', '.join(da) or '—'}")
    print(f"  ДВИЖОК — приёмы камеры, ни разу не взятые: {len(dp)}")
    print(f"    {', '.join(dp) or '—'}\n")

    sh = kucha_shutok()
    print(f"  БАНК ШУТОК — станки, не названные ни в одной шапке: {len(sh)}")
    for n, name in sh:
        print(f"    · {n}. {name}")
    print()

    nikto, rukami = kucha_instrumentov()
    print(f"  ИНСТРУМЕНТЫ — не вызываются и нигде не описаны: {len(nikto)}")
    print(f"    {', '.join(nikto) or '—'}")
    print(f"  ИНСТРУМЕНТЫ — не в конвейере, но описаны как ручная оснастка: "
          f"{len(rukami)}")
    print(f"    {', '.join(rukami) or '—'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
