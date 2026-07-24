#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lipsync.py — автолипсинк по реальной озвучке (mp3/wav → дорожка ртов).

Снимает огибающую громкости аудио через ffmpeg и превращает её в
последовательность фонемных ртов Фримена/Фреди:

  * громко + пик        → pose "gab"   (широко открытый рот)
  * речь средней силы   → pose "talk"  (рот «о»)
  * тихо/пауза          → pose "idle"  (рот закрыт)

Выход — фрагмент .anim (pose + wait), который вставляется в сценарий вместо
блока `freeman speaks for Ns`. Так рот попадает в реальный ритм голоса.

Использование:
    python3 tools/lipsync.py voice.mp3 --entity freeman -o mouth-track.anim.inc
    python3 tools/lipsync.py voice.mp3 --entity fredi --fps 12

Требуется ffmpeg в PATH (в CI/Docker есть; локально: apt install ffmpeg).
"""

import argparse
import math
import shutil
import struct
import subprocess
import sys


def extract_envelope(path, hop_s):
    """Возвращает список RMS-значений громкости с шагом hop_s секунд."""
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg не найден в PATH — установите ffmpeg (apt install ffmpeg).")

    rate = 16000
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", path,
            "-ac", "1", "-ar", str(rate),
            "-f", "s16le", "-",
        ],
        stdout=subprocess.PIPE,
        check=True,
    )
    raw = proc.stdout
    n = len(raw) // 2
    samples = struct.unpack(f"<{n}h", raw[: n * 2])

    hop = int(rate * hop_s)
    env = []
    for i in range(0, n, hop):
        chunk = samples[i : i + hop]
        if not chunk:
            break
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
        env.append(rms)
    return env


def envelope_to_mouths(env, hop_s):
    """RMS-огибающая → список (pose, длительность)."""
    if not env:
        return []
    peak = max(env) or 1.0
    # Пороги относительно пика записи (устойчиво к разной громкости мастера).
    talk_thr = 0.18 * peak
    gab_thr = 0.45 * peak

    frames = []
    for v in env:
        if v >= gab_thr:
            frames.append("gab")
        elif v >= talk_thr:
            frames.append("talk")
        else:
            frames.append("idle")

    # Слить одинаковых соседей в (pose, dur); отсечь дребезг короче 2 хопов.
    track = []
    for pose in frames:
        if track and track[-1][0] == pose:
            track[-1][1] += hop_s
        else:
            track.append([pose, hop_s])
    merged = []
    for pose, dur in track:
        if merged and dur < hop_s * 2 and merged[-1][0] != "idle":
            merged[-1][1] += dur  # дребезг приклеиваем к предыдущему
        else:
            merged.append([pose, dur])
    return merged


def main(argv):
    ap = argparse.ArgumentParser(description="Автолипсинк: mp3 → дорожка ртов .anim")
    ap.add_argument("audio", help="Файл озвучки (mp3/wav/ogg)")
    ap.add_argument("--entity", default="freeman", help="Имя персонажа в сцене (default: freeman)")
    ap.add_argument("--fps", type=float, default=10.0, help="Частота смены ртов (default: 10/сек)")
    ap.add_argument("-o", "--output", help="Куда писать (default: stdout)")
    args = ap.parse_args(argv)

    hop_s = 1.0 / args.fps
    env = extract_envelope(args.audio, hop_s)
    track = envelope_to_mouths(env, hop_s)

    lines = [
        f"    // --- липсинк из {args.audio} ({len(track)} смен, шаг {hop_s:.2f}с) ---",
    ]
    for pose, dur in track:
        lines.append(f'    {args.entity} pose "{pose}"')
        lines.append(f"    wait {round(dur, 2)}s")
    out = "\n".join(lines) + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        total = sum(d for _, d in track)
        print(f"OK: {args.output} ({total:.1f}s речи, {len(track)} смен ртов)")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
