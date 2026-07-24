#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
studio.py — «завод» Лектория: одна команда → готовый ролик со звуком.

Оркестратор всего конвейера. По манифесту продакшенов (tools/productions.json)
для каждого ролика последовательно:

  1) КАРТИНКИ  — генерит недостающие иллюстрации по текстовым промтам
                 (tools/image_gen.py, Nano Banana / image API). Опционально.
  2) РЕНДЕР    — движок animdsl рендерит НЕМОЙ ролик (.anim → mp4/png).
  3) ОЗВУЧКА   — Fish Audio по VO-сценарию (tools/voiceover.py) → mp3. Опц.
  4) СВЕДЕНИЕ  — ffmpeg подмешивает голос к видео (tools/compose_video.sh)
                 → финальный mp4 со звуком.

Любой шаг, у которого нет ключа/инструмента, аккуратно пропускается с
понятным логом — конвейер не падает, а отдаёт что смог (немой mp4 как минимум).

Ключи берутся ТОЛЬКО из окружения (в CI — из GitHub Secrets), никогда из кода:
  * FISH_AUDIO_API_KEY   — озвучка (обязателен для звука);
  * FISH_AUDIO_VOICE_ID  — голос Фреди (reference_id), желателен;
  * IMAGE_API_KEY        — генерация картинок (Nano Banana / провайдер), опц.;
  * IMAGE_API_PROVIDER   — gemini|openai|... (по умолчанию gemini).

Использование:
    python3 tools/studio.py                 # все продакшены из манифеста
    python3 tools/studio.py pereproshivka-intro   # только один (по id)
    python3 tools/studio.py --engine ./target/release/animdsl
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DEFAULT_MANIFEST = TOOLS / "productions.json"
DEFAULT_ENGINE = ROOT / "target" / "release" / "animdsl"


def log(msg):
    print(msg, flush=True)


def have_ffmpeg():
    from shutil import which
    return which("ffmpeg") is not None


def run(cmd, **kw):
    log("  $ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def step_images(prod, out_dir):
    """Генерит объявленные картинки (если задан IMAGE_API_KEY)."""
    images = prod.get("images", [])
    if not images:
        return
    if not os.environ.get("IMAGE_API_KEY"):
        log("  [картинки] IMAGE_API_KEY не задан — пропуск генерации "
            f"({len(images)} шт., будут использованы существующие ассеты).")
        return
    gen = TOOLS / "image_gen.py"
    for img in images:
        dst = ROOT / img["out"]
        if dst.exists() and not img.get("force"):
            log(f"  [картинки] уже есть: {img['out']} — пропуск.")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(gen), "-o", str(dst), "--prompt", img["prompt"]]
        if img.get("wrap_svg"):
            cmd += ["--wrap-svg", str(ROOT / img["wrap_svg"])]
        if img.get("size"):
            cmd += ["--size", img["size"]]
        try:
            run(cmd)
        except subprocess.CalledProcessError as e:
            log(f"  [картинки] не удалось сгенерить {img['out']}: {e} — пропуск.")


def step_render(prod, engine, out_mp4):
    """Немой рендер .anim → mp4."""
    src = ROOT / prod["anim"]
    if not src.exists():
        raise FileNotFoundError(f"нет сценария: {src}")
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    run([str(engine), "render", str(src), "-o", str(out_mp4)])
    return out_mp4


