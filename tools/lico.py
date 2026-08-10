#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lico.py — ГЕЙТ ЛИЦА: кисть не закрывает маску.

ЗАМЕЧАНИЕ СТУДИИ: на кадре в библиотеке кисть стоит НА ЛИЦЕ — чёрная пятерня
поверх белой маски. Читается это не как жест, а как будто персонаж бьёт себя по
лицу; и держится такой кадр в «Девяносто девятом дне» двенадцать секунд.

ПОЧЕМУ ЭТО НЕ ЛОВИЛ НИ ОДИН ГЕЙТ. Маска — единственное светлое пятно фигуры и
единственное, чем она играет. Все мерки читают силуэт ПО ТУШИ: кисть, легшая на
лицо, силуэта не меняет — она внутри него. Приёмка по готовому файлу
(`prosmotr.py`) такое видит, но видит ПОЗДНО: ролик к тому моменту уже собран и
озвучен, а прогон завода стоит двадцать пять минут.

ЗДЕСЬ ЭТО МЕРИТСЯ ДО РЕНДЕРА.

МЕРИТЬ НАДО НАКОПЛЕННЫЙ СТЕК, А НЕ ОТДЕЛЬНУЮ ПОЗУ, и это главное в гейте.
Первая версия проверяла слои поодиночке — и на том самом ролике, где студия
показала кисть на лице, отрапортовала «все сорок три слоя чисты». Слои
НАКАПЛИВАЮТСЯ до следующей ПОЛНОЙ позы: `confident_cilindr` надевает цилиндр,
цилиндр не снимается до конца сцены, и через шесть слоёв к нему добавляется
поднятая кисть. Ни один из них в одиночку лица не закрывает; вместе — закрывают.

Замер по той сцене: `raskryl` 31%, `+confident_cilindr` 44%, дальше стек гуляет
между 34 и 42, а на `+vzglyad` даёт 47% — и держится так до конца сцены.

КАК МЕРИТСЯ. Раскадровка проходится подряд; на каждой ПОЛНОЙ позе стек
обнуляется, каждый `overlays` в него добавляется. Стек целиком выкладывается на
стенд — движок складывает слои ровно так же, — и на снимке ищется маска:
светлое пятно-яйцо с дырами (глаза и рот), не касающееся кромки кадра. Меряется
доля ТЁМНОГО внутри её рамки. Глаза и рот дают 27–34%. Закрытое лицо — 47–51%.
Порог 45% посередине, снят с готового файла, а не выдуман.

ЧТО НЕ СЧИТАЕТСЯ БРАКОМ. Мимические слои (`prishchur`, `smug` и прочие) меняют
рисунок глаз и рта, а не закрывают лицо: доля тёмного у них растёт на единицы
процентов и порога не достигает.

Использование:
    python3 tools/lico.py examples/lektorij/lebed.anim
    python3 tools/lico.py --pozy zakrylsya point     # разовый замер поз
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from karta import STAND, label, render                          # noqa: E402

TEMNO = 90
MASKA_MAKS = 0.15
MASKA_MIN = 0.0004
POROG = 0.45

OVERLAY = re.compile(r'^\s*\w+\s+overlays\s+"([^"]+)"', re.M)
POSE = re.compile(r'^\s*\w+\s+pose\s+"([^"]+)"', re.M)
IMPORT = re.compile(r'import\s+character\s+\S+\s+from\s+"([^"]+)"')


def porog_bumagi(g):
    """Порог бумаги берётся ИЗ КАДРА, а не зашивается.

    Стенд рисует фон в 233, а маску в 240 — разница в семь уровней. Зашитый
    порог 245, снятый с готового файла (там монохромный проход растягивает
    контраст), на стенде не находил маску НИ РАЗУ, и гейт бодро сообщал, что
    лицо закрыто у всех ста девяноста слоёв. Фон — самое частое значение кадра,
    от него и считаем.
    """
    v, c = np.unique(g.astype(int), return_counts=True)
    return int(v[np.argmax(c)]) + 4


