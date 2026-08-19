#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
risuem_lekciya1.py — кадры видеоряда к лекции 1 «Чью жизнь вы живёте».

Каждый кадр держит экран от сорока секунд до трёх минут, поэтому мерка тут
жёстче, чем у ролика: предмет обязан читаться С ОДНОГО ВЗГЛЯДА и не умереть на
третьей секунде. Первый набор эту мерку провалил — семь тонких линий посреди
бумаги («список Торо»), квадрат со стрелкой в шесть квадратов («так все»),
четыре сходящиеся линии («всё рядом»): все три читались НИЧЕМ. Здесь каждый
кадр назван тем, что зритель должен в нём увидеть, и если название не
складывается в одну фразу — кадр не годится и переделывается.

Порядок кадров — порядок лекции.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risuem import (BUMAGA, TUSH, W, H, holst, liniya, lomanaya, pryamoug,
                    krug, shtrih_ruka, shtrih_mashina, sohranit)


def domik(d, cx, y_niz, w, h, krysha=0.55, dver=True, ww=15):
    """Домик: коробка плюс двускатная крыша. Базовая форма половины кадров."""
    x0, x1 = cx - w / 2, cx + w / 2
    y0 = y_niz - h
    lomanaya(d, [(x0, y_niz), (x0, y0), (x1, y0), (x1, y_niz)], w=ww)
    liniya(d, (x0, y_niz), (x1, y_niz), w=ww)
    lomanaya(d, [(x0 - w * 0.10, y0), (cx, y0 - h * krysha), (x1 + w * 0.10, y0)], w=ww)
    if dver:
        dw, dh = w * 0.26, h * 0.5
        pryamoug(d, (cx - dw / 2, y_niz - dh, cx + dw / 2, y_niz), w=ww - 3)


def figura(d, cx, y_niz, h, ww=14):
    """Человек одной формой: голова плюс трапеция корпуса. Без лиц и рук."""
    r = h * 0.20
    krug(d, cx, y_niz - h + r, r, w=ww, zaliv=TUSH)
    lomanaya(d, [(cx - h * 0.26, y_niz), (cx - h * 0.16, y_niz - h + 2.2 * r),
                 (cx + h * 0.16, y_niz - h + 2.2 * r), (cx + h * 0.26, y_niz)],
             w=ww, zamknut=True)


def strelka(d, p1, p2, w=15, per=26):
    """Стрелка: древко плюс два пера. Дрожит, как и всё остальное."""
    import math
    liniya(d, p1, p2, w=w)
    a = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    for s in (+1, -1):
        b = a + s * math.radians(150)
        liniya(d, p2, (p2[0] + per * math.cos(b), p2[1] + per * math.sin(b)), w=w)


# ─────────────────────────────────────────────────────────────────────────────
# ВСТУПЛЕНИЕ — «обычная жизнь разложена по коробкам, и все коробки заполнены»
def obychnaya_zhizn():
    im, d = holst(11)
    x = 78
    for i in range(4):
        pryamoug(d, (x, 150, x + 268, 570), w=17)
        # содержимое: у каждой коробки своё, но заполнены ВСЕ одинаково плотно
        if i == 0:
            for k in range(4):
                shtrih_mashina(d, x + 40, 250 + k * 78, x + 228, shag=30, h=22)
        elif i == 1:
            figura(d, x + 96, 500, 190)
            figura(d, x + 180, 500, 150)
        elif i == 2:
            domik(d, x + 134, 500, 190, 150)
        else:
            krug(d, x + 134, 300, 66, w=15)
            for k in range(3):
                liniya(d, (x + 40, 420 + k * 62), (x + 228, 420 + k * 62), w=13)
        x += 288
    return sohranit(im, "lek1-obychnaya-zhizn")


# АНКЕТА — «шесть ползунков, и все уже кем-то выставлены»
def shest_osej():
    im, d = holst(2)
    pos = [0.30, 0.44, 0.78, 0.12, 0.58, 0.86]
    for i, p in enumerate(pos):
        y = 118 + i * 98
        liniya(d, (150, y), (1130, y), w=14)
        for xx in (150, 1130):
            liniya(d, (xx, y - 30), (xx, y + 30), w=14)
        cx = 150 + (1130 - 150) * p
        pryamoug(d, (cx - 30, y - 42, cx + 30, y + 42), w=15, zaliv=TUSH)
    return sohranit(im, "lek1-shest-osej")