def step_voice(prod, out_voice):
    """Озвучка VO-сценария → mp3 (Fish Audio). Возвращает путь или None."""
    vo = prod.get("vo")
    if not vo:
        log("  [озвучка] VO-сценарий не задан — немой ролик.")
        return None
    if not (os.environ.get("FREDERICK_ADMIN_TOKEN") or os.environ.get("FISH_AUDIO_API_KEY")):
        log("  [озвучка] нет FREDERICK_ADMIN_TOKEN и FISH_AUDIO_API_KEY — озвучка "
            "пропущена (добавьте секрет в Settings → Secrets and variables → Actions).")
        return None
    vo_path = ROOT / vo
    if not vo_path.exists():
        log(f"  [озвучка] нет VO-файла: {vo} — пропуск.")
        return None
    # Мягко: сбой озвучки (недоступен Frederick, не тот токен, пустая реплика)
    # НЕ рушит весь завод — просто отдаём немой ролик и логируем причину.
    try:
        run([sys.executable, str(TOOLS / "voiceover.py"), str(vo_path), "-o", str(out_voice)])
        return out_voice
    except subprocess.CalledProcessError as e:
        log(f"  [озвучка] не удалась ({e}) — оставляю немой ролик. "
            "Проверь FREDERICK_ADMIN_TOKEN и /api/tts/video/health.")
        return None


def step_mux(prod, video_mp4, voice_mp3, out_final):
    """Свести видео+голос → финальный mp4 (ffmpeg)."""
    if voice_mp3 is None or not Path(voice_mp3).exists():
        log("  [сведение] нет озвучки — финальный ролик = немой рендер.")
        return None
    if not have_ffmpeg():
        log("  [сведение] ffmpeg не найден — сведение пропущено "
            "(в CI ffmpeg ставится; локально установите ffmpeg).")
        return None
    cmd = ["bash", str(TOOLS / "compose_video.sh"),
           str(video_mp4), str(voice_mp3), str(out_final)]
    if prod.get("title"):
        cmd.append(prod["title"])
    run(cmd)
    return out_final


def build_one(prod, engine, videos_dir):
    pid = prod["id"]
    log(f"\n=== ПРОДАКШЕН: {pid} — {prod.get('desc', '')}")
    video_mp4 = videos_dir / f"{pid}.mp4"
    voice_mp3 = videos_dir / f"{pid}-voice.mp3"
    final_mp4 = videos_dir / f"{pid}-final.mp4"

    step_images(prod, videos_dir)
    step_render(prod, engine, video_mp4)
    voice = step_voice(prod, voice_mp3)
    step_mux(prod, video_mp4, voice, final_mp4)

    made = []
    for p in (video_mp4, voice_mp3, final_mp4):
        if p.exists():
            mb = p.stat().st_size / 1048576
            made.append(f"{p.name} ({mb:.1f}МБ)")
            if p.suffix == ".mp4" and mb > 95:
                log(f"  [!] {p.name} = {mb:.0f}МБ — превысит лимит GitHub (>100МБ), "
                    "снизь битрейт/длительность.")
    log(f"  → готово: {', '.join(made)}")


def main(argv):
    ap = argparse.ArgumentParser(description="Завод Лектория: ролики со звуком")
    ap.add_argument("only", nargs="?", help="id одного продакшена (иначе — все)")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--engine", default=str(DEFAULT_ENGINE))
    ap.add_argument("--videos", default=str(ROOT / "videos"))
    args = ap.parse_args(argv)

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    prods = manifest["productions"]
    if args.only:
        prods = [p for p in prods if p["id"] == args.only]
        if not prods:
            sys.exit(f"нет продакшена с id={args.only}")

    engine = Path(args.engine)
    if not engine.exists():
        sys.exit(f"движок не собран: {engine} (cargo build --release)")
    videos_dir = Path(args.videos)
    videos_dir.mkdir(parents=True, exist_ok=True)

    log(f"Завод: {len(prods)} продакшен(ов); движок {engine}; "
        f"ffmpeg={'есть' if have_ffmpeg() else 'нет'}; "
        f"озвучка={'вкл' if (os.environ.get('FREDERICK_ADMIN_TOKEN') or os.environ.get('FISH_AUDIO_API_KEY')) else 'выкл'}; "
        f"картинки={'вкл' if os.environ.get('IMAGE_API_KEY') else 'выкл'}")
    for prod in prods:
        build_one(prod, engine, videos_dir)
    log("\nЗавод отработал.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
