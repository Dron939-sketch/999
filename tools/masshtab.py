#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
masshtab.py — ГЕЙТ: фигура человеческого размера для СВОЕЙ локации.

ЗАЧЕМ. Замечание студии по «О чём думать»: «размер персонажа не соответствует
локации, и его позиция тоже». Замер по готовому ролику показал, насколько:

    чайник на плите   290 px   должен быть  ~45 px   промах 6.4×
    кружка на столе    79 px   должен быть  ~17 px   промах 4.6×

Фигура в том же кадре — 315 px. То есть чайник почти с человека ростом, а
кружка ему по колено. Локация рисовалась без человека в качестве меры, фигуру
в неё поставили с масштабом «как в прошлый раз», и персонаж стал куклой.

Тринадцать гейтов это пропустили: они читают ТЕКСТ. Контактный лист мизансцен
такое показывает — но он не гейт, а картинка, и её надо ОТКРЫТЬ. Я собрал его,
не открыл и отправил ролик на завод. Правило, которое держится только на
внимательности, рано или поздно не держится.

КАК ПРОВЕРЯЕТСЯ. У каждой локации в `<сет>.surfaces.json` объявляется её
человеческая мера:

    { "floor": {...}, "chelovek": 0.57 }

`chelovek` — какую долю высоты кадра занимает СТОЯЩИЙ ВЗРОСЛЫЙ в этой локации.
Число берётся не с потолка: в кадре ищется предмет известного размера и от него
считается рост. В кухне это холодильник — 1.8 м и 434 px, значит метр это 241
px, а человек 1.7 м это 410 px, то есть 0.57 кадра.

Дальше гейт РЕНДЕРИТ по одному кадру на сцену — с фигурой и без неё, — вычитает
один из другого и меряет силуэт. Полученный рост сверяется с `chelovek` с
допуском ±15%: это разброс, внутри которого разница на глаз не читается.

ПОЧЕМУ РЕНДЕР, А НЕ АРИФМЕТИКА. Размер фигуры в кадре задаётся не только
`scales`: движок дополнительно ужимает её по карте пола, тем сильнее, чем
дальше она поставлена. В «Этике» именно это и превратило фигуру на переломе в
точку размером с ноготь при честном `scales 0.86`. Считать этот множитель
руками — значит повторять движок в другом файле и разойтись с ним на первой же
правке.

Локация без `chelovek` НЕ РОНЯЕТ гейт: он печатает её отдельным списком как
неразмеченную. Заполнять по мере работы, как `MISSTRESS` в script_lint.

Использование:
    python3 tools/masshtab.py examples/lektorij/o-chem-dumat.anim
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from mizanscena import IMPORT_CHAR, IMPORT_SET, PLACE, scenes  # noqa: E402

# Допуск, внутри которого разница в росте на глаз не читается. Взят по разбору
# готовых роликов: 57% и 50% кадра выглядят одним человеком, 57% и 44% — уже
# разными, и второй случай студия и забраковала.
DOPUSK = 0.15


def probe_lines(chars, sets, scs, s_figura):
    """Текст пробного .anim: по сцене на локацию, с фигурой или без неё.

    ТЕНИ ВЫКЛЮЧЕНЫ НАМЕРЕННО. Контактная тень лежит под ногами и попадает в
    разницу кадров, добавляя силуэту десяток пикселей снизу. На росте 400 px
    это 2-3% — внутри допуска, но врёт всегда в одну сторону.
    """
    lines = []
    for n, p in chars.items():
        lines.append(f'import character {n} from "{p}"')
    for n in {s["set"] for s in scs}:
        if n in sets:
            lines.append(f'import set {n} from "{sets[n]}"')
    lines.append("config { width: 1280 height: 720 fps: 6 background: #b0b3ab "
                 "monochrome: true mono-contrast: 2.2 "
                 "ground-shadow: false cast-shadow: 0.0 }")
    for i, s in enumerate(scs):
        lines.append(f'scene "m{i}" (duration: 1.2s, set: {s["set"]}) {{')
        if s_figura:
            lines.append(f'    {s["place"]}')
            who = PLACE.match(s["place"]).group(1)
            lines.append(f'    {who} scales {s["scale"]}')
            lines.append("    camera wide")
            lines.append(f'    {who} pose "{s["pose"]}"')
        else:
            lines.append("    camera wide")
        lines.append("    wait 1.2s")
        lines.append("}")
    return "\n".join(lines) + "\n"


def render(engine, text, td, tag):
    src = os.path.join(td, f"{tag}.anim")
    Path(src).write_text(text, encoding="utf-8")
    out = os.path.join(td, tag)
    os.makedirs(out, exist_ok=True)
    r = subprocess.run([engine, "render", src, "--png-dir", out],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1200:])
    return sorted(glob.glob(os.path.join(out, "frame_*.png")))


