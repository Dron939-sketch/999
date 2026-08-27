#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
risuem_anketa.py — кадры образца 1:28–3:22: анкета и заказанная схема.

ЗАЧЕМ ОТДЕЛЬНЫЙ ФАЙЛ. Это не «ещё пятнадцать иллюстраций», а другой принцип
сборки. Прежние кадры вешались на РАЗДЕЛ и висели по тридцать пять секунд;
здесь кадр меняется на КАЖДОЙ названной вещи. Лектор перечисляет шесть граф —
строки появляются по одной, ровно на своём слове: «работа» на 92.70, «график»
на 95.88, «место» на 99.69, «отдых» на 106.65, «люди» на 110.79, «темп» на
117.12. Поэтому кадры тут — не отдельные картинки, а СОСТОЯНИЯ одного бланка,
и рисуются одной функцией с параметром.

СХЕМУ ЗАКАЗАЛА САМА ЗАПИСЬ. На 174.99 звучит «взгляните на схему», и дальше
лектор её описывает: анкета из шести граф, ответы (в офисе, пять на два, город
где родился, море в августе, семья и два школьных друга, календарь забит на
месяц), «пять красных меток по умолчанию» и «только одна зелёная, выбранная».
Это не место для вольной композиции: зритель услышит перечисление и сверит его
с экраном. В прежней сборке здесь стояли шесть чёрных ползунков.

ЦВЕТ ЗДЕСЬ ЕСТЬ, И ЭТО НЕ НАРУШЕНИЕ. Правило «один цветной предмет на ролик,
не больше 3% кадра» writes про интро: там цвет — приём удержания. Тут цвет
НАЗВАН ГОЛОСОМ («пять красных», «одна зелёная»), и чёрно-белая схема прямо
противоречила бы дорожке. Красный и зелёный берутся приглушённые, чтобы не
выпасть из бумажной палитры серии.

ПОДПИСИ РИСУЮТСЯ, А НЕ ПРОСЯТСЯ У ГЕНЕРАТОРА. Кириллица у генератора приезжает
исковерканной всегда — это свойство, а не придирка. DejaVu Sans Bold рисует её
верно, и заодно снимает запрет на текст в кадре, из-за которого прежние
иллюстрации объяснялись одними формами.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risuem import BUMAGA, TUSH, W, H, holst, liniya, lomanaya, pryamoug, krug, \
    shtrih_ruka, sohranit

KRASNY = (176, 58, 46)
ZELENY = (58, 122, 72)
SHRIFT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

GRAFY = ["РАБОТА", "ГРАФИК", "МЕСТО", "ОТДЫХ", "ЛЮДИ", "ТЕМП"]
#  Ответы — ДОСЛОВНО из записи (179.8–193.08), иначе зритель сверит экран со
#  слухом и найдёт расхождение.
OTVETY = ["в офисе", "пять на два", "город, где родился",
          "море в августе", "семья и два друга", "календарь забит"]
VYBRANA = 4          # «одна зелёная, выбранная» — графа ЛЮДИ

VERH, SHAG = 108, 96
LEV, PRAV = 168, 1112
STOLB = 452          # граница подписи и ответа


def _sh(px):
    return ImageFont.truetype(SHRIFT, px)


def nadpis(d, xy, txt, px=40, fill=TUSH, centr=False):
    f = _sh(px)
    if centr:
        l, t, r, b = d.textbbox((0, 0), txt, font=f)
        xy = (xy[0] - (r - l) / 2, xy[1] - (b - t) / 2)
    d.text(xy, txt, font=f, fill=fill)


def blank(d):
    """Лист и шесть пустых строк — то, что стоит под всеми состояниями."""
    pryamoug(d, (LEV - 46, VERH - 62, PRAV + 46, VERH + SHAG * 6 + 26), w=17)
    liniya(d, (STOLB - 18, VERH - 46), (STOLB - 18, VERH + SHAG * 6 + 10), w=9)


