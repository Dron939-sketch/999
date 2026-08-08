#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mizanscena.py — КОНТАКТНЫЙ ЛИСТ МИЗАНСЦЕН ДО ЗАВОДА.

ЗАЧЕМ ЭТОТ ИНСТРУМЕНТ ВООБЩЕ ПОЯВИЛСЯ. Разбор пяти роликов подряд показал: из
переделок, которые стоили полного прогона завода, БОЛЬШЕ ПОЛОВИНЫ — не сценарий
и не звук, а мизансцена, то есть где стоит фигура и какого она размера:

  · «Влияние»: в прихожей фигура была вдвое мельче нужного, у стола сливалась
    со столешницей;
  · «Дистанция»: в кухне столешница срезала фигуру по грудь — человек читался
    ребёнком за столом;
  · «Дистанция», финал: палец показывал мимо банки, потому что персонаж встал
    прямо под подоконником;
  · «Влияние», ПУСТОТА: белая рука сливалась с белой маской, а чёрная вообще
    не была видна на чёрном.

Каждый раз дефект был ВИДЕН НА ОДНОМ КАДРЕ и невиден в тексте раскадровки. И
каждый раз его находили после сборки — то есть через полный прогон рендера,
озвучки и сведения.

ЧТО ДЕЛАЕТ ИНСТРУМЕНТ. Читает `.anim`, берёт из каждой сцены первую расстановку
(`place`, `scales`, первая `pose`) и собирает ОДИН статичный кадр на сцену в
отдельный маленький ролик. Дальше складывает кадры в контактный лист PNG.
Тридцать секунд работы вместо десяти минут завода.

Он НЕ проверяет ничего сам и не ставит оценок: композицию смотрит человек.
Задача инструмента — сделать так, чтобы посмотреть было НЕ ДОРОГО.

Использование:
    python3 tools/mizanscena.py examples/lektorij/emocii.anim
    python3 tools/mizanscena.py examples/lektorij/emocii.anim --out /tmp/lист.png

Требует собранный `animdsl` в PATH (или target/release).
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

SCENE = re.compile(r'scene\s+"([^"]+)"\s*\(([^)]*)\)\s*\{')
SET_IN_HEAD = re.compile(r"set:\s*([A-Za-z_][\w-]*)")
IMPORT_SET = re.compile(r'import\s+set\s+([A-Za-z_][\w-]*)\s+from\s+"([^"]+)"')
IMPORT_CHAR = re.compile(r'import\s+character\s+([A-Za-z_][\w-]*)\s+from\s+"([^"]+)"')
PLACE = re.compile(r"place\s+(\w+)\s+at\s+\(([^)]*)\)([^\n]*)")
SCALES = re.compile(r"^\s*(\w+)\s+scales\s+([\d.]+)\s*$", re.M)
POSE = re.compile(r'(\w+)\s+pose\s+"([^"]+)"')


def scenes(text):
    """Список сцен: имя, сет, строка place, масштаб, первая поза."""
    out = []
    for m in SCENE.finditer(text):
        name, head = m.group(1), m.group(2)
        body_start = m.end()
        depth, i = 1, body_start
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[body_start:i]
        s = SET_IN_HEAD.search(head)
        p = PLACE.search(body)
        sc = SCALES.search(body)
        po = POSE.search(body)
        out.append({
            "name": name,
            "set": s.group(1) if s else None,
            "place": p.group(0).strip() if p else None,
            "scale": sc.group(2) if sc else "1.0",
            "pose": po.group(2) if po else "calm",
        })
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="Контактный лист мизансцен по .anim")
    ap.add_argument("anim")
    ap.add_argument("--out", default=None, help="куда положить PNG (по умолчанию рядом с .anim)")
    ap.add_argument("--width", type=int, default=426, help="ширина клетки листа")
    a = ap.parse_args(argv)

    src = Path(a.anim)
    text = src.read_text(encoding="utf-8")
    base = src.parent
    sets = {n: str((base / p).resolve()) for n, p in IMPORT_SET.findall(text)}
    chars = {n: str((base / p).resolve()) for n, p in IMPORT_CHAR.findall(text)}
    scs = [s for s in scenes(text) if s["set"] and s["place"]]
    if not scs:
        print("не нашёл ни одной сцены с расстановкой", file=sys.stderr)
        return 1

    engine = shutil.which("animdsl") or "target/release/animdsl"
    if not (shutil.which("animdsl") or Path(engine).exists()):
        print("animdsl не найден: собери движок (cargo build --release)", file=sys.stderr)
        return 1

    lines = []
    for n, p in chars.items():
        lines.append(f'import character {n} from "{p}"')
    used = {s["set"] for s in scs}
    for n in used:
        if n in sets:
            lines.append(f'import set {n} from "{sets[n]}"')
    # Кадр ДОЛЖЕН БЫТЬ ДЛИННЕЕ ПЕРЕХОДА ПОЗЫ. У поз `transition_duration` 0.25-0.4 с:
    # на сцене в полсекунды поза не доезжает, и лист показывает не мизансцену, а
    # промежуточный кадр. Наступал на это — все восемь поз выглядели одинаково.
    lines.append("config { width: 1280 height: 720 fps: 6 background: #b0b3ab "
                 "monochrome: true mono-contrast: 2.2 on-twos: 2 "
                 "ground-shadow: true cast-shadow: 0.32 }")
    for i, s in enumerate(scs):
        lines.append(f'scene "m{i}" (duration: 1.2s, set: {s["set"]}) {{')
        lines.append(f'    {s["place"]}')
        who = PLACE.match(s["place"]).group(1)
        lines.append(f'    {who} scales {s["scale"]}')
        lines.append("    camera wide")
        lines.append(f'    {who} pose "{s["pose"]}"')
        lines.append("    wait 1.2s")
        lines.append("}")

    with tempfile.TemporaryDirectory() as td:
        probe = os.path.join(td, "mizanscena.anim")
        Path(probe).write_text("\n".join(lines) + "\n", encoding="utf-8")
        pngs = os.path.join(td, "png")
        os.makedirs(pngs)
        r = subprocess.run([engine, "render", probe, "--png-dir", pngs],
                           capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-1500:], file=sys.stderr)
            return 1
        frames = sorted(glob.glob(os.path.join(pngs, "frame_*.png")))
        if not frames:
            print("движок не отдал кадров", file=sys.stderr)
            return 1
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            print("нужен pillow: python3 -m pip install pillow", file=sys.stderr)
            return 1
        per = len(frames) // len(scs)
        picks = [frames[min((i + 1) * per - 1, len(frames) - 1)] for i in range(len(scs))]
        cols = min(3, len(picks))
        rows = (len(picks) + cols - 1) // cols
        cw, ch = a.width, int(a.width * 9 / 16)
        sheet = Image.new("RGB", (cw * cols, ch * rows), (255, 255, 255))
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(picks):
            x, y = (i % cols) * cw, (i // cols) * ch
            sheet.paste(Image.open(f).convert("RGB").resize((cw, ch)), (x, y))
            s = scs[i]
            d.text((x + 5, y + 4), f'{s["name"]}  {s["scale"]}  {s["pose"]}', fill=(255, 0, 0))
        out = Path(a.out) if a.out else src.with_name(src.stem + "-mizanscena.png")
        sheet.save(out)
        print(f"  контактный лист: {out}  ({len(picks)} сцен)")
        print("  СМОТРИ ГЛАЗАМИ: не срезана ли фигура мебелью, не мелкая ли она, "
              "не сливается ли с фоном, туда ли смотрит жест.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
