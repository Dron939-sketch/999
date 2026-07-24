#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prep_lipsync.py — впаивает липсинк по реальной озвучке в сценарий перед рендером.

Идея «завода без рассинхрона»: в .anim речь размечается маркером, а не
жёстким `speaks for Ns`:

    freeman pose "stern"        // выражение под смысл реплики (авторски)
    //@speak freeman 1 3.2      // реплика VO-1, запас 3.2с

Препроцессор для каждого маркера ищет mp3 этой реплики
(<parts>/vo-<n>.mp3), снимает огибающую громкости (tools/lipsync.py) и
подставляет дорожку ртов — рот открывается ровно там, где звук. Если mp3 нет
(озвучка ещё не готова), маркер разворачивается в обычный `speaks for Ns`,
так что сценарий рендерится всегда.

Выражение лица стоит ПЕРЕД маркером и держится всю реплику (рты — overlay,
ложатся поверх позы), поэтому лицо и звук совпадают по построению.

Использование:
    python3 tools/prep_lipsync.py scene.anim --parts videos/<id>-parts \
        -o scene.lipsynced.anim
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lipsync import extract_envelope, envelope_to_mouths  # noqa: E402

MARKER = re.compile(r'^(\s*)//@speak\s+(\S+)\s+(\d+)\s+([\d.]+)\s*$')


def mouth_track_lines(entity, mp3, indent, fps=11.0):
    hop = 1.0 / fps
    env = extract_envelope(mp3, hop)
    track = envelope_to_mouths(env, hop)
    out = [f'{indent}// липсинк {os.path.basename(mp3)} ({len(track)} смен ртов)']
    for pose, dur in track:
        out.append(f'{indent}{entity} pose "{pose}"')
        out.append(f'{indent}wait {round(dur, 2)}s')
    out.append(f'{indent}{entity} pose "idle"')  # рот закрыт после реплики
    return out


def process(anim_text, parts_dir):
    out, subbed, fell_back = [], 0, 0
    for line in anim_text.splitlines():
        m = MARKER.match(line)
        if not m:
            out.append(line)
            continue
        indent, entity, idx, dur = m.group(1), m.group(2), m.group(3), m.group(4)
        mp3 = os.path.join(parts_dir or "", f"vo-{idx}.mp3")
        if parts_dir and os.path.isfile(mp3) and os.path.getsize(mp3) > 0:
            out.extend(mouth_track_lines(entity, mp3, indent))
            subbed += 1
        else:
            # запасной путь: обычные флэпы на запас длительности
            out.append(f'{indent}{entity} speaks for {dur}s')
            fell_back += 1
    return "\n".join(out) + "\n", subbed, fell_back


def main(argv):
    ap = argparse.ArgumentParser(description="Впаять липсинк в .anim перед рендером")
    ap.add_argument("anim", help="Исходный .anim с маркерами //@speak")
    ap.add_argument("--parts", help="Каталог с vo-<n>.mp3 (если нет — везде флэпы)")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args(argv)

    text = open(args.anim, encoding="utf-8").read()
    result, subbed, fell_back = process(text, args.parts)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"OK: {args.output} — липсинк по звуку: {subbed}, флэп-фолбэк: {fell_back}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
