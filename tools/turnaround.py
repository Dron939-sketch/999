#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
turnaround.py — ГЕЙТ РАЗВОРОТА: одна ли это фигура на всех ракурсах.

Зачем. Развороты собираются расчётом (`tools/turn.py`) и правятся руками, а
проверялись глазом по контрольной картинке. Глаз ловит грубое и пропускает
ряд: у нас профиль схлопнулся до 0.40 ширины анфаса вместо 0.70, четверть
оказалась УЖЕ полуоборота, а на профиле и полуспине фигура просела на пятьдесят
пикселей — и всё это жило в риге, пока ролики шли анфасом и никто туда не
смотрел. Правка «поделить вертикальный масштаб головы на 1.2» проверялась
замером ТОЛЬКО на анфасе; на ракурсах у маски другая пропорция, и там деление
легло не туда.

Отсюда правило: развороты принимает ЗАМЕР, а не картинка. Условия приёмки —
те же, что записаны в промте на лист разворотов
(`examples/assets/characters/<риг>/TURNAROUND_PROMPT.md`), только теперь их
проверяет машина на каждом прогоне завода, а не человек раз в неделю:

  1. рост фигуры одинаков на всех ракурсах (иначе это разные персонажи);
  2. линия глаз горизонтальна по всему листу (иначе фигура «проседает»);
  3. со спины и с полуспины на маске НЕТ черт лица;
  4. в профиль виден ровно ОДИН глаз — не два и не ноль;
  5. ширина плаща убывает МОНОТОННО от анфаса к профилю и симметрично растёт
     к спине; ряд без возвратов — это и есть «поворот одного тела», а не набор
     независимых рисунков;
  6. левый и правый ракурсы зеркальны по ширине.

Пятое условие появилось после разбора первого листа разворотов: величины по
отдельности были разумные, но между ними не было монотонности, и собранный по
ним разворот «прыгал».

Использование:
    python3 tools/turnaround.py                 # замер и печать таблицы
    python3 tools/turnaround.py --check         # гейт: ненулевой выход при провале
    python3 tools/turnaround.py --rig examples/assets/characters/freeman_rig
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from karta import ROOT, RIGS, label, render  # noqa: E402

# Ракурсы по кругу. Имя позы в риге → угол и подпись. Правые и левые ракурсы
# идут парами: пара обязана быть зеркальной, это шестое условие.
# ИМЕНА ПОЗ ОБМАНЫВАЮТ, УГЛЫ — НЕТ. `chetvert_*` — это ТРИ ЧЕТВЕРТИ, 45°, а
# `povorot_*` — четверть оборота, 22.5°. Названия сложились по-русски («три
# четверти» и «полуоборот» — про один и тот же ракурс), и первая версия этого
# гейта развернула их наоборот: ряд ширин выходил немонотонным, хотя фигура
# была ни при чём. Порядок здесь задаётся УГЛОМ, а не именем.
# ЭТАЛОН АНФАСА — `calm`, А НЕ `idle`. У `idle` голова опущена на 21 единицу
# собственной правкой позы (offset [-4,87] против дефолтных [0,66]), и все
# ракурсы разворота, считанные от дефолта, выходили относительно неё «выше на
# 8–10% роста». Ошибка была в эталоне, а не в развороте. Ролики играют
# `calm`/`smug`/`doubt` — они и есть анфас.
VIEWS = [
    ("calm",           0,   "анфас"),
    ("povorot_pravo",  22,  "четверть вправо 22°"),
    ("povorot_levo",   -22, "четверть влево 22°"),
    ("chetvert_pravo", 45,  "три четверти вправо"),
    ("chetvert_levo",  -45, "три четверти влево"),
    ("bok_pravo",      90,  "профиль вправо"),
    ("bok_levo",       -90, "профиль влево"),
    ("polu_spina",     135, "полуспина"),
    ("spina",          180, "спина"),
]

