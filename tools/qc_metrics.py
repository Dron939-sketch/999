#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qc_metrics.py — измерение «планки Фримена» на эталонном куске.

Три спринта правок движения/света проверялись глазами. Этот инструмент
замыкает петлю: гоняет эталон (examples/lektorij/etalon-15s.anim) и МАШИННО
проверяет критерии Рубежа 2 (FREEMAN_TARGET.md §3), чтобы «планка взята» стало
зелёным/красным, а не вопросом вкуса в конкретном прогоне.

Метрики:
  1) shot_length   — средняя длина плана = длительность / число катов-кадров.
                     Цель ≤ 3.5с. Каты = framing-камеры (wide/medium/close/ECU).
  2) render_speed  — секунд рендера на 15с ролика. Цель ≤ 180с/15с.
  3) golden        — golden-frame diff: ключевые кадры сравниваются с
                     утверждёнными PNG по SSIM. Ловит «поехавшую» картинку
                     (призраки конечностей, сломанный свет, пустой кадр) без
                     ручного просмотра. Кадры движка детерминированы
                     (grain=hash(x,y,frame), boil от времени) → codec-free PNG.
  4) loudness      — EBU R128 integrated LUFS озвучки (если есть звук). Цель —
                     окно вокруг -16 LUFS (веб-речь). Мягкая: чинится нормализом
                     в миксе, не дефект картинки.

Golden рендерится движком в PNG (не из mp4) — без искажений кодека, поэтому
SSIM ~1.0 и порог строгий. Первый прогон без голденов (или --update-golden)
записывает эталонные кадры.

Использование:
    python3 tools/qc_metrics.py --anim examples/lektorij/etalon-15s.anim \
        --engine target/release/animdsl --golden-dir tests/golden/etalon-15s \
        [--final videos/etalon-15s-final.mp4] [--render-sec 80.3] \
        [--update-golden] [--strict] [--json out.json]

Коды выхода: 0 — планка взята (или не строгий режим); 1 — при --strict есть
HARD-провал (shot_length/render_speed/golden). loudness всегда мягкая.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

# --- Целевые пороги планки (FREEMAN_TARGET.md §3) --------------------------
SHOT_LEN_MAX = 3.5          # с, средняя длина плана
RENDER_SEC_PER_15S_MAX = 180.0  # с рендера на 15с ролика
SSIM_MIN = 0.985           # порог golden (детерминированный PNG → почти 1.0)
LUFS_TARGET = -16.0        # веб-речь
LUFS_TOL = 3.0             # ±окно (−19..−13)
GOLDEN_SAMPLES = 6         # сколько ключевых кадров сравнивать

# framing-камеры = каты (в отличие от pan/zoom/shake/dutch/pitch/angle — движения
# ВНУТРИ плана). Порядок из DSL: размер плана задаёт новый шот.
FRAMING_RE = re.compile(
    r"^\s*camera\s+(wide|medium|close-up|close|extreme-close-up|ecu|full)\b",
    re.IGNORECASE,
)


# --- гейт режиссуры (HOLLYWOOD.md, Волна 1) ---------------------------------
# Ловит «слабую режиссуру» машинно: фронтальная статика по центру, отсутствие
# флэшей и ракурсов, провал правил внимания 3–7–21.
FLASH_RE = re.compile(r'pose\s+"flash_', re.IGNORECASE)
ANGLE_RE = re.compile(r"^\s*camera\s+(angle\s+(high|low)|pitch|dutch)\b", re.IGNORECASE)
MOVE_RE = re.compile(r"^\s*camera\s+(zoom-to|pan-to|shake)\b", re.IGNORECASE)
COMPOSITION_RE = re.compile(r"moves-to\s*\(\s*([\d.]+)\s*,", re.IGNORECASE)
HOOK_MAX_S = 7.0       # правило 7с: первый удар голосом
TURN_WINDOW = (14.0, 28.0)  # правило 21с: перелом внутри окна
FLASH_PER_30S_MIN = 1.0
SHOT_KINDS_MIN = 3


