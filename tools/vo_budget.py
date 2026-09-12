#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vo_budget.py — СКОЛЬКО РЕАЛЬНО ПРОЗВУЧИТ СЦЕНАРИЙ, до синтеза.

ЗАЧЕМ. Две подводки ушли на завод с `speaks for N`, прикинутыми на глаз, и
вернулись озвученными на 68.5 и 79.4 секунды при потолке 60. Гейт длины
(`lint_dlina`) мягкий, прогон остался зелёным, и ролики уехали в релиз
полуторной длины. Причина в том, что `script_lint` проверяет слова в ударной
фразе (≤7), но не проверяет, СКОЛЬКО ЭТО ЗВУЧИТ, — а Fish (модель s2) держит
паузу почти в секунду на каждой точке. Рубленый стиль «Ма́ма. Тре́нер. Сосе́д
Серёга.» — это три паузы там, где текста на две секунды.

МОДЕЛЬ. Откалибрована по 18 репликам двух озвученных прогонов (фактические
длины — из `voiceover.py --assemble-only`, «Сборка по временам движка»):

    длина ≈ 0.494 с/слово + 0.916 с/паузу + 0.18 с      (ср. ошибка 0.58 с)

Пауза — граница предложения (. ! ? …). Разброс самого синтеза ±0.7 с на
реплику (одно и то же приветствие вышло 4.99 и 5.69 с), поэтому запас
закладывать обязательно: бюджет речи считать с потолка 60 с МИНУС
неречевое время сценария МИНУС 2 с.

Использование:
    python3 tools/vo_budget.py examples/lektorij/svoe-delo-intro-VO.md
    python3 tools/vo_budget.py examples/lektorij/svoe-delo-intro-VO.md \\
        --anim examples/lektorij/svoe-delo-intro.anim      # с бюджетом от сцены
    python3 tools/vo_budget.py <VO.md> --patch-anim <anim>  # вписать speaks for
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import script_lint as L  # noqa: E402

PER_WORD, PER_PAUSE, BASE = 0.494, 0.916, 0.18
CEILING = 60.0
MARGIN = 2.0
ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "target" / "release" / "animdsl"


def estimate(text):
    t = text.replace(L.ACCENT, "")
    words = len(re.findall(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)?", t))
    sents = len([s for s in re.split(r"[.!?…]+", t) if s.strip()])
    return round(PER_WORD * words + PER_PAUSE * max(sents - 1, 0) + BASE, 2), words, max(sents - 1, 0)


def anim_overhead(anim):
    """Неречевое время сценария: полная длина минус сумма `speaks for`."""
    out = subprocess.run([str(ENGINE), "timing", str(anim)], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    speech = sum(b["end"] - b["start"] for b in j["blocks"])
    return j["total"] - speech, j


def patch_speaks(anim, durations):
    """Вписать оценки в `speaks for N` по порядку блоков `//lip`."""
    s = Path(anim).read_text(encoding="utf-8")
    i = 0
    def rep(m):
        nonlocal i
        d = durations[i] if i < len(durations) else float(m.group(1))
        i += 1
        return f"speaks for {d:.1f}s"
    s2 = re.sub(r"speaks for ([\d.]+)s", rep, s)
    Path(anim).write_text(s2, encoding="utf-8")
    return i


def main(argv=None):
    ap = argparse.ArgumentParser(description="Оценка длины озвучки до синтеза")
    ap.add_argument("vo")
    ap.add_argument("--anim", help="сценарий: бюджет речи считается от него")
    ap.add_argument("--patch-anim", help="вписать оценки в `speaks for` этого сценария")
    a = ap.parse_args(argv)

    rows = L.parse(a.vo)
    total = 0.0
    ests = []
    print(f"\n  {Path(a.vo).name}\n")
    for r in rows:
        d, w, p = estimate(r["raw"])
        ests.append(d)
        total += d
        flag = "  ← длинно" if d > 7.0 else ""
        print(f"  {r['n']:5s} {d:5.1f}с  слов {w:2d}  пауз {p}{flag}")
    print(f"\n  речь по модели: {total:.1f}с")

    anim = a.patch_anim or a.anim
    if anim:
        overhead, _ = anim_overhead(anim)
        budget = CEILING - overhead - MARGIN
        print(f"  неречевое время сценария: {overhead:.1f}с  →  бюджет речи {budget:.1f}с "
              f"(потолок {CEILING:.0f} − запас {MARGIN:.0f})")
        verdict = "УКЛАДЫВАЕТСЯ" if total <= budget else f"ПЕРЕБОР на {total - budget:.1f}с — режь текст"
        print(f"  {verdict}\n")
        if a.patch_anim:
            n = patch_speaks(a.patch_anim, ests)
            print(f"  вписано {n} значений `speaks for` в {Path(a.patch_anim).name}")
        return 0 if total <= budget else 1
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