# Ширина силуэта в долях анфасной. Взято с листа разворотов: профиль 0.70,
# полуоборот 0.86. Допуск широкий — гейт ловит СЛОМ (доска вместо фигуры), а
# не расхождение в пару процентов, которое художник вправе выбрать сам.
WIDTH_BAND = {
    0:   (0.97, 1.03),
    22:  (0.88, 1.00),
    45:  (0.78, 0.94),
    90:  (0.60, 0.80),
    135: (0.78, 0.94),
    180: (0.92, 1.06),
}

# РОСТ МЕРЯЕТСЯ ПО МАКУШКЕ, А НЕ ПО ГАБАРИТУ. Ноги в позах разворота разной
# длины НАМЕРЕННО — ближняя длиннее дальней, это и есть глубина, — поэтому
# нижняя кромка тёмного гуляет законно, и первая версия гейта ругалась на неё
# как на «разный рост». Неизменны две вещи: экранная высота макушки (фигура
# стоит на одном якоре и в одном масштабе) и высота маски (голова — жёсткий
# предмет, ракурсом не растягивается).
# Допуск 3%, а не 2%: маска нарисована ОТ РУКИ и несимметрична (левый глаз
# шире правого, контур слева круче) — зеркальный профиль ставит макушку на
# десяток пикселей иначе, чем прямой, при неизменной посадке кости. Это
# асимметрия самого рисунка, на которой персонаж и построен, а не поломка.
CROWN_TOL = 0.03       # макушка: разброс по ракурсам, доля роста анфаса
MASKH_TOL = 0.08       # высота маски спереди и сбоку: разброс, доля анфасной
# СО СПИНЫ МАСКА — НИЗКИЙ КУПОЛ, А НЕ ОВАЛ: виден верх черепа, низ съедают
# плечи. По листу разворотов высота обрушивается до 0.60 анфасной, и это
# ПРАВИЛО, а не поломка — поэтому спина и полуспина в проверку «голова жёсткий
# предмет» не входят, у них своя полоса.
DOME_BAND = (0.50, 0.75)
MIRROR_TOL = 0.05      # зеркальность пары, доля


