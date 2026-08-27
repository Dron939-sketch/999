#!/usr/bin/env python3
"""СЛУШАТЕЛЬ: где зритель отваливается.

Приёмщики сценария (`script_lint.py`) проверяют устройство текста: биты
формулы, длину фраз, запрещённые обороты. Слушатель проверяет другое — как
текст ложится на УХО подряд, минута за минутой. Он не про правильность, он
про удержание.

Меряет три вещи, каждая из которых уводит зрителя:

1. КОГДА ЕГО ПОЗВАЛИ. Секунда, на которой в тексте впервые появляется «ты» /
   «тебя» / «твой». Пока зритель не назван, он наблюдатель.

2. ДИСТАНЦИЯ БЕЗ ЗАЦЕПКИ. Зацепка — то, за что ухо цепляется само:
   вопрос, число, приказ, названный предмет из быта, прямое обращение.
   Считаем секунды между соседними зацепками. Дыра длиннее ~12 секунд —
   это место, где зритель уходит; на ней и обрывается досмотр.

3. ДОЛЯ АБСТРАКЦИИ. Реплики, где нет ни одного конкретного существительного
   и ни одного числа. «Свобода — это различать» держится только если рядом
   стоит «на полке лежала последняя».

Темп берётся замеренный: слов в секунду задаётся --rate (по умолчанию
1.66 — среднее по собранным дорожкам завода).
"""
import argparse
import re
import sys

VOCATIVE = re.compile(r"\b(ты|тебе|тебя|тобой|твой|твоя|твоих|твоей|твою|твоего)\b", re.I)
ORDER = re.compile(r"\b(проживи|назови|смотри|слышишь|следи|проверь|сядь|стоп|жди)\b", re.I)
NUMBER = re.compile(r"\b(\d+|один|два|три|четыре|пять|шесть|семь|восемь|девять|десять|"
                    r"двадцать|тридцать|сорок|пятьдесят|сто|двести|тысяч\w*|месяц\w*|"
                    r"час\w*|сутки|день|дня|дней)\b", re.I)
# Быт: предметы и роли, которые зритель видел вчера.
CONCRETE = re.compile(
    r"\b(кредит\w*|полк[аеи]|очеред\w*|мам\w*|телефон\w*|ноутбук\w*|витрин\w*|кухн\w*|"
    r"кноп\w*|дверь|двери|стул\w*|стол\w*|календар\w*|экран\w*|браузер\w*|работ\w*|"
    r"начальник\w*|коллег\w*|домашн\w*|врач\w*|сон|спать|спал|ночи|ночь|пятниц\w*|"
    r"вторник\w*|переплат\w*|одобрен\w*|карт\w*|пауз\w*|игр\w*|ссылк\w*)\b", re.I)
ABSTRACT_OK = re.compile(r"\b(свобод\w*|достоинств\w*|смысл\w*|бдительност\w*|"
                         r"усталост\w*|глупост\w*|обман\w*|довери\w*)\b", re.I)

ROW = re.compile(r"^\|\s*VO-(\d+)\s*\|([^|]*)\|([^|]*)\|(.*)\|\s*$")


def rows(path):
    out = []
    for line in open(path, encoding="utf-8"):
        m = ROW.match(line.rstrip())
        if not m:
            continue
        text = m.group(4)
        rep = re.search(r"«(.+?)»", text)
        out.append({"n": int(m.group(1)), "beat": m.group(3).strip(),
                    "text": rep.group(1) if rep else text.strip()})
    return out


def hooks(t):
    """Какие зацепки есть в реплике."""
    h = []
    if "?" in t: h.append("вопрос")
    if ORDER.search(t): h.append("приказ")
    if NUMBER.search(t): h.append("число")
    if CONCRETE.search(t): h.append("предмет")
    if VOCATIVE.search(t): h.append("обращение")
    return h


def report(path, rate, gap_max):
    rs = rows(path)
    if not rs:
        print(f"{path}: не нашёл таблицы VO"); return 1
    t = 0.0
    first_you = None
    last_hook = 0.0
    holes, dry = [], []
    print(f"\n=== {path} ===")
    for r in rs:
        words = len(r["text"].split())
        dur = words / rate
        h = hooks(r["text"])
        if first_you is None and VOCATIVE.search(r["text"]):
            first_you = t
        if h:
            gap = t - last_hook
            if gap > gap_max:
                holes.append((last_hook, gap, r["n"]))
            last_hook = t + dur
        if not CONCRETE.search(r["text"]) and not NUMBER.search(r["text"]) \
                and not ABSTRACT_OK.search(r["text"]):
            dry.append(r["n"])
        mark = ",".join(h) or "—"
        print(f"  VO-{r['n']:<3} {t:6.1f}с {dur:5.1f}с  {mark:32s} {r['text'][:52]}")
        t += dur
    total = t
    print(f"\n  хронометраж по тексту: {int(total//60)}:{total%60:04.1f} ({rate} слов/с)")
    print(f"  зрителя позвали на: {first_you:.1f}с" if first_you is not None
          else "  зрителя не позвали ни разу")
    if holes:
        for start, gap, n in holes:
            print(f"  ДЫРА {gap:.1f}с без зацепки — с {start:.1f}с до VO-{n}")
    else:
        print(f"  дыр без зацепки длиннее {gap_max}с нет")
    if dry:
        print(f"  реплики без конкретики: {', '.join('VO-' + str(x) for x in dry)} "
              f"({100 * len(dry) / len(rs):.0f}%)")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Слушатель: где зритель отваливается")
    ap.add_argument("scripts", nargs="+")
    ap.add_argument("--rate", type=float, default=1.66, help="слов в секунду")
    ap.add_argument("--gap", type=float, default=12.0, help="потолок дыры без зацепки, с")
    a = ap.parse_args(argv)
    rc = 0
    for s in a.scripts:
        rc |= report(s, a.rate, a.gap)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
