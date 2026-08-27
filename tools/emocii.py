#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emocii.py — ГЕЙТ РАЗНООБРАЗИЯ: ролик не повторяет два предыдущих.

ЗАЧЕМ. Замечание студии: «все ролики похожи, а нужно, чтобы каждый раз
вызывалась разная эмоция». Замер подтвердил претензию арифметикой (разбор —
`EMOCII.md` §I): у «Эстетики», «Этики» и «Экзистенциальных вопросов» профиль
подачи совпал ЕДИНИЦА В ЕДИНИЦУ, а пять последних роликов открываются одной
конструкцией «Вы + глагол».

Стандартизирована оказалась не структура, а эмоциональная кривая. Правило
3–7–21 задаёт ЧАСЫ — когда перезагружается внимание, — и ничего не говорит о
том, каким ЗАРЯДОМ бить на засечке. Мы четыре ролика подряд ставили на одни
часы один и тот же заряд.

ЧТО СЧИТАЕТСЯ. Ролик сверяется с ДВУМЯ ПРЕДЫДУЩИМИ по порядку продакшена
(`tools/productions.json` — порядок сдачи, а не алфавит):

  1. эмоция объявлена строкой `**ЭМОЦИЯ:**` и входит в палитру;
  2. эмоция не повторяет ни один из двух предыдущих роликов;
  3. доминанта подачи соответствует эмоции: названный регистр первый или
     второй по доле в партитуре;
  4. профиль регистров отличается от предыдущего — косинус < 0.96;
  5. тип хука не совпадает с обоими предыдущими.

ПОРОГ 0.96 СНЯТ С КАТАЛОГА. Живые переходы дают 0.726–0.946 (стоицизм после
паруса, отказ после трёх раз, станок после логики), копии — 0.968–1.000.
Порог разводит два облака с запасом.

ПОЧЕМУ ЭТО НЕ ВКУСОВЩИНА. Гейт не оценивает, ХОРОША ли эмоция. Он проверяет
ровно одно: что она ДРУГАЯ. Одинаковость — единственное, что можно померить
без спора, и именно она была претензией.

Использование:
    python3 tools/emocii.py examples/lektorij/lozh-VO.md
    python3 tools/emocii.py --all
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PALITRA = {
    "стыд узнавания": ("приговор", "ирония"),
    "облегчение": ("тепло", "буднично"),
    "злость на устройство": ("приговор", "вызов"),
    "азарт": ("вызов", "вовлечение"),
    "тревога узнавания": ("тревога", "приговор"),
    "нежность": ("тепло", "вовлечение"),
    "любопытство": ("вовлечение", "буднично"),
}

POROG = 0.96          # выше — считается повтором предыдущего ролика

#  Скелет — устройство основной части, а не жанр. Их три, и это не список
#  «на выбор из многого»: любое четвёртое устройство надо сначала завести в
#  EMOCII.md §IV, объяснив, чем оно держит внимание.
SKELETY = {"разбор", "притча", "прямой показ"}

EMO = re.compile(r"^\s*\*\*ЭМОЦИЯ:?\*\*\s*:?\s*([^—\n]+?)\s*(?:—|$)", re.M | re.I)
SKEL = re.compile(r"^\s*\*\*СКЕЛЕТ:?\*\*\s*:?\s*([^—\n]+?)\s*(?:—|$)", re.M | re.I)
#  Станок шутки — номер раздела `BANK-SHUTOK.md`. Банк заведён именно потому,
#  что готовая шутка протухает за семь роликов: приём превращается в слот, слот
#  заполняется автоматически. Слотом может стать и сам станок — пять последних
#  роликов взяли первый и только первый, а их в банке восемь.
STANOK = re.compile(r"Станок\s+(\d+)", re.I)
REG = re.compile(r"^\|\s*\d+\s*\|\s*[\d.]+\s*\|\s*([а-яё]+)\s*\|", re.M)
REPL = re.compile(r"^\|\s*VO-?\d+\s*\|[^|]*\|[^|]*\|\s*«(.*?)»", re.M)


def hod_huka(t):
    """Тип захода по ПЕРВОЙ реплике. Форма, а не содержание."""
    t = t.strip()
    if not t:
        return "нет"
    if t.startswith(("«", '"')):
        return "чужая реплика"
    if re.match(r"^(Я|Мне|Меня)\b", t):
        return "признание рассказчика"
    if re.match(r"^\d|^(Один|Два|Три|Четыре|Пять|Шесть|Семь|Восемь|Девять|Десять|"
                r"Сорок|Пятьдесят|Сто)\b", t, re.I):
        return "число"
    if re.match(r"^(Вы|Ваш|Вам|Вас)\b", t):
        return "обвинение"
    if t.rstrip().endswith("?"):
        return "вопрос"
    if re.match(r"^[А-ЯЁ][а-яё]+(те|йте|и)\b", t):
        return "приказ"
    return "сцена"


def razbor(path):
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    m = EMO.search(t)
    s = SKEL.search(t)
    regs = REG.findall(t)
    repl = REPL.findall(t)
    c = Counter(regs)
    vsego = sum(c.values())
    return {
        "id": p.stem.replace("-VO", ""),
        "emo": (m.group(1).strip().lower() if m else None),
        "skelet": (s.group(1).strip().lower() if s else None),
        "stanok": (STANOK.search(t).group(1) if STANOK.search(t) else None),
        "profil": {k: v / vsego for k, v in c.items()} if vsego else {},
        "top": [k for k, _ in c.most_common(2)],
        "huk": hod_huka(repl[0]) if repl else "нет",
        "est_partitura": vsego >= 12,
    }


