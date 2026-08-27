#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
risuem_perehod.py — локации ролика 27 «Тысяча часов», интро к курсу «Переход».

ЛОКАЦИЯ РИСУЕТСЯ ПОД ЗРИТЕЛЯ, А НЕ ПОДБИРАЕТСЯ. Взять похожую из имеющихся —
это и есть «вообще комната», и разрыву не от чего отталкиваться.

ЗРИТЕЛЬ: тридцать–сорок пять, зарплата средняя или выше, кредит, пяток подписок,
работа по найму. Деньги есть; ощущение, что распоряжается ими кто-то другой,
тоже есть, но названия у него нет.

УЗНАЁТСЯ НЕ МЕСТО, А ПОЛОЖЕНИЕ. Документальный кадр («магазин», «касса») даёт
«да, это магазин» — и на этом кончается: место опознано, дальше оно фон. Здесь в
кадре ПОЛОЖЕНИЕ: на каждом крючке висит цена, а взять нечего. Зритель узнаёт
себя, а не помещение, и тезис курса стоит в кадре до первого слова.

ЦЕННИК БЕЗ ТОВАРА — ВТОРОЙ СЛОЙ РАЗРЫВА. Ценник существует только при товаре;
глаз ищет товар, не находит и не отпускает. Предмет проходит через все локации,
его никто не трогает и ни разу не называет словом — назвать значит объяснить
якорь. Лампа как предмет разрыва здесь не используется сознательно: горящая при
дневном свете настольная лампа была разрывом ролика 23, и повтор превратил бы
приём в примету серии.

МЕРА ЧЕЛОВЕКА. Для говорящей сцены локация годится при мере 0.5 и выше
(реестр §XL). Пол объявляется в `<сет>.surfaces.json` рядом с картинкой.
"""

import json
import sys
from pathlib import Path

from PIL import ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risuem import TUSH, BUMAGA, W, H, holst, liniya, lomanaya, pryamoug, krug, \
    shtrih_ruka, sohranit
from risuem_anketa import nadpis


def cennik(d, dd, cx, cy, sh=96, vys=64, cena="—", ww=11):
    """Ценник на крючке: карточка, дырка, крючок. Товара под ним нет."""
    liniya(d, (cx, cy - vys / 2 - 46), (cx, cy - vys / 2), w=6)
    krug(d, cx, cy - vys / 2 - 50, 13, w=6)
    pryamoug(d, (cx - sh / 2, cy - vys / 2, cx + sh / 2, cy + vys / 2), w=ww)
    krug(d, cx, cy - vys / 2 + 15, 6, w=5)
    nadpis(dd, (cx, cy + 6), cena, int(vys * 0.42), centr=True)


def polka_bez_tovara():
    """ПЕРВАЯ ЛОКАЦИЯ. На каждом месте висит цена, а взять нечего."""
    im, d = holst(300)
    dd = ImageDraw.Draw(im)
    #  Три полки уходят вглубь: чем дальше, тем короче — глубина без перспективы
    #  в линиях, только масштабом, чтобы кадр остался плоским, как в серии.
    for k, (y, x0, x1, ww) in enumerate(((250, 60, 1220, 16),
                                         (410, 30, 1250, 18))):
        liniya(d, (x0, y), (x1, y), w=ww)
        liniya(d, (x0, y + 14), (x1, y + 14), w=7)
    #  Ценники: восемь штук, все с ценой, все ни на чём.
    for i, cena in enumerate(("799", "1 290", "349", "2 400", "590")):
        cennik(d, dd, 150 + i * 236, 176, cena=cena)
    for i, cena in enumerate(("1 190", "450", "3 100")):
        cennik(d, dd, 250 + i * 372, 336, cena=cena)
    #  Пол — под ноги персонажу.
    liniya(d, (0, 690), (1280, 690), w=18)
    return sohranit(im, "polka-bez-tovara")


def kuhnya_schet():
    """ВТОРАЯ ЛОКАЦИЯ. Стол, на нём лента распечатки; ценник висит и здесь."""
    im, d = holst(301)
    dd = ImageDraw.Draw(im)
    pryamoug(d, (150, 380, 1130, 430), w=18)          # столешница
    for x in (230, 1050):
        liniya(d, (x, 430), (x, 690), w=16)
    #  Лента распечатки свисает со стола: считали, но не он.
    lomanaya(d, [(560, 380), (566, 300), (548, 236), (572, 180)], w=14)
    for k in range(6):
        shtrih_ruka(d, 500, 214 + k * 30, 640)
    cennik(d, dd, 950, 210, cena="₽")
    liniya(d, (0, 690), (1280, 690), w=18)
    return sohranit(im, "kuhnya-schet")


def podezd_pochta():
    """ТРЕТЬЯ ЛОКАЦИЯ. Ряд почтовых ящиков; из каждого торчит бумага."""
    im, d = holst(302)
    dd = ImageDraw.Draw(im)
    for r in range(2):
        for c in range(5):
            x, y = 180 + c * 190, 200 + r * 190
            pryamoug(d, (x, y, x + 150, y + 150), w=14)
            liniya(d, (x + 26, y + 108), (x + 124, y + 108), w=9)
            #  бумага, которую никто не вынимал
            lomanaya(d, [(x + 40, y + 100), (x + 34, y + 40), (x + 96, y + 26)], w=10)
    cennik(d, dd, 1130, 250, cena="—")
    liniya(d, (0, 690), (1280, 690), w=18)
    return sohranit(im, "podezd-pochta")


def cennik_krupno():
    """ЧЕТВЁРТАЯ. Ценник крупным планом — под возврат якоря и финальный кадр."""
    im, d = holst(303)
    dd = ImageDraw.Draw(im)
    cennik(d, dd, 640, 380, sh=520, vys=330, cena="1000", ww=22)
    liniya(d, (0, 690), (1280, 690), w=18)
    return sohranit(im, "cennik-krupno")


def mera(imya, chelovek=0.55, back_y=0.50, front_y=0.96):
    """Мера человека и пол — без них локация не годится для говорящей сцены."""
    p = Path(f"examples/assets/sets/{imya}.surfaces.json")
    p.write_text(json.dumps({
        "floor": {"back_y": back_y, "front_y": front_y},
        "chelovek": chelovek,
        "_comment": ("Мера человека — доля высоты кадра, которую занимает фигура "
                     "у передней кромки пола. Ниже 0.5 локация для говорящей "
                     "сцены не годится (реестр §XL): фигура становится мелкой, "
                     "и мимика перестаёт читаться.")
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    polka_bez_tovara(); mera("polka-bez-tovara")
    kuhnya_schet();     mera("kuhnya-schet")
    podezd_pochta();    mera("podezd-pochta")
    cennik_krupno();    mera("cennik-krupno", chelovek=0.52)
    print("нарисовано локаций: 4")
