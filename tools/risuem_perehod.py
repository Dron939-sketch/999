#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
risuem_perehod.py — локации ролика 27 «Парус», интро к курсу «Переход».

ТЕКСТ И РАСКАДРОВКА ПРИШЛИ ОТ СТУДИИ. Здесь нарисовано ровно то, что стоит в
колонке «Локация / ход» партитуры `perehod-VO.md`, кадр в кадр, и ничего сверх.

ЗРИТЕЛЬ: тридцать–сорок пять, работа по найму, за плечами несколько брошенных
«с понедельника». Считает себя ленивым; на деле гребёт годами.

УЗНАЁТСЯ НЕ МЕСТО, А ПОЛОЖЕНИЕ. Первый кадр — не «стол с бумагой», а СПИСОК,
СТРОКИ КОТОРОГО НАЕЗЖАЮТ ДРУГ НА ДРУГА: обещание себе, данное уже не в первый
раз, и предыдущие ещё видны под ним. Зритель опознаёт не лист, а положение.

ВОДЫ НЕТ НИ В ОДНОМ КАДРЕ. Запрет студии: «Никакого моря. Лодка на сухом
асфальте — половина смысла; вода превращает притчу в морскую заставку.»

ГРЕБЕЦ РИСУЕТСЯ В ЛОКАЦИЮ, А НЕ БЕРЁТСЯ ИЗ РИГА. Он сидит, а персонажу серии
сидеть нельзя — указание студии повторено трижды и меряется гейтом осанки.

ПАРУС ЛЕЖИТ В ЛОДКЕ С ПЕРВОГО ЕЁ ПОЯВЛЕНИЯ И МОЛЧИТ. В кадрах 5, 7, 9 он
свёрнут и нарисован тушью — вещь среди вещей. Цветным он становится ровно один
раз, в последнем кадре (`tools/cvet.py`).