def cos(a, b):
    ks = set(a) | set(b)
    num = sum(a.get(k, 0) * b.get(k, 0) for k in ks)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    return num / (da * db) if da and db else 0.0


def poryadok():
    """id роликов в порядке сдачи, у которых есть VO с партитурой."""
    prods = json.loads((ROOT / "tools/productions.json").read_text(encoding="utf-8"))
    out = []
    for p in prods["productions"]:
        vo = p.get("vo")
        if not vo:
            continue
        f = ROOT / vo
        if f.exists() and razbor(f)["est_partitura"]:
            out.append((p["id"], f))
    return out


def proverit(target):
    ryad = poryadok()
    ids = [i for i, _ in ryad]
    tid = Path(target).stem.replace("-VO", "")
    if tid not in ids:
        return [("ролик в реестре продакшена", False,
                 f"«{tid}» нет в tools/productions.json — порядок сдачи "
                 f"неизвестен, сравнивать не с чем")]
    k = ids.index(tid)
    ja = razbor(target)
    pred = [razbor(f) for _, f in ryad[max(0, k - 2):k]]

    out = []
    out.append(("эмоция объявлена и есть в палитре",
                ja["emo"] in PALITRA,
                f"«{ja['emo']}» — не из палитры (EMOCII.md §II)" if ja["emo"]
                else "в шапке нет строки «**ЭМОЦИЯ:**»"))

    povtor = [p["id"] for p in pred if p["emo"] and p["emo"] == ja["emo"]]
    out.append(("эмоция не повторяет два предыдущих", not povtor,
                f"та же эмоция, что у {', '.join(povtor)} — зритель получит "
                f"третий раз одно состояние, и польза курсов сольётся"))

    if ja["emo"] in PALITRA:
        nado = PALITRA[ja["emo"]]
        est = any(r in ja["top"] for r in nado)
        out.append((f"доминанта подачи соответствует эмоции", est,
                    f"объявлено «{ja['emo']}» (доминанта {nado[0]}/{nado[1]}), "
                    f"а по партитуре ведут {ja['top']} — надпись, а не работа"))

    if pred:
        s = cos(ja["profil"], pred[-1]["profil"])
        out.append((f"профиль подачи отличается от предыдущего ({s:.3f})",
                    s < POROG,
                    f"кривая подачи совпадает с «{pred[-1]['id']}» на {s:.3f} "
                    f"при пороге {POROG}: те же доли регистров в том же порядке"))

    out.append(("скелет объявлен и есть в списке трёх",
                ja["skelet"] in SKELETY,
                f"«{ja['skelet']}» — не из трёх законных устройств "
                f"(EMOCII.md §IV)" if ja["skelet"]
                else "в шапке нет строки «**СКЕЛЕТ:**»"))

    skel = [p["skelet"] for p in pred]
    out.append((f"скелет «{ja['skelet']}» не идёт третий раз подряд",
                not (len(skel) == 2 and skel[0] == skel[1] == ja["skelet"]),
                f"третий ролик подряд собран одним устройством — "
                f"{', '.join(p['id'] for p in pred)}. Зритель узнаёт ход "
                f"наперёд, и перелом перестаёт быть переломом"))

    st = [p["stanok"] for p in pred]
    out.append((f"станок шутки «{ja['stanok'] or '—'}» назван и не третий подряд",
                bool(ja["stanok"]) and
                not (len(st) == 2 and st[0] == st[1] == ja["stanok"]),
                "в шапке не назван станок из BANK-SHUTOK.md" if not ja["stanok"]
                else f"третий ролик подряд на станке {ja['stanok']} — "
                     f"{', '.join(p['id'] for p in pred)}. Банк знает восемь; "
                     f"приём, ставший слотом, перестаёт быть шуткой"))

    huki = [p["huk"] for p in pred]
    out.append((f"ход хука «{ja['huk']}» не совпадает с обоими предыдущими",
                not (len(huki) == 2 and huki[0] == huki[1] == ja["huk"]),
                f"третий раз подряд заход «{ja['huk']}» — "
                f"{', '.join(p['id'] for p in pred)}"))
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="Гейт разнообразия эмоций")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true",
                    help="пройти по всему реестру продакшена и напечатать карту")
    a = ap.parse_args(argv)

    if a.all:
        ryad = poryadok()
        print("\n  КАРТА ЭМОЦИЙ ПО ПОРЯДКУ СДАЧИ\n")
        prev = None
        for i, f in ryad:
            r = razbor(f)
            s = f"{cos(r['profil'], prev['profil']):.3f}" if prev else "  —  "
            print(f"    {i:24} {str(r['emo'] or '—'):22} "
                  f"{str(r['skelet'] or '—'):14} "
                  f"хук: {r['huk']:22} сходство {s}")
            prev = r
        print()
        return 0

    if not a.files:
        raise SystemExit("укажи VO-файл или --all")
    bad = 0
    for f in a.files:
        print(f"\n  РАЗНООБРАЗИЕ: {Path(f).name}\n")
        for name, ok, why in proverit(f):
            print(f"    [{'OK  ' if ok else 'ПРОВАЛ'}] {name}")
            if not ok:
                bad += 1
                print(f"             → {why}")
    if bad:
        print(f"\n  Совпадений с предыдущими: {bad}. "
              f"Ролик повторяет то, что зритель уже видел.\n")
        return 1
    print("\n  Ролик не повторяет два предыдущих.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
