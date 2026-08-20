#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_chastyami.py — рендер длинного .anim ЧАСТЯМИ, в обход дедлока с ffmpeg.

ЧТО СЛУЧИЛОСЬ. Полная лекция (174 сцены, 23 655 кадров) встала намертво на
двух третях: движок спал в `anon_pipe_write`, ffmpeg — в ожидании. Классический
взаимный клин на трубах. Движок пишет ffmpeg сырые кадры в одну трубу, а его
вывод читает из другой — и читает только ПОСЛЕ того, как отдаст все кадры.
Пока ffmpeg печатает мало, его вывод помещается в буфер трубы (64 КБ) и всё
работает; как только он переполнил буфер, ffmpeg блокируется на записи, пере-
стаёт читать кадры, а движок блокируется на записи кадров. Оба спят вечно.

Прежние сборки проходили случайно: тот же ролик той же длины укладывался в
буфер. Длина тут ни при чём — важен ОБЪЁМ вывода ffmpeg, и он в любой момент
может перевалить за буфер.

ПОЧЕМУ НЕ ЧИНИМ ДВИЖОК. Починка на месте — вычитывать вывод ffmpeg в отдельном
потоке — это правка Rust и пересборка; сделать её надо, но она не должна
задерживать сдачу. Здесь обход: .anim режется на части по границам СЦЕН,
каждая рендерится своим процессом (свой ffmpeg, свой буфер), готовые куски
сшиваются демультиплексором `concat` БЕЗ перекодирования — параметры кодека у
всех частей одинаковые, поэтому склейка побитовая и качество не теряется.

Границы частей проходят строго между сценами, а число кадров в сцене от
разбиения не меняется, поэтому сумма кадров у частей совпадает с целым.

    python3 tools/render_chastyami.py examples/lektorij/foo.anim -o videos/foo.mp4
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANIMDSL = ROOT / "target/release/animdsl"


def razrezat(tekst, chastej):
    """→ список исходников частей: общая шапка плюс свой кусок сцен."""
    m = list(re.finditer(r"^scene ", tekst, flags=re.M))
    if not m:
        raise SystemExit("в файле нет сцен")
    shapka = tekst[:m[0].start()]
    granicy = [x.start() for x in m] + [len(tekst)]
    n = len(m)
    razmer = (n + chastej - 1) // chastej
    out = []
    for i in range(0, n, razmer):
        j = min(i + razmer, n)
        out.append((shapka + tekst[granicy[i]:granicy[j]], j - i))
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("anim")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--chastej", type=int, default=6)
    a = ap.parse_args(argv)

    src = ROOT / a.anim
    tekst = src.read_text(encoding="utf-8")
    chasti = razrezat(tekst, a.chastej)
    print(f"\n  РЕНДЕР ЧАСТЯМИ: {len(chasti)} шт., сцен всего "
          f"{sum(k for _, k in chasti)}\n")

    #  ЧАСТИ ЛЕЖАТ РЯДОМ С ИСХОДНИКОМ, а не во временной подпапке: импорты в
    #  .anim заданы относительно файла («../assets/...»), и любой лишний
    #  уровень вложенности их ломает — первая попытка так и упала на риге.
    kuski, vsego = [], 0
    import shutil
    tmp = src.parent / f".chasti_{src.stem}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    try:
        for i, (kod, scen) in enumerate(chasti):
            p = src.parent / f".chast_{i:02d}.anim"
            p.write_text(kod, encoding="utf-8")
            out = tmp / f"chast_{i:02d}.mp4"
            r = subprocess.run([str(ANIMDSL), "render", str(p), "-o", str(out)],
                               cwd=str(src.parent), capture_output=True, text=True)
            if r.returncode != 0 or not out.exists():
                print(r.stdout[-2000:], r.stderr[-2000:])
                raise SystemExit(f"часть {i} не отрендерилась")
            kadrov = int(re.search(r"(\d+) frames", r.stdout + r.stderr).group(1))
            vsego += kadrov
            kuski.append(out)
            print(f"    часть {i + 1}/{len(chasti)}: сцен {scen}, кадров {kadrov}")

        spisok = tmp / "spisok.txt"
        spisok.write_text("".join(f"file '{k}'\n" for k in kuski), encoding="utf-8")
        cel = ROOT / a.output
        cel.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(spisok), "-c", "copy", str(cel)], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for f in src.parent.glob(".chast_*.anim"):
            f.unlink()

    print(f"\n  кадров всего {vsego} = {vsego / 24:.2f}с")
    print(f"  собрано: {a.output}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
