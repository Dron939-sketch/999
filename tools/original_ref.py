#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
original_ref.py — ЗАМЕР ОРИГИНАЛА: пропорции и пластика с настоящих кадров.

ЗАЧЕМ. Всё, чем мы до сих пор мерили похожесть, замкнуто на нас самих: болван
берёт глубину фигуры с НАШЕГО рисунка профиля, приёмщик разворота сравнивает
наши ракурсы друг с другом. Если исходный рисунок врёт, вся система врёт
согласованно и незаметно. Внешнего эталона не было — а он всё это время лежал
в корне репозитория: три ролика Мистера Фримена, семь с половиной минут
настоящей анимации 1280×720.

ЧТО МЕРЯЕТСЯ. По кадрам, где фигура видна целиком:

  · ГЛУБИНА/ШИРИНА. Фигура за ролик поворачивается во все стороны. Значит
    ширина плаща, нормированная на рост, гуляет от анфаса (максимум) до
    профиля (минимум). Их отношение и есть искомое k — снятое с настоящего
    тела, а не выведенное из нашего рисунка.
  · ПРОПОРЦИИ МАСКИ: ширина и высота в долях роста.
  · ПЛАСТИКА: доля силуэта, меняющаяся между соседними кадрами. Это грубая
    мера «живости»: у рисованной вручную фигуры она заметно выше, чем у
    подменяемых плоских деталей.

КАК ОТБИРАЮТСЯ КАДРЫ. В оригинале полно планов без фигуры (текст, предметы,
чёрный экран) и обрезанных сверхкрупных. Берём кадр, только если:
  1. есть крупная тёмная компонента — тело;
  2. внутри неё есть замкнутая светлая область — маска;
  3. компонента не касается верхней и нижней кромки кадра — иначе фигура
     обрезана и рост неизвестен, а все доли считаются от роста.
Третье условие отсекает как раз те сверхкрупные планы, на которых пропорции
посчитались бы от куска.

ЧТО ИЗМЕРИЛОСЬ, А ЧТО НЕТ (итог первого прогона, 35 годных кадров).

ИЗМЕРИЛОСЬ — ПРОПОРЦИИ МАСКИ. Величина устойчивая: маска это замкнутая светлая
область внутри тела, её границы не зависят от позы и ракурса.

    маска / рост      оригинал      у нас     расхождение
    ширина            0.202         0.238     +18%
    высота            0.287         0.363     +26%
    высота/ширина     1.425         1.527     +7%

Наша голова КРУПНЕЕ оригинальной на четверть роста и при этом уже. Это
подтверждается независимо: карта рига (crown −0.105, chin 0.1127, feet 0.4953)
даёт ровно 0.2177/0.6003 = 0.363.

НЕ ИЗМЕРИЛОСЬ — ГЛУБИНА К ШИРИНЕ. Замысел был: ширина плаща гуляет от анфаса к
профилю, отношение краёв даст k. Не работает по двум причинам, обе выяснились
только на кадрах:
  · угол поворота в кадре неизвестен, и профиль неотличим от приседа — обе позы
    дают узкую строку;
  · у оригинала плащ КОРОЧЕ нашего, и строка «45% роста» попадает у него на
    ноги, а у нас на плащ. Мы мерили разные вещи и сравнивали результаты.
Первый прогон выдал «анфас 2.062» — плащ вдвое шире роста, — и это было видно
как абсурд. Второй, с ужесточённым отбором, выдал правдоподобные 0.245, и вот
это опаснее: число выглядит разумным и всё равно неверно.

НЕ ИЗМЕРИЛОСЬ — ВЫСОТА ПОДОЛА. Детектор ищет резкое падение ширины и на нашей
фигуре ловит конец разведённых рук вместо края плаща: «ширина плаща» вышла
0.019 роста. На оригинале (0.835) число похоже на правду, но сравнивать не с
чем, пока наша сторона мерится неверно.

Вывод для следующего захода: величины, не зависящие от позы (маска), меряются
по видео; всё, что зависит от ракурса или от разметки частей, требует либо
листа разворотов, либо ручной пометки кадров по углам.

Использование:
    python3 tools/original_ref.py "Mr. Freeman, part 00 ... .mp4"
    python3 tools/original_ref.py *.mp4 --fps 4
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from karta import label  # noqa: E402

INK = 90            # порог «это тушь»
LIGHT = 190         # порог «это светлое» (маска, фон)
MIN_BODY = 0.004    # тело — компонента не мельче этой доли площади кадра


def flood_bg(light):
    """Светлое, связанное с краем кадра, — это фон, а не маска."""
    lab = label(light)
    if not lab.max():
        return np.zeros_like(light, bool)
    edge = set(lab[0]) | set(lab[-1]) | set(lab[:, 0]) | set(lab[:, -1])
    edge.discard(0)
    return np.isin(lab, list(edge)) if edge else np.zeros_like(light, bool)