# ОТКУДА НАСТРОЙКИ 1 — «трое взрослых, и от каждого стрелка вниз в одного»
def semya():
    im, d = holst(3)
    for i, cx in enumerate((300, 640, 980)):
        figura(d, cx, 330, 250)
        strelka(d, (cx, 360), (640 + (cx - 640) * 0.14, 470), w=14)
    figura(d, 640, 690, 210)
    return sohranit(im, "lek1-semya")


# ОТКУДА НАСТРОЙКИ 2 — «пять одинаковых домов на одной земле»
def sreda():
    im, d = holst(4)
    liniya(d, (40, 600), (1240, 600), w=18)
    for i in range(5):
        domik(d, 168 + i * 236, 600, 196, 210)
    return sohranit(im, "lek1-sreda")


# ОТКУДА НАСТРОЙКИ 3 — «каждая ступень выше, а фигура на ней та же самая»
def pokolenie():
    im, d = holst(5)
    for i in range(4):
        y = 655 - i * 128
        x0 = 70 + i * 250
        pryamoug(d, (x0, y, x0 + 300, y + 46), w=16, zaliv=TUSH)
        figura(d, x0 + 150, y, 168)
    return sohranit(im, "lek1-pokolenie")


# НАСТРОЙКИ ЗАВОДСКИЕ — «телефон звонит, а рингтон выбирали не вы»
def ringtone():
    im, d = holst(6)
    pryamoug(d, (150, 120, 520, 640), w=20)
    pryamoug(d, (192, 178, 478, 582), w=14)
    for k in range(4):
        y = 236 + k * 96
        pryamoug(d, (228, y - 22, 372, y + 22), w=11)
        pryamoug(d, (398, y - 24, 452, y + 24), w=11, zaliv=TUSH)
    for k, r in enumerate((150, 250, 350, 450)):
        krug(d, 560, 380, r, w=16 - k, ot=-52, do=52)
    return sohranit(im, "lek1-ringtone")


# ПОЧЕМУ КОЛЕЯ НЕ ЖМЁТ — «две борозды, и всё нужное стоит по их краям, близко»
def vse_ryadom():
    im, d = holst(7)
    liniya(d, (40, 260), (1240, 260), w=16)
    for x_niz, x_verh in ((300, 566), (980, 714)):
        liniya(d, (x_niz, 720), (x_verh, 260), w=22)
    #  Предметы стоят ВПЛОТНУЮ к бороздам и уменьшаются к горизонту: тянуться
    #  ни за одним не надо — в этом вся мысль раздела.
    for y in (660, 520, 410, 330):
        k = (y - 260) / 460
        for s in (-1, +1):
            gx = 640 + s * (640 - (300 + (566 - 300) * (720 - y) / 460))
            cx = gx + s * (150 * k + 40)
            w_, h_ = 118 * k + 26, 150 * k + 30
            pryamoug(d, (cx - w_ / 2, y - h_, cx + w_ / 2, y), w=int(16 * k) + 5)
    return sohranit(im, "lek1-vse-ryadom")


# ПРИЗНАК «ТАК ВСЕ» — «поле одинаковых стрелок, все в одну сторону»
def tak_vse():
    im, d = holst(8)
    for r in range(4):
        for c in range(6):
            x, y = 120 + c * 190, 140 + r * 148
            strelka(d, (x - 62, y), (x + 62, y), w=14, per=22)
    return sohranit(im, "lek1-tak-vse")


# ПРИЗНАК «ВОСКРЕСНЫЙ ВЕЧЕР» — «шесть клеток пройдено, а за седьмой стена»
def voskresnyj_vecher():
    im, d = holst(9)
    x = 60
    for i in range(5):
        pryamoug(d, (x, 300, x + 104, 430), w=15)
        lomanaya(d, [(x + 18, 366), (x + 46, 404), (x + 88, 322)], w=13)
        x += 118
    pryamoug(d, (x, 296, x + 110, 434), w=18, zaliv=TUSH)
    #  Стена занимает ТРЕТЬ кадра и идёт от края до края по высоте: неделя
    #  кончилась не следующей клеткой, а тем, во что клетки упираются.
    pryamoug(d, (x + 168, 40, 1240, 700), w=24)
    for k in range(6):
        y = 40 + (700 - 40) * (k + 1) / 7
        liniya(d, (x + 168, y), (1240, y), w=14)
    for k in range(3):
        liniya(d, (x + 168 + (1240 - x - 168) * (k + 1) / 4, 40),
               (x + 168 + (1240 - x - 168) * (k + 1) / 4, 700), w=14)
    return sohranit(im, "lek1-voskresnyj-vecher")