def anketa(nomer, otkryto, otvetov=0, metki=None, imya=None):
    """Состояние бланка: `otkryto` строк заполнено подписью.

    otvetov — сколько ответов уже вписано (их называют по одному, 182–193);
    metki — 'chernye' | 'krasnye' (пять, шестая ещё пуста) | 'cvet'.
    """
    im, d = holst(nomer)
    dd = ImageDraw.Draw(im)
    blank(d)
    for i in range(6):
        y = VERH + i * SHAG
        if i >= otkryto:
            continue
        nadpis(dd, (LEV, y + 6), GRAFY[i], 42)
        liniya(d, (STOLB + 22, y + 56), (PRAV - (110 if metki else 0), y + 56), w=9)
        if i < otvetov:
            nadpis(dd, (STOLB + 30, y + 8), OTVETY[i], 38)
        if metki:
            #  «пять красных меток по умолчанию» звучит на 196.62, а «одна
            #  зелёная» — только на 199.71: три секунды на экране должно быть
            #  ровно пять меток, иначе счёт голосом расходится со счётом глазом.
            if metki == "krasnye" and i == VYBRANA:
                continue
            cvet = TUSH
            if metki == "krasnye":
                cvet = KRASNY
            elif metki == "cvet":
                cvet = ZELENY if i == VYBRANA else KRASNY
            pryamoug(d, (PRAV - 74, y + 12, PRAV - 6, y + 74), w=12, zaliv=cvet)
    return sohranit(im, imya)


def zapolnena(nomer, imya):
    """Все шесть заполнены — но рукой, штрихом: ответы ещё не названы."""
    im, d = holst(nomer)
    dd = ImageDraw.Draw(im)
    blank(d)
    for i in range(6):
        y = VERH + i * SHAG
        nadpis(dd, (LEV, y + 6), GRAFY[i], 42)
        shtrih_ruka(d, STOLB + 40, y + 52, PRAV - 30)
    return sohranit(im, imya)


def dve_iz_desyati(imya):
    """«две-три графы из десятка» — счёт, который зритель проверяет глазом."""
    im, d = holst(31)
    dd = ImageDraw.Draw(im)
    for i in range(10):
        x = 150 + (i % 5) * 200
        y = 210 + (i // 5) * 240
        pryamoug(d, (x, y, x + 150, y + 150), w=16,
                 zaliv=TUSH if i >= 2 else None)
        if i < 2:
            lomanaya(d, [(x + 28, y + 82), (x + 62, y + 124), (x + 122, y + 30)], w=15)
    return sohranit(im, imya)


def telefon(imya):
    """«как в новом телефоне, где рингтон, обои и язык уже выбраны»."""
    im, d = holst(32)
    dd = ImageDraw.Draw(im)
    pryamoug(d, (356, 60, 924, 690), w=22)
    pryamoug(d, (400, 122, 880, 630), w=13)
    for k, s in enumerate(("рингтон", "обои", "язык")):
        y = 220 + k * 140
        nadpis(dd, (440, y - 32), s, 40)
        pryamoug(d, (764, y - 30, 848, y + 26), w=11, zaliv=TUSH)
    return sohranit(im, imya)


if __name__ == "__main__":
    #  Бланк наполняется по одной строке — по слову лектора.
    anketa(20, 0, imya="lek1a-anketa-0")
    for k in range(1, 7):
        anketa(20 + k, k, imya=f"lek1a-anketa-{k}")
    zapolnena(28, "lek1a-anketa-zapolnena")
    dve_iz_desyati("lek1a-dve-iz-desyati")
    telefon("lek1a-telefon")
    #  Схема, заказанная голосом: ответы, потом метки, потом цвет.
    for k in range(7):
        anketa(40 + k, 6, otvetov=k, imya=f"lek1a-shema-{k}")
    anketa(50, 6, otvetov=6, metki="chernye", imya="lek1a-shema-metki")
    anketa(51, 6, otvetov=6, metki="krasnye", imya="lek1a-shema-krasnye")
    anketa(52, 6, otvetov=6, metki="cvet", imya="lek1a-shema-cvet")
    print("нарисовано состояний: 20")