def measure(g):
    """Кадр → замер фигуры или None, если фигуры целиком нет."""
    h, w = g.shape
    dark = g < INK
    lab = label(dark)
    if not lab.max():
        return None
    sizes = [(int((lab == i).sum()), i) for i in range(1, lab.max() + 1)]
    n, i = max(sizes)
    if n < MIN_BODY * h * w:
        return None
    body = lab == i
    ys, xs = np.nonzero(body)
    y0, y1 = int(ys.min()), int(ys.max())
    # обрезанная фигура: рост неизвестен, доли от него считать нельзя
    if y0 <= 1 or y1 >= h - 2:
        return None
    hh = y1 - y0 + 1
    if hh < 0.25 * h:
        return None

    # маска — замкнутое светлое внутри фигуры
    light = g > LIGHT
    inner = light & ~flood_bg(light)
    lab_w = label(inner)
    mask = None
    if lab_w.max():
        best = max(((int((lab_w == j).sum()), j) for j in range(1, lab_w.max() + 1)))
        my, mx = np.nonzero(lab_w == best[1])
        if len(my) > 40:
            mask = (int(mx.max() - mx.min() + 1), int(my.max() - my.min() + 1))
    if mask is None:
        return None

    # ЭТО ВООБЩЕ ФИГУРА? Первый прогон дал «анфас 2.062», то есть плащ вдвое
    # шире роста, — в отбор лезли широкие тёмные пятна со светлой дырой:
    # телефон, мясорубка, надписи. Три условия, каждое от конкретного мусора:
    x0, x1 = int(xs.min()), int(xs.max())
    if (x1 - x0 + 1) > hh:                    # стоящая фигура выше, чем шире
        return None
    mcy = float(np.nonzero(lab_w == best[1])[0].mean())
    if (mcy - y0) / hh > 0.45:                # маска — в верхней части тела
        return None
    if not 0.12 <= mask[0] / hh <= 0.45:      # голова правдоподобной доли роста
        return None

    # ШИРИНА ПЛАЩА БЕЗ РУК. Руки-ниточки приклеиваются к корпусу и добавляют
    # к ширине свой размах — тот же изъян, что чинили в приёмщике разворота.
    # Берём самый длинный СПЛОШНОЙ тёмный отрезок строки, а не габарит.
    row = y0 + int(hh * 0.45)
    idx = np.flatnonzero(body[row])
    if not len(idx):
        return None
    cuts = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([0], cuts + 1))
    ends = np.concatenate((cuts, [len(idx) - 1]))
    cw = int((idx[ends] - idx[starts]).max()) + 1
    return {"h": hh, "cloak_w": cw, "mask_w": mask[0], "mask_h": mask[1],
            "body": body}


def scan(video, fps, limit=None):
    rows, prev, churn = [], None, []
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
                        "-vf", f"fps={fps},scale=640:360", f"{d}/f%05d.png"],
                       check=True)
        files = sorted(Path(d).glob("f*.png"))
        if limit:
            files = files[:limit]
        for f in files:
            g = np.asarray(Image.open(f).convert("L"))
            m = measure(g)
            if m is None:
                prev = None
                continue
            rows.append(m)
            if prev is not None and prev.shape == m["body"].shape:
                churn.append(float((prev ^ m["body"]).sum()) /
                             max(prev.sum() + m["body"].sum(), 1))
            prev = m["body"]
    return rows, churn


def main(argv=None):
    ap = argparse.ArgumentParser(description="Замер оригинала Фримена")
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--fps", type=float, default=3.0)
    args = ap.parse_args(argv)

    allrows, allchurn = [], []
    for v in args.videos:
        rows, churn = scan(v, args.fps)
        print(f"  {Path(v).name[:46]:46} годных кадров {len(rows):4}")
        allrows += rows
        allchurn += churn
    if not allrows:
        sys.exit("ни одного кадра с целой фигурой — проверь пороги")

    rel = np.array([r["cloak_w"] / r["h"] for r in allrows])
    mw = np.array([r["mask_w"] / r["h"] for r in allrows])
    mh = np.array([r["mask_h"] / r["h"] for r in allrows])
    # Границы ряда берём квантилями, а не min/max: одиночный кадр с рукой
    # поперёк корпуса или с обрезанным подолом задрал бы край.
    lo, hi = float(np.quantile(rel, 0.05)), float(np.quantile(rel, 0.95))

    print(f"\n  ОРИГИНАЛ — {len(allrows)} кадров с целой фигурой\n")
    print(f"  ширина плаща / рост:  профиль {lo:.3f} … анфас {hi:.3f}")
    print(f"  ГЛУБИНА / ШИРИНА = {lo / hi:.3f}")
    print(f"     у нас в риге:     0.700  (turn.py, константа SIDE)")
    print(f"     расхождение:      {lo / hi - 0.700:+.3f}")
    print(f"\n  маска / рост:  ширина {np.median(mw):.3f}   высота {np.median(mh):.3f}")
    print(f"     у нас:      ширина 0.238   высота 0.363")
    print(f"  маска: высота/ширина {np.median(mh) / np.median(mw):.3f}"
          f"   у нас 1.527")
    if allchurn:
        print(f"\n  пластика: между соседними кадрами меняется "
              f"{np.median(allchurn) * 100:.1f}% силуэта")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
