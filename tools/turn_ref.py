#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
turn_ref.py — снять РАЗВОРОТ с кадров оригинала: как у Фримена устроен поворот.

Зачем. Разворот рига собран расчётом (`tools/turn.py`) по ЛИСТУ РАЗВОРОТОВ, а
лист сгенерирован моделью — то есть риг сверялся с ЧУЖОЙ КОПИЕЙ персонажа, а не
с самим персонажем. Лист же, по признанию его собственного промта, «гуляет от
клетки к клетке»: сутулость в профиле там вчетверо глубже, чем в соседнем
полуобороте. Числа с него — компромисс между законом и выбросом.

Этот измеритель берёт числа с НАСТОЯЩИХ кадров (`_9 октября 2024.mp4`,
`Фрииман.mp4`) и отвечает на два вопроса, от которых зависит узнаваемость
полуоборота:

  * ВЫНОС МАСКИ — насколько центр лица уходит от центра плаща, в долях ширины
    плаща. Это и есть мера поворота: анфас 0, профиль максимум. По нему кадры
    и сортируются на ракурсы — имена поз врут, геометрия нет.
  * ШИРИНА ПЛАЩА в долях анфасной при этом выносе. Ради этого числа всё и
    затевалось: если полуоборот у́же оригинального, фигура на повороте худеет,
    и зритель видит не поворот, а другого персонажа.

Обе величины считаются в единицах САМОЙ ФИГУРЫ (ширина маски, ширина плаща),
поэтому от плана и разрешения не зависят и сравнимы с ригом напрямую.

Использование:
    python3 tools/turn_ref.py "_9 октября 2024.mp4"
    python3 tools/turn_ref.py "Фрииман.mp4" --step 0.5 --json out.json
    python3 tools/turn_ref.py кадр.png            # один кадр
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from face_ref import find_face, load_gray, INK  # noqa: E402

# Полосы выноса маски → ракурс. Границы взяты по смыслу, а не подогнаны:
# анфас — вынос в пределах толщины линии; профиль — маска за кромкой плаща.
BANDS = [
    (0.00, 0.04, "анфас"),
    (0.04, 0.10, "четверть"),
    (0.10, 0.22, "полуоборот"),
    (0.22, 1.00, "профиль"),
]


# Правдоподобная ширина плеч в ширинах маски. По SIMILARITY.md корпус у плеч
# 1.44 маски, в широком месте 1.73. Всё вне полосы — не наш персонаж (в кадрах
# оригинала есть и другие белые пятна: морда волка, логотип, титры).
SHOULDER_MIN, SHOULDER_MAX = 1.05, 2.60
# Маска мельче — замер шумит: на общем плане у неё десяток пикселей, и одна
# точка обводки сдвигает вынос на проценты.
MASK_MIN_PX = 14


def run_through(ink_row, x):
    """Непрерывная чернильная полоса, накрывающая столбец x. (x0, x1) или None."""
    n = len(ink_row)
    x = int(round(x))
    if not (0 <= x < n) or not ink_row[x]:
        # Маска в полуобороте съезжает к кромке; допускаем небольшой поиск.
        for d in range(1, 6):
            if 0 <= x - d < n and ink_row[x - d]:
                x -= d
                break
            if 0 <= x + d < n and ink_row[x + d]:
                x += d
                break
        else:
            return None
    x0 = x
    while x0 > 0 and ink_row[x0 - 1]:
        x0 -= 1
    x1 = x
    while x1 < n - 1 and ink_row[x1 + 1]:
        x1 += 1
    return x0, x1


def measure_frame(g):
    """(вынос маски, ширина плеч / ширина маски) или None, если кадр не читается.

    Плащ меряем ЛОКАЛЬНО — одной строкой сразу под маской, идя от столбца лица
    влево и вправо, пока идут чернила. Первый заход искал самую широкую
    чернильную полосу во всём кадре ниже маски и находил ТЁМНУЮ ПОЛОСУ ЗЕМЛИ:
    у оригинала фон серый, а низ кадра почти чёрный, и «плащ» выходил в
    одиннадцать масок шириной. Локальный замер до земли не дотягивается.
    """
    face = find_face(g)
    if face is None:
        return None
    fy0, fy1, fx0, fx1 = face
    mask_w = fx1 - fx0 + 1
    mask_h = fy1 - fy0 + 1
    if mask_w < MASK_MIN_PX:
        return None
    mask_cx = (fx0 + fx1) / 2.0
    # Строка замера — сразу под подбородком, на плечевой дуге. Ниже начинается
    # разлёт плаща к подолу, и число поехало бы за кадрированием.
    y = int(fy1 + 0.28 * mask_h)
    if y >= g.shape[0]:
        return None
    seg = run_through(g[y] < INK, mask_cx)
    if seg is None:
        return None
    x0, x1 = seg
    cloak_w = x1 - x0 + 1
    ratio = cloak_w / mask_w
    if not (SHOULDER_MIN <= ratio <= SHOULDER_MAX):
        return None
    offset = abs(mask_cx - (x0 + x1) / 2.0) / cloak_w
    # H/W МАСКИ — масштабонезависимая мера ЕЁ ШИРИНЫ. Голова крутится вокруг
    # вертикали, высота при этом не меняется, поэтому H/W растёт ровно обратно
    # ширине: (H/W анфаса) / (H/W ракурса) и есть доля анфасной ширины. Сама
    # ширина в пикселях для этого не годится — план в оригинале гуляет от
    # общего до сверхкрупа.
    return offset, ratio, mask_h / mask_w


