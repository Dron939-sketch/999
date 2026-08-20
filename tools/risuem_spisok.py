#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
risuem_spisok.py — кадры-перечисления: заголовок и пункты, встающие по одному.

ЗАЧЕМ. Лекция то и дело считает вслух: три автора настроек, три механизма
маскировки, три признака чужой колеи, пять осей курса, два обещания, четыре
вопроса ЧаВо, шесть вопросов для самопроверки, две книги. Каждый раз это
перечисление, растянутое на двадцать-сорок секунд, и каждый раз зритель должен
видеть на экране РОВНО СТОЛЬКО пунктов, сколько уже названо. Показать сразу все
— значит отдать конец списка раньше голоса; показать один неподвижный кадр на
всё перечисление — то, за что первую сборку и забраковали.

ЧЕРЕДОВАНИЕ ОБЯЗАТЕЛЬНО. Если каждое перечисление рисовать списком, лекция
превратится в презентацию, а это своя бедность. Правило: СПИСОК на заголовке
перечисления — зритель видит рамку разговора; дальше на каждый пункт своя
КАРТИНКА; список возвращается, когда пункт закрыт. Так держится и счёт, и
образность.

ПОДПИСИ РИСУЮТСЯ ЗАВОДОМ. Кириллица у генератора приезжает исковерканной; DejaVu
Sans Bold рисует её верно, и запрет на текст в кадре, стоявший из-за генератора,
здесь не действует.
"""

import sys
from pathlib import Path

from PIL import ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risuem import TUSH, W, H, holst, liniya, lomanaya, pryamoug, krug, sohranit
from risuem_anketa import KRASNY, ZELENY, nadpis, _sh

LEV = 150


def _perenos(d, txt, px, shirina):
    """Разбивка длинной строки: пункты ЧаВо в одну строку не влезают."""
    f = _sh(px)
    stroki, cur = [], ""
    for s in txt.split():
        proba = (cur + " " + s).strip()
        if d.textlength(proba, font=f) > shirina and cur:
            stroki.append(cur)
            cur = s
        else:
            cur = proba
    if cur:
        stroki.append(cur)
    return stroki


def spisok(nomer, zagolovok, punkty, otkryto, imya, nomerki=True, px=48):
    """Заголовок и `otkryto` пунктов.

    Названный последним стоит СПЛОШНОЙ меткой, прежние — контурной с номером:
    глаз сразу находит, о чём речь сейчас, не перечитывая список.
    """
    im, d = holst(nomer)
    dd = ImageDraw.Draw(im)
    nadpis(dd, (LEV, 52), zagolovok, 56)
    liniya(d, (LEV, 130), (W - LEV + 40, 130), w=13)

    y = 196
    for i, p in enumerate(punkty):
        if i >= otkryto:
            break
        posl = (i == otkryto - 1)
        if nomerki:
            pryamoug(d, (LEV, y + 4, LEV + 44, y + 48), w=11,
                     zaliv=TUSH if posl else None)
            if not posl:
                nadpis(dd, (LEV + 13, y + 4), str(i + 1), 34)
        for k, st in enumerate(_perenos(dd, p, px, W - LEV - 250)):
            nadpis(dd, (LEV + 74, y + k * (px + 8)), st, px)
        y += max(1, len(_perenos(dd, p, px, W - LEV - 250))) * (px + 8) + 24
    return sohranit(im, imya)


def schet(nomer, vsego, otmecheno, imya, podpis=None, cvet=None):
    """Ряд клеток: сколько из скольких. Счёт, который зритель проверяет глазом."""
    im, d = holst(nomer)
    dd = ImageDraw.Draw(im)
    ryad = min(vsego, 13)
    shag = (W - 300) // ryad
    bok = min(shag - 14, 118)
    ryadov = (vsego + ryad - 1) // ryad
    y0 = 300 - (ryadov - 1) * (bok + 20) // 2
    for i in range(vsego):
        x = 150 + (i % ryad) * shag
        y = y0 + (i // ryad) * (bok + 20)
        zal = None
        if i < otmecheno:
            zal = cvet or TUSH
        pryamoug(d, (x, y, x + bok, y + bok), w=12, zaliv=zal)
    if podpis:
        nadpis(dd, (W / 2, 560), podpis, 60, centr=True)
    return sohranit(im, imya)


def vopros(nomer, txt, imya, px=62):
    """Один вопрос крупно — под ЧаВо и вопросы для самопроверки."""
    im, d = holst(nomer)
    dd = ImageDraw.Draw(im)
    stroki = _perenos(dd, txt, px, W - 280)
    vys = len(stroki) * (px + 16)
    y = (H - vys) / 2
    for k, st in enumerate(stroki):
        nadpis(dd, (W / 2, y + k * (px + 16)), st, px, centr=True)
    liniya(d, (LEV, y - 48), (W - LEV, y - 48), w=11)
    liniya(d, (LEV, y + vys + 28), (W - LEV, y + vys + 28), w=11)
    return sohranit(im, imya)


def kniga(nomer, avtor, nazvanie, god, imya):
    """Книга: корешок, автор, название, год."""
    im, d = holst(nomer)
    dd = ImageDraw.Draw(im)
    pryamoug(d, (150, 170, 470, 620), w=20)
    for k in range(3):
        liniya(d, (188, 216 + k * 26), (432, 216 + k * 26), w=9)
    nadpis(dd, (540, 206), avtor, 44)
    for k, st in enumerate(_perenos(dd, nazvanie, 54, 580)):
        nadpis(dd, (540, 286 + k * 64), st, 54)
    nadpis(dd, (540, 470), god, 70)
    return sohranit(im, imya)