def flood_background(white):
    """Белое, связное с краем кадра, — это фон, а не маска."""
    h, w = white.shape
    seen = np.zeros_like(white, bool)
    stack = []
    for x in range(w):
        for y in (0, h - 1):
            if white[y, x] and not seen[y, x]:
                seen[y, x] = True
                stack.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if white[y, x] and not seen[y, x]:
                seen[y, x] = True
                stack.append((y, x))
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and white[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                stack.append((ny, nx))
    return seen


def _open_x(dark, k):
    """Горизонтальное морфологическое открытие шириной k: стирает всё тоньше k.

    Руки-ветки у фигуры толщиной в несколько пикселей, плащ — в двести. Пока
    рука висит на просвете, её отрезает разрыв строки; но стоит ей лечь НА
    корпус, и она приклеивается к его отрезку, добавляя к ширине плаща свою.
    Из-за этого четверть оборота мерилась ШИРЕ анфаса, хотя масштаб плаща в
    позе меньше анфасного. Открытие убирает тонкое целиком и не трогает
    толстое: остаётся ровно плащ.
    """
    a = dark
    er = a.copy()
    for d in range(1, k + 1):
        er[:, d:] &= a[:, :-d]
        er[:, :-d] &= a[:, d:]
    di = er.copy()
    for d in range(1, k + 1):
        di[:, d:] |= er[:, :-d]
        di[:, :-d] |= er[:, d:]
    return di


def widest_run(dark, y0, y1):
    """Самый длинный СПЛОШНОЙ тёмный отрезок в полосе строк — это плащ."""
    best = 0
    for y in range(max(y0, 0), min(y1, dark.shape[0])):
        idx = np.flatnonzero(dark[y])
        if not len(idx):
            continue
        cuts = np.flatnonzero(np.diff(idx) > 1)
        starts = np.concatenate(([0], cuts + 1))
        ends = np.concatenate((cuts, [len(idx) - 1]))
        best = max(best, int((idx[ends] - idx[starts]).max()) + 1)
    return best


def measure(frame):
    """Кадр стенда → замер одного ракурса."""
    dark = frame < 90
    ys, xs = np.nonzero(dark)
    if not len(xs):
        return None
    fig = {"h": int(ys.max() - ys.min() + 1),
           "top": int(ys.min()), "bottom": int(ys.max()),
           "x0": int(xs.min()), "x1": int(xs.max())}
    # Плащ меряем в средней трети фигуры: выше — маска и плечи, ниже — рваный
    # подол и ноги.
    # НА 45% ВЫСОТЫ — ровно та строка, по которой снят лист разворотов
    # (TURNAROUND_PROMPT.md, «ширина плаща по клеткам»). Максимум по полосе
    # строк брать нельзя: у разных ракурсов плащ шире в разных местах, и
    # сравнение уезжает — четверть оборота выходила ШИРЕ анфаса, хотя масштаб
    # плаща в позе меньше анфасного.
    body = _open_x(dark, 12)

    white = frame > 200
    inner = white & ~flood_background(white)
    iy, ix = np.nonzero(inner)
    if not len(ix):
        fig.update(mask=None, eyes=0, feats=0)
        return fig
    # МАСКА — САМАЯ КРУПНАЯ замкнутая белая область, а не габарит всего
    # замкнутого белого. Габарит врал: рука, пересекающая корпус, запечатывает
    # карман фона между собой и плащом, и этот карман — тоже «замкнутое
    # белое». На ракурсах разворота такой карман раздувал «маску» вдвое, и
    # гейт объявлял голову резиновой, хотя она не менялась вовсе.
    lab_w = label(inner)
    if not lab_w.max():
        fig.update(mask=None, eyes=0, feats=0)
        return fig
    sizes = np.bincount(lab_w.ravel())
    sizes[0] = 0
    big = int(sizes.argmax())
    my, mx = np.nonzero(lab_w == big)
    fig["mask"] = {"x0": int(mx.min()), "x1": int(mx.max()),
                   "y0": int(my.min()), "y1": int(my.max())}

    # Черты лица — тёмные пятна ЦЕЛИКОМ внутри габарита маски. Глаз стоит
    # вертикально (выше своей ширины), рот лежит; так они и различаются, без
    # разбора того, какая деталь поднята позой.
    mx0, mx1, my0, my1 = (fig["mask"]["x0"], fig["mask"]["x1"],
                          fig["mask"]["y0"], fig["mask"]["y1"])
    sub = dark[my0:my1 + 1, mx0:mx1 + 1]
    lab = label(sub)
    eyes = feats = 0
    for i in range(1, lab.max() + 1):
        yy, xx = np.nonzero(lab == i)
        if len(yy) < 60:
            continue
        if yy.min() == 0 or xx.min() == 0 or \
           yy.max() == sub.shape[0] - 1 or xx.max() == sub.shape[1] - 1:
            continue          # прилипло к краю — это плащ, а не черта лица
        feats += 1
        if (yy.max() - yy.min()) > (xx.max() - xx.min()):
            eyes += 1
    fig["eyes"], fig["feats"] = eyes, feats
    # СТРОКА ЗАМЕРА ПЛАЩА ОТСЧИТЫВАЕТСЯ ОТ ПОДБОРОДКА, А НЕ ОТ ГАБАРИТА ФИГУРЫ.
    # Было «45% высоты фигуры» — доля, снятая с листа разворотов, когда плащ
    # занимал почти весь рост. После правки пропорций по скульптуре ноги стали
    # вдвое длиннее, плащ — половина роста, и та же доля увела строку под подол:
    # гейт мерил ногу и отдавал ширину плаща 0.00. Отсчёт от низа маски к низу
    # фигуры попадает в ткань при ЛЮБЫХ пропорциях: между подбородком и полом
    # плащ идёт первым.
    base = fig["mask"]["y1"] if fig.get("mask") else fig["top"]
    span = fig["bottom"] - base
    # МЕДИАНА ПО ПОЛОСЕ, А НЕ ОДНА СТРОКА. Одна строка ловит руку: на трёх
    # четвертях рука ложится НА плащ, морфологическое открытие её не снимает
    # (она толще порога), и в этой строке «ширина плаща» выходит больше
    # анфасной — разворот объявлялся сломанным там, где сломана была мерка.
    # Рука пересекает считанные строки, ткань идёт через все: медиана берёт
    # ткань. Полоса та же, что и была, — верхняя треть от подбородка до пола.
    rows = [widest_run(body, y, y + 1)
            for y in range(int(base + span * 0.25), int(base + span * 0.55), 2)]
    rows = [r for r in rows if r > 0]
    fig["w"] = int(np.median(rows)) if rows else 0
    return fig


def run(rig_dir, scale=0.90, y=0.60):
    rows = []
    for pose, ang, title in VIEWS:
        m = measure(render(rig_dir, pose, y, scale))
        if m is None:
            print(f"  [!] ракурс «{title}»: в кадре пусто — поза {pose} есть в риге?")
            return None, []
        m.update(pose=pose, ang=ang, title=title)
        rows.append(m)
    return rows[0], rows


def report(rig_dir, do_check, used=None):
    front, rows = run(rig_dir)
    if front is None:
        return 1
    fw, fh = front["w"], front["h"]
    fail = []

    print(f"\n  РАЗВОРОТ — {Path(rig_dir).name}\n")
    print(f"  {'ракурс':22s} {'плащ':>6s} {'доля':>6s} {'макушка':>8s} "
          f"{'маска H':>8s} {'глаз':>5s} {'черт':>5s}")
    crown, maskh = {}, {}
    fmh = front["mask"]["y1"] - front["mask"]["y0"] if front.get("mask") else 1
    for r in rows:
        cr = (r["top"] - front["top"]) / fh
        mh = ((r["mask"]["y1"] - r["mask"]["y0"]) / fmh) if r.get("mask") else float("nan")
        crown[r["ang"]], maskh[r["ang"]] = cr, mh
        print(f"  {r['title']:22s} {r['w']:6d} {r['w'] / fw:6.2f} {cr:+8.3f} "
              f"{mh:8.2f} {r['eyes']:5d} {r['feats']:5d}")

    # 1. макушка на одной высоте
    crs = list(crown.values())
    if max(crs) - min(crs) > CROWN_TOL:
        worst = max(crown, key=lambda a: abs(crown[a]))
        fail.append(([worst], f"макушка гуляет на {100 * (max(crs) - min(crs)):.1f}% роста "
                    f"(норма ≤{100 * CROWN_TOL:.0f}%), хуже всего на {worst}° "
                    f"({crown[worst]:+.3f}) — фигура проседает или подпрыгивает"))

    # 2. маска — жёсткий предмет
    face = {a: v for a, v in maskh.items() if abs(a) <= 90 and v == v}
    if face and max(face.values()) - min(face.values()) > MASKH_TOL:
        worst = max(face, key=lambda a: abs(face[a] - 1.0))
        fail.append(([worst], f"высота маски гуляет на "
                    f"{100 * (max(face.values()) - min(face.values())):.0f}% "
                    f"(норма ≤{100 * MASKH_TOL:.0f}%), хуже всего на {worst}° "
                    f"({face[worst]:.2f}) — голова не жёсткий предмет, а резиновая"))
    for a in (135, 180):
        v = maskh.get(a, float("nan"))
        if v == v and not DOME_BAND[0] <= v <= DOME_BAND[1]:
            fail.append(([a], f"{a}°: высота маски {v:.2f} вне полосы купола "
                        f"{DOME_BAND[0]:.2f}..{DOME_BAND[1]:.2f} — сзади должен быть "
                        f"низкий купол, а не овал лица"))

    # 3. со спины лица нет
    for r in rows:
        if r["ang"] in (135, 180) and r["feats"]:
            fail.append(([r["ang"]], f"{r['title']}: на маске {r['feats']} черт лица — "
                        f"со спины лица быть не должно"))

    # 4. в профиль ровно один глаз
    for r in rows:
        if abs(r["ang"]) == 90 and r["eyes"] != 1:
            fail.append(([r["ang"]], f"{r['title']}: глаз видно {r['eyes']}, а должен быть ровно один"))

    # 5. монотонность ряда ширин
    order = [0, 22, 45, 90, 135, 180]
    byang = {r["ang"]: r["w"] / fw for r in rows}
    seq = [byang[a] for a in order]
    for i in range(3):
        if seq[i + 1] > seq[i] + 0.01:
            fail.append(([order[i], order[i + 1]], f"ширина растёт там, где обязана убывать: "
                        f"{order[i]}°={seq[i]:.2f} → {order[i + 1]}°={seq[i + 1]:.2f}"))
    for i in range(3, 5):
        if seq[i + 1] < seq[i] - 0.01:
            fail.append(([order[i], order[i + 1]], f"ширина убывает там, где обязана расти: "
                        f"{order[i]}°={seq[i]:.2f} → {order[i + 1]}°={seq[i + 1]:.2f}"))
    for a in order:
        lo, hi = WIDTH_BAND[a]
        if not lo <= byang[a] <= hi:
            fail.append(([a], f"{a}°: ширина {byang[a]:.2f} вне полосы {lo:.2f}..{hi:.2f}"))

    # 6. зеркальность пар
    for a in (22, 45, 90):
        if a in byang and -a in byang:
            d = abs(byang[a] - byang[-a])
            if d > MIRROR_TOL:
                fail.append(([a, -a], f"пара ±{a}° не зеркальна: {byang[a]:.2f} против "
                            f"{byang[-a]:.2f}"))

    print()
    if not fail:
        print("  Разворот принят: одна фигура на всех ракурсах.\n")
        return 0

    # РАКУРС, КОТОРЫЙ РОЛИК ИГРАЕТ, — ЖЁСТКИЙ. ОСТАЛЬНЫЕ — ПРЕДУПРЕЖДЕНИЕ.
    # Гейт «всё или ничего» бесполезен: сломанный профиль не должен запрещать
    # выпуск ролика, который снят анфасом, — но и не должен молчать, если ролик
    # этот профиль показывает. `--used` называет позы, которые сцена реально
    # поднимает; нарушение на их углах роняет прогон, прочие идут в лог.
    hard, soft = [], []
    for angs, msg in fail:
        (hard if used is None or any(a in used for a in angs) else soft).append(msg)
    for m in hard:
        print(f"    [ПРОВАЛ] {m}")
    for m in soft:
        print(f"    [warn ] {m}   (ракурс в роликах не используется)")
    print()
    if hard:
        print(f"  Разворот НЕ принят: нарушений на используемых ракурсах {len(hard)}"
              + (f", ещё {len(soft)} на неиспользуемых.\n" if soft else ".\n"))
        print("  Условия приёмки и что с чем сверяется — в шапке этого файла\n"
              "  и в TURNAROUND_PROMPT.md рига.\n")
        return 1 if do_check else 0
    print(f"  Используемые ракурсы приняты; на полке ждут починки {len(soft)}.\n")
    return 0


def angles_of(poses):
    """Имена поз → углы разворота, которые они показывают."""
    m = {p: a for p, a, _ in VIEWS}
    out = {0}                       # анфас участвует всегда
    for p in poses:
        base = p.split("_shag")[0]
        for k, a in m.items():
            if base == k or base.startswith(k):
                out.add(a)
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="Гейт разворота персонажа")
    ap.add_argument("--rig", default=str(ROOT / RIGS / "freeman_rig"))
    ap.add_argument("--check", action="store_true",
                    help="ненулевой выход при нарушении условий приёмки")
    ap.add_argument("--used", default=None,
                    help="позы, которые ролик реально играет (через запятую): "
                         "нарушения на их ракурсах жёсткие, прочие — предупреждение")
    a = ap.parse_args(argv)
    used = angles_of([x.strip() for x in a.used.split(",") if x.strip()]) \
        if a.used is not None else None
    return report(a.rig, a.check, used)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