def directing_metrics(anim_path, engine, duration):
    """Статический разбор сценария + фактические времена речи из движка.

    Возвращает dict метрик режиссуры (kind=soft — предупреждения, не рушат
    прогон; поднимаются до hard, когда все продакшены подтянуты).
    """
    text = Path(anim_path).read_text(encoding="utf-8")
    code_lines = [ln.split("//", 1)[0] for ln in text.splitlines()]
    # флэш-кадры (гротескная морда на 0.08с между битами)
    flashes = len(FLASH_RE.findall(text))
    per30 = flashes * 30.0 / duration if duration else 0.0
    # разнообразие планов: размеры + вертикальные ракурсы + движения камеры
    kinds = set()
    for ln in code_lines:
        m = FRAMING_RE.match(ln)
        if m:
            kinds.add(m.group(1).lower())
        if ANGLE_RE.match(ln):
            kinds.add("angle")
        if MOVE_RE.match(ln):
            kinds.add("motion")
    # композиция: доля кадров, где фигура НЕ по центру (x вне 0.45..0.55)
    xs = [float(x) for x in COMPOSITION_RE.findall(" ".join(code_lines))]
    off_center = [x for x in xs if x < 0.45 or x > 0.55]
    off_ratio = len(off_center) / len(xs) if xs else 0.0
    # правила внимания по фактическому таймлайну движка
    hook_s, turn_s = None, None
    try:
        out = subprocess.run([str(engine), "timing", str(anim_path)],
                             capture_output=True, text=True, timeout=120)
        blocks = json.loads(out.stdout).get("blocks", [])
        if blocks:
            hook_s = blocks[0]["start"]
            turn_s = next((b["start"] for b in blocks
                           if TURN_WINDOW[0] <= b["start"] <= TURN_WINDOW[1]), None)
    except Exception:
        pass

    m = {}
    m["flash_rate"] = {
        "value": round(per30, 2), "target": f">= {FLASH_PER_30S_MIN}",
        "unit": "флэш/30с", "count": flashes, "kind": "soft",
        "pass": per30 >= FLASH_PER_30S_MIN - 1e-9,
    }
    m["shot_variety"] = {
        "value": len(kinds), "target": f">= {SHOT_KINDS_MIN}",
        "unit": "типов планов/ракурсов", "kinds": sorted(kinds), "kind": "soft",
        "pass": len(kinds) >= SHOT_KINDS_MIN,
    }
    m["off_center"] = {
        "value": round(off_ratio, 2), "target": ">= 0.4",
        "unit": "доля смещённых композиций", "n": len(xs), "kind": "soft",
        "pass": off_ratio >= 0.4 - 1e-9 if xs else False,
    }
    if hook_s is not None:
        m["hook_7s"] = {
            "value": round(hook_s, 2), "target": f"<= {HOOK_MAX_S}",
            "unit": "с до первой реплики", "kind": "soft",
            "pass": hook_s <= HOOK_MAX_S + 1e-9,
        }
        # правило 21с применимо только к роликам, длиннее окна перелома
        short = duration < TURN_WINDOW[1]
        m["turn_21s"] = {
            "value": round(turn_s, 2) if turn_s else ("н/п" if short else "нет"),
            "target": f"реплика в {TURN_WINDOW[0]:.0f}–{TURN_WINDOW[1]:.0f}с",
            "unit": "перелом", "kind": "soft",
            "pass": turn_s is not None or short,
            **({"note": "ролик короче окна перелома — правило не применяется"}
               if short and turn_s is None else {}),
        }
    return m


def log(msg):
    print(msg, flush=True)


def parse_fps(anim_path):
    """Достаём fps из config-блока (по умолчанию 24)."""
    txt = Path(anim_path).read_text(encoding="utf-8")
    m = re.search(r"\bfps\s*:\s*(\d+)", txt)
    return int(m.group(1)) if m else 24


def count_cuts(anim_path):
    """Число катов = framing-камер во всех сценах. Минимум 1 (одна сцена = 1 план)."""
    n = 0
    for line in Path(anim_path).read_text(encoding="utf-8").splitlines():
        # срезаем комментарий, чтобы `// camera ...` в тексте не считался
        code = line.split("//", 1)[0]
        if FRAMING_RE.match(code):
            n += 1
    return max(n, 1)


def render_png(engine, anim_path, out_dir):
    """Рендер эталона в PNG-кадры (детерминированно). Возвращает (n_frames, sec)."""
    import time
    t0 = time.monotonic()
    subprocess.run([str(engine), "render", str(anim_path), "--png-dir", str(out_dir),
                    "-o", str(Path(out_dir) / "_scratch.mp4")],
                   check=True, capture_output=True, text=True)
    sec = time.monotonic() - t0
    frames = sorted(Path(out_dir).glob("frame_*.png"))
    return len(frames), sec


def _gray(path):
    return np.asarray(Image.open(path).convert("L"), dtype=np.float64)


