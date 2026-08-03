#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
katalog.py — КАТАЛОГ ЛОКАЦИЙ: превью, линия пола, где уже стоит.

ЗАЧЕМ. Локаций в серии сорок, и половина из них не видна по имени файла:
`dve-tropy`, `field-empty`, `wasteland` — что там на картинке, знает только тот,
кто её делал. Из-за этого дважды брали чужой фон вместо своего и один раз
искали «что-нибудь про горизонт», хотя подходящее уже лежало в репозитории.

ПОЧЕМУ ПРЕВЬЮ, А НЕ КОПИИ. Студия просила «скопировать все локации в отдельную
папку». Копия — это второй файл, который начинает жить своей жизнью: поправишь
оригинал, а в копии останется старое, и однажды ролик соберётся не с той
картинкой. Каталог показывает, ЧТО у нас есть, и не создаёт второй правды:
сами локации остаются на своём месте, в `examples/assets/sets/`.

ЧТО ДЕЛАЕТ. Рендерит по одному пустому кадру на каждую локацию (без персонажа),
складывает превью в `sets/katalog/` и пишет `sets/KATALOG.md`: имя файла,
картинка, линия пола из карты поверхностей и список роликов, где локация уже
стоит. Прочерк в колонке пола означает, что карты нет и `place ... on floor`
молча не сработает.

Использование:
    python3 tools/katalog.py
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SETS = Path("examples/assets/sets")
ANIMS = "examples/lektorij/*.anim"


def main():
    engine = shutil.which("animdsl") or "target/release/animdsl"
    if not (shutil.which("animdsl") or Path(engine).exists()):
        print("animdsl не найден: cargo build --release", file=sys.stderr)
        return 1
    try:
        from PIL import Image
    except ImportError:
        print("нужен pillow", file=sys.stderr)
        return 1

    names = [os.path.basename(p)[:-4] for p in sorted(glob.glob(str(SETS / "*.svg")))]
    if not names:
        print("локаций не нашёл", file=sys.stderr)
        return 1

    lines = ["config { width: 1280 height: 720 fps: 4 background: #b0b3ab "
             "monochrome: true mono-contrast: 2.2 }"]
    for i, n in enumerate(names):
        lines.append(f'import set s{i} from "{(SETS / (n + ".svg")).resolve()}"')
    for i, n in enumerate(names):
        lines.append(f'scene "s{i}" (duration: 0.5s, set: s{i}) {{ wait 0.5s }}')

    out_dir = SETS / "katalog"
    out_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        probe = os.path.join(td, "katalog.anim")
        Path(probe).write_text("\n".join(lines) + "\n", encoding="utf-8")
        pngs = os.path.join(td, "png")
        os.makedirs(pngs)
        r = subprocess.run([engine, "render", probe, "--png-dir", pngs],
                           capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-1200:], file=sys.stderr)
            return 1
        frames = sorted(glob.glob(os.path.join(pngs, "frame_*.png")))
        per = max(1, len(frames) // len(names))
        for i, n in enumerate(names):
            f = frames[min((i + 1) * per - 1, len(frames) - 1)]
            Image.open(f).convert("RGB").resize((426, 240)).save(out_dir / f"{n}.png")

    used = {}
    for a in glob.glob(ANIMS):
        t = Path(a).read_text(encoding="utf-8")
        for n in names:
            if f"/{n}.svg" in t:
                used.setdefault(n, []).append(os.path.basename(a)[:-5])

    md = ["# Каталог локаций", "",
          "Все локации серии одним списком: превью, линия пола и в каких роликах",
          "уже стоят. Собирается инструментом — `python3 tools/katalog.py`.", "",
          "**Почему превью, а не копии SVG.** Копия начинает жить своей жизнью:",
          "поправишь оригинал, а в копии останется старое, и однажды ролик",
          "соберётся не с той картинкой. Локации лежат там же, где лежали;",
          "каталог показывает, ЧТО есть, и не создаёт второй правды.", "",
          "**Линия пола** — `back_y` из карты поверхностей. Прочерк значит, что",
          "карты нет и `place ... on floor` молча не сработает: снять карту перед",
          "первым использованием.", "",
          "| Локация | Превью | Пол | Где стоит |", "|---|---|---|---|"]
    for n in names:
        sj = SETS / f"{n}.surfaces.json"
        floor = "—"
        if sj.exists():
            try:
                floor = str(json.loads(sj.read_text(encoding="utf-8"))
                            .get("floor", {}).get("back_y", "—"))
            except Exception:
                pass
        md.append(f"| `{n}.svg` | ![{n}](katalog/{n}.png) | {floor} | "
                  f"{', '.join(used.get(n, [])) or '—'} |")
    md += ["", f"Всего локаций: **{len(names)}**."]
    (SETS / "KATALOG.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"  каталог: {len(names)} локаций, превью в {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