# ТОРО — «столбец записан рукой, и внизу подведён итог»
def spisok_toro():
    im, d = holst(10)
    pryamoug(d, (250, 60, 1030, 690), w=18)
    liniya(d, (700, 90), (700, 560), w=13)
    for k in range(6):
        y = 150 + k * 68
        shtrih_ruka(d, 300, y, 660)
        shtrih_ruka(d, 740, y, 990)
    liniya(d, (300, 590), (990, 590), w=16)
    shtrih_ruka(d, 740, 645, 990)
    return sohranit(im, "lek1-spisok-toro")


# ТОРО — «дом на два шага от воды, и больше ничего вокруг»
def hizhina():
    im, d = holst(1)
    krug(d, 1060, 150, 74, w=16)
    domik(d, 520, 520, 380, 260)
    for k in range(5):
        liniya(d, (60, 580 + k * 34), (1240, 580 + k * 34), w=13, drozh=5.0)
    return sohranit(im, "lek1-hizhina")


# ИТОГИ — «дом стоит на фундаменте, который заложил не он»
def fundament():
    im, d = holst(12)
    domik(d, 640, 470, 500, 330)
    pryamoug(d, (300, 470, 980, 640), w=18, zaliv=TUSH)
    liniya(d, (60, 640), (1240, 640), w=18)
    return sohranit(im, "lek1-fundament")


# ПРИЗНАК «ЗАВИСТЬ» — «свой дом и соседний, на одной земле, и соседний больше»
def zavist():
    #  Первая версия ставила окно и дом рядом одного размера: читались два
    #  предмета, а не сравнение. Сравнение читается только тогда, когда обе
    #  вещи ОДНОГО РОДА и стоят на ОДНОЙ линии — тогда разницу видно сразу.
    im, d = holst(13)
    liniya(d, (40, 640), (1240, 640), w=18)
    domik(d, 300, 640, 300, 210)
    domik(d, 890, 640, 540, 400)
    return sohranit(im, "lek1-zavist")


# ЧТО ДАЛЬШЕ — «от борозды отходит один след в сторону, и он свежий»
def chto_dalshe():
    #  След НЕ ПЕРЕСЕКАЕТ борозды и НЕ СХОДИТСЯ с ними внизу: и то, и другое
    #  читается не развилкой, а кучей палок (первая версия дала ровный конус).
    #  Он отходит от правой борозды ВБОК и уходит за край кадра, всё время
    #  расходясь с ней, — только расхождение и читается как «можно иначе».
    im, d = holst(14)
    liniya(d, (40, 260), (1240, 260), w=16)
    for x_niz, x_verh in ((300, 566), (980, 714)):
        liniya(d, (x_niz, 720), (x_verh, 260), w=22)
    lomanaya(d, [(830, 462), (930, 452), (1050, 430), (1160, 400), (1244, 372)],
             w=18, drozh=3.0)
    return sohranit(im, "lek1-chto-dalshe")


# ЧАВО — «облака вопросов, и все чужие»
def chavo():
    im, d = holst(15)
    for cx, cy, w_, h_ in ((260, 200, 380, 200), (860, 170, 340, 170),
                           (300, 520, 320, 180), (900, 500, 400, 220)):
        pryamoug(d, (cx - w_ / 2, cy - h_ / 2, cx + w_ / 2, cy + h_ / 2), w=17)
        lomanaya(d, [(cx - 40, cy + h_ / 2), (cx - 70, cy + h_ / 2 + 54),
                     (cx + 24, cy + h_ / 2)], w=15)
        for k in range(2):
            shtrih_ruka(d, cx - w_ / 2 + 36, cy - 20 + k * 56, cx + w_ / 2 - 36)
    return sohranit(im, "lek1-chavo")


