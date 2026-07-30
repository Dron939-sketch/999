#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stl_to_rig.py — СКУЛЬПТУРА → ПЛОСКИЕ ЧАСТИ РИГА.

Зачем. Части персонажа копировались с кадров на глаз: обводишь маску в потрейсе,
подгоняешь плащ «чтобы читалось», руке ставишь толщину, какая нарисовалась. Пока
частей было пять, это работало. Когда их стало сорок, между ними поехали
пропорции: плащ жил от одного кадра, нога — от другого, и разворот приходилось
чинить гейтом (`turnaround.py`), а не рисунком.

Здесь источник истины другой: ОДНА трёхмерная скульптура персонажа
(`source/mr_freeman.stl`). Из неё вынимаются ВСЕ части сразу, одним замером, в
одном масштабе — поэтому они не могут разойтись между собой. Скульптура стоит в
позе «приподнял цилиндр, опёрся на трость» (тот самый канонический кадр), и это
не мешает: каждая часть перед проекцией РАЗВОРАЧИВАЕТСЯ по своей кости, то есть
из позы вынимается форма, а не поза.

Что делает:

  1. читает STL (двоичный или ascii);
  2. СНИМАЕТ ПОДСТАВКУ — скульптура стоит на плоском диске, в риге он не нужен:
     ищется компонента-«блин» (тонкая по высоте, широкая по низу, лежит на самом
     дне) и выбрасывается;
  3. привязывает треугольники к костям скульптуры (`freeman_bones.json`) по
     ОТНОСИТЕЛЬНОМУ расстоянию до отрезка (dist/radius) — иначе толстый плащ
     съедает тонкую руку у плеча;
  4. каждую часть разворачивает: ось кости кладётся ВНИЗ по экрану, ширина
     снимается в плоскости, наиболее развёрнутой к камере (форшортенинг позы
     уходит, длина и сбег толщины остаются);
  5. рисует ПЛОСКИЙ силуэт — двухтоновый, без объёма и полутонов: персонаж
     двухмерный и черно-белый, тени на маске канон запрещает (см. FREEMAN_TARGET);
  6. обводит силуэт по контуру, упрощает (Дуглас—Пекер) и сглаживает в цепочку
     квадратичных безье — и пишет SVG в конвенции рига: viewBox + `ink`-фильтр
     + один путь на заливку;
  7. печатает ЗАМЕР: размеры viewBox и положение пивота в его координатах —
     числа, которые идут в `rig.json`.

Использование:
    python3 tools/stl_to_rig.py                       # все части в риг
    python3 tools/stl_to_rig.py --only head,hat       # только эти
    python3 tools/stl_to_rig.py --dry-run             # только замер, без записи
    python3 tools/stl_to_rig.py --segments seg.png    # картинка привязки к костям
    python3 tools/stl_to_rig.py --sheet parts.png     # лист вынутых частей