def maska(g):
    svet = g > porog_bumagi(g)
    if not svet.any():
        return None
    lab = label(svet)
    kromka = set(lab[0]) | set(lab[-1]) | set(lab[:, 0]) | set(lab[:, -1])
    ids, cnt = np.unique(lab[lab > 0], return_counts=True)
    luchshee = None
    for k, c in zip(ids, cnt):
        if k in kromka or c > MASKA_MAKS * g.size or c < MASKA_MIN * g.size:
            continue
        ys, xs = np.nonzero(lab == k)
        h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
        if not (1.05 < h / w < 2.0) or c >= 0.80 * h * w:
            continue
        if luchshee is None or c > luchshee[0]:
            luchshee = (c, (ys.min(), ys.max(), xs.min(), xs.max()))
    if luchshee is None:
        return None
    _, (y0, y1, x0, x1) = luchshee
    box = g[y0:y1 + 1, x0:x1 + 1]
    return float((box < TEMNO).sum() / box.size)


def zamer(rig, poza):
    return maska(render(rig, poza, 0.60, 0.90))


def zamer_steka(rig, stek):
    """Стек слоёв на стенде: движок складывает их так же, как в ролике."""
    if len(stek) == 1:
        return zamer(rig, stek[0])
    src = ROOT / "examples" / "lektorij" / f"_stek_{os.getpid()}.anim"
    rel = os.path.relpath(Path(rig).resolve(), src.parent)
    stroki = "\n".join(f'    hero overlays "{p}"' for p in stek[1:])
    src.write_text(
        STAND.format(rig=rel, pose=stek[0], y=0.60, s=0.90, props_off="")
        .replace("    camera wide", stroki + "\n    camera wide"),
        encoding="utf-8")
    d = Path(tempfile.mkdtemp())
    try:
        r = subprocess.run([str(ROOT / "target/release/animdsl"), "render",
                            str(src), "--png-dir", str(d)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None
        kadry = sorted(d.glob("*.png"))
        if not kadry:
            return None
        return maska(np.asarray(Image.open(kadry[-1]).convert("L")))
    finally:
        src.unlink(missing_ok=True)
        shutil.rmtree(d, ignore_errors=True)


SCENE = re.compile(r'^\s*scene\s+"([^"]+)"', re.M)


def steki(text):
    """(сцена, стек) на каждом событии слоя — в том порядке, что и в ролике."""
    out, scena, stek = [], "?", None
    for stroka in text.splitlines():
        m = SCENE.match(stroka)
        if m:
            scena, stek = m.group(1), None
            continue
        m = POSE.match(stroka)
        if m:
            stek = [m.group(1)]
            out.append((scena, list(stek)))
            continue
        m = OVERLAY.match(stroka)
        if m:
            if stek is None:
                stek = ["calm"]
            stek.append(m.group(1))
            out.append((scena, list(stek)))
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="Гейт лица: кисть не закрывает маску")
    ap.add_argument("anim", nargs="?")
    ap.add_argument("--pozy", nargs="*")
    a = ap.parse_args(argv)

    rig = str(ROOT / "examples/assets/characters/freeman_rig")

    if a.pozy:
        for p in a.pozy:
            d = zamer(rig, p)
            print(f"  {p:22} " + ("маска не найдена — лицо закрыто целиком"
                                  if d is None else f"тёмного внутри маски {d * 100:5.1f}%"))
        return 0

    if not a.anim:
        raise SystemExit("укажи .anim или --pozy")
    src = Path(a.anim)
    text = src.read_text(encoding="utf-8")
    m = IMPORT.search(text)
    if m:
        rig = str((src.parent / m.group(1)).resolve())

    vse = steki(text)
    bed = []
    for scena, stek in vse:
        d = zamer_steka(rig, stek)
        if d is None or d > POROG:
            bed.append((scena, stek, d))

    if bed:
        print("  ЛИЦО ЗАКРЫТО:")
        for scena, stek, d in bed:
            skolko = ("маска не находится вовсе" if d is None
                      else f"{d * 100:.0f}% тёмного внутри маски")
            print(f"    · {scena}: {' + '.join(stek)}")
            print(f"        {skolko} при норме 27–34%")
        print("  Слои копятся до следующей ПОЛНОЙ позы: то, что надето в начале "
              "сцены, не снимается до её конца. Либо убрать слой, либо закрыть "
              "стек полной позой.")
        return 1
    print(f"  лицо: все {len(vse)} накопленных стеков держат маску открытой")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