def rost(png_s, png_bez, x_dolya):
    """Высота силуэта фигуры в долях кадра: разница кадра с ней и без неё."""
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(png_s).convert("L"), dtype=int)
    b = np.asarray(Image.open(png_bez).convert("L"), dtype=int)
    # СМОТРИМ ТОЛЬКО ПОЛОСУ ВОКРУГ ФИГУРЫ. Монохромный проход с контрастом 2.2
    # стоит у самого порога: полутон, на волосок разошедшийся в двух рендерах,
    # перекидывается из белого в чёрное целыми пятнами по всему кадру. По
    # полному кадру силуэт выходил 0.99 при настоящих 0.57.
    w = a.shape[1]
    x0 = max(0, int((x_dolya - 0.18) * w))
    x1 = min(w, int((x_dolya + 0.18) * w))
    a, b = a[:, x0:x1], b[:, x0:x1]
    d = np.abs(a - b) > 40
    # ПОРОГ ПО СТРОКЕ, А НЕ ПО ПИКСЕЛЮ, И БЕРЁТСЯ САМЫЙ ДЛИННЫЙ СПЛОШНОЙ БЛОК.
    # Монохромный проход с контрастом 2.2 стоит у самого порога: полутон, на
    # волосок разошедшийся в двух рендерах, перекидывается из белого в чёрное
    # целыми пятнами по всему кадру. По одиночным пикселям силуэт выходил во
    # весь кадр — 0.99 при настоящих 0.57. Фигура же даёт СПЛОШНУЮ вертикаль
    # шириной хотя бы в пару процентов кадра.
    # Порог низкий (три пикселя в строке): НОГИ У ФИГУРЫ — ДВА ТОНКИХ ШТРИХА,
    # и на пороге в пару процентов ширины они выпадали, а рост занижался на
    # пятую часть — ровно на длину ног.
    plotno = d.sum(1) > 3
    luchshiy, tek, start, best_start = 0, 0, 0, 0
    for y, v in enumerate(plotno):
        if v:
            if tek == 0:
                start = y
            tek += 1
            if tek > luchshiy:
                luchshiy, best_start = tek, start
        else:
            tek = 0
    if not luchshiy:
        return None
    return luchshiy / a.shape[0]


def main(argv):
    ap = argparse.ArgumentParser(description="Гейт масштаба фигуры по локациям")
    ap.add_argument("anim")
    a = ap.parse_args(argv)

    src = Path(a.anim)
    text = src.read_text(encoding="utf-8")
    base = src.parent
    sets = {n: str((base / p).resolve()) for n, p in IMPORT_SET.findall(text)}
    chars = {n: str((base / p).resolve()) for n, p in IMPORT_CHAR.findall(text)}
    scs = [s for s in scenes(text) if s["set"] and s["place"]]
    if not scs:
        print("  масштаб: сцен с расстановкой нет — проверять нечего")
        return 0

    engine = shutil.which("animdsl") or str(ROOT / "target/release/animdsl")
    if not Path(engine).exists() and not shutil.which("animdsl"):
        print("animdsl не найден: собери движок (cargo build --release)", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as td:
        try:
            fs = render(engine, probe_lines(chars, sets, scs, True), td, "s")
            fb = render(engine, probe_lines(chars, sets, scs, False), td, "b")
        except RuntimeError as e:
            print(f"  масштаб: пробный рендер не собрался\n{e}", file=sys.stderr)
            return 1
        # КАДРОВ В ДВУХ ПРОБАХ РАЗНОЕ ЧИСЛО, И ЭТО НОРМАЛЬНО. `duration:` сцены
        # — пол, а не цель: в пробе с фигурой к нему добавляются `scales` и
        # переход позы, и сцена выходит длиннее. Поэтому сравниваем не кадр к
        # кадру, а ПОСЛЕДНИЙ кадр каждой сцены с последним кадром той же сцены
        # во второй пробе — к этому моменту и поза доехала, и свет устоялся.
        if not fs or not fb or len(fs) % len(scs) or len(fb) % len(scs):
            print("  масштаб: пробы не делятся на сцены поровну", file=sys.stderr)
            return 1
        ns, nb = len(fs) // len(scs), len(fb) // len(scs)
        pary = [(fs[(i + 1) * ns - 1], fb[(i + 1) * nb - 1]) for i in range(len(scs))]

        bed, bez_metki = [], []
        for s, (ps, pb) in zip(scs, pary):
            mx = re.search(r"at\s*\(\s*([\d.]+)", s["place"])
            h = rost(ps, pb, float(mx.group(1)) if mx else 0.5)
            svg = Path(sets.get(s["set"], ""))
            surf = svg.with_name(svg.stem + ".surfaces.json")
            cel = None
            if surf.exists():
                try:
                    cel = json.loads(surf.read_text(encoding="utf-8")).get("chelovek")
                except (OSError, ValueError):
                    cel = None
            if h is None:
                bed.append(f"{s['name']} ({s['set']}): фигуры в кадре нет вовсе")
                continue
            if cel is None:
                bez_metki.append(f"{s['set']}: рост вышел {h:.2f} кадра, "
                                 f"мера не объявлена")
                continue
            otkl = abs(h - cel) / cel
            if otkl > DOPUSK:
                kuda = "мельче" if h < cel else "крупнее"
                bed.append(f"{s['name']} ({s['set']}): фигура {h:.2f} кадра при "
                           f"мере {cel:.2f} — на {otkl * 100:.0f}% {kuda} "
                           f"человеческого роста для этой локации")

    if bez_metki:
        print("  масштаб: локации без объявленной меры «chelovek»:")
        for b in bez_metki:
            print(f"    · {b}")
    if bed:
        print("  ФИГУРА НЕ В МАСШТАБЕ ЛОКАЦИИ:")
        for b in bed:
            print(f"    · {b}")
        return 1
    razmech = len(scs) - len(bez_metki)
    print(f"  масштаб: {razmech} из {len(scs)} сцен сверены с мерой локации, "
          f"допуск ±{DOPUSK * 100:.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