Проверка привязки — ГЛАЗАМИ ПО `--segments`: если рука окрасилась в цвет плаща,
правится `radius` в `freeman_bones.json`, а не код.
"""

import argparse
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BONES = Path(__file__).resolve().parent / "freeman_bones.json"

# Камера смотрит вдоль +Y (стоит со стороны -Y) — это «анфас» скульптуры, тот же
# ракурс, что на подлинном кадре: та рука, что приподнимает цилиндр, уходит
# влево по экрану. Ось Z — вверх (Blender).
VIEW = np.array([0.0, 1.0, 0.0])

# Полутонов нет: заливка и обводка — две краски, как в туши.
INK = "#0e0e0e"
PAPER = "#eef1ec"


# --------------------------------------------------------------------------- #
#  STL
# --------------------------------------------------------------------------- #

def load_stl(path):
    """Треугольники (n,3,3). Двоичный STL или ascii."""
    data = Path(path).read_bytes()
    if len(data) >= 84:
        count = struct.unpack("<I", data[80:84])[0]
        if len(data) == 84 + count * 50:
            dt = np.dtype([("n", "<3f4"), ("v", "(3,3)f4"), ("a", "<u2")])
            rec = np.frombuffer(data, dtype=dt, count=count, offset=84)
            return rec["v"].astype(np.float64)
    # ascii
    verts = []
    for line in data.decode("utf-8", "replace").splitlines():
        p = line.split()
        if p and p[0] == "vertex":
            verts.append([float(p[1]), float(p[2]), float(p[3])])
    if not verts:
        raise SystemExit(f"{path}: не похоже ни на двоичный, ни на ascii STL")
    return np.asarray(verts, np.float64).reshape(-1, 3, 3)


def components(tris):
    """Метка компоненты связности для каждого треугольника (склейка по сетке)."""
    q = np.round(tris.reshape(-1, 3) * 1000).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    faces = inv.reshape(-1, 3)
    parent = np.arange(faces.max() + 1)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for f in faces:
        for a, b in ((f[0], f[1]), (f[1], f[2])):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
    roots = np.array([find(i) for i in range(len(parent))])
    return roots[faces[:, 0]]


def drop_pedestal(tris, verbose=True):
    """Выбросить подставку: тонкий по высоте широкий «блин» на самом дне.

    Признак именно такой, а не «просто нижние треугольники»: у стоп низ ровно
    там же, и порог по Z срезал бы вместе с диском ступни. Диск отличается тем,
    что он ПЛОСКИЙ (высота — единицы процентов) и ШИРОКИЙ (почти вся ширина
    модели), а стопа — ни то, ни другое.
    """
    lab = components(tris)
    span = tris.reshape(-1, 3).max(0) - tris.reshape(-1, 3).min(0)
    floor = tris.reshape(-1, 3)[:, 2].min()
    keep = np.ones(len(tris), bool)
    for name in np.unique(lab):
        m = lab == name
        sub = tris[m].reshape(-1, 3)
        lo, hi = sub.min(0), sub.max(0)
        flat = (hi[2] - lo[2]) < 0.10 * span[2]
        wide = (hi[0] - lo[0]) > 0.45 * span[0] and (hi[1] - lo[1]) > 0.45 * span[1]
        bottom = lo[2] < floor + 0.02 * span[2]
        if flat and wide and bottom:
            keep &= ~m
            if verbose:
                print(f"  подставка снята: {m.sum()} треугольников, "
                      f"z=[{lo[2]:.1f}..{hi[2]:.1f}]")
    return tris[keep]


# --------------------------------------------------------------------------- #
#  привязка к костям
# --------------------------------------------------------------------------- #

def seg_distance(pts, a, b):
    """Расстояние от точек до ОТРЕЗКА ab (не до бесконечной прямой)."""
    ab = b - a
    L2 = float(ab @ ab)
    t = np.clip((pts - a) @ ab / (L2 if L2 else 1.0), 0.0, 1.0)
    return np.linalg.norm(pts - (a + t[:, None] * ab), axis=1)


def poly_distance(pts, axis):
    """Расстояние до ЛОМАНОЙ. Стопа и трость не ложатся на один отрезок:

    голень идёт «колено→пятка→носок», и одним отрезком стопа-капля не
    захватывается — она уходит на 6-7 единиц в сторону от оси голени.
    """
    d = seg_distance(pts, axis[0], axis[1])
    for i in range(1, len(axis) - 1):
        d = np.minimum(d, seg_distance(pts, axis[i], axis[i + 1]))
    return d


def assign(tris, bones):
    """Кость для каждого треугольника — разбор ПО ОЧЕРЕДИ (`priority`).

    Сначала пробовали одну формулу на всех: минимум dist/radius. Она разошлась
    на голове. Поля цилиндра — это КОЛЬЦО ВОКРУГ маски, а тулья стоит НА маске,
    то есть ось шляпы проходит сквозь голову. Для точки на лбу расстояние до
    оси шляпы и до оси маски одинаковое, и никакой подбор радиусов их не
    разводит: маска уезжала в шляпу, а подбородок — в плащ.

    Разбор по очереди снимает спор: тугая кость маски (радиус ~8.4) забирает
    СВОЁ яйцо первой, а шляпа получает лишь то, что осталось, — тулью выше
    макушки и кольцо полей, которое дальше от оси маски, чем её поверхность.
    Порядок «сначала тонкое и определённое, плащ последним» — общее правило:
    плащ стоит в очереди последним и подбирает остаток.
    """
    c = tris.mean(1)
    who = np.full(len(tris), -1, np.int32)
    for i in sorted(range(len(bones)), key=lambda k: bones[k].get("priority", 50)):
        b = bones[i]
        if b.get("source"):
            continue                      # часть режется из чужого куска
        free = who < 0
        if not free.any():
            break
        take = free & (poly_distance(c, b["axis"]) <= b["radius"])
        boxes = b.get("clips") or ([b["clip"]] if b.get("clip") else [])
        if boxes:
            # ОБЪЕДИНЕНИЕ коробок, а не одна. Цилиндр держится на кисти на весу:
            # поля проходят ПЕРЕД лицом (y < -16), а тулья стоит ВЫШЕ макушки
            # (z > 44). Одной коробкой это не описать — она захватит и яйцо.
            ok = np.zeros(len(c), bool)
            for box in boxes:
                lo, hi = np.array(box[0], float), np.array(box[1], float)
                ok |= np.all((c >= lo) & (c <= hi), axis=1)
            take &= ok
        who[take] = i
    return who


# --------------------------------------------------------------------------- #
#  разворот части и растр силуэта
# --------------------------------------------------------------------------- #

def turn(tris, a, deg):
    """Повернуть часть вокруг СВОЕЙ вертикали — снять ракурс с той же формы.

    Развороты плаща (`torso_34`, `torso_side`) раньше были отдельными рисунками
    в своей рамке 220x392. Пивот же принадлежит КОСТИ, а не рисунку: стоило
    поставить его под новый анфасный плащ, и подменённые ракурсы поехали —
    якорь попал к правому краю их рамки. Теперь все три вида снимаются с ОДНОЙ
    геометрии, одним поворотом, в одну рамку: у них не может разойтись ни
    пивот, ни длина, ни толщина линии.
    """
    r = math.radians(deg)
    c, sn = math.cos(r), math.sin(r)
    rel = tris - a
    x = rel[:, :, 0] * c - rel[:, :, 1] * sn
    y = rel[:, :, 0] * sn + rel[:, :, 1] * c
    return np.stack([x, y, rel[:, :, 2]], axis=2) + a


def unroll(tris, a, b):
    """Плоские координаты части: ось кости — ВНИЗ, ширина — в плане камеры.

    Так из позы вынимается ФОРМА. Скульптура стоит в конкретной позе, руки
    сложены и укорочены перспективой; если снимать проекцию как есть, поза
    впечатается в рисунок части и рига сложит её со своим поворотом дважды.
    """
    d = b - a
    d = d / (np.linalg.norm(d) or 1.0)
    n = VIEW if abs(float(d @ VIEW)) < 0.95 else np.array([0.0, 0.0, 1.0])
    r = np.cross(d, n)
    r /= np.linalg.norm(r) or 1.0
    rel = tris - a
    return np.stack([rel @ r, rel @ d], axis=2)   # (n,3,2): (вправо, вниз)


def cut(flat, span):
    """Отрезать по доле длины вдоль оси кости.

    Зачем. Руки скульптуры НЕ симметричны: одна сложена у цилиндра, другая
    вытянута к трости, и замер даёт им разную длину костей (53 против 36).
    В риге руки обязаны быть одной длины, иначе поворот «то же тело» врёт.
    Поэтому обе руки режутся из ОДНОГО вынутого спиндля: верх спиндля (толстый
    конец у локтя) — плечо, низ (тонкий, к кисти) — предплечье. Сбег толщины
    настоящий, скульптурный; симметрия — по построению, а не по удаче.
    """
    v = flat[:, :, 1].mean(1)
    v0, v1 = flat[:, :, 1].min(), flat[:, :, 1].max()
    lo = v0 + span[0] * (v1 - v0)
    hi = v0 + span[1] * (v1 - v0)
    sel = (v >= lo) & (v <= hi)
    if sel.sum() < 12:
        return flat
    out = flat[sel].copy()
    # Треугольники на границе среза прижимаются к ней: иначе стык бедро↔голень
    # выходит зубчатым (кусок берётся по центроиду, а вершины уезжают за срез).
    out[:, :, 1] = np.clip(out[:, :, 1], lo, hi)
    if span[0] > 0:
        out[:, :, 1] -= lo                 # пивот куска — в его собственный верх
    return out                             # при span[0]==0 отсчёт от кости цел:
                                           # он нужен колонне `extend_a`


def hull2d(flat):
    """Выпуклая оболочка плоской проекции (обход Эндрю).

    Нужна маске. Яйцо в скульптуре СРОСЛОСЬ с телом и с полями цилиндра: часть
    поверхности на стыках попросту отсутствует, а по краю воротника торчит
    бахрома. Прямая проекция давала из яйца «серп» с рваной выемкой. Маска —
    выпуклое тело, поэтому её силуэт корректно достаётся оболочкой: выемки от
    срастаний затягиваются, бахрома не влияет на форму.
    """
    p = np.unique(np.round(flat.reshape(-1, 2), 2), axis=0)
    p = p[np.lexsort((p[:, 1], p[:, 0]))]
    if len(p) < 3:
        return flat

    def half(pts):
        out = []
        for q in pts:
            while len(out) >= 2:
                (x1, y1), (x2, y2) = out[-2], out[-1]
                if (x2 - x1) * (q[1] - y1) - (y2 - y1) * (q[0] - x1) <= 0:
                    out.pop()
                else:
                    break
            out.append(tuple(q))
        return out

    ring = half(p)[:-1] + half(p[::-1])[:-1]
    c = np.mean(ring, axis=0)
    return np.array([[ring[i], ring[(i + 1) % len(ring)], c]
                     for i in range(len(ring))], float)


def extend_mask(mask, origin):
    """Дотянуть часть колонной ВВЕРХ до точки крепления — по РАСТРУ.

    Нога под подолом в скульптуре не смоделирована: она слита с плащом, и
    вынутое бедро начинается от подола, а крепится к тазу выше. Без колонны нога
    висела бы с просветом под тканью, а правило персонажа (`RULES.md`) требует
    обратного: стойки продолжаются вверх за подол.

    Считается по растру, а не по треугольникам. В треугольниках «верх части»
    задавал один случайный лоскут бахромы подола, торчащий выше ноги: колонна
    приставлялась к нему, а между ней и настоящей ногой оставалась белая щель.
    По растру берётся первая строка, где часть выходит на СВОЮ ширину (треть от
    самой широкой), — это и есть нога, а не обрывок ткани.
    """
    rows = mask.sum(1)
    if not rows.any():
        return mask, origin
    solid = np.flatnonzero(rows >= max(3, int(0.33 * rows.max())))
    if len(solid) == 0:
        return mask, origin
    top = int(solid[0])
    pivot_row = int(round(origin[1]))
    # Пивот лежит ВЫШЕ вынутой геометрии (таз под подолом), и растр его не
    # содержит — рамку надо сперва отрастить вверх, иначе колонне некуда идти.
    pad = 0
    if pivot_row < 4:
        pad = 4 - pivot_row
        mask = np.vstack([np.zeros((pad, mask.shape[1]), bool), mask])
        top += pad
        pivot_row += pad
        origin = (origin[0], origin[1] + pad)
    if top <= pivot_row + 1:
        return mask, origin
    band = mask[top:top + max(2, (len(mask) - top) // 8)]
    cols = np.flatnonzero(band.any(0))
    out = mask.copy()
    out[pivot_row:top + 2, cols.min():cols.max() + 1] = True
    return out, origin


def fill_columns(mask):
    """В каждом столбце залить от первого чернильного пикселя до последнего.

    Плащ вынимается БЕЗ рук (их забрали свои кости), и на месте руки в
    поверхности остаётся дыра. Анфас её не видит — рука стоит там же. Но
    развороты снимаются поворотом ТОЙ ЖЕ геометрии, и на трёх четвертях дыра
    выезжает в силуэт: в плече появляется клин, будто ткань прорезали.

    Плащ — сплошная тёмная колонна: в столбце чернила идут от кромки до подола
    без просветов. Заливка столбца это и утверждает — и заодно закрывает
    внутренние дыры от срастаний.
    """
    out = mask.copy()
    for x in range(mask.shape[1]):
        col = np.flatnonzero(mask[:, x])
        if len(col):
            out[col[0]:col[-1] + 1, x] = True
    return out


def shoulder_arc(mask, origin, rise, drop):
    """Срезать верх части СИММЕТРИЧНОЙ дугой плеч.

    Правило персонажа (`RULES.md`): «верх плаща — дуга, а не прямая». У
    скульптуры верх несимметричен — фигура сутулится, и правое плечо выше
    левого. Это ПОЗА, и в риге она вредна: со спины маску кладут ПОД ткань
    (z_order), и сзади должен читаться низкий купол черепа. С покатым влево
    срезом маска по центру оказывалась выше ткани, и сзади выходил целый овал
    лица — гейт разворота ловит это как «сзади не купол».

    Дуга — парабола: вершина над пивотом, края опущены к бокам.
    """
    H, W = mask.shape
    cols = np.flatnonzero(mask.any(0))
    if len(cols) < 2:
        return mask
    x0, x1 = int(cols.min()), int(cols.max())
    cx = (x0 + x1) / 2.0
    half = max(1.0, (x1 - x0) / 2.0)
    py = origin[1]
    out = mask.copy()
    for x in range(x0, x1 + 1):
        t = abs(x - cx) / half
        top = max(0, min(H - 1, int(round(py - rise + (rise + drop) * t * t))))
        out[:top, x] = False
        col = np.flatnonzero(out[top:, x])
        if len(col):
            # Дуга ЗАДАЁТ кромку, а не только срезает лишнее. Срезать было
            # мало: плащ вынут без рук, и на месте руки в поверхности дыра —
            # на трёх четвертях она выезжает в плечо открытым сверху клином,
            # и его нечем закрыть, кроме дозаливки от дуги вниз до ткани.
            out[top:top + col[0], x] = True
    return out


def body_width(mask):
    """Ширина ЧАСТИ, а не её выбросов: медиана по строкам средней полосы.

    Габарит врал. В силуэте плаща слева торчит культя рукава (плечевой корень
    прижатой руки, он сросся с тканью), и по габариту плащ выходил на четверть
    шире, чем сама колонна. Отношения ширин ракурсов считались от этого габарита
    — и три четверти получались ШИРЕ анфаса, хотя рисунок был уже.
    """
    rows = np.flatnonzero(mask.any(1))
    if not len(rows):
        return 1.0
    y0, y1 = int(rows.min()), int(rows.max())
    h = y1 - y0
    ws = []
    for y in range(y0 + int(h * 0.25), y0 + int(h * 0.55) + 1, 2):
        cols = np.flatnonzero(mask[y])
        if len(cols):
            ws.append(float(cols.max() - cols.min() + 1))
    return float(np.median(ws)) if ws else 1.0


def reframe(mask, origin, frame):
    """Уложить часть в ЗАДАННУЮ рамку так, чтобы пивот встал в заданную точку.

    Пивот в риге принадлежит кости, а не рисунку, — значит все рисунки одной
    кости обязаны жить в одной рамке с одним пивотом. Иначе подмена ракурса
    сдвигает часть на разницу их рамок, и это заметно только на том ракурсе,
    который никто не смотрел.
    """
    W, H, px, py = frame
    out = np.zeros((int(H), int(W)), bool)
    dx = int(round(px - origin[0]))
    dy = int(round(py - origin[1]))
    sh, sw = mask.shape
    y0, x0 = max(0, dy), max(0, dx)
    y1, x1 = min(int(H), dy + sh), min(int(W), dx + sw)
    if y1 > y0 and x1 > x0:
        out[y0:y1, x0:x1] = mask[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    return out, (float(px), float(py))


def raster(flat, px_per_unit, margin, supersample=4):
    """Плоский двухтоновый силуэт + положение начала кости в пикселях."""
    pts = flat.reshape(-1, 2)
    lo, hi = pts.min(0), pts.max(0)
    W = int(math.ceil((hi[0] - lo[0]) * px_per_unit)) + 2 * margin
    H = int(math.ceil((hi[1] - lo[1]) * px_per_unit)) + 2 * margin
    S = supersample
    img = Image.new("L", (W * S, H * S), 0)
    dr = ImageDraw.Draw(img)
    xy = (flat - lo) * px_per_unit + margin
    for t in xy:
        dr.polygon([(t[0, 0] * S, t[0, 1] * S), (t[1, 0] * S, t[1, 1] * S),
                    (t[2, 0] * S, t[2, 1] * S)], fill=255)
    mask = np.array(img.resize((W, H), Image.LANCZOS)) > 110
    origin = (-lo[0] * px_per_unit + margin, -lo[1] * px_per_unit + margin)
    return mask, origin


# --------------------------------------------------------------------------- #
#  контур → путь
# --------------------------------------------------------------------------- #

def boundaries(mask):
    """Все замкнутые границы маски — по РЁБРАМ пикселей.

    Обход границы по соседям (Мура) переписан на это после провала: на кисти он
    сходил с контура через два шага и отдавал пять точек вместо шести тысяч —
    силуэт выходил пустым. Здесь трассировки нет вообще, а значит нечему
    сбиваться: каждая сторона пикселя, за которой фон, — это отрезок границы с
    заданным направлением (по часовой вокруг тела), отрезки просто сшиваются
    конец-в-конец в циклы.

    Даром выходят и дырки: их циклы получают ОБРАТНЫЙ обход, и с
    `fill-rule="evenodd"` они рисуются вырезом сами — щепоть пальцев на полях
    цилиндра остаётся щепотью, а не превращается в лопату.
    """
    H, W = mask.shape
    pad = np.zeros((H + 2, W + 2), bool)
    pad[1:-1, 1:-1] = mask
    edges = {}
    ys, xs = np.nonzero(pad)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if not pad[y - 1, x]:
            edges.setdefault((x, y), []).append((x + 1, y))
        if not pad[y, x + 1]:
            edges.setdefault((x + 1, y), []).append((x + 1, y + 1))
        if not pad[y + 1, x]:
            edges.setdefault((x + 1, y + 1), []).append((x, y + 1))
        if not pad[y, x - 1]:
            edges.setdefault((x, y + 1), []).append((x, y))
    loops = []
    while edges:
        first = next(iter(edges))
        loop = [first]
        cur = first
        while True:
            nxt = edges[cur].pop()
            if not edges[cur]:
                del edges[cur]
            if nxt == first or nxt not in edges:
                break
            loop.append(nxt)
            cur = nxt
        if len(loop) > 3:
            loops.append([(px - 1.0, py - 1.0) for px, py in loop])
    return loops


def simplify(poly, eps):
    """Дуглас—Пекер на замкнутой ломаной."""
    if len(poly) < 4:
        return poly

    def rec(pts):
        if len(pts) < 3:
            return pts
        a, b = np.array(pts[0]), np.array(pts[-1])
        ab = b - a
        L = np.linalg.norm(ab) or 1.0
        rel = np.array(pts[1:-1]) - a
        dist = np.abs(ab[0] * rel[:, 1] - ab[1] * rel[:, 0]) / L
        i = int(dist.argmax())
        if dist[i] <= eps:
            return [pts[0], pts[-1]]
        return rec(pts[:i + 2])[:-1] + rec(pts[i + 1:])

    half = len(poly) // 2
    return rec(poly[:half + 1])[:-1] + rec(poly[half:] + [poly[0]])[:-1]


def densify(poly, step=44.0):
    """Разбить длинные звенья — РЕДКО. Сглаживание через середины НАДУВАЕТ короткий путь:

    прямоугольная колонна ноги (четыре точки) выходила из него пузырём, и на
    стыке с бедром появлялась «осиная талия». Если на прямом участке точки идут
    часто, квадратичные звенья остаются коллинеарными — прямая остаётся прямой,
    а кривая по-прежнему сглаживается.

    Шаг РЕДКИЙ, и это не мелочь. При шаге 10 пикселей вынутые части несли в
    20-100 раз больше звеньев, чем рисованные (у голени 54 против 4), а resvg
    тесселирует путь на КАЖДУЮ растеризацию — то есть на каждый кадр и каждый
    новый размер. Ролик со многими крупными планами перестал укладываться в
    раннер CI. Для сохранения прямых достаточно нескольких точек на участок:
    сорок пикселей дают ту же прямизну при вчетверо меньшей цене.
    """
    out = []
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        out.append((x1, y1))
        n = int(math.hypot(x2 - x1, y2 - y1) // step)
        for k in range(1, n):
            t = k / n
            out.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return out


def to_path(poly):
    """Гладкая замкнутая цепочка квадратичных безье через середины звеньев.

    Ломаная читалась бы гранёной: живая линия рисуется дугами, а не отрезками.
    Ink-фильтр поверх добавляет дрожание туши, но кривизну он не создаёт.
    """
    if len(poly) < 3:
        return ""
    P = densify(poly)

    def mid(i, j):
        return ((P[i][0] + P[j][0]) / 2, (P[i][1] + P[j][1]) / 2)

    m0 = mid(0, 1)
    out = [f"M{m0[0]:.1f} {m0[1]:.1f}"]
    for i in range(1, len(P)):
        j = (i + 1) % len(P)
        m = mid(i, j)
        out.append(f"Q{P[i][0]:.1f} {P[i][1]:.1f} {m[0]:.1f} {m[1]:.1f}")
    out.append("Z")
    return " ".join(out)


def close_cracks(mask, n):
    """Замкнуть тонкие щели: раздуть на n пикселей и сдуть обратно.

    Поля цилиндра в проекции рассекаются маской надвое, и дальний край брима
    отваливается отдельным осколком в 10 пикселей от основного пятна. Осколок
    не мусор — его надо ПРИШИТЬ, а не выбросить, иначе поля останутся с одной
    стороны.
    """
    m = mask
    for _ in range(n):
        g = m.copy()
        g[1:, :] |= m[:-1, :]
        g[:-1, :] |= m[1:, :]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        m = g
    for _ in range(n):
        g = m.copy()
        g[1:, :] &= m[:-1, :]
        g[:-1, :] &= m[1:, :]
        g[:, 1:] &= m[:, :-1]
        g[:, :-1] &= m[:, 1:]
        m = g
    return m


def contours(mask, eps, min_area=140.0):
    """Пути силуэта. Мелкие обрывки отбрасываются и об этом ГОВОРИТСЯ вслух.

    Порог по ПЛОЩАДИ, а не по числу точек: на срезе полей цилиндра отваливаются
    осколки в 20-30 пикселей, и в риге они читаются как грязь рядом с фигурой.
    Молча их ронять нельзя — счёт печатается, иначе «вроде всё вынулось».
    """
    kept, dropped = [], 0
    for loop in boundaries(mask):
        area = 0.0
        for i in range(len(loop)):
            x1, y1 = loop[i]
            x2, y2 = loop[(i + 1) % len(loop)]
            area += x1 * y2 - x2 * y1
        if abs(area) / 2.0 < min_area:
            dropped += 1
            continue
        p = simplify(loop, eps)
        if len(p) > 2:
            kept.append(p)
        else:
            dropped += 1
    return kept, dropped


# --------------------------------------------------------------------------- #
#  SVG
# --------------------------------------------------------------------------- #

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <filter id="ink" x="-25%" y="-25%" width="150%" height="150%">
      <feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="1" seed="{seed}" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="{boil}" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
  </defs>
  <!-- СНЯТО СО СКУЛЬПТУРЫ `source/mr_freeman.stl` инструментом tools/stl_to_rig.py.
       Руками не править: правка сотрётся следующим прогоном. Форма меняется в
       скульптуре, привязка — в tools/freeman_bones.json. Плоский двухтоновый
       силуэт: объёма и полутонов у персонажа нет.
       Пивот кости в этом viewBox: ({px}, {py}). -->
  <g filter="url(#ink)">
    <path d="{d}" fill="{fill}"{stroke} fill-rule="evenodd"/>
  </g>
</svg>
"""


