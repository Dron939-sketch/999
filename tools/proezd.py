#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
proezd.py — ГЕЙТ ПРОЕЗДА КАМЕРЫ: не уезжает ли кадр за собственный край.

ОТКУДА ВЗЯЛСЯ. Пилот видеоряда лекции был сдан «чистым»: длительности сошлись,
склейки легли в паузы, звук совпал побитово, контактный лист посмотрен. А в
готовом файле на каждом проезде из-за края картинки выползала голая подложка —
серая полоса снизу и справа. Ни одна проверка её не увидела, потому что все
они смотрели на ПЕРВЫЙ кадр сцены, где камера ещё стоит в центре.

ПОЧЕМУ ТАК ВЫХОДИТ. Сет натянут на кадр ровно, край в край. `camera wide` — это
зум 1.0, то есть видно РОВНО картинку и ни пикселя запаса. Любой `pan-to` при
зуме 1.0 сдвигает окно за край, и в освободившееся место рисуется `background`
из `config`. Смещение на 0.10 даёт 128 px голого фона: проверено замером,
зависимость линейная.

СКОЛЬКО МОЖНО. При зуме z видно 1/z картинки, значит с каждой стороны остаётся
запас (1 − 1/z)/2 — на столько и разрешено уезжать от центра:

    camera wide           z = 1.0   запас 0       проезд НЕВОЗМОЖЕН
    camera two-shot       z = 1.2   запас 0.083   спокойный дрейф
    camera over-shoulder  z = 1.8   запас 0.222   проезд по детали
    camera medium         z = 2.2   запас 0.227
    camera close-up       z = 3.4   запас 0.147 … (считается так же)

Числа зума — из `src/timeline/mod.rs::frame_shot`; `wide`, `two-shot` и
`over-shoulder` не требуют цели и потому годятся сценам без персонажа.

Гейт разбирает .anim посценно, помнит последний план и валит проезд, который
выходит за запас этого плана. Запас берётся с полем 10%: у самого края
подложка ещё не видна, но дрожание линии и виньетка уже показывают шов.

    python3 tools/proezd.py examples/lektorij/foo.anim
    python3 tools/proezd.py --all
"""

import argparse
import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#  Зум по типу плана — дословно из src/timeline/mod.rs::frame_shot.
ZUM = {"wide": 1.0, "two-shot": 1.2, "over-shoulder": 1.8,
       "medium": 2.2, "close-up": 3.4, "extreme-close-up": 6.0}
POLE = 0.90  # запас берём с полем: у самого края уже виден шов

SCENE = re.compile(r'^\s*scene\s+"([^"]+)"')
SHOT = re.compile(r"^\s*camera\s+(wide|two-shot|over-shoulder|medium|close-up|"
                  r"extreme-close-up)\b")
PAN = re.compile(r"^\s*camera\s+(?:pan-to|zoom-to)\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)")


def zapas(z):
    """Насколько можно увести центр от 0.5 при зуме z."""
    return (1.0 - 1.0 / z) / 2.0 * POLE


def check(path):
    """→ список нарушений (строка, сообщение)"""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    bad, shot, scene = [], None, "?"
    for i, line in enumerate(lines, 1):
        m = SCENE.match(line)
        if m:
            scene, shot = m.group(1), None
            continue
        m = SHOT.match(line)
        if m:
            shot = m.group(1)
            continue
        m = PAN.match(line)
        if m:
            if shot is None:
                bad.append((i, f'сцена «{scene}»: проезд до объявления плана — '
                               f'зум неизвестен, запас посчитать не от чего'))
                continue
            x, y = float(m.group(1)), float(m.group(2))
            lim = zapas(ZUM[shot])
            dx, dy = abs(x - 0.5), abs(y - 0.5)
            if max(dx, dy) > lim:
                if lim == 0:
                    bad.append((i, f'сцена «{scene}»: проезд на плане `wide` '
                                   f'(зум 1.0) — запаса нет вовсе, из-под '
                                   f'картинки вылезет подложка '
                                   f'({int(max(dx, dy) * 1280)} px). '
                                   f'Возьми `camera two-shot`'))
                else:
                    bad.append((i, f'сцена «{scene}»: проезд в ({x}, {y}) при '
                                   f'плане `{shot}` уводит на {max(dx, dy):.3f} '
                                   f'при запасе {lim:.3f} — вылезет подложка. '
                                   f'Уменьши ход или возьми план крупнее'))
    return bad


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)

    files = a.files
    if a.all or not files:
        files = sorted(glob.glob(str(ROOT / "examples/**/*.anim"), recursive=True))
        files = [f for f in files if not Path(f).name.startswith(".")]

    total = 0
    print("\n  ПРОЕЗД КАМЕРЫ\n")
    for f in files:
        bad = check(f)
        if bad:
            print(f"    {Path(f).name}: нарушений {len(bad)}")
            for ln, msg in bad:
                print(f"      [ПРОВАЛ] строка {ln}: {msg}")
            total += len(bad)
    if total:
        print(f"\n  Нарушений: {total}. Почему это ошибка — в шапке файла.\n")
        return 1
    print(f"    [OK] проверено файлов: {len(files)}, все проезды в запасе\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
