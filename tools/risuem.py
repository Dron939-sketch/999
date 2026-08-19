#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
risuem.py — рисовалка иллюстраций лекции в стиле серии.

ЗАЧЕМ. Видеоряд лекции требует полутора десятков кадров. Ждать каждый от
генератора — это полтора десятка кругов «промт → квадрат вместо 16:9 → правка
смысла», а мы уже прошли этот круг трижды (воронка ролика 24, кухня ролика 25,
анкета пилота). Иллюстрация лекции устроена проще локации: несколько сильных
форм, никакой перспективы, никакой фактуры. Такое рисуется кодом надёжнее, чем
выпрашивается.

СТИЛЬ СЕРИИ, СВЕДЁННЫЙ К ПРАВИЛАМ:
  · бумага #d4d7cf, тушь #141410, третьего цвета нет;
  · линия ТОЛСТАЯ (14–20 px) и ДРОЖИТ: прямых машинных линий в кадре не бывает,
    иначе рисунок читается чертежом, а не рукой;
  · заливки плоские — ни градиентов, ни теней, ни полутонов;
  · деталей мало, форм мало, силуэт читается с одного взгляда;
  · кадр 1280×720 сразу, без обрезки: формат задаётся тем, ЧТО в кадре, и
    композиция здесь горизонтальная по построению.

ДРОЖЬ ЛИНИИ — НЕ УКРАШЕНИЕ. Ровная линия в кадре, где всё остальное дрожит,
выглядит вставкой из другой программы. Поэтому дрожат все контуры, включая
прямоугольники и окружности: `shag` задаёт, как часто ломается линия, `drozh` —
насколько.

КОНТУР ПРОВОДИТСЯ ДВАЖДЫ, И ЭТО ГЛАВНОЕ. Первый набор кадров вышел тонким и
пустым — рядом с картинками пилота он читался вставкой из другой программы.
Разница оказалась не в толщине: у рисунка серии контур ДВОЙНОЙ. Линия обведена
второй раз с другой дрожью, две линии то сливаются, то расходятся на пиксель —
отсюда «кипящий» край, которого одна линия любой толщины не даёт. Поэтому
`liniya` и всё, что на ней стоит, кладут два прохода (`prohody`), и второй
тоньше первого: так край получается живым, а не просто жирным.

ПЛОТНОСТЬ. Кадр держит экран минуту с лишним — предмет в нём занимает две трети
поля, а не четверть. Семь тонких линий посреди бумаги умирают на третьей
секунде просмотра.
"""

import math
import random

from PIL import Image, ImageDraw

BUMAGA = (212, 215, 207)
TUSH = (20, 20, 18)
W, H = 1280, 720


def holst(seed=0):
    random.seed(seed)
    im = Image.new("RGB", (W, H), BUMAGA)
    return im, ImageDraw.Draw(im)


def _tochki(p1, p2, shag=26, drozh=2.2):
    """Ломаная между двумя точками с дрожью поперёк направления."""
    x1, y1 = p1
    x2, y2 = p2
    d = math.hypot(x2 - x1, y2 - y1)
    n = max(2, int(d / shag))
    nx, ny = -(y2 - y1) / (d or 1), (x2 - x1) / (d or 1)
    out = []
    for i in range(n + 1):
        t = i / n
        s = random.uniform(-drozh, drozh) * (0 if i in (0, n) else 1)
        out.append((x1 + (x2 - x1) * t + nx * s, y1 + (y2 - y1) * t + ny * s))
    return out


def liniya(d, p1, p2, w=15, drozh=2.2, fill=TUSH, prohody=2):
    """Линия в ДВА прохода — отсюда «кипящий» край (см. шапку файла)."""
    for k in range(prohody):
        d.line(_tochki(p1, p2, drozh=drozh + k * 0.8),
               fill=fill, width=max(3, w - k * 5), joint="curve")


def lomanaya(d, pts, w=15, drozh=2.0, zamknut=False, fill=TUSH, prohody=2):
    pp = list(pts) + ([pts[0]] if zamknut else [])
    for a, b in zip(pp, pp[1:]):
        liniya(d, a, b, w=w, drozh=drozh, fill=fill, prohody=prohody)


def pryamoug(d, box, w=15, drozh=2.0, zaliv=None, prohody=2):
    x0, y0, x1, y1 = box
    if zaliv:
        d.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill=zaliv)
    lomanaya(d, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
             w=w, drozh=drozh, zamknut=True, prohody=prohody)


def krug(d, cx, cy, r, w=15, drozh=2.0, zaliv=None, ot=0, do=360, prohody=2):
    for k in range(prohody):
        pts = []
        n = max(16, int(r / 2.5))
        for i in range(n + 1):
            a = math.radians(ot + (do - ot) * i / n)
            rr = r + random.uniform(-drozh, drozh) - k * 1.5
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        if zaliv and k == 0:
            d.polygon(pts, fill=zaliv)
        lomanaya(d, pts, w=max(3, w - k * 5), drozh=0.6, prohody=1)


def shtrih_ruka(d, x0, y0, x1, w=11):
    """Свободная завитушка — «написано рукой»."""
    pts = []
    x = x0
    up = True
    while x < x1:
        pts.append((x, y0 + (-18 if up else 14) + random.uniform(-5, 5)))
        x += random.uniform(26, 44)
        up = not up
    lomanaya(d, pts, w=w, drozh=1.6, prohody=1)


def shtrih_mashina(d, x0, y0, x1, w=9, shag=32, h=24):
    """Ровная гребёнка — «заполнено машиной»."""
    x = x0
    while x < x1:
        d.line([(x, y0 - h), (x, y0)], fill=TUSH, width=w)
        x += shag
    liniya(d, (x0, y0), (x1, y0), w=8, drozh=0.8, prohody=1)


def sohranit(im, imya):
    import base64
    import os
    p = f"examples/assets/sets/{imya}.png"
    im.save(p)
    b = base64.b64encode(open(p, "rb").read()).decode()
    with open(f"examples/assets/sets/{imya}.svg", "w", encoding="utf-8") as f:
        f.write(
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
            ' viewBox="0 0 1280 720" width="1280" height="720">\n'
            f'  <!-- Иллюстрация лекции, нарисована tools/risuem.py в стиле серии:\n'
            f'       бумага #d4d7cf, тушь #141410, дрожащая линия, плоские заливки. -->\n'
            f'  <image x="0" y="0" width="1280" height="720" xlink:href="data:image/png;base64,{b}"/>\n'
            "</svg>\n")
    return os.path.getsize(p)