def write_svg(path, mask, origin, spec, eps):
    if spec.get("close"):
        mask = close_cracks(mask, int(spec["close"]))
    body, dropped = contours(mask, eps, spec.get("min_area", 140.0))
    if not body:
        raise SystemExit(f"{spec['name']}: силуэт пустой — проверь привязку костей")
    if dropped:
        print(f"      {spec['name']}: отброшено обрывков — {dropped}")
    d = " ".join(to_path(p) for p in body)
    H, W = mask.shape
    fill = PAPER if spec.get("paper") else INK
    stroke = ""
    if spec.get("outline"):
        stroke = f' stroke="{INK}" stroke-width="{spec["outline"]}" stroke-linejoin="round"'
    svg = SVG.format(w=W, h=H, d=d, fill=fill, stroke=stroke,
                     freq=spec.get("boil_freq", 0.02), boil=spec.get("boil", 1.0),
                     seed=spec.get("seed", 7),
                     px=round(origin[0], 1), py=round(origin[1], 1))
    Path(path).write_text(svg, encoding="utf-8")


# --------------------------------------------------------------------------- #
#  main
# --------------------------------------------------------------------------- #

def sheet_image(items, path):
    """Контрольный лист вынутых частей — глазами видно, что вынулось не то."""
    cell_w = max(m.shape[1] for _, m, _ in items) + 12
    cell_h = max(m.shape[0] for _, m, _ in items) + 26
    cols = min(8, len(items))
    rows = (len(items) + cols - 1) // cols
    out = Image.new("RGB", (cell_w * cols, cell_h * rows), (233, 234, 228))
    dr = ImageDraw.Draw(out)
    for i, (name, m, org) in enumerate(items):
        cx, cy = (i % cols) * cell_w, (i // cols) * cell_h
        tile = Image.fromarray(np.where(m, 20, 233).astype(np.uint8)).convert("RGB")
        out.paste(tile, (cx + 6, cy + 20))
        dr.text((cx + 6, cy + 6), name, fill=(180, 0, 0))
        dr.ellipse([cx + 6 + org[0] - 2, cy + 20 + org[1] - 2,
                    cx + 6 + org[0] + 2, cy + 20 + org[1] + 2], fill=(220, 0, 0))
    out.save(path)
    print(f"  лист частей: {path}")


def segments_image(tris, who, bones, path):
    """Привязка к костям в цвете, анфас. Единственная честная проверка привязки."""
    pts = tris.reshape(-1, 3)
    lo, hi = pts.min(0), pts.max(0)
    W, H = 640, 900
    s = min((W - 40) / (hi[0] - lo[0]), (H - 40) / (hi[2] - lo[2]))
    img = Image.new("RGB", (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(img)
    palette = [(200, 40, 40), (40, 120, 200), (40, 160, 60), (220, 140, 20),
               (140, 60, 200), (0, 150, 150), (200, 60, 140), (110, 110, 110),
               (150, 90, 40), (60, 60, 200), (20, 180, 120), (190, 40, 90),
               (90, 140, 40), (230, 100, 100), (60, 100, 140), (170, 170, 30),
               (250, 200, 0), (120, 0, 60), (0, 90, 40), (255, 150, 200),
               (80, 0, 130), (0, 60, 90), (200, 200, 120), (30, 30, 30)]
    depth = tris[:, :, 1].mean(1)
    for t in np.argsort(-depth):
        col = (250, 250, 250) if who[t] < 0 else palette[who[t] % len(palette)]
        dr.polygon([((tris[t, i, 0] - lo[0]) * s + 20,
                     H - 20 - (tris[t, i, 2] - lo[2]) * s) for i in range(3)], fill=col)
    for i, b in enumerate(bones):
        dr.text((8, 8 + i * 12), b["name"], fill=palette[i % len(palette)])
    img.save(path)
    print(f"  привязка к костям: {path}")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bones", default=str(BONES))
    ap.add_argument("--stl", default=None, help="по умолчанию — из файла костей")
    ap.add_argument("--out", default=None, help="папка рига; по умолчанию из файла костей")
    ap.add_argument("--only", default="", help="список частей через запятую")
    ap.add_argument("--dry-run", action="store_true", help="только замер, без записи")
    ap.add_argument("--segments", default="", help="png привязки к костям")
    ap.add_argument("--sheet", default="", help="png листа вынутых частей")
    a = ap.parse_args(argv)

    cfg = json.loads(Path(a.bones).read_text(encoding="utf-8"))
    stl = Path(a.stl or (ROOT / cfg["stl"]))
    out = Path(a.out or (ROOT / cfg["rig"]))
    px_per_unit = cfg.get("px_per_unit", 10.0)

    print(f"скульптура: {stl}")
    tris = load_stl(stl)
    print(f"  треугольников: {len(tris)}")
    tris = drop_pedestal(tris)
    print(f"  осталось: {len(tris)}")

    bones = cfg["bones"]
    by_name = {b["name"]: i for i, b in enumerate(bones)}
    for b in bones:
        if b.get("source"):
            continue                       # ось наследуется от кости-источника
        b["a"] = np.array(b["a"], float)
        b["b"] = np.array(b["b"], float)
        b["axis"] = np.array(b.get("capture") or [b["a"], b["b"]], float)
    who = assign(tris, bones)

    if a.segments:
        segments_image(tris, who, bones, a.segments)

    wanted = {s.strip() for s in a.only.split(",") if s.strip()}
    items = []
    ink_width = {}
    print(f"\n{'часть':18s} {'viewBox':>12s} {'пивот':>14s} {'длина':>7s} {'тр-ков':>7s}")
    for i, b in enumerate(bones):
        if b.get("skip") or not b.get("svg"):
            continue
        if wanted and b["name"] not in wanted:
            continue
        src = by_name[b["source"]] if b.get("source") else i
        part = tris[who == src]
        if len(part) < 12:
            print(f"{b['name']:18s}  ПУСТО ({len(part)} треугольников) — правь radius")
            continue
        ref = bones[src]
        if b.get("view_deg"):
            part = turn(part, ref["a"], b["view_deg"])
        flat = unroll(part, ref["a"], ref["b"])
        if b.get("slice"):
            flat = cut(flat, b["slice"])
        if b.get("hull"):
            flat = hull2d(flat)
        if b.get("pivot") == "bottom":
            flat = flat * np.array([1.0, -1.0])       # кость смотрит ВВЕРХ
        if b.get("mirror"):
            flat = flat * np.array([-1.0, 1.0])
        if b.get("width_frac"):
            # ШИРИНА РАКУРСА — ПО КАНОНУ, А НЕ ПО СКУЛЬПТУРЕ. Плащ скульптуры —
            # почти тело вращения: в профиль он выходит 0.94 анфасной ширины,
            # и разворот перестаёт читаться поворотом. Подлинный лист разворотов
            # (TURNAROUND_PROMPT.md, полоса в turnaround.py) даёт профиль 0.70 и
            # три четверти 0.86 — плащ у Фримена ПЛОСКИЙ, это графика, а не
            # объём. Длину, подол и кромку берём со скульптуры, ширину ракурса —
            # с листа: каждая сторона отвечает за то, что мерит лучше.
            frac, ref_name = b["width_frac"]
            probe, _ = raster(flat, px_per_unit, b.get("margin", 4))
            own = body_width(probe)
            target = frac * ink_width[ref_name]
            flat = flat * np.array([target / max(own, 1.0), 1.0])
        mask, origin = raster(flat, px_per_unit, b.get("margin", 4))
        ink_width[b["name"]] = body_width(mask)
        if b.get("extend_a"):
            mask, origin = extend_mask(mask, origin)
        if b.get("fill_columns"):
            mask = fill_columns(mask)
        if b.get("shoulder_arc"):
            mask = shoulder_arc(mask, origin, *b["shoulder_arc"])
        if b.get("frame"):
            mask, origin = reframe(mask, origin, b["frame"])
        H, W = mask.shape
        length = float(np.linalg.norm(ref["b"] - ref["a"]))
        if b.get("slice"):
            length *= b["slice"][1] - b["slice"][0]
        print(f"{b['name']:18s} {W:5d}x{H:<6d} {origin[0]:6.1f},{origin[1]:6.1f} "
              f"{length:7.1f} {len(part):7d}")
        items.append((b["name"], mask, origin))
        if not a.dry_run and b.get("svg"):
            write_svg(out / b["svg"], mask, origin, b, cfg.get("simplify_eps", 1.4))

    if a.sheet and items:
        sheet_image(items, a.sheet)
    if a.dry_run:
        print("\n--dry-run: SVG не записаны")
    else:
        print(f"\nзаписано в {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