ТРИ ПРОСМОТРА КОНТАКТНОГО ЛИСТА, ТРИ КЛАССА БРАКА — разбор у каждой функции.
Ни один из них не ловится гейтами: все они читают текст и силуэты, а брак был
в том, ЧЕМ ЧИТАЕТСЯ ПЛОСКОСТЬ и ЧЕМ ЧИТАЕТСЯ РУКА.
"""

import json
import math
import random
import sys
from pathlib import Path

from PIL import ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risuem import TUSH, BUMAGA, W, H, holst, liniya, lomanaya, pryamoug, krug, \
    shtrih_ruka, shtrih_mashina, sohranit
from risuem_anketa import nadpis

# Цвет паруса — единственная краска ролика. Охра, а не красный: красный в серии
# уже занят «проблемой» из ролика про бизнес-мышление, и повтор превратил бы
# цвет в примету серии вместо знака этого ролика.
OHRA = (196, 132, 46)

STROKI = ["Выучиться", "Открыть своё", "Переехать", "Начать с понедельника"]


def oval(d, cx, cy, rx, ry, w=13, zaliv=None, drozh=2.0, shag=18):
    """Эллипс дрожащей линией. Нужен постоянно: круг в перспективе — овал, а
    круглый люк, нарисованный кругом, кладёт плоскость набок."""
    pts = [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
           for a in range(0, 360, shag)]
    if zaliv is not None:
        d.polygon(pts, fill=zaliv)
    lomanaya(d, pts, w=w, zamknut=True, drozh=drozh)


# ============================== СПИСОК ======================================

def _list_bumagi(d, x0=250, y0=90, x1=1030, y1=650, w=13):
    """Лист с загнутым углом. Загиб нужен: без него прямоугольник читается
    как окно, а не как бумага."""
    zag = 74
    lomanaya(d, [(x0, y0), (x1 - zag, y0), (x1, y0 + zag), (x1, y1), (x0, y1)],
             w=w, zamknut=True)
    lomanaya(d, [(x1 - zag, y0), (x1 - zag, y0 + zag), (x1, y0 + zag)], w=w - 4)


def spisok_ruka():
    """VO-1. Лист и рука, которая пишет первую строку.

    КИСТЬ БЕРЁТСЯ СИЛУЭТОМ, А НЕ КОНТУРОМ. Две пробы вели её линией — оба раза
    получался клубок палок: контурная кисть требует верной анатомии в каждом
    суставе, и любая неточность рвёт узнавание. Залитый силуэт прощает всё:
    глаз читает ОБЩУЮ ФОРМУ и достраивает остальное сам. Собирается она из
    простых залитых тел, и ни одно из них не обязано быть точным.
    """
    im, d = holst(2701)
    dd = ImageDraw.Draw(im)
    _list_bumagi(d, x0=180, y0=120, x1=880, y1=690)
    nadpis(dd, (232, 186), STROKI[0], 60)
    liniya(d, (228, 262), (560, 264), w=8)

    kx, ky = 830, 330
    liniya(d, (1290, 250), (kx + 40, ky + 20), w=132, fill=TUSH)      # предплечье
    oval(d, kx, ky + 40, 132, 112, w=1, zaliv=TUSH, shag=12)          # ладонь
    for i, (ax, ay) in enumerate([(-118, -34), (-134, 16), (-124, 64), (-100, 110)]):
        liniya(d, (kx - 20, ky + 40), (kx + ax, ky + ay), w=46 - i * 4, fill=TUSH)
        krug(d, kx + ax, ky + ay, (46 - i * 4) / 2, w=1, zaliv=TUSH)
    liniya(d, (kx - 10, ky - 40), (kx - 96, ky - 118), w=48, fill=TUSH)   # большой
    krug(d, kx - 96, ky - 118, 24, w=1, zaliv=TUSH)

    # КАРАНДАШ СВЕТЛЫЙ ПОВЕРХ ТЁМНОЙ КИСТИ — иначе он в силуэте пропадает.
    # Он же объясняет хват: тело идёт сквозь пальцы, грифель стоит ровно на
    # конце строки, и видно, что пишут именно её.
    liniya(d, (kx + 66, ky - 148), (kx - 150, ky + 26), w=26, fill=BUMAGA)
    liniya(d, (kx - 150, ky + 26), (576, 266), w=22, fill=TUSH)
    liniya(d, (kx - 148, ky + 22), (578, 262), w=8, fill=BUMAGA)
    lomanaya(d, [(566, 272), (600, 246), (596, 288)], w=7, zamknut=True)
    return sohranit(im, "spisok-ruka")


def spisok_naezd():
    """VO-2. Четыре строки наползают друг на друга.

    СЛОИ ПРОШЛЫХ ПОПЫТОК ИДУТ ПЕРВЫМИ И ИХ МНОГО. Первая проба ставила один
    серый след под каждой строкой — его не было видно вовсе, и список читался
    как аккуратный план. Наезд виден только тогда, когда под свежей строкой
    лежат ЧЕТЫРЕ старых, каждая под своим углом: тогда лист читается как
    исписанный, а обещание — как данное не в первый раз.
    """
    im, d = holst(2702)
    dd = ImageDraw.Draw(im)
    _list_bumagi(d, x0=180, y0=90, x1=1100, y1=660)
    random.seed(2702)
    for sloj in range(4):
        ton = 176 - sloj * 9
        for i, txt in enumerate(STROKI):
            px = 62 - i * 5
            nadpis(dd, (214 + random.randint(-40, 40),
                        150 + i * 118 + random.randint(-46, 46)),
                   txt, px, fill=(ton, ton + 3, ton - 4))
    # свежие строки: шаг МЕНЬШЕ кегля, поэтому они садятся друг на друга
    y = 176
    for i, txt in enumerate(STROKI):
        px = 62 - i * 5
        nadpis(dd, (222 + i * 16, y), txt, px)
        liniya(d, (216 + i * 16, y + px * 0.96),
               (216 + i * 16 + px * len(txt) * 0.50,
                y + px * 0.96 + random.randint(-8, 8)), w=7)
        y += px * 0.92
    return sohranit(im, "spisok-naezd")


def spisok_pyl():
    """VO-3. «Красивый список. Мёртвый.» Бумага осыпается в пыль.

    РАССЫПАНИЕ ИДЁТ СНИЗУ ВВЕРХ И СЪЕДАЕТ БУКВЫ. Осыпать края и оставить текст
    целым — это «старая бумага»; съесть текст — это «список умер».
    """
    im, d = holst(2703)
    dd = ImageDraw.Draw(im)
    random.seed(2703)
    zub = [(250, 90), (956, 90), (1030, 164), (1030, 300)]
    x = 1030
    while x > 250:
        zub.append((x, 300 + random.randint(-30, 70)))
        x -= random.randint(30, 70)
    lomanaya(d, zub, w=13, zamknut=True)
    nadpis(dd, (300, 152), STROKI[0], 58)
    liniya(d, (296, 212), (296 + 58 * len(STROKI[0]) * 0.52, 212), w=7)
    nadpis(dd, (300, 232), STROKI[1], 54, fill=(120, 123, 116))
    for i in range(2600):
        yy = 300 + random.random() ** 1.7 * 400
        xx = 250 + random.random() * 780 + (yy - 300) * random.uniform(-0.35, 0.35)
        krug(d, xx, yy, random.choice([1, 1, 2, 2, 3]), w=1, zaliv=TUSH, drozh=0.3)
    return sohranit(im, "spisok-pyl")


# ============================== ЛОДКА =======================================

def _lodka(d, cx, cy, dlina=560, vys=118, w=15, punktir=False, parus_svern=True):
    """Лодка сбоку: корпус, планширь, банки, свёрнутое полотнище на дне.

    ЛОДКА НА СУШЕ КРЕНИТСЯ. Стоящая ровно читается как плывущая, даже если под
    ней нарисован асфальт: ровный киль — признак воды, которая держит. Крен
    стоит дешевле любого другого довода в этом кадре.
    """
    kren = 0.10
    pol = dlina / 2
    nos_v = vys * 0.55          # нос задран выше кормы — лодка не симметрична

    def t(x, y):
        return (cx + x, cy + y + x * kren)

    korpus = [t(-pol, -nos_v), t(-pol * 0.80, vys * 0.20), t(-pol * 0.40, vys * 0.50),
              t(pol * 0.55, vys * 0.46), t(pol * 0.86, vys * 0.10), t(pol, -vys * 0.34)]
    if not punktir:
        # КОРПУС ЗАЛИВАЕТСЯ ЦВЕТОМ БУМАГИ. Асфальт под ним крапчатый, и без
        # заливки крап просвечивает сквозь лодку — вместо предмета решето.
        d.polygon(korpus, fill=BUMAGA)
    lomanaya(d, korpus, w=(6 if punktir else w), zamknut=True,
             drozh=(6.0 if punktir else 2.2))
    lomanaya(d, [t(-pol + 14, -nos_v + 24), t(0, -vys * 0.06),
                 t(pol - 14, -vys * 0.34 + 24)], w=max(4, w - 6))
    for bx in (-pol * 0.34, pol * 0.28):        # банки
        liniya(d, t(bx, -vys * 0.10), t(bx, vys * 0.42), w=max(4, w - 7))
    if not punktir:                             # уключины
        for bx in (-pol * 0.14, pol * 0.10):
            krug(d, *t(bx, -vys * 0.12), 11, w=6)
    if parus_svern:
        rx, ry = pol * 0.06, vys * 0.30
        lomanaya(d, [t(rx - 130, ry - 30), t(rx + 130, ry - 30),
                     t(rx + 130, ry + 8), t(rx - 130, ry + 8)], w=8, zamknut=True)
        for k in range(-2, 3):
            liniya(d, t(rx + k * 52, ry - 28), t(rx + k * 52 - 16, ry + 6), w=5)
        liniya(d, t(rx - 40, ry - 36), t(rx - 40, ry + 14), w=6)


def _grebec(d, cx, cy, golova_k_zritelyu=False, vyosla=True, w=14):
    """Гребец: голова, плечи, руки. БРОВЕЙ НЕТ — правило серии.

    ГРЕБЕЦ СИДИТ В ЛОДКЕ, А НЕ СТОИТ ЗА НЕЙ. На первом контактном листе фигура
    была нарисована целиком поверх корпуса и читалась как распятая над лодкой:
    ноги шли сквозь дно. Из-за планширя видно ровно то, что и бывает видно, —
    голову, плечи и руки; лодка от этого впервые становится лодкой.
    """
    m = w / 14.0
    krug(d, cx, cy - 104 * m, 40 * m, w=w)
    if golova_k_zritelyu:
        krug(d, cx - 15 * m, cy - 112 * m, 5 * m, w=max(3, int(4 * m)), zaliv=TUSH)
        krug(d, cx + 15 * m, cy - 112 * m, 5 * m, w=max(3, int(4 * m)), zaliv=TUSH)
        liniya(d, (cx - 14 * m, cy - 86 * m), (cx + 14 * m, cy - 86 * m),
               w=max(3, int(6 * m)))
    else:
        krug(d, cx + 19 * m, cy - 110 * m, 5 * m, w=max(3, int(4 * m)), zaliv=TUSH)
    lomanaya(d, [(cx - 40 * m, cy + 10 * m), (cx - 30 * m, cy - 58 * m),
                 (cx + 30 * m, cy - 58 * m), (cx + 40 * m, cy + 10 * m)], w=w)
    if vyosla:
        for zn in (-1, 1):
            lomanaya(d, [(cx + zn * 28 * m, cy - 50 * m), (cx - 74 * m, cy - 34 * m),
                         (cx - 118 * m, cy - 6 * m)], w=max(4, w - 3))
    else:
        lomanaya(d, [(cx - 28 * m, cy - 50 * m), (cx - 70 * m, cy + 6 * m)],
                 w=max(4, w - 3))
        lomanaya(d, [(cx + 28 * m, cy - 50 * m), (cx + 70 * m, cy + 6 * m)],
                 w=max(4, w - 3))


def _veslo(d, ux, uy, dl=290, ugol=28, w=13):
    """Весло от уключины наружу и вниз: валёк, лопасть, упор в асфальт.

    ЛОПАСТЬ ОБЯЗАТЕЛЬНА. Палка, торчащая из борта, — это шест; вёслами её
    делает лопасть, и она же показывает, что упирается весло в ТВЁРДОЕ.
    """
    r = math.radians(ugol)
    ex, ey = ux - dl * math.cos(r), uy + dl * math.sin(r)
    liniya(d, (ux + 46 * math.cos(r), uy - 46 * math.sin(r)), (ex, ey), w=w)
    lop = [(ex + 46 * math.cos(r) + 26 * math.sin(r), ey - 46 * math.sin(r) + 26 * math.cos(r)),
           (ex - 30 * math.cos(r) + 22 * math.sin(r), ey + 30 * math.sin(r) + 22 * math.cos(r)),
           (ex - 30 * math.cos(r) - 22 * math.sin(r), ey + 30 * math.sin(r) - 22 * math.cos(r)),
           (ex + 46 * math.cos(r) - 26 * math.sin(r), ey - 46 * math.sin(r) - 26 * math.cos(r))]
    lomanaya(d, lop, w=max(4, w - 4), zamknut=True)


def lodka_iz_pyli():
    """VO-4. Из пыли собирается человек в лодке — контур ещё не сомкнут.

    ОБЛАКО, А НЕ ЗАПЛАТКА. Первая проба сыпала точки по прямоугольнику, и
    резкий край читался как наклеенный лоскут. Плотность падает от центра к
    краям — тогда пыль именно висит.
    """
    im, d = holst(2704)
    random.seed(2704)
    for i in range(4200):
        a = random.random() * math.tau
        r = random.random() ** 0.65
        xx = 640 + math.cos(a) * r * 610
        yy = 400 + math.sin(a) * r * 330
        if random.random() > 1.02 - r * 0.85:
            continue
        krug(d, xx, yy, random.choice([1, 1, 2]), w=1, zaliv=TUSH, drozh=0.3)
    _lodka(d, 640, 470, punktir=True, parus_svern=False)
    _grebec(d, 560, 452, w=11)
    return sohranit(im, "lodka-iz-pyli")


def _asfalt(d, gorizont=352, zebra=True):
    """Сухой асфальт. ВОДЫ НЕТ — запрет студии, и он оказался самым дорогим.

    ЧЕМ БЫЛ ИСПОРЧЕН ПЕРВЫЙ ПРОГОН. Асфальт рисовался двумя параллельными
    горизонталями с гребёнкой поверху — и на контактном листе это читалось как
    берег и рябь. То есть кадр, вся сила которого в отсутствии воды, сообщал
    зрителю воду. Ни один гейт этого не ловит: все они читают силуэты и
    надписи, а тут неверно читалась ПЛОСКОСТЬ.

    ПЛОСКОСТЬ НАДО ЗАЛИТЬ ФАКТУРОЙ, ИНАЧЕ ЕЁ НЕТ. Второй лист показал кадр,
    наполовину состоящий из чистой бумаги: линии разметки висели в пустоте.
    Крап — самая дешёвая фактура и самая точная: гладкой поверхности не бывает
    крапчатой, поэтому он заодно снимает последнее подозрение на воду.

    РАЗМЕТКА ПИШЕТСЯ ЦВЕТОМ БУМАГИ ПОВЕРХ КРАПА, А НЕ ТУШЬЮ. Тушь по крапу —
    ещё одна тёмная линия среди тёмных; светлая полоса по крапу читается ровно
    тем, чем является, — краской на асфальте.
    """
    shod_x, shod_y = 700, gorizont
    random.seed(int(gorizont))

    for _ in range(9000):
        f = random.random() ** 0.55
        yy = gorizont + 14 + f * (H - gorizont - 14)
        xx = random.random() * W
        krug(d, xx, yy, 1, w=1, zaliv=TUSH, drozh=0.2)

    y, dl = 716, 82
    while y > gorizont + 56:
        f = (y - shod_y) / (716 - shod_y)
        x = shod_x + (110 - shod_x) * f
        liniya(d, (x, y), (x + dl * 0.30 * f, y - dl * 1.05 * f),
               w=max(3, int(20 * f)), fill=BUMAGA, prohody=1)
        y -= dl * 2.0
        dl *= 0.84

    if zebra:
        # ЗЕБРА — вещь, которую нельзя спутать с водой ни при какой погоде.
        # Стоит она в ДАЛЬНЕЙ половине плоскости: лодка живёт в ближней, и
        # накладываться им негде. Проба, положившая её через весь кадр, дала
        # полосы поверх корпуса — довод, поставленный на главный предмет,
        # портит и предмет, и довод.
        for i in range(6):
            f0 = 0.16 + i * 0.058
            f1 = f0 + 0.030
            yy0 = shod_y + (716 - shod_y) * f0
            yy1 = shod_y + (716 - shod_y) * f1
            xl0 = shod_x + (-420 - shod_x) * f0
            xl1 = shod_x + (-420 - shod_x) * f1
            xr0 = shod_x + (1760 - shod_x) * f0
            xr1 = shod_x + (1760 - shod_x) * f1
            d.polygon([(xl0, yy0), (xr0, yy0), (xr1, yy1), (xl1, yy1)], fill=BUMAGA)

    # дальняя кромка и бордюр С ТОРЦОМ — у воды толщины кромки не бывает
    liniya(d, (0, gorizont + 4), (W, gorizont - 6), w=7)
    liniya(d, (0, gorizont + 26), (W, gorizont + 12), w=13)
    for x in range(-20, W + 60, 96):
        liniya(d, (x, gorizont + 6), (x - 6, gorizont + 26), w=5)

    # ДВОР ЗА БОРДЮРОМ — верх кадра тоже обязан быть занят. Пустая бумага над
    # горизонтом читается не как небо, а как незаконченный рисунок.
    for bx, bw, bh in [(-30, 300, 250), (330, 210, 180), (600, 250, 300),
                       (900, 190, 200), (1130, 260, 260)]:
        top = gorizont - bh
        pryamoug(d, (bx, top, bx + bw, gorizont + 2), w=11)
        for r in range(int(bh / 62)):
            for c in range(int(bw / 66)):
                pryamoug(d, (bx + 18 + c * 66, top + 20 + r * 62,
                             bx + 52 + c * 66, top + 52 + r * 62), w=5)

    for _ in range(6):                      # трещины: вода не трескается
        x0 = random.randint(60, W - 60)
        y0 = random.randint(gorizont + 110, H - 20)
        pts = [(x0, y0)]
        for k in range(4):
            pts.append((pts[-1][0] + random.randint(-100, 100),
                        pts[-1][1] - random.randint(8, 40)))
        lomanaya(d, pts, w=4, drozh=3.2)

    oval(d, 1108, 656, 100, 46, w=11)       # люк — овалом, не кругом
    oval(d, 1108, 656, 68, 31, w=6)
    for a in range(0, 360, 45):
        r = math.radians(a)
        liniya(d, (1108 + 68 * math.cos(r), 656 + 31 * math.sin(r)),
               (1108 + 98 * math.cos(r), 656 + 44 * math.sin(r)), w=5)


def lodka_asfalt():
    """VO-5. РАЗРЫВ: камера отъехала — воды нет, лодка стоит на асфальте."""
    im, d = holst(2705)
    _asfalt(d, gorizont=300)
    _veslo(d, 520, 486, dl=250, ugol=34, w=12)
    _lodka(d, 600, 520, dlina=640, vys=136)
    _grebec(d, 508, 452, w=15)
    # тень лежит ПОД днищем и наружу, а не внутри корпуса
    lomanaya(d, [(300, 612), (560, 630), (880, 604)], w=20, drozh=4.5)
    return sohranit(im, "lodka-asfalt")


def ladoni_vyosla():
    """VO-6, VO-7. Крупно: ладонь, мозоли, стёртая рукоять.

    ЛАДОНЬ БЕРЁТСЯ СИЛУЭТОМ, А МОЗОЛИ — ПРОСВЕТАМИ В НЁМ. Три пробы вели кисть
    контуром, и все три дали не руку: сжатую — частоколом скоб, раскрытую —
    коробкой с карандашами. Контур требует верной анатомии в каждом суставе;
    силуэт читается общей формой и прощает всё — ровно это уже спасло пишущую
    руку в первом кадре.

    И СВЕТЛЫЕ МОЗОЛИ НА ТЁМНОЙ ЛАДОНИ БУКВАЛЬНЫ. «Стёр ладони до кости» — это
    места, где кожи не осталось; светлое пятно на чёрном и есть стёртое место.
    Тёмные мозоли на светлой ладони показывали ровно обратное.
    """
    im, d = holst(2706)
    # ВЕСЛО ПРОХОДИТ ПОД ЛАДОНЬЮ И УХОДИТ ЗА КРОМКУ. Проба вела его вверх
    # наискось, и полоса вылезла между пальцами — рука оказалась проткнутой.
    lom = [(0, 470), (740, 700), (720, 800), (0, 580)]
    d.polygon(lom, fill=BUMAGA)
    lomanaya(d, lom, w=13, zamknut=True)
    shtrih_ruka(d, 40, 546, 300, w=5)
    shtrih_ruka(d, 300, 630, 560, w=5)

    lx, ly = 640, 520                        # центр ладони, запястье за кромкой
    d.polygon([(lx - 250, ly - 130), (lx + 250, ly - 130), (lx + 214, ly + 150),
               (lx + 170, ly + 260), (lx - 162, ly + 260), (lx - 206, ly + 150)],
              fill=TUSH)
    # ПАЛЬЦЫ РАЗВЕДЕНЫ И РАЗНОЙ ДЛИНЫ: сомкнутые одинаковые дают частокол.
    for i, (dl_, ug) in enumerate([(292, -0.26), (368, -0.08), (332, 0.10), (250, 0.30)]):
        fx = lx - 178 + i * 118
        vx = fx + dl_ * math.sin(ug)
        vy = ly - 130 - dl_ * math.cos(ug)
        sh_ = 44 - i * 4
        liniya(d, (fx, ly - 70), (vx, vy + sh_), w=sh_ * 2, fill=TUSH)
        krug(d, vx, vy + sh_, sh_, w=1, zaliv=TUSH)
    liniya(d, (lx + 190, ly - 30), (lx + 400, ly + 116), w=94, fill=TUSH)  # большой
    krug(d, lx + 400, ly + 116, 47, w=1, zaliv=TUSH)

    # МОЗОЛИ — ЧЕТЫРЕ СВЕТЛЫХ ПЯТНА разного размера и НА РАЗНОЙ ВЫСОТЕ. Ровный
    # ряд вплотную читался зубами; вразброс они читаются мозолями, и глаз их
    # считает — «годами» получает единицу измерения.
    for i, (rr, dy) in enumerate([(52, 0), (64, -22), (56, 8), (42, 26)]):
        mx = lx - 178 + i * 118
        oval(d, mx, ly - 56 + dy, rr, rr * 0.60, w=1, zaliv=BUMAGA, shag=20)
        shtrih_ruka(d, mx - rr * 0.55, ly - 44 + dy, mx + rr * 0.55, w=4)
    for y0, x0, x1 in [(ly + 96, -186, 150), (ly + 168, -170, 168)]:
        lomanaya(d, [(lx + x0, y0), (lx + (x0 + x1) / 2, y0 - 30), (lx + x1, y0 + 14)],
                 w=10, fill=BUMAGA)
    return sohranit(im, "ladoni-vyosla")


def vzglyad_grebca():
    """VO-8. «Оторви взгляд от вёсел.» Голова поднялась — первый прямой взгляд.

    ВЁСЛА ОСТАЮТСЯ В КАДРЕ И ОСТАЮТСЯ ОПУЩЕННЫМИ. Убрать их — показать решение
    раньше слова; поднять — показать, что он уже послушался.
    """
    im, d = holst(2707)
    _asfalt(d, gorizont=272)
    _veslo(d, 560, 500, dl=300, ugol=30, w=14)
    _lodka(d, 660, 540, dlina=780, vys=158)
    _grebec(d, 546, 462, golova_k_zritelyu=True, w=18)
    lomanaya(d, [(320, 636), (620, 656), (960, 626)], w=20, drozh=4.5)
    return sohranit(im, "vzglyad-grebca")


# ============================== ДВОР ========================================

def _silue(d, x, y, h, w=7):
    """Силуэт человека: голова, корпус, шаг. Без шага поток превращается
    в частокол."""
    krug(d, x, y - h, h * 0.20, w=w, zaliv=TUSH)
    liniya(d, (x, y - h * 0.78), (x, y - h * 0.34), w=int(h * 0.20) + w)
    liniya(d, (x, y - h * 0.34), (x - h * 0.17, y), w=w)
    liniya(d, (x, y - h * 0.34), (x + h * 0.20, y), w=w)


def dvor_potok():
    """VO-9, VO-10. Двор сверху: тропа наискось по газону, поток идёт по ней.

    ТРОПА ПРОТОПТАНА, А НЕ ПРОЛОЖЕНА. Дорожка, начерченная кем-то, — городское
    планирование; тропа поперёк газона — ДОКАЗАТЕЛЬСТВО, что поток идёт здесь
    давно и сам. Она и есть довод реплики «Годами. Без тебя».

    ЛОДКА В ЭТОМ КАДРЕ КРОШЕЧНАЯ И СТОИТ ПОПЕРЁК: человек в ней гребёт не
    туда, куда идёт двор, и это видно без единого слова.
    """
    im, d = holst(2708)
    random.seed(2708)
    for x0 in (0, 1010):
        pryamoug(d, (x0 - 40, 0, x0 + 310, 300), w=15)
        for r in range(4):
            for c in range(4):
                pryamoug(d, (x0 - 4 + c * 78, 34 + r * 66,
                             x0 + 44 + c * 78, 78 + r * 66), w=6)
    for i in range(240):
        gx, gy = random.random() * W, 320 + random.random() * 400
        liniya(d, (gx, gy), (gx + random.randint(-6, 6), gy - random.randint(10, 22)),
               w=3, drozh=0.6)
    verh = [(300, 720), (520, 560), (760, 440), (1010, 336)]
    lomanaya(d, verh, w=9)
    lomanaya(d, [(x + 96, y + 30) for x, y in verh], w=9)

    # ПОТОК РАЗРЕЖИВАЕТСЯ, ИНАЧЕ ЭТО ГУСЕНИЦА. На первом листе ближние силуэты
    # слились в сплошное чёрное тело: шаг был мельче ширины фигуры.
    t = 0.0
    while t < 1.0:
        i = min(int(t * 3), 2)
        p0, p1 = verh[i], verh[i + 1]
        f = t * 3 - i
        x = p0[0] + (p1[0] - p0[0]) * f + 48 + random.randint(-30, 30)
        y = p0[1] + (p1[1] - p0[1]) * f + 16 + random.randint(-12, 12)
        _silue(d, x, y, 118 * (1.0 - t * 0.76), w=max(3, int(7 * (1 - t * 0.6))))
        t += 0.020 + (1.0 - t) * 0.062
    _lodka(d, 236, 688, dlina=270, vys=58, w=8)
    _grebec(d, 200, 672, w=6)
    return sohranit(im, "dvor-potok")


def lodka_krupno():
    """VO-11. «Не потому, что ты ленивый.» Возврат в лодку, крупный план.

    ЭТО ТА ЖЕ ЛОДКА И ТОТ ЖЕ РУЛОН НА ДНЕ. Кольцо закрывается в ОДНОЙ локации,
    иначе кадр сомкнулся, а фраза пришла из чужого места. Крупность другая,
    предмет тот же — и рулон впервые попадает в центр кадра, всё ещё не
    названный.
    """
    im, d = holst(2709)
    _asfalt(d, gorizont=214, zebra=False)
    _lodka(d, 660, 520, dlina=1040, vys=250, w=19)
    _grebec(d, 470, 456, golova_k_zritelyu=True, vyosla=False, w=26)
    lomanaya(d, [(160, 640), (620, 668), (1160, 620)], w=24, drozh=5.0)
    return sohranit(im, "lodka-krupno")


def vopros_chern():
    """VO-12. Чёрный экран, вопрос набирается по букве.

    ПАУЗА ПЕРЕД ДОГАДКОЙ — РАБОЧЕЕ ВРЕМЯ ЗРИТЕЛЯ, и заполнять её нечем.

    ЗАЛИВАТЬ НАДО ВЕСЬ ХОЛСТ, А НЕ КАДР. `sohranit` кладёт рисунок 1280×720 в
    поле 1760×990 — оно и есть запас на проезд. Чёрный прямоугольник по
    границе кадра оставлял вокруг светлую бумагу, и «чёрный экран» на проезде
    превращался в заплатку.
    """
    im, d = holst(2710)
    d.rectangle((0, 0, W, H), fill=TUSH)
    im._zaliv_holsta = TUSH
    dd = ImageDraw.Draw(im)
    nadpis(dd, (W / 2, 322), "Что рядом с тобой", 68, fill=BUMAGA, centr=True)
    nadpis(dd, (W / 2, 412), "уже движется само?", 68, fill=BUMAGA, centr=True)
    return sohranit(im, "vopros-chern")


def parus():
    """VO-13. Ветер. Полотнище выпрямляется парусом — единственный цвет ролика.

    ПАРУС НЕ ДОРИСОВЫВАЕТСЯ, А РАЗВОРАЧИВАЕТСЯ. Мачты в лодке не было ни в
    одном кадре, и дорисовать её в финале значит подсунуть зрителю недостающую
    деталь. Парус держит то же весло, которым он греб, — другого у него не
    было ни минуты, и это видно.

    ЦВЕТ ЗАНИМАЕТ МЕНЬШЕ ТРЁХ ПРОЦЕНТОВ КАДРА (`tools/cvet.py`). Больше — и
    это уже не вещь, а цветной кадр.
    """
    im, d = holst(2711)
    _asfalt(d, gorizont=300)
    _lodka(d, 620, 520, dlina=680, vys=136, parus_svern=False)
    _grebec(d, 470, 450, golova_k_zritelyu=True, vyosla=False, w=15)
    liniya(d, (688, 536), (712, 152), w=15)     # весло стоймя вместо мачты
    krug(d, 690, 528, 16, w=8)
    puz = [(710, 176), (798, 244), (846, 344), (838, 452), (700, 494)]
    d.polygon(puz, fill=OHRA)
    lomanaya(d, puz, w=13, zamknut=True)
    for k in range(1, 4):
        liniya(d, (706 + k * 4, 200 + k * 82), (774 + k * 20, 254 + k * 76), w=6)
    liniya(d, (712, 172), (846, 344), w=7)      # шкот к концу весла
    for y in (232, 296, 372):                   # ветер
        liniya(d, (120, y), (330, y - 14), w=6, drozh=3.5)
        liniya(d, (150, y + 18), (300, y + 8), w=4, drozh=3.5)
    for k in range(3):                          # штрихи движения за кормой
        liniya(d, (200 - k * 42, 560 + k * 16), (300 - k * 42, 556 + k * 16), w=7)
    return sohranit(im, "parus")


# ============================== МЕРА ========================================

def mera(imya, chelovek=0.55, back_y=0.50, front_y=0.96):
    """Мера человека и пол — без них локация не годится для говорящей сцены."""
    Path(f"examples/assets/sets/{imya}.surfaces.json").write_text(json.dumps({
        "floor": {"back_y": back_y, "front_y": front_y},
        "chelovek": chelovek,
        "_comment": ("Мера человека — доля высоты кадра, которую занимает фигура "
                     "у передней кромки пола. Ниже 0.5 локация для говорящей "
                     "сцены не годится (реестр §XL).")
    }, ensure_ascii=False, indent=2), encoding="utf-8")


KADRY = [
    (spisok_ruka,    "spisok-ruka",     0.58),
    (spisok_naezd,   "spisok-naezd",    0.58),
    (spisok_pyl,     "spisok-pyl",      0.58),
    (lodka_iz_pyli,  "lodka-iz-pyli",   0.55),
    (lodka_asfalt,   "lodka-asfalt",    0.55),
    (ladoni_vyosla,  "ladoni-vyosla",   0.62),
    (vzglyad_grebca, "vzglyad-grebca",  0.58),
    (dvor_potok,     "dvor-potok",      0.52),
    (lodka_krupno,   "lodka-krupno",    0.64),
    (vopros_chern,   "vopros-chern",    0.55),
    (parus,          "parus",           0.58),
]

if __name__ == "__main__":
    for fn, imya, ch in KADRY:
        n = fn()
        mera(imya, chelovek=ch)
        print(f"  {imya:<16} {n // 1024:>5} КБ")
    print(f"нарисовано локаций: {len(KADRY)}")
