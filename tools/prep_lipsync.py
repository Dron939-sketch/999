#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prep_lipsync.py — впаивает липсинк по реальной озвучке в сценарий перед рендером.

«Завод без рассинхрона»: речь в .anim размечается ПОДСКАЗКОЙ-комментарием и
обычным `speaks for`, который работает и сам по себе:

    //lip 1                      # это реплика VO-1
    freeman speaks for 3.2s      # запасной вариант (флэпы), если озвучки нет

Препроцессор для каждой пары ищет mp3 этой реплики (<parts>/vo-<N>.mp3), снимает
огибающую громкости (tools/lipsync.py) и ЗАМЕНЯЕТ строку `speaks for` на дорожку
из действий `lips` — рот открывается ровно там, где звук (амплитудный липсинк),
а тело держит позу (lips — overlay). Если mp3 нет — строка `speaks for` остаётся
как есть, так что сценарий рендерится всегда.

Использование:
    python3 tools/prep_lipsync.py scene.anim --parts videos/<id>-parts \
        -o scene.lipsynced.anim
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lipsync import extract_envelope, envelope_to_mouths  # noqa: E402

LIP = re.compile(r"^\s*//lip\s+(\d+)\s*$")
SPEAK = re.compile(r"^(\s*)(\S+)\s+speaks\s+for\s+([\d.]+)s\s*$")

# Виземы Rhubarb → позы рига (rig.json: visA..visF). Расширенные G/H/X
# сводим к ближайшим базовым.
RHUBARB_MAP = {
    "A": "visA", "B": "visB", "C": "visC", "D": "visD",
    "E": "visE", "F": "visF", "G": "visB", "H": "visC", "X": "visA",
}


def rhubarb_bin():
    """Путь к бинарю Rhubarb Lip Sync (или None): $RHUBARB_BIN либо в PATH."""
    cand = os.environ.get("RHUBARB_BIN") or shutil.which("rhubarb")
    return cand if cand and os.path.exists(cand) else None


def gate_viseme(pose, prev_pose, dur, loud):
    """Гейт виземы по РЕАЛЬНОЙ громкости (loud = local RMS / peak, 0..1).

    Rhubarb метит рот по фонеме, без громкости → шёпот и крик дают один удар.
    Здесь громкость рулит акцентом: тихий «широкий» слог оседает в скромный рот
    (visB, без удара → жеста/сквоша нет — микро на шёпоте); громкий ударный слог
    получает _acc (удар → жест+сквош по огибающей mp3 — размашисто на крике).
    Средняя громкость оставляет базовый широкий рот (обычный акцент)."""
    if pose in ("visC", "visD", "visE"):
        if loud < 0.40:
            return "visB"                      # тихо → скромный рот, БЕЗ удара
        if (prev_pose in ("visA", "visB", "visF")
                and dur >= 0.08 and loud >= 0.58):
            return pose + "_acc"               # громкий ударный слог → удар
    return pose


def rhubarb_track(mp3):
    """mp3 → [(поза, длительность)] через фонемный Rhubarb (None при сбое).

    Rhubarb ест wav/ogg — конвертируем ffmpeg'ом; распознаватель phonetic
    языконезависим (наш текст — русский). Выход: JSON mouthCues (A..X).
    Виземы гейтятся реальной огибающей громкости (gate_viseme).
    """
    rb = rhubarb_bin()
    if not rb or not shutil.which("ffmpeg"):
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            wav = os.path.join(td, "line.wav")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ar", "16000", "-ac", "1", wav],
                check=True,
            )
            res = subprocess.run(
                [rb, "-r", "phonetic", "-f", "json", "--machineReadable", wav],
                check=True, capture_output=True, text=True,
            )
        cues = json.loads(res.stdout).get("mouthCues", [])
        # Огибающая громкости этой же реплики — гейт акцентов по силе голоса.
        hop = 0.05
        try:
            env = extract_envelope(mp3, hop)
            peak = max(env) or 1.0
        except Exception:
            env, peak = [], 1.0

        def loud_at(t):
            if not env:
                return 1.0
            return env[min(int(t / hop), len(env) - 1)] / peak

        track = []
        prev_pose = "visA"
        for c in cues:
            start = float(c["start"])
            dur = float(c["end"]) - start
            pose = RHUBARB_MAP.get(c["value"], "visA")
            pose = gate_viseme(pose, prev_pose, dur, loud_at(start + dur * 0.5))
            prev_pose = pose.replace("_acc", "")
            if track and track[-1][0] == pose:
                track[-1] = (pose, track[-1][1] + dur)
            elif dur > 0:
                track.append((pose, dur))
        return track or None
    except Exception as e:  # noqa: BLE001 — любой сбой → честный фолбэк на RMS
        print(f"  [rhubarb] не сработал ({e}) — амплитудный липсинк.")
        return None


def lips_track_lines(entity, mp3, indent, fps=11.0):
    # Сначала фонемы (Rhubarb): рот артикулирует слоги. Фолбэк — RMS-огибающая.
    track = rhubarb_track(mp3)
    src = "фонемы" if track else "амплитуда"
    if not track:
        hop = 1.0 / fps
        track = envelope_to_mouths(extract_envelope(mp3, hop), hop)
    out = [f"{indent}// липсинк {os.path.basename(mp3)} ({len(track)} ртов, {src})"]
    for pose, dur in track:
        out.append(f'{indent}{entity} lips "{pose}" for {round(dur, 2)}s')
    return out


def process(text, parts_dir):
    out, pending, subbed, fell = [], None, 0, 0
    order = []  # номера vo-N в порядке появления речевых блоков в файле
    for line in text.splitlines():
        m = LIP.match(line)
        if m:
            pending = int(m.group(1))  # запомнить номер реплики, сам маркер убрать
            continue
        s = SPEAK.match(line)
        if s and pending is not None:
            indent, entity, dur = s.group(1), s.group(2), s.group(3)
            mp3 = os.path.join(parts_dir or "", f"vo-{pending}.mp3")
            if parts_dir and os.path.isfile(mp3) and os.path.getsize(mp3) > 0:
                out.extend(lips_track_lines(entity, mp3, indent))
                subbed += 1
            else:
                out.append(line)  # запасной путь: обычные флэпы
                fell += 1
            order.append(pending)
            pending = None
            continue
        pending = None  # маркер без следующей за ним речи — просто игнор
        out.append(line)
    return "\n".join(out) + "\n", subbed, fell, order


def main(argv):
    ap = argparse.ArgumentParser(description="Впаять липсинк в .anim перед рендером")
    ap.add_argument("anim")
    ap.add_argument("--parts", help="каталог с vo-<N>.mp3 (нет → везде флэпы)")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args(argv)

    text = open(args.anim, encoding="utf-8").read()
    result, subbed, fell, order = process(text, args.parts)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(result)
    # Карта «речевой блок № → номер vo-N» для сборки голоса по фактическим
    # временам движка (animdsl timing) — синхрон по конструкции.
    with open(args.output + ".map.json", "w", encoding="utf-8") as f:
        json.dump(order, f)
    print(f"OK: {args.output} — липсинк по звуку: {subbed}, флэп-фолбэк: {fell}; карта блоков: {order}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
