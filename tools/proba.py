#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
proba.py — цикл проверки гипотез о персонаже в одну команду.

Рендерит стенд `examples/lektorij/proba-15s.anim`, собирает контактный лист и
печатает замеры разворота. Полторы минуты вместо прогона каталога.

ЗАЧЕМ ОТДЕЛЬНАЯ КОМАНДА. Правка персонажа проверяется глазом И числом: числа
ловят подмену силуэта, глаз — заломы и рывки в суставах, которых число не
видит. Всю сессию я собирал это руками — рендер, вырезка кадров, склейка
листа, — и каждый раз по-разному: то снимал позу через 0.15с, когда она ещё не
доехала, то мерил силуэт не тем прибором, что гейт. Оба раза вывод получался
уверенный и неверный. Инструмент нужен, чтобы замер был ОДИН И ТОТ ЖЕ.

СРАВНЕНИЕ «ДО/ПОСЛЕ» — главное здесь. Судить о правке по одному листу нельзя:
глаз принимает то, что видит последним. Поэтому:

    python3 tools/proba.py --keep до     # снимок перед правкой
    ... правка ...
    python3 tools/proba.py --vs до       # два листа рядом, кадр в кадр

Использование:
    python3 tools/proba.py                 # рендер, лист, замеры
    python3 tools/proba.py --keep <имя>    # сохранить прогон под именем
    python3 tools/proba.py --vs <имя>      # сравнить с сохранённым
    python3 tools/proba.py --no-render     # пересобрать лист без рендера
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from karta import ROOT  # noqa: E402

ANIM = ROOT / "examples" / "lektorij" / "proba-15s.anim"
ENGINE = ROOT / "target" / "release" / "animdsl"
OUT = ROOT / "videos" / "proba"
# Кадры берём по одному на каждый отрезок стенда и по паре внутри разворота:
# именно там подмена силуэта заметна, а между отрезками смотреть нечего.
MARKS = [0.3, 0.9, 1.5, 2.1, 2.7, 3.3, 4.2, 5.2, 6.5, 7.6, 8.6, 9.4,
         10.4, 11.2, 12.4, 13.6, 14.6]
COLS = 6


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True)


def render(dst):
    if not ENGINE.exists():
        sys.exit("движок не собран: cargo build --release")
    dst.mkdir(parents=True, exist_ok=True)
    mp4 = dst / "proba.mp4"
    run([ENGINE, "render", ANIM, "-o", mp4])
    return mp4


def frames(mp4, dst):
    from PIL import Image  # noqa: F401
    out = []
    for i, t in enumerate(MARKS):
        p = dst / f"f{i:02d}.png"
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", t, "-i", mp4,
             "-vframes", "1", p])
        out.append(p)
    return out


def sheet(paths, dst, label=""):
    from PIL import Image, ImageDraw
    tw, th = 300, 169
    rows = (len(paths) + COLS - 1) // COLS
    sh = Image.new("RGB", (COLS * tw, rows * (th + 16)), "white")
    d = ImageDraw.Draw(sh)
    for i, p in enumerate(paths):
        sh.paste(Image.open(p).resize((tw, th)), ((i % COLS) * tw,
                                                  (i // COLS) * (th + 16)))
        d.text(((i % COLS) * tw + 4, (i // COLS) * (th + 16) + th + 2),
               f"{MARKS[i]}с", fill="black")
    out = dst / f"sheet{label}.png"
    sh.save(out)
    return out


def compare(cur, old, dst):
    """Два листа встык: правка судится по паре, а не по последнему виду."""
    from PIL import Image, ImageDraw
    a, b = Image.open(old), Image.open(cur)
    w = max(a.width, b.width)
    sh = Image.new("RGB", (w, a.height + b.height + 30), "white")
    d = ImageDraw.Draw(sh)
    d.text((4, 2), "БЫЛО", fill="black")
    sh.paste(a, (0, 14))
    d.text((4, a.height + 18), "СТАЛО", fill="black")
    sh.paste(b, (0, a.height + 30))
    out = dst / "sheet-vs.png"
    sh.save(out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Стенд персонажа: рендер, лист, замеры")
    ap.add_argument("--keep", metavar="ИМЯ", help="сохранить прогон под именем")
    ap.add_argument("--vs", metavar="ИМЯ", help="сравнить с сохранённым прогоном")
    ap.add_argument("--no-render", action="store_true", help="только пересобрать лист")
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    mp4 = OUT / "proba.mp4"
    if not args.no_render:
        print("рендер стенда…")
        mp4 = render(OUT)
    if not mp4.exists():
        sys.exit(f"нет {mp4} — сначала прогони без --no-render")

    fs = frames(mp4, OUT)
    cur = sheet(fs, OUT)
    print(f"контактный лист: {cur}")

    if args.keep:
        d = OUT / f"snap-{args.keep}"
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(cur, d / "sheet.png")
        shutil.copy(mp4, d / "proba.mp4")
        print(f"сохранено как «{args.keep}»")

    if args.vs:
        old = OUT / f"snap-{args.vs}" / "sheet.png"
        if not old.exists():
            sys.exit(f"нет снимка «{args.vs}» — сделай сначала --keep {args.vs}")
        print(f"сравнение: {compare(cur, old, OUT)}")

    print("\nзамер разворота (тот же прибор, что у приёмщика):")
    subprocess.run([sys.executable, str(ROOT / "tools" / "turnaround.py")])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
