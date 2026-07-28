#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
title_card.py — титры-карточки в стиле Фримена: жирный белый текст на чёрном.

У эталона каждая серия прошита карточками («ИНОЙ», «9 ОКТЯБРЯ», URL) —
резкий белый гротеск на чёрном, лёгкое дрожание ink-фильтра.

Использование:
    python3 tools/title_card.py "ПЕРЕПРОШИВКА" -o examples/assets/sets/card-title.svg
    python3 tools/title_card.py "ЛЕКЦИЯ 1" --sub "Ты никогда не начинался с чистого листа" \
        -o examples/assets/sets/card-l1.svg
"""

import argparse


def make_card(text, sub=None, w=1280, h=720):
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        '<defs><filter id="ink" x="-10%" y="-10%" width="120%" height="120%">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="1" seed="9" result="n"/>'
        '<feDisplacementMap in="SourceGraphic" in2="n" scale="3" xChannelSelector="R" yChannelSelector="G"/>'
        "</filter></defs>",
        f'<rect width="{w}" height="{h}" fill="#0b0b0b"/>',
        '<g filter="url(#ink)">',
    ]
    # основной текст: крупный жирный гротеск, вписываем по ширине
    size = min(140, int(w * 1.55 / max(1, len(text))))
    y = h // 2 + (0 if sub else size // 3)
    lines.append(
        f'<text x="{w//2}" y="{y}" text-anchor="middle" '
        f'font-family="Arial Black, Arial, sans-serif" font-weight="900" '
        f'font-size="{size}" fill="#e8ebe6" letter-spacing="6">{text}</text>'
    )
    if sub:
        ssize = max(26, size // 4)
        lines.append(
            f'<text x="{w//2}" y="{y + size//2 + 30}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-weight="400" font-style="italic" '
            f'font-size="{ssize}" fill="#9aa096">{sub}</text>'
        )
    lines.append("</g></svg>")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Титр-карточка в стиле Фримена")
    ap.add_argument("text")
    ap.add_argument("--sub", help="подзаголовок (мельче, курсив)")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    with open(a.output, "w", encoding="utf-8") as f:
        f.write(make_card(a.text, a.sub))
    print(f"OK: {a.output}")


if __name__ == "__main__":
    main()