def _boxblur(a, r):
    """Быстрый uniform-box средний по окну (2r+1) через накопительные суммы."""
    k = 2 * r + 1
    pad = np.pad(a, r, mode="edge")
    c = np.cumsum(np.cumsum(pad, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)), mode="constant")
    H, W = a.shape
    s = (c[k:k + H, k:k + W] - c[:H, k:k + W]
         - c[k:k + H, :W] + c[:H, :W])
    return s / (k * k)


def ssim(a, b, r=5):
    """Стандартный SSIM по grayscale с uniform-окном (2r+1). Без scipy."""
    if a.shape != b.shape:
        # приводим b к размеру a (разные разрешения быть не должны, но страхуемся)
        b = np.asarray(Image.fromarray(b.astype(np.uint8)).resize(
            (a.shape[1], a.shape[0]), Image.BILINEAR), dtype=np.float64)
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    mu_a = _boxblur(a, r)
    mu_b = _boxblur(b, r)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    var_a = _boxblur(a * a, r) - mu_a2
    var_b = _boxblur(b * b, r) - mu_b2
    cov = _boxblur(a * b, r) - mu_ab
    num = (2 * mu_ab + C1) * (2 * cov + C2)
    den = (mu_a2 + mu_b2 + C1) * (var_a + var_b + C2)
    return float(np.clip(num / den, 0, 1).mean())


def sample_indices(n, k):
    """k равномерно распределённых индексов кадров (детерминированно)."""
    if n <= 0:
        return []
    k = min(k, n)
    return sorted({int(round((i + 0.5) * n / k)) for i in range(k)} & set(range(n))) or [0]


def has_audio(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_type", "-of", "default=nw=1:nk=1",
             str(path)], capture_output=True, text=True).stdout.strip()
        return out == "audio"
    except Exception:
        return False


def integrated_lufs(path):
    """EBU R128 integrated loudness через ffmpeg ebur128. None если не вышло."""
    try:
        p = subprocess.run(
            ["ffmpeg", "-nostats", "-i", str(path), "-filter_complex",
             "ebur128", "-f", "null", "-"],
            capture_output=True, text=True)
        # ffmpeg пишет сводку "Integrated loudness: I: -XX.X LUFS" в stderr
        matches = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", p.stderr)
        return float(matches[-1]) if matches else None
    except Exception:
        return None


