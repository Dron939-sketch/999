#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thumb.py — ОБЛОЖКА РОЛИКА: пластина от генератора + надпись шрифтом.

ПОЧЕМУ ТЕКСТ НЕ РИСУЕТ ГЕНЕРАТОР. Кириллицу он пишет мусором: начертания
похожи на русские буквы, слова нечитаемы. На фоне это простительно, на
обложке — нет, потому что обложка И ЕСТЬ текст. Поэтому генератор отдаёт
только пластину (сюжет справа, пустое тёмное поле слева), а надпись ставится
здесь, настоящим шрифтом.

ЧТО ДЕЛАЕТ ИНСТРУМЕНТ:

  · ПРИВОДИТ К 16:9. Генератор регулярно отдаёт квадрат, сколько его ни проси
    про landscape. Полоса берётся не вслепую по центру: сначала ищется
    СВЕТЛОЕ ПЯТНО — на тёмной пластине это и есть сюжет, — и окно 16:9
    ставится так, чтобы пятно уцелело целиком, а если не помещается — по его
    центру тяжести. Слепой центральный кроп срезал персонажу голову.

  · СТАВИТ СКРИМ ПОД ТЕКСТ. Слева кладётся горизонтальный градиент в чёрное.
    Даже когда пластина в текстовой зоне окажется светлее задуманного, белые
    буквы держатся. Без скрима обложка зависит от везения генератора.

  · НАБИРАЕТ НАДПИСЬ. Кегль подбирается САМ: строка растягивается до тех пор,
    пока влезает в текстовую колонку. Ручной кегль всегда либо мелкий, либо
    вылезает за поле — оба раза это видно только на готовом файле.

  · ПРОВЕРЯЕТ ЧИТАЕМОСТЬ И ВАЛИТ ПРОГОН. Три мерки, каждая на своём отказе:
      — высота прописной ведущей строки ≥ 1/9 высоты кадра. В ленте обложка
        ужимается до ~320 px, и всё, что мельче, превращается в серую кашу;
      — фон под текстом темнее 90 из 255 по среднему. Белый по светлому не
        читается, а заметно это только на телефоне;
      — текст не залезает в правый нижний угол: там ютуб рисует хронометраж.

ПОЧЕМУ ЭТО ГЕЙТ, А НЕ СОВЕТ. Обложку смотрят один раз, размером с ноготь, и
проверить «читается ли» глазами на большом экране нельзя — на большом читается
всё. Мерка снимается в тех же условиях, в каких обложку увидит зритель.

Использование:
    python3 tools/thumb.py пластина.png обложка.png \\
        --line "ВЫ НЕ" --line "ВЛЮБЛЯЕТЕСЬ." --line "ВЫ УЗНАЁТЕ:red"
    python3 tools/thumb.py ... --check-only    # только мерки, ничего не пишет

Строка с суффиксом `:red` набирается акцентным цветом, `:plate` — белым по
красной плашке. Без суффикса — белым.
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np
except ImportError:
    sys.exit("нужны Pillow и numpy")

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "tools" / "fonts" / "Montserrat.ttf"

W, H = 1280, 720
TEXT_COL = 0.40          # доля ширины под текстовую колонку
MARGIN = 46              # поле от края кадра до букв
GAP = 0.10               # межстрочный интервал в долях кегля
ACCENT = (224, 32, 32)
WHITE = (245, 245, 242)

CAP_MIN = H / 9.0        # прописная ведущей строки, ниже — не читается в ленте
BG_MAX = 90              # средняя яркость фона под текстом, выше — белое тонет
TIMECODE = (0.86, 0.88)  # левый верхний угол плашки хронометража ютуба