# ЛИТЕРАТУРА — «стопка прочитанного и одна раскрытая книга»
def knigi():
    im, d = holst(16)
    y = 660
    for i, w_ in enumerate((520, 470, 500, 440)):
        h_ = 62
        pryamoug(d, (140, y - h_, 140 + w_, y), w=16)
        liniya(d, (140 + w_ * 0.10, y - h_ + 16), (140 + w_ * 0.92, y - h_ + 16), w=10)
        y -= h_ + 10
    lomanaya(d, [(700, 300), (960, 220), (1230, 300)], w=18)
    lomanaya(d, [(700, 300), (960, 250), (1230, 300)], w=13)
    lomanaya(d, [(700, 300), (700, 380), (960, 330), (1230, 380), (1230, 300)], w=18)
    for k in range(3):
        liniya(d, (760, 262 + k * 26), (930, 250 + k * 26), w=9)
        liniya(d, (1000, 250 + k * 26), (1170, 262 + k * 26), w=9)
    return sohranit(im, "lek1-knigi")


# ЧАВО — «часы: сколько это займёт»
def chasy():
    im, d = holst(17)
    krug(d, 640, 360, 290, w=24)
    krug(d, 640, 360, 254, w=12)
    for k in range(12):
        import math
        a = math.radians(k * 30 - 90)
        liniya(d, (640 + 220 * math.cos(a), 360 + 220 * math.sin(a)),
               (640 + 250 * math.cos(a), 360 + 250 * math.sin(a)),
               w=18 if k % 3 == 0 else 11)
    liniya(d, (640, 360), (640 + 130, 360 - 75), w=22)
    liniya(d, (640, 360), (640 - 40, 360 - 185), w=17)
    krug(d, 640, 360, 22, w=10, zaliv=TUSH)
    return sohranit(im, "lek1-chasy")


# ЧТО ДАЛЬШЕ — «трое идут по борозде, один стоит рядом с ней»
def shag():
    #  Следы отпали: ступня — мелкая форма, в этом стиле она читается сыпью, а
    #  не шагами, сколько её ни увеличивай. Выход из колеи показывается не
    #  следом, а ФИГУРОЙ: трое в борозде и один вне её — сравнение, которое
    #  читается мгновенно и не требует додумывания.
    im, d = holst(18)
    liniya(d, (40, 250), (1240, 250), w=16)
    for x_niz, x_verh in ((300, 566), (980, 714)):
        liniya(d, (x_niz, 720), (x_verh, 250), w=22)
    #  Фигуры в борозде НЕ ДОЛЖНЫ КАСАТЬСЯ: голова дальней, севшая на плечи
    #  ближней, собирается глазом в один столб, и трое читаются одним. Разнос
    #  по высоте больше суммы половин, плюс сдвиг вбок.
    for x, y, h in ((618, 706, 208), (658, 466, 136), (676, 344, 92)):
        figura(d, x, y, h, ww=int(13 * h / 208) + 4)
    figura(d, 1086, 700, 208)
    return sohranit(im, "lek1-shag")


# ЧАВО — «весы: одно перевешивает, и видно, какое»
def vesy():
    #  Чаши — ШИРОКИЕ и ПЛОСКИЕ. Узкая глубокая чаша с двумя подвесами читается
    #  палаткой: треугольник поверх трапеции глаз собирает в шатёр, а не в весы.
    im, d = holst(19)
    liniya(d, (640, 640), (640, 210), w=24)
    liniya(d, (450, 668), (830, 668), w=22)
    liniya(d, (250, 330), (1030, 232), w=22)
    for cx, cy, gruz in ((250, 330, True), (1030, 232, False)):
        for s in (-1, +1):
            liniya(d, (cx, cy), (cx + s * 150, cy + 118), w=10)
        lomanaya(d, [(cx - 168, cy + 118), (cx + 168, cy + 118)], w=20)
        lomanaya(d, [(cx - 168, cy + 118), (cx - 140, cy + 168),
                     (cx + 140, cy + 168), (cx + 168, cy + 118)], w=14)
        if gruz:
            pryamoug(d, (cx - 96, cy - 6, cx + 96, cy + 112), w=16, zaliv=TUSH)
    return sohranit(im, "lek1-vesy")


if __name__ == "__main__":
    kadry = [obychnaya_zhizn, shest_osej, semya, sreda, pokolenie, ringtone,
             vse_ryadom, tak_vse, voskresnyj_vecher, spisok_toro, hizhina,
             fundament, zavist, chto_dalshe, chavo, knigi, chasy, shag, vesy]
    for f in kadry:
        f()
    print(f"нарисовано {len(kadry)} кадров")