def band(offset):
    for lo, hi, name in BANDS:
        if lo <= offset < hi:
            return name
    return "профиль"


def sweep(video, t0, t1, step):
    """Замер по кадрам видео. Возвращает список (t, вынос, плащ/маска)."""
    rows = []
    with tempfile.TemporaryDirectory() as td:
        t = t0
        while t <= t1:
            png = Path(td) / "f.png"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
                            "-frames:v", "1", "-y", str(png)], check=False)
            if png.exists():
                m = measure_frame(load_gray(png))
                if m:
                    rows.append((round(t, 2), round(m[0], 4), round(m[1], 3),
                                 round(m[2], 3)))
                png.unlink()
            t += step
    return rows


def summarize(rows):
    """Сводка по ракурсам: ширина плаща в долях АНФАСНОЙ.

    Берём НИЖНИЙ КВАРТИЛЬ, а не медиану. Замер идёт по строке под подбородком,
    и когда персонаж разводит руки, в эту строку попадает рука: те же кадры
    дают 1.9–2.3 маски вместо 1.35–1.55. Загрязнение ОДНОСТОРОННЕЕ — рука
    ширину только добавляет, отнять не может, — поэтому нижний квартиль
    отбрасывает ровно её, а медиана тянется вверх вслед за жестикуляцией.
    """
    by = {}
    for t, off, ratio, hw in rows:
        by.setdefault(band(off), []).append((t, off, ratio, hw))
    q = lambda v: float(np.percentile(v, 25))                # noqa: E731
    front = by.get("анфас", [])
    base = q([r[2] for r in front]) if front else None
    hw_base = float(np.median([r[3] for r in front])) if front else None
    out = {}
    for name, items in by.items():
        hw = float(np.median([r[3] for r in items]))
        out[name] = {
            "кадров": len(items),
            "плащ/маска": round(q([r[2] for r in items]), 3),
            "доля анфаса": round(q([r[2] for r in items]) / base, 3) if base else None,
            "вынос": round(float(np.median([r[1] for r in items])), 3),
            "маска H/W": round(hw, 3),
            "ширина маски": round(hw_base / hw, 3) if hw_base else None,
        }
    return out, base


def main(argv=None):
    ap = argparse.ArgumentParser(description="Замер разворота по кадрам оригинала")
    ap.add_argument("src", help="видео или картинка")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--json", help="куда сложить построчный замер")
    a = ap.parse_args(argv)

    src = Path(a.src)
    if src.suffix.lower() in (".png", ".jpg", ".jpeg"):
        m = measure_frame(load_gray(src))
        if not m:
            return print("кадр не читается: маска или фигура не найдены") or 1
        print(f"вынос {m[0]:.3f} ({band(m[0])}), плащ/маска {m[1]:.2f}, "
              f"маска H/W {m[2]:.2f}")
        return 0

    t1 = a.t1
    if t1 is None:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                              "format=duration", "-of", "csv=p=0", str(src)],
                             capture_output=True, text=True).stdout.strip()
        t1 = float(out or 0) or 60.0
    rows = sweep(src, a.t0, t1, a.step)
    if not rows:
        return print("не удалось замерить ни одного кадра") or 1
    table, base = summarize(rows)

    print(f"\n  РАЗВОРОТ ОРИГИНАЛА — {src.name}   кадров замерено: {len(rows)}")
    print(f"  единица: ширина плаща в ширинах маски; анфас = {base:.2f}\n")
    print(f"  {'ракурс':14} {'кадров':>7} {'плащ/маска':>11} {'доля анфаса':>12}"
          f" {'вынос':>7} {'маска H/W':>10} {'ширина маски':>13}")
    for name in ("анфас", "четверть", "полуоборот", "профиль"):
        if name not in table:
            continue
        r = table[name]
        da = f"{r['доля анфаса']:.2f}" if r["доля анфаса"] else "—"
        wm = f"{r['ширина маски']:.3f}" if r["ширина маски"] else "—"
        print(f"  {name:14} {r['кадров']:>7} {r['плащ/маска']:>11.2f} {da:>12}"
              f" {r['вынос']:>7.3f} {r['маска H/W']:>10.2f} {wm:>13}")
    if a.json:
        Path(a.json).write_text(json.dumps(
            {"rows": rows, "summary": table, "base": base}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"\n  построчно: {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