def subject_box(im):
    """Где на пластине сюжет. Светлое пятно на тёмном фоне — это он."""
    a = np.asarray(im.convert("L"), np.float32)
    thr = max(a.mean() + 2.2 * a.std(), 120.0)
    ys, xs = np.nonzero(a > thr)
    if not len(ys):                       # пластина ровная — сюжета не видно
        h, w = a.shape
        return 0, 0, w, h
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def to_169(im):
    """Полоса 16:9, поставленная так, чтобы сюжет уцелел."""
    w, h = im.size
    if abs(w / h - 16 / 9) < 0.01:
        return im
    x0, y0, x1, y1 = subject_box(im)
    if w / h < 16 / 9:                    # кадр слишком высокий — режем по высоте
        th = int(w * 9 / 16)
        top = min(max(0, (y0 + y1) // 2 - th // 2), h - th)
        # сюжет важнее центровки: если он влезает целиком — сдвигаем окно к нему
        if y1 - y0 <= th:
            top = min(max(y0, 0), min(y1 - th, h - th)) if y1 - th > 0 else 0
            top = max(0, min(top, h - th))
        return im.crop((0, top, w, top + th))
    tw = int(h * 16 / 9)                  # кадр слишком широкий — режем по ширине
    left = min(max(0, (x0 + x1) // 2 - tw // 2), w - tw)
    return im.crop((left, 0, left + tw, h))


def scrim(im, rect, target=BG_MAX - 20):
    """Градиент в чёрное слева, ГЛУБИНА ПОДБИРАЕТСЯ ПОД ПЛАСТИНУ.

    Фиксированная непрозрачность работает ровно до первой светлой пластины: на
    тёмной она лишняя, на светлой её не хватает, и белые буквы тонут. Поэтому
    глубина считается из замера — какая средняя яркость под текстом сейчас и
    какая нужна. Скрим существует не ради красоты, а ради гарантии.
    """
    x0, y0, x1, y1 = rect
    a = np.asarray(im.convert("L"), np.float32)
    now = a[y0:y1, x0:x1].mean()
    need = 0.0 if now <= target else 1.0 - target / now
    depth = min(0.97, max(0.50, need))
    # ПЛОСКО ПОД ТЕКСТОМ, растушёвка — только за ним. Чистый градиент от края
    # кадра эту работу не делает: к правому краю блока он почти сходит на нет,
    # и последние буквы каждой строки остаются на светлом. Так и обожглись.
    hold = min(W - 1, x1 + int(W * 0.02))
    feather = int(W * 0.20)
    g = np.zeros((H, W), np.float32)
    g[:, :hold] = depth
    # Спад — S-образной кривой, а не прямой. У прямой на стыке с плоской частью
    # ломается производная, и глаз читает этот излом как вертикальную границу:
    # получается не свет, а приклеенная тёмная плашка. У smoothstep наклон на
    # обоих концах нулевой, и переход не виден.
    t = np.linspace(0.0, 1.0, feather)
    tail = depth * (1.0 - t * t * (3.0 - 2.0 * t))
    g[:, hold:hold + feather] = tail[:max(0, W - hold)]
    mask = Image.fromarray((g * 255).astype(np.uint8), "L")
    return Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, mask)


def fit(text, box_w, cap_target):
    """Кегль, при котором строка занимает колонку целиком, но не вылезает."""
    lo, hi = 10, 400
    while lo < hi:
        mid = (lo + hi + 1) // 2
        f = ImageFont.truetype(str(FONT), mid)
        f.set_variation_by_name("ExtraBold")
        if f.getbbox(text)[2] <= box_w:
            lo = mid
        else:
            hi = mid - 1
    f = ImageFont.truetype(str(FONT), min(lo, int(cap_target)))
    f.set_variation_by_name("ExtraBold")
    return f


def layout(lines, col):
    """Кегль и место блока — БЕЗ рисования: скриму нужен прямоугольник заранее."""
    box_w = int(W * col) - MARGIN
    # Ведущая строка задаёт кегль всему блоку: разнокалиберные строки в такой
    # вёрстке читаются как ошибка, а не как акцент. Акцент — цветом.
    lead = max(lines, key=lambda l: f_width(l[0]))[0]
    f = fit(lead, box_w, H * 0.34)
    step = int(f.size * (1 + GAP))
    total = step * len(lines)
    y = (H - total) // 2
    wide = max(f.getbbox(t)[2] for t, _ in lines)
    return f, step, y, [MARGIN, y, MARGIN + wide, y + total]


def f_width(text):
    """Ширина строки в единицах кегля — по ней ищется самая длинная."""
    f = ImageFont.truetype(str(FONT), 100)
    f.set_variation_by_name("ExtraBold")
    return f.getbbox(text)[2]


def draw(im, lines, f, step, y):
    d = ImageDraw.Draw(im)
    stroke = max(4, f.size // 14)

    for text, kind in lines:
        x = MARGIN
        bb = f.getbbox(text)
        if kind == "plate":
            pad = int(f.size * 0.13)
            d.rectangle((x - pad, y + bb[1] - pad, x + bb[2] + pad, y + bb[3] + pad),
                        fill=ACCENT)
            d.text((x, y), text, font=f, fill=WHITE)
        else:
            d.text((x, y), text, font=f, fill=ACCENT if kind == "red" else WHITE,
                   stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += step


def gates(bg, font, used, lead):
    """Мерки в тех же условиях, в каких обложку увидит зритель.

    Фон меряется ДО того, как лягут буквы. Если мерить готовую обложку, белые
    литеры сами задирают среднее, и проверка «фон достаточно тёмный» начинает
    подтверждаться тем самым текстом, который она должна защищать.
    """
    bad = []
    cap = font.getbbox("В")[3] - font.getbbox("В")[1]
    print(f"    прописная ведущей строки {cap} px (нужно ≥ {CAP_MIN:.0f})")
    if cap < CAP_MIN:
        # Кегль здесь — следствие, а не причина: он зажат длиной самой длинной
        # строки. Поэтому в отказе стоит НЕ «увеличь кегль» (некуда), а сколько
        # знаков реально влезает. Русские слова длинные, и это главная разница
        # с английскими обложками, у которых копирайт короче вдвое.
        fits = int(len(lead) * cap / CAP_MIN)
        bad.append(f"кегль мал: {cap} px против {CAP_MIN:.0f}. Длинная строка "
                   f"«{lead}» — {len(lead)} знаков, влезает {fits}. Резать текст, "
                   f"а не тянуть колонку")

    x0, y0, x1, y1 = used
    a = np.asarray(bg.convert("L"), np.float32)[y0:y1, x0:x1]
    print(f"    фон под текстом {a.mean():.0f} из 255 (нужно ≤ {BG_MAX})")
    if a.mean() > BG_MAX:
        bad.append(f"фон под текстом светлый ({a.mean():.0f}) — белое утонет")

    if x1 > W * TIMECODE[0] and y1 > H * TIMECODE[1]:
        bad.append("текст заходит в правый нижний угол — там хронометраж ютуба")
    return bad


def parse(spec):
    for suffix, kind in ((":red", "red"), (":plate", "plate")):
        if spec.endswith(suffix):
            return spec[:-len(suffix)], kind
    return spec, "white"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("plate")
    ap.add_argument("dst")
    ap.add_argument("--line", action="append", default=[],
                    help="строка надписи; суффикс :red или :plate даёт акцент")
    ap.add_argument("--col", type=float, default=TEXT_COL,
                    help="доля ширины кадра под текстовую колонку")
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args(argv)
    if not a.line:
        sys.exit("нечего писать: нужен хотя бы один --line")
    if not FONT.exists():
        sys.exit(f"нет шрифта {FONT}")

    src = Image.open(a.plate).convert("RGB")
    print(f"  пластина {src.size[0]}×{src.size[1]}")
    im = to_169(src).resize((W, H), Image.LANCZOS)
    lines = [parse(s) for s in a.line]
    font, step, y, used = layout(lines, a.col)
    im = scrim(im, used)
    bg = im.copy()                 # фон под текстом — до букв, не после
    draw(im, lines, font, step, y)

    print("  ЧИТАЕМОСТЬ")
    bad = gates(bg, font, used, max((t for t, _ in lines), key=f_width))
    if bad:
        for b in bad:
            print(f"    [ПЛОХО] {b}")
        return 1
    print("    [OK] обложка читается в ленте")

    if not a.check_only:
        Image.open(a.plate)  # держим исходник нетронутым
        im.save(a.dst, optimize=True)
        small = im.resize((320, 180), Image.LANCZOS)
        small.save(Path(a.dst).with_suffix(".lenta.png"))
        print(f"  {a.dst} — и рядом .lenta.png, как это видно в ленте")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
