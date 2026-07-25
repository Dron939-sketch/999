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


def step_render(src_anim, engine, out_mp4):
    """Немой рендер .anim → mp4."""
    src = Path(src_anim)
    if not src.exists():
        raise FileNotFoundError(f"нет сценария: {src}")
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    run([str(engine), "render", str(src), "-o", str(out_mp4)])
    return out_mp4


def step_voice(prod, out_voice, parts_dir):
    """Озвучка VO-сценария → mp3 + реплики по файлам (vo-<N>.mp3) для липсинка."""
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
    # Мягко: сбой озвучки НЕ рушит завод — просто немой ролик + лог причины.
    try:
        run([sys.executable, str(TOOLS / "voiceover.py"), str(vo_path),
             "-o", str(out_voice), "--parts-dir", str(parts_dir)])
        return out_voice
    except subprocess.CalledProcessError as e:
        log(f"  [озвучка] не удалась ({e}) — оставляю немой ролик. "
            "Проверь FREDERICK_ADMIN_TOKEN и /api/tts/video/health.")
        return None


def step_voice_parts(prod, parts_dir):
    """Сгенерить реплики по файлам (vo-<N>.mp3) БЕЗ сборки дорожки."""
    vo = prod.get("vo")
    if not vo:
        log("  [озвучка] VO-сценарий не задан — немой ролик.")
        return False
    if not (os.environ.get("FREDERICK_ADMIN_TOKEN") or os.environ.get("FISH_AUDIO_API_KEY")):
        log("  [озвучка] нет токенов — озвучка пропущена.")
        return False
    vo_path = ROOT / vo
    if not vo_path.exists():
        log(f"  [озвучка] нет VO-файла: {vo} — пропуск.")
        return False
    try:
        run([sys.executable, str(TOOLS / "voiceover.py"), str(vo_path),
             "-o", str(parts_dir / "_unused.mp3"), "--parts-dir", str(parts_dir),
             "--no-assemble"])
        return True
    except subprocess.CalledProcessError as e:
        log(f"  [озвучка] не удалась ({e}) — немой ролик.")
        return False


def step_assemble_voice(prod, prepped_anim, parts_dir, out_voice, engine):
    """Собрать голосовую дорожку по фактическим временам движка."""
    vo_path = ROOT / prod["vo"]
    times = Path(str(prepped_anim) + ".times.json")
    mapf = Path(str(prepped_anim) + ".map.json")
    try:
        with open(times, "w") as f:
            subprocess.run([str(engine), "timing", str(prepped_anim)],
                           check=True, stdout=f)
        run([sys.executable, str(TOOLS / "voiceover.py"), str(vo_path),
             "-o", str(out_voice), "--assemble-only",
             "--parts-dir", str(parts_dir),
             "--times-json", str(times), "--map-json", str(mapf)])
        return out_voice
    except subprocess.CalledProcessError as e:
        log(f"  [сборка голоса] не удалась ({e}) — немой ролик.")
        return None


def step_prep_lipsync(prod, parts_dir):
    """Впаять липсинк по звуку в сценарий (или флэп-фолбэк). Возвращает .anim для рендера.

    Пишем рядом с оригиналом (относительные import'ы разрешаются от папки .anim).
    """
    src = ROOT / prod["anim"]
    prepped = src.with_name(f".{src.stem}.lipsynced.anim")
    try:
        run([sys.executable, str(TOOLS / "prep_lipsync.py"), str(src),
             "--parts", str(parts_dir), "-o", str(prepped)])
        return prepped
    except subprocess.CalledProcessError as e:
        log(f"  [липсинк] препроцессор не сработал ({e}) — рендерю исходный сценарий.")
        return src


def step_sfx(prod, video_mp4, out_sfx):
    """Синтезировать SFX-дорожку по таблице из VO.md (длина = длине видео)."""
    vo = prod.get("vo")
    if not vo or not (ROOT / vo).exists() or not have_ffmpeg():
        return None
    try:
        dur = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(video_mp4)],
            check=True, capture_output=True, text=True).stdout.strip()
        run([sys.executable, str(TOOLS / "sfx.py"), str(ROOT / vo),
             "-o", str(out_sfx), "--duration", dur])
        return out_sfx if Path(out_sfx).exists() else None
    except subprocess.CalledProcessError as e:
        log(f"  [sfx] синтез не удался ({e}) — без звуковых эффектов.")
        return None


def step_mux(prod, video_mp4, voice_mp3, sfx_mp3, out_final):
    """Свести видео + голос + SFX → финальный mp4 (ffmpeg)."""
    have_voice = voice_mp3 is not None and Path(voice_mp3).exists()
    have_sfx = sfx_mp3 is not None and Path(sfx_mp3).exists()
    if not have_voice and not have_sfx:
        log("  [сведение] нет ни озвучки, ни SFX — финальный ролик = немой рендер.")
        return None
    if not have_ffmpeg():
        log("  [сведение] ffmpeg не найден — сведение пропущено "
            "(в CI ffmpeg ставится; локально установите ffmpeg).")
        return None
    # Голос + SFX премиксуются в одну дорожку (голос громче, SFX — подложка).
    audio = voice_mp3 if have_voice else sfx_mp3
    if have_voice and have_sfx:
        mixed = Path(video_mp4).with_name(Path(video_mp4).stem + "-mix.mp3")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(voice_mp3), "-i", str(sfx_mp3),
             "-filter_complex",
             "[0]volume=1.0[v];[1]volume=0.75[s];"
             "[v][s]amix=inputs=2:duration=longest:normalize=0",
             "-b:a", "160k", str(mixed)])
        audio = mixed
    cmd = ["bash", str(TOOLS / "compose_video.sh"),
           str(video_mp4), str(audio), str(out_final)]
    if prod.get("title"):
        cmd.append(prod["title"])
    run(cmd)
    return out_final


