#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_lecture_anim.py — генератор .anim-роликов Лектория для персонажа Фреди.

Берёт HTML-страницу лекции с сайта meysternlp.ru (репозиторий
Dron939-sketch/dron939-sketch.github.io, файлы blog/lekciya-*.html) и собирает
из неё немой чёрно-белый ролик в стиле «Фреди / Мистер Фримен»:

  * заголовок лекции → интро-доля;
  * каждый пронумерованный раздел («1. …», «2. …») → одна доля (beat);
  * «Итоги» → финальная доля;
  * доли раскладываются по канонической библиотеке поз Фреди с чередованием
    ракурсов (wide / medium / close-up) и покадровым таймингом.

Видео немое. Закадровый голос — серверный TTS лекции (Frederick); он
подмешивается на этапе сборки (tools/compose_video.sh). Тайминг долей —
эвристический (по длине заголовка раздела); при монтаже под реальную озвучку
паузы `wait` правятся вручную.

Использование:
    python3 tools/gen_lecture_anim.py <путь-к-lekciya-*.html> [-o <out.anim>]
    python3 tools/gen_lecture_anim.py ../dron939-sketch.github.io/blog/lekciya-2-frejd-psihodinamika.html

Без -o файл кладётся в examples/lektorij/<имя-html>.anim.
Скрипт из стандартной библиотеки — сторонних зависимостей нет.
"""

import argparse
import html
import os
import re
import sys
from html.parser import HTMLParser

# --- Канон поз Фреди. Держим синхронно с examples/lektorij/fredi-lecture-template.anim
POSE_LIBRARY = """\
pose "fredi-calm" {
    torso-squash: 1.02
    head-nod: -2
    arm-left-angle: 7
    arm-right-angle: 7
    elbow-left-bend: 0.05
    elbow-right-bend: 0.05
    eye-open-left: 0.85
    eye-open-right: 0.85
    eyebrow-left: -0.15
    eyebrow-right: -0.15
    mouth-smile: -0.08
}

pose "fredi-blink" {
    head-nod: -1
    arm-left-angle: 7
    arm-right-angle: 7
    eye-open-left: 0.25
    eye-open-right: 0.25
}

pose "fredi-think" {
    torso-bend: -2
    head-tilt: 4
    head-nod: -8
    arm-right-angle: -95
    elbow-right-bend: 0.85
    arm-left-angle: 6
    elbow-left-bend: 0.1
    eye-open-left: 0.8
    eye-open-right: 0.8
    eye-direction: 0.4
    eyebrow-left: 0.1
    eyebrow-right: 0.1
}

pose "fredi-explain" {
    torso-bend: 2
    head-nod: -2
    arm-left-angle: -45
    elbow-left-bend: 0.35
    arm-right-angle: -45
    elbow-right-bend: 0.35
    eye-open-left: 0.9
    eye-open-right: 0.9
    mouth-open: 0.2
}

pose "fredi-point" {
    torso-bend: 4
    head-tilt: -2
    head-nod: -3
    arm-right-angle: -60
    elbow-right-bend: 0.2
    arm-left-angle: 5
    elbow-left-bend: 0.1
    eye-open-left: 0.95
    eye-open-right: 0.95
    eyebrow-left: -0.3
    eyebrow-right: -0.3
    mouth-open: 0.1
}

pose "fredi-stern" {
    torso-squash: 1.03
    head-nod: -4
    arm-left-angle: 6
    arm-right-angle: 6
    eye-open-left: 0.9
    eye-open-right: 0.9
    eyebrow-left: -0.5
    eyebrow-right: -0.5
    mouth-smile: -0.25
}

pose "fredi-smirk" {
    head-tilt: 4
    head-nod: -1
    arm-left-angle: 7
    arm-right-angle: 7
    eye-open-left: 0.8
    eye-open-right: 0.85
    eyebrow-left: 0.15
    eyebrow-right: -0.2
    mouth-smile: 0.35
}

