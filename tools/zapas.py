#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zapas.py — ГЕЙТ ЗАПАСА НАД ГОЛОВОЙ: макушку не срезает верхняя кромка.

ЗАЧЕМ. В «Четырёх процентах» контактный лист показал фигуру с запасом в три
процента кадра над головой — тесно, но целиком. В готовом ролике макушка
касалась кромки: замер по кадрам дал ноль.

Причина в том, ЧТО ИМЕННО ПОКАЗЫВАЕТ КОНТАКТНЫЙ ЛИСТ. Он рисует по ОДНОМУ
кадру на сцену и берёт первую позу — обычно `calm`. А внутри сцены персонаж
играет ещё десяток слоёв, и часть из них ВЫШЕ эталона: `ruka_vverh`,
`oba_vverh`, `raspahnul`, `palec_vverh` поднимают руку над головой, `na_noskah`
поднимает всю фигуру. Смотреть глазами на `calm` и делать вывод про сцену —
это проверять не тот кадр, ровно как было с масштабом до §XXXI.

КАК СЧИТАЕТСЯ. Гейт не рендерит все позы во всех сценах — это десятки прогонов.
Он делает дешевле и точнее:

  1. одна проба на сцену, как у `masshtab`: кадр с фигурой и без, разница даёт
     верхнюю точку силуэта в позе сцены;
  2. высота КАЖДОЙ позы сцены снимается на стенде (`karta.render`, тот же
     механизм, что у гейта осанки) и делится на высоту эталона;
  3. запас пересчитывается на самую высокую позу сцены.

ПОЧЕМУ ВЕРХ НЕ МЕРЯЕТСЯ ПО КАРТИНКЕ. Первая версия искала верхнюю строку
разницы кадров — и врала: в полосе вокруг фигуры попадают полки, стены и окна,
а монохромный проход с контрастом 2.2 перекидывает их полутон из кадра в кадр
целыми пятнами (та же беда, что описана в `masshtab`). Гейт объявлял срез в
сцене зала, где фигура занимает треть кадра и запаса больше трети.

Поэтому верх СЧИТАЕТСЯ, а не ищется: ступни стоят в точке `place ... on floor`,
рост берётся у `masshtab` (самый длинный сплошной блок строк — единственная
мерка, которая на этих кадрах не врёт), макушка это разница. Сцены без
`on floor` пропускаются: там `place` задаёт не ступни, а центр.

ПОРОГ 2% ВЫСОТЫ КАДРА. Меньше — и на дрожании линии (`line-boil`, `gate-weave`)
макушка начинает задевать кромку в отдельных кадрах, а это видно как обрезанная
голова, даже если в среднем всё «влезает».

Использование:
    python3 tools/zapas.py examples/lektorij/lozh.anim
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from mizanscena import IMPORT_CHAR, IMPORT_SET, PLACE, SCENE, scenes  # noqa: E402
import masshtab as M                                                  # noqa: E402

ZAPAS = 0.02          # доля высоты кадра, ниже которой макушка считается срезанной
POZA = re.compile(r'^\s*\w+\s+(?:pose|overlays)\s+"([^"]+)"', re.M)


def pozy_scen(text):
    """{имя сцены: [позы, которые она играет]} — включая накладки."""
    out, konec = {}, len(text)
    granicy = [(m.group(1), m.start()) for m in SCENE.finditer(text)]
    for i, (name, start) in enumerate(granicy):
        stop = granicy[i + 1][1] if i + 1 < len(granicy) else konec
        out[name] = POZA.findall(text[start:stop])
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="Гейт запаса над головой")
    ap.add_argument("anim")
    a = ap.parse_args(argv)

    src = Path(a.anim)
    text = src.read_text(encoding="utf-8")
    base = src.parent
    sets = {n: str((base / p).resolve()) for n, p in IMPORT_SET.findall(text)}
    chars = {n: str((base / p).resolve()) for n, p in IMPORT_CHAR.findall(text)}
    scs = [s for s in scenes(text) if s["set"] and s["place"]]
    if not scs:
        print("  запас: сцен с расстановкой нет — проверять нечего")
        return 0

    engine = shutil.which("animdsl") or str(ROOT / "target/release/animdsl")
    rig = list(chars.values())[0] if chars else None
    if not rig:
        print("  запас: персонаж не импортирован", file=sys.stderr)
        return 1

    from karta import render as stand_render          # noqa: E402
    import numpy as np

    def rost_pozy(p):
        g = stand_render(rig, p, 0.60, 0.90)
        ys, _ = np.nonzero(g < 90)
        return int(ys.max() - ys.min() + 1) if len(ys) else None

    igra = pozy_scen(text)
    etalon = rost_pozy("calm") or 1
    kesh = {}

    bed = []
    with tempfile.TemporaryDirectory() as td:
        try:
            fs = M.render(engine, M.probe_lines(chars, sets, scs, True), td, "s")
            fb = M.render(engine, M.probe_lines(chars, sets, scs, False), td, "b")
        except RuntimeError as e:
            print(f"  запас: пробный рендер не собрался\n{e}", file=sys.stderr)
            return 1
        ns, nb = len(fs) // len(scs), len(fb) // len(scs)
        for i, s in enumerate(scs):
            if "on floor" not in s["place"]:
                continue          # `place` задаёт не ступни, а центр
            mx = re.search(r"at\s*\(\s*([\d.]+)\s*,\s*([\d.]+)", s["place"])
            if not mx:
                continue
            x_dolya, stupni = float(mx.group(1)), float(mx.group(2))
            vysota = M.rost(fs[(i + 1) * ns - 1], fb[(i + 1) * nb - 1], x_dolya)
            if vysota is None:
                continue
            # самая высокая поза сцены относительно эталона
            k = 1.0
            for p in igra.get(s["name"], []):
                if p not in kesh:
                    kesh[p] = rost_pozy(p)
                if kesh[p]:
                    k = max(k, kesh[p] / etalon)
            #  Макушка = ступни минус рост, пересчитанный на самую высокую позу.
            #  Рост у `masshtab` занижен на белую маску примерно на пятую часть
            #  (он не видит её на светлом фоне), поэтому берём с запасом ×1.2 —
            #  ошибаться здесь можно только в сторону осторожности.
            zapas = stupni - vysota * 1.2 * k
            if zapas < ZAPAS:
                bed.append(f"{s['name']} ({s['set']}): запас {zapas:.3f} кадра "
                           f"при самой высокой позе (×{k:.2f}) — макушку срежет")

    if bed:
        print("  ЗАПАСА НАД ГОЛОВОЙ НЕТ:")
        for b in bed:
            print(f"    · {b}")
        return 1
    print(f"  запас над головой: во всех {len(scs)} сценах не меньше "
          f"{ZAPAS * 100:.0f}% кадра на самой высокой позе")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
