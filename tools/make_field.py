#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_field.py — цех локаций: генератор «поля» (небо + горизонт + земля).

Зачем. Замер `tools/scene_ref.py` по 51 кадру оригинала против наших:

    признак                оригинал   наш
    горизонт                   78%      7%
    фактура земли              57%     15%
    заполненность чернилами   0.62     0.14

То есть наши кадры вчетверо пустее и почти всегда без земли: персонаж висит
в молоке. Рисовать под каждую сцену полный SVG-сет дорого, а «поле» нужно
почти всем — поэтому оно генерится параметрами.

(Проверено отдельно и НЕ вошло в список нехватки: вертикальный перепад
яркости неба у нас уже есть — его даёт виньетка рендера, 35.4 против 35.0
у оригинала. Гипотеза «нет градиента неба» замером не подтвердилась.)

Стиль — по `examples/assets/sets/LOCATION_STYLE.md`: плоские заливки, жирная
тушь, никаких градиентов в самом SVG. Глубину даёт не растяжка тона, а
СГУЩЕНИЕ штриха к горизонту (перспектива) — так у оригинала.

Использование:
    python3 tools/make_field.py --out examples/assets/sets/field-night.svg
    python3 tools/make_field.py --out ... --horizon 0.62 --sky "#5f625b" \
        --ground "#b0b3ab" --hatch 260 --seed 7
"""

import argparse
import math
import sys


def rng(seed):
    """Простой детерминированный генератор: голдены должны воспроизводиться."""
    state = seed & 0xFFFFFFFF

    def nxt():
        nonlocal state
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        return state / 0xFFFFFFFF
    return nxt


def build(w, h, horizon, sky, ground, ink, hatch, seed, emblem):
    hy = h * horizon
    r = rng(seed)
    parts = []

    parts.append(f'<rect width="{w}" height="{h}" fill="{sky}"/>')
    parts.append(f'<rect y="{hy:.0f}" width="{w}" height="{h - hy:.0f}" fill="{ground}"/>')

    if emblem:
        # знак на полу: у оригинала под ногами бывает гигантский символ.
        # Кладём ПОД штриховку и почти в тон земли — читается, но не спорит
        # с персонажем.
        cx, cy = w * 0.5, hy + (h - hy) * 0.62
        rx, ry = w * 0.30, (h - hy) * 0.42
        parts.append(f'<g opacity="0.30" fill="none" stroke="{ink}" stroke-width="5">')
        parts.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{ry:.0f}"/>')
        parts.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx*0.62:.0f}" ry="{ry*0.62:.0f}"/>')
        for i in range(12):
            a = i * math.pi / 6
            parts.append(f'<line x1="{cx + math.cos(a)*rx*0.62:.0f}" '
                         f'y1="{cy + math.sin(a)*ry*0.62:.0f}" '
                         f'x2="{cx + math.cos(a)*rx:.0f}" '
                         f'y2="{cy + math.sin(a)*ry:.0f}"/>')
        parts.append('</g>')

    # ── штриховка-ПАУТИНА: три семейства наклонов, которые РЕАЛЬНО пересекаются.
    # Один разброс углов вокруг горизонтали давал рябь «как вода» — у оригинала
    # штрих идёт крест-накрест. Штрих сгущается и укорачивается к горизонту:
    # перспективу держит плотность, а не растяжка тона.
    parts.append(f'<g stroke="{ink}" stroke-linecap="round" opacity="0.30">')
    families = (-0.62, 0.10, 0.74)
    for i in range(hatch):
        t = r() ** 0.55                  # 0 у горизонта, 1 у нижнего края
        y = hy + (h - hy) * t
        length = w * (0.05 + 0.24 * t)
        x = r() * (w + length) - length * 0.5
        ang = families[i % 3] + (r() - 0.5) * 0.34
        # сплющиваем по вертикали — земля лежит, а не стоит стеной
        dx, dy = math.cos(ang) * length, math.sin(ang) * length * 0.34
        sw = 0.8 + 2.4 * t
        parts.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{x+dx:.0f}" '
                     f'y2="{y+dy:.0f}" stroke-width="{sw:.1f}"/>')
    parts.append('</g>')

    # ── горизонт: рукотворная линия, слегка гуляющая по высоте
    pts, x = [], 0.0
    while x <= w:
        pts.append(f'{x:.0f} {hy + (r() - 0.5) * 5:.1f}')
        x += w / 26
    parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{ink}" '
                 f'stroke-width="5.5" stroke-linejoin="round" stroke-linecap="round"/>')

    body = "\n    ".join(parts)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <filter id="ink" x="-6%" y="-6%" width="112%" height="112%">
      <feTurbulence type="fractalNoise" baseFrequency="0.011" numOctaves="2" seed="{seed}" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="2.6" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
  </defs>
  <!-- ПОЛЕ, собрано tools/make_field.py (горизонт {horizon}, штрихов {hatch}, seed {seed}).
       Плоские заливки без градиентов (LOCATION_STYLE.md): вертикальный перепад
       яркости даёт виньетка рендера — замерено, 35.4 против 35.0 у оригинала.
       Глубину держит СГУЩЕНИЕ штриха к горизонту, а не растяжка тона. -->
  <g filter="url(#ink)">
    {body}
  </g>
</svg>
'''


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--horizon", type=float, default=0.66,
                    help="высота линии земли, доля кадра сверху")
    ap.add_argument("--sky", default="#5f625b")
    ap.add_argument("--ground", default="#b0b3ab")
    ap.add_argument("--ink", default="#141410")
    ap.add_argument("--hatch", type=int, default=260, help="число штрихов на земле")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--emblem", action="store_true", help="знак на полу")
    a = ap.parse_args(argv)

    svg = build(a.width, a.height, a.horizon, a.sky, a.ground, a.ink,
                a.hatch, a.seed, a.emblem)
    with open(a.out, "w") as f:
        f.write(svg)
    print(f"поле записано: {a.out}  ({len(svg)} байт, штрихов {a.hatch})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