def _ffprobe(path, entries, select=None):
    cmd = ["ffprobe", "-v", "error", "-show_entries", entries,
           "-of", "default=nw=1:nk=1"]
    if select:
        cmd += ["-select_streams", select]
    cmd.append(str(path))
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def media_duration(path):
    try:
        return float(_ffprobe(path, "format=duration") or 0.0)
    except ValueError:
        return 0.0


def has_audio(path):
    return bool(_ffprobe(path, "stream=codec_type", select="a:0"))


def qc_production(prod, video_mp4, final_mp4, voice_expected):
    """Гейт качества: ловит немой/рассинхронный ролик. Возвращает список ошибок.

    Философия завода — «отдать хоть что-то» — годится для черновика, но в CI с
    ключами (voice_expected=True) немой или рассинхронный ролик НЕ должен
    проходить зелёным. Проверяем: выход существует; если заявлен vo — есть
    звук; длительности video≈final."""
    errs = []
    if not Path(video_mp4).exists():
        return [f"{prod['id']}: нет отрендеренного video ({Path(video_mp4).name})"]
    if voice_expected and prod.get("vo"):
        if not have_ffmpeg():
            return errs  # без ffprobe проверить нечем
        if not Path(final_mp4).exists() or not has_audio(final_mp4):
            errs.append(f"{prod['id']}: заявлен vo, но в финале НЕТ звуковой дорожки")
        else:
            vd, ad = media_duration(video_mp4), media_duration(final_mp4)
            if vd > 0 and abs(ad - vd) / vd > 0.20:
                errs.append(f"{prod['id']}: рассинхрон длительностей "
                            f"video={vd:.1f}s vs final={ad:.1f}s (>20%)")
    return errs


def build_one(prod, engine, videos_dir, voice_expected=False):
    pid = prod["id"]
    log(f"\n=== ПРОДАКШЕН: {pid} — {prod.get('desc', '')}")
    video_mp4 = videos_dir / f"{pid}.mp4"
    voice_mp3 = videos_dir / f"{pid}-voice.mp3"
    final_mp4 = videos_dir / f"{pid}-final.mp4"
    parts_dir = videos_dir / f"{pid}-parts"

    # Порядок: картинки → озвучка ЧАСТЯМИ → липсинк по звуку в сцену →
    # ФАКТИЧЕСКИЕ времена речи из движка (animdsl timing) → сборка голосовой
    # дорожки по этим временам (синхрон по конструкции) → рендер → SFX → микс.
    step_images(prod, videos_dir)
    parts_ok = step_voice_parts(prod, parts_dir)
    src_anim = step_prep_lipsync(prod, parts_dir)
    voice = step_assemble_voice(prod, src_anim, parts_dir, voice_mp3, engine) if parts_ok else None
    step_render(src_anim, engine, video_mp4)
    sfx = step_sfx(prod, video_mp4, videos_dir / f"{pid}-sfx.mp3")
    step_mux(prod, video_mp4, voice, sfx, final_mp4)

    made = []
    for p in (video_mp4, voice_mp3, final_mp4):
        if p.exists():
            mb = p.stat().st_size / 1048576
            made.append(f"{p.name} ({mb:.1f}МБ)")
            if p.suffix == ".mp4" and mb > 95:
                log(f"  [!] {p.name} = {mb:.0f}МБ — превысит лимит GitHub (>100МБ), "
                    "снизь битрейт/длительность.")
    log(f"  → готово: {', '.join(made)}")

    errs = qc_production(prod, video_mp4, final_mp4, voice_expected)
    for e in errs:
        log(f"  [QC-FAIL] {e}")
    return errs


def main(argv):
    ap = argparse.ArgumentParser(description="Завод Лектория: ролики со звуком")
    ap.add_argument("only", nargs="?", help="id одного продакшена (иначе — все)")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--engine", default=str(DEFAULT_ENGINE))
    ap.add_argument("--videos", default=str(ROOT / "videos"))
    ap.add_argument("--strict", action="store_true",
                    help="ненулевой выход, если QC-гейт нашёл немой/рассинхронный ролик")
    args = ap.parse_args(argv)
    strict = args.strict or bool(os.environ.get("QC_STRICT"))

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
    voice_expected = bool(
        os.environ.get("FREDERICK_ADMIN_TOKEN") or os.environ.get("FISH_AUDIO_API_KEY")
    )
    all_errs = []
    for prod in prods:
        all_errs += build_one(prod, engine, videos_dir, voice_expected) or []
    log("\nЗавод отработал.")
    if all_errs:
        log(f"\nQC: {len(all_errs)} проблема(ы):")
        for e in all_errs:
            log(f"  - {e}")
        if strict:
            log("QC-гейт строгий → падаем (немой/рассинхронный ролик не проходит).")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
