#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voiceover.py — генерация озвучки через Fish Audio по VO-сценарию.

Читает сценарий озвучки (examples/lektorij/*-VO.md), берёт из таблицы реплики
с таймкодами, синтезирует каждую через Fish Audio API и собирает единый
«дубль»: дорожку, где каждая реплика стоит на своём таймкоде (паузы — тишина).
Результат кладётся рядом с видео (videos/<имя>-voice.mp3).

Требования:
  * переменная окружения FISH_AUDIO_API_KEY — ключ API Fish Audio;
  * опционально FISH_AUDIO_VOICE_ID — reference_id голоса Фреди
    (если не задан — голос Fish Audio по умолчанию);
  * ffmpeg в PATH (сборка дорожки).

Использование:
    python3 tools/voiceover.py examples/lektorij/pereproshivka-intro-VO.md \
        -o videos/pereproshivka-intro-voice.mp3
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

API_URL = "https://api.fish.audio/v1/tts"
# Frederick — источник правды по озвучке (голос Фреди). Если задан токен, реплики
# синтезирует он (ключ Fish не покидает сервер Frederick) и кэширует mp3 у себя.
# `or` (не default-аргумент): пустой секрет FREDERICK_TTS_URL приходит как ""
# — get(..., default) вернул бы "", а нам нужен дефолтный адрес.
FREDERICK_BASE = (os.environ.get("FREDERICK_TTS_URL") or "https://ffred-ddd989.amvera.io").rstrip("/")
FREDERICK_TOKEN = os.environ.get("FREDERICK_ADMIN_TOKEN") or ""


def parse_vo_table(md_path):
    """Достаёт из VO-таблицы (| VO-n | 0:02.5–0:05.7 | «текст» |) реплики.

    Возвращает список (start_seconds, text).
    """
    rows = []
    with open(md_path, encoding="utf-8") as f:
        for line in f:
            m = re.match(
                r"\|\s*VO-\d+\s*\|\s*(\d+):(\d+(?:\.\d+)?)\s*[–-]\s*[\d:.]+\s*\|(.+)\|",
                line,
            )
            if not m:
                continue
            start = int(m.group(1)) * 60 + float(m.group(2))
            cell = m.group(3).strip()
            # Убираем ремарки *(...)* и кавычки-ёлочки.
            text = re.sub(r"\*\([^)]*\)\*", "", cell).strip()
            text = text.strip("«»«» \t")
            if text:
                rows.append((start, text))
    return rows


def tts_via_frederick(text):
    """Одна реплика → mp3-байты через Frederick (голос Фреди, кэш на сервере)."""
    req = urllib.request.Request(
        f"{FREDERICK_BASE}/api/tts/video/say",
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Admin": FREDERICK_TOKEN},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def tts_fish_audio(text, api_key, voice_id=None):
    """Одна реплика → mp3-байты через Fish Audio."""
    payload = {"text": text, "format": "mp3"}
    if voice_id:
        payload["reference_id"] = voice_id
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def assemble_track(replicas, out_path):
    """Собирает дорожку: каждая реплика на своём таймкоде, между — тишина."""
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg не найден в PATH.")
    with tempfile.TemporaryDirectory() as td:
        inputs = []
        filters = []
        amix = []
        for i, (start, mp3_bytes) in enumerate(replicas):
            p = os.path.join(td, f"r{i}.mp3")
            with open(p, "wb") as f:
                f.write(mp3_bytes)
            inputs += ["-i", p]
            delay_ms = int(start * 1000)
            filters.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
            amix.append(f"[a{i}]")
        filter_complex = (
            ";".join(filters)
            + f";{''.join(amix)}amix=inputs={len(amix)}:normalize=0[out]"
        )
        cmd = (
            ["ffmpeg", "-y", "-v", "error"]
            + inputs
            + ["-filter_complex", filter_complex, "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "3", out_path]
        )
        subprocess.run(cmd, check=True)


def main(argv):
    ap = argparse.ArgumentParser(description="Озвучка VO-сценария через Fish Audio")
    ap.add_argument("script", help="Путь к *-VO.md со сценарием")
    ap.add_argument("-o", "--output", required=True, help="Куда писать mp3")
    args = ap.parse_args(argv)

    use_frederick = bool(FREDERICK_TOKEN)
    api_key = os.environ.get("FISH_AUDIO_API_KEY")
    if not use_frederick and not api_key:
        sys.exit("Нет ни FREDERICK_ADMIN_TOKEN, ни FISH_AUDIO_API_KEY — пропускаю озвучку.")
    voice_id = os.environ.get("FISH_AUDIO_VOICE_ID")

    rows = parse_vo_table(args.script)
    if not rows:
        sys.exit(f"В {args.script} не найдено реплик VO-таблицы.")
    src = f"Frederick ({FREDERICK_BASE})" if use_frederick else f"Fish напрямую (голос {voice_id or 'по умолчанию'})"
    print(f"Реплик: {len(rows)}; озвучка: {src}")

    replicas = []
    for start, text in rows:
        print(f"  {start:6.1f}s  {text[:60]}")
        audio = tts_via_frederick(text) if use_frederick else tts_fish_audio(text, api_key, voice_id)
        replicas.append((start, audio))

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    assemble_track(replicas, args.output)
    print(f"OK: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