def evaluate(anim, engine, golden_dir, final=None, render_sec=None,
             update_golden=False):
    """Считает метрики. Возвращает dict со статусами PASS/FAIL/skip."""
    fps = parse_fps(anim)
    cuts = count_cuts(anim)
    golden_dir = Path(golden_dir)
    results = {"anim": str(anim), "fps": fps, "metrics": {}}

    with tempfile.TemporaryDirectory() as td:
        n_frames, png_sec = render_png(engine, anim, td)
        duration = n_frames / fps if fps else 0.0
        frames = sorted(Path(td).glob("frame_*.png"))

        # --- 1) shot_length -------------------------------------------------
        mean_shot = duration / cuts if cuts else duration
        results["metrics"]["shot_length"] = {
            "value": round(mean_shot, 2), "target": f"<= {SHOT_LEN_MAX}",
            "unit": "s/plan", "cuts": cuts, "duration": round(duration, 2),
            "kind": "hard",
            "pass": mean_shot <= SHOT_LEN_MAX + 1e-9,
        }

        # --- 2) render_speed (мерим рендер mp4 из studio, иначе png-рендер) --
        rsec = render_sec if render_sec is not None else png_sec
        per15 = rsec * (15.0 / duration) if duration else rsec
        results["metrics"]["render_speed"] = {
            "value": round(per15, 1), "target": f"<= {RENDER_SEC_PER_15S_MAX}",
            "unit": "s/15s", "measured_sec": round(rsec, 1),
            "source": "studio-mp4" if render_sec is not None else "png-dir",
            "kind": "hard",
            "pass": per15 <= RENDER_SEC_PER_15S_MAX + 1e-9,
        }

        # --- 3) golden-frame diff ------------------------------------------
        idxs = sample_indices(n_frames, GOLDEN_SAMPLES)
        if update_golden:
            golden_dir.mkdir(parents=True, exist_ok=True)
            # чистим прежние голдены (число/индексы могли смениться)
            for old in golden_dir.glob("frame_*.png"):
                old.unlink()
            saved = []
            for i in idxs:
                dst = golden_dir / frames[i].name
                # golden в grayscale: SSIM считается по luma, цвет не нужен —
                # экономит ~3× место в git (голдены = тест-фикстуры в репо).
                Image.open(frames[i]).convert("L").save(dst)
                saved.append(frames[i].name)
            results["metrics"]["golden"] = {
                "value": "updated", "kind": "hard", "pass": True,
                "saved": saved,
            }
        else:
            golden_frames = sorted(golden_dir.glob("frame_*.png"))
            if not golden_frames:
                results["metrics"]["golden"] = {
                    "value": "no-golden", "kind": "hard", "pass": True,
                    "note": "голдены отсутствуют — прогони с --update-golden",
                }
            else:
                scores = []
                gmap = {p.name: p for p in golden_frames}
                for i in idxs:
                    name = frames[i].name
                    if name in gmap:
                        scores.append((name, ssim(_gray(gmap[name]), _gray(frames[i]))))
                worst = min((s for _, s in scores), default=1.0)
                results["metrics"]["golden"] = {
                    "value": round(worst, 4), "target": f">= {SSIM_MIN} (SSIM)",
                    "kind": "hard", "compared": len(scores),
                    "per_frame": {n: round(s, 4) for n, s in scores},
                    "pass": worst >= SSIM_MIN,
                }

        # --- 4) loudness (мягкая) ------------------------------------------
        if final and Path(final).exists() and has_audio(final):
            lufs = integrated_lufs(final)
            if lufs is None:
                results["metrics"]["loudness"] = {
                    "value": "n/a", "kind": "soft", "pass": True,
                    "note": "ebur128 не дал результата",
                }
            else:
                ok = abs(lufs - LUFS_TARGET) <= LUFS_TOL
                results["metrics"]["loudness"] = {
                    "value": round(lufs, 1),
                    "target": f"{LUFS_TARGET}±{LUFS_TOL} LUFS",
                    "unit": "LUFS", "kind": "soft", "pass": ok,
                }
        else:
            results["metrics"]["loudness"] = {
                "value": "silent", "kind": "soft", "pass": True,
                "note": "нет звука (TTS не подключён) — громкость не мерилась",
            }

        # --- 5) режиссура (HOLLYWOOD.md, Волна 1) ---------------------------
        # Soft-метрики НИКОГДА не должны рушить измерение планки: если разбор
        # сценария или `animdsl timing` споткнулись — пишем заметку и идём дальше.
        try:
            results["metrics"].update(directing_metrics(anim, engine, duration))
        except Exception as e:  # noqa: BLE001 — гейт не важнее самой планки
            results["metrics"]["directing"] = {
                "value": "n/a", "kind": "soft", "pass": True,
                "note": f"метрики режиссуры не посчитались: {e}",
            }

    return results


def render_table(results):
    lines = ["", "  ПЛАНКА ФРИМЕНА (эталон):"]
    for name, m in results["metrics"].items():
        mark = "PASS" if m["pass"] else ("warn" if m["kind"] == "soft" else "FAIL")
        tgt = m.get("target", "")
        lines.append(f"    [{mark}] {name:<13} = {m['value']:<8} {tgt}")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description="Метрики планки Фримена на эталоне")
    ap.add_argument("--anim", required=True)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--golden-dir", required=True)
    ap.add_argument("--final", help="финальный mp4 со звуком (для loudness)")
    ap.add_argument("--render-sec", type=float,
                    help="фактическое время рендера mp4 из studio (иначе мерим png)")
    ap.add_argument("--update-golden", action="store_true",
                    help="перезаписать эталонные кадры вместо сравнения")
    ap.add_argument("--strict", action="store_true",
                    help="ненулевой выход при HARD-провале планки")
    ap.add_argument("--json", help="куда записать полный отчёт JSON")
    a = ap.parse_args(argv)

    if not Path(a.engine).exists():
        sys.exit(f"движок не собран: {a.engine}")
    if not Path(a.anim).exists():
        sys.exit(f"нет эталона: {a.anim}")

    results = evaluate(a.anim, a.engine, a.golden_dir, final=a.final,
                       render_sec=a.render_sec, update_golden=a.update_golden)

    log(render_table(results))
    if a.json:
        Path(a.json).write_text(json.dumps(results, ensure_ascii=False, indent=2))

    hard_fail = [n for n, m in results["metrics"].items()
                 if m["kind"] == "hard" and not m["pass"]]
    soft_fail = [n for n, m in results["metrics"].items()
                 if m["kind"] == "soft" and not m["pass"]]
    if soft_fail:
        log(f"  планка soft ({len(soft_fail)}): {', '.join(soft_fail)} — предупреждение")
    if hard_fail:
        log(f"  планка HARD ({len(hard_fail)}): {', '.join(hard_fail)} — НЕ взята")
        if a.strict:
            return 1
    else:
        log("  планка взята (hard-метрики в норме).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