pose "fredi-lean" {
    torso-bend: 7
    head-nod: 2
    arm-left-angle: -20
    elbow-left-bend: 0.3
    arm-right-angle: -20
    elbow-right-bend: 0.3
    eye-open-left: 1.0
    eye-open-right: 1.0
    eyebrow-left: -0.2
    eyebrow-right: -0.2
    mouth-open: 0.15
}
"""

# Позы, которыми «говорит» очередная доля (чередуем для разнообразия).
BEAT_POSES = ["fredi-explain", "fredi-think", "fredi-point", "fredi-stern", "fredi-lean"]
# Ракурсы по долям (чередуем крупность).
BEAT_CAMERAS = ["close-up", "medium", "close-up", "medium"]


class _Extractor(HTMLParser):
    """Достаёт <title>, <h1> и тексты <h2>/<h3> в порядке появления."""

    def __init__(self):
        super().__init__()
        self._stack = []
        self.title = ""
        self.h1 = ""
        self.headings = []  # список (tag, text)
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag in ("title", "h1", "h2", "h3"):
            self._stack.append(tag)
            self._buf = []

    def handle_endtag(self, tag):
        if self._stack and self._stack[-1] == tag:
            text = html.unescape("".join(self._buf)).strip()
            text = re.sub(r"\s+", " ", text)
            if tag == "title" and not self.title:
                self.title = text
            elif tag == "h1" and not self.h1:
                self.h1 = text
            elif tag in ("h2", "h3"):
                self.headings.append((tag, text))
            self._stack.pop()
            self._buf = []

    def handle_data(self, data):
        if self._stack:
            self._buf.append(data)


def clean_title(raw):
    """«Лекция 2. … | Андрей Мейстер» → «Лекция 2. …»."""
    return raw.split("|")[0].strip()


def is_section(text):
    """Пронумерованный раздел лекции: начинается с «N.» или «N)»."""
    return bool(re.match(r"^\d+[.)]\s+\S", text))


def is_summary(text):
    return text.lower().startswith(("итог", "вывод", "заключ"))


def escape_str(s):
    """Экранируем для строкового литерала DSL (кавычки и обратный слэш недопустимы)."""
    return s.replace("\\", "").replace('"', "'")


def estimate_wait(text):
    """Грубая оценка длительности озвучки заголовка раздела, сек."""
    words = max(1, len(text.split()))
    return min(6.0, max(2.5, round(words * 0.55, 1)))


def build_anim(title, sections, summary, scene_name):
    beats = []
    total = 0.0

    # Интро.
    intro = [
        "    // === ИНТРО ===",
        f'    // VO: "{escape_str(title)}"',
        "    camera wide",
        "    wait 2s",
        "    camera medium fredi",
        '    fredi pose "fredi-blink"',
        "    wait 0.3s",
        '    fredi pose "fredi-calm"',
        "    wait 1.7s",
        "",
    ]
    total += 4.0

    for i, sec in enumerate(sections):
        pose = BEAT_POSES[i % len(BEAT_POSES)]
        cam = BEAT_CAMERAS[i % len(BEAT_CAMERAS)]
        w = estimate_wait(sec)
        total += w + 1.0
        block = [
            f"    // === {escape_str(sec)} ===",
            f'    // VO: <раздел {i + 1}>',
            f"    camera {cam} fredi",
            f'    fredi pose "{pose}"',
            f"    wait {w}s",
        ]
        # Изредка добавляем «удар» камеры на акцентных долях.
        if pose in ("fredi-point", "fredi-stern"):
            block.append("    camera shake 0.4s intensity 3")
        block += ['    fredi pose "fredi-calm"', "    wait 1s", ""]
        beats.extend(block)

    # Итог.
    outro = [
        "    // === ИТОГ ===",
        f'    // VO: "{escape_str(summary or "Если коротко — вот суть.")}"',
        "    camera close-up fredi",
        '    fredi pose "fredi-smirk"',
        "    wait 3s",
        '    fredi pose "fredi-calm"',
        "    wait 2s",
        "",
        "    // === АУТРО ===",
        "    camera wide",
        "    wait 2s",
        "    transition fade-black 2s",
    ]
    total += 9.0
    duration = int(total) + 2

    lines = []
    lines.append("// " + "=" * 76)
    lines.append(f"//  {title}")
    lines.append("//  Лекторий → ролик стиля «Фреди / Мистер Фримен» (немой, ч/б).")
    lines.append("//  Сгенерировано tools/gen_lecture_anim.py. Озвучка — TTS (Frederick),")
    lines.append("//  подмешивается в tools/compose_video.sh. Паузы правьте под озвучку.")
    lines.append("// " + "=" * 76)
    lines.append("")
    lines.append('import character fredi from "../assets/characters/procedural/fredi.json"')
    lines.append('import set paper from "../assets/sets/lektorij-paper.svg"')
    lines.append("")
    lines.append("// 1280x720 @ 24fps: движок держит все кадры в памяти — этот формат")
    lines.append("// надёжно рендерится даже для длинных лекций.")
    lines.append("config {")
    lines.append("    width: 1280")
    lines.append("    height: 720")
    lines.append("    fps: 24")
    lines.append("    background: #ece7db")
    lines.append("    monochrome: true")
    lines.append("}")
    lines.append("")
    lines.append(POSE_LIBRARY)
    lines.append(f'scene "{scene_name}" (duration: {duration}s, set: paper) {{')
    lines.append("    place fredi at center facing front")
    lines.append('    fredi pose "fredi-calm"')
    lines.append("")
    lines.extend(intro)
    lines.extend(beats)
    lines.extend(outro)
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def slug_scene_name(basename):
    name = re.sub(r"[^a-z0-9]+", "-", basename.lower()).strip("-")
    return name or "lecture"


def main(argv):
    ap = argparse.ArgumentParser(description="Генератор .anim-роликов Лектория (Фреди).")
    ap.add_argument("html", help="Путь к HTML-странице лекции (blog/lekciya-*.html)")
    ap.add_argument("-o", "--output", help="Куда записать .anim (по умолчанию examples/lektorij/<имя>.anim)")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.html):
        print(f"Файл не найден: {args.html}", file=sys.stderr)
        return 1

    with open(args.html, encoding="utf-8") as f:
        source = f.read()

    ex = _Extractor()
    ex.feed(source)

    title = clean_title(ex.h1 or ex.title or "Лекция Лектория")
    sections = [t for (_, t) in ex.headings if is_section(t)]
    summary = next((t for (_, t) in ex.headings if is_summary(t)), None)

    if not sections:
        # Фолбэк: если нумерованных разделов нет, берём первые h2/h3.
        sections = [t for (_, t) in ex.headings if t and not is_summary(t)][:5]

    if not sections:
        print("Не удалось выделить разделы лекции из HTML.", file=sys.stderr)
        return 2

    base = os.path.splitext(os.path.basename(args.html))[0]
    scene_name = slug_scene_name(base)
    anim = build_anim(title, sections, summary, scene_name)

    out = args.output
    if not out:
        here = os.path.dirname(os.path.abspath(__file__))
        out = os.path.join(here, "..", "examples", "lektorij", base + ".anim")
        out = os.path.normpath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(anim)

    print(f"OK: {out}")
    print(f"  Заголовок: {title}")
    print(f"  Разделов:  {len(sections)}")
    print(f"  Проверка:  cargo run -- check {os.path.relpath(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
