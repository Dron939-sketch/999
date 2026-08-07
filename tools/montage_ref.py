#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
montage_ref.py — снять МОНТАЖ и КАМЕРУ с готового видео.

В семье измерителей уже есть форма (compare_ref), физика движения (motion_ref),
населённость кадра (scene_ref) и фактура линии (ink_metrics). Все они смотрят
ВНУТРЬ кадра. Никто не мерит слой выше — как кадры сменяют друг друга: ритм
катов, разброс крупностей, где фигура стоит в раме.

Это слепое пятно дорого стоило. Планка (qc_metrics) считает длину плана и
композицию ПО ТЕКСТУ сценария — и только на эталоне. Для девяти остальных
продакшенов режиссура не мерилась вообще, а по тексту не видно того, что видно
на экране: `shot medium` в сценарии и реальная крупность фигуры в кадре — разные
величины, потому что крупность задаётся ещё и масштабом фигуры, и её позицией.

Инструмент работает с ЛЮБЫМ mp4 — нашим и оригинальным, — поэтому даёт то, чего
не даёт статический разбор: прямое сравнение с подлинником в одних единицах.

Метрики:

  * shots_min    — катов в минуту и средняя длина плана. Ритм монтажа.
  * shot_len_p50 — медианная длина плана: среднее врёт, когда есть один
                   длинный монолог и десяток врезок;
  * flash_share  — доля планов короче 0.4с. Врезка-удар — фирменный приём
                   оригинала, у нас её может не быть вовсе;
  * long_share   — доля ЭКРАННОГО ВРЕМЕНИ, проведённого в планах длиннее 6с.
                   Это и есть ощущение «ролик стоит на месте»;
  * scale_*      — гистограмма крупностей по высоте силуэта в кадре:
                   wide (<0.35 высоты кадра) / medium (0.35–0.6) /
                   close (0.6–0.85) / ecu (>0.85);
  * scale_var    — разброс крупности (СКО доли высоты). Одна крупность весь
                   ролик = ноль;
  * scale_jump   — доля катов, меняющих КЛАСС крупности. Кат без смены
                   крупности глаз читает как дёрганье, а не как монтаж;
  * off_center   — доля экранного времени, когда центр силуэта вне 0.45..0.55
                   по ширине. Фигура, вечно стоящая по центру, — театр, не кино;
  * churn        — доля кадров, где ПЕРЕРИСОВАН персонаж без смены плана. Это
                   покадровая рисовка оригинала: фон стоит, фигура каждый раз
                   новая. Интерполяция скелета даёт околонулевой churn.

Как отличается кат от нового рисунка: кадр бьётся на сетку блоков, считается
доля блоков, чья средняя яркость скакнула. Склейка двигает ВЕСЬ кадр вместе с
фоном (больше половины блоков), новый рисунок персонажа — только площадь под
фигурой. Без этого разделения замер вырождается в «каждый кадр — план»: у
оригинала очереди перерисовок идут подряд по десятку кадров.

Наплывов у оригинала нет, поэтому детектора жёстких склеек достаточно.

ТОЧНОСТЬ. На размеченном вручную окне оригинала (part 00, 60–70с) детектор
находит все склейки, но добавляет примерно столько же лишних — переходы через
пустое поле он режет надвое. Инструмент годится для СРАВНЕНИЯ роликов в одних
единицах и для порядка величины, но не для точного числа планов: разрыв между
нами и оригиналом здесь кратный, и на выводы эта погрешность не влияет.

Силуэт отделяется не порогом по «тёмному», а отклонением от МОДЫ яркости кадра:
у оригинала есть и чёрное на светлом поле, и белое на чёрном, и фиксированный
порог на второй половине ломается.

Использование:
    python3 tools/montage_ref.py "Mr. Freeman, part 00.mp4" --label оригинал
    python3 tools/montage_ref.py videos/*.mp4 --json out.json
    python3 tools/montage_ref.py наш.mp4 --ref оригинал.mp4   # таблица разрыва
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

# --- Параметры замера ------------------------------------------------------
SAMPLE_W, SAMPLE_H = 160, 90   # анализ идёт на уменьшенном кадре: монтаж и
                               # крупность — крупные величины, детали только
                               # добавляют шум и время
SAMPLE_FPS = 24.0              # нативная частота рисованного: на 12 к/с наплыв
                               # и врезка в один кадр неразличимы, и детектор
                               # дробит один переход на очередь катов
BLOCK = 10                     # сторона блока сетки, в пикселях уменьшенного
                               # кадра: 16×9 блоков на кадр
BLOCK_DELTA = 15               # блок считается изменившимся при таком скачке
                               # средней яркости
CUT_BLOCKS = 0.40              # кат: изменилась такая доля блоков кадра —
                               # поехала раскладка, а не только фигура. Порог
                               # подобран по размеченному вручную окну
                               # оригинала (part 00, 60–70с): выше — теряются
                               # склейки внутри одного фона, ниже — в каты
                               # уходят крупные перерисовки
CHURN_BLOCKS = 0.12            # смена рисунка: изменилась область размером с
                               # фигуру, фон на месте
MIN_SHOT_S = 2.0 / 24          # два кадра подряд — минимальный план
FLASH_MAX_S = 0.4              # план короче — врезка-удар
LONG_MIN_S = 6.0               # план длиннее — «ролик стоит»
MASK_DELTA = 55                # отклонение от моды яркости → силуэт (запасной
                               # путь, когда дисперсия не разделяет)
MOTION_DELTA = 18              # отличие пикселя от фона плана → фигура
MOTION_MIN_PX = 20             # меньше — в кадре никого (пустое поле, титр)
EDGE_TRIM = 0.02               # доля крайних пикселей маски, отбрасываемая при
                               # поиске габарита (грязь по краям кадра)

SCALE_BINS = (("wide", 0.0, 0.35), ("medium", 0.35, 0.60),
              ("close", 0.60, 0.85), ("ecu", 0.85, 10.0))


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def load_gray(path):
    """Видео → массив (N, H, W) серых кадров на SAMPLE_FPS."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(path),
           "-vf", f"fps={SAMPLE_FPS},scale={SAMPLE_W}:{SAMPLE_H}",
           "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (SAMPLE_W * SAMPLE_H)
    return np.frombuffer(raw[:n * SAMPLE_W * SAMPLE_H],
                         dtype=np.uint8).reshape(n, SAMPLE_H, SAMPLE_W)


def block_change(frames):
    """Доля блоков сетки, изменившихся между соседними кадрами.

    Порог по средней яркости всего кадра не различает две разные вещи: склейку
    (уехал ВЕСЬ кадр вместе с фоном) и новый рисунок персонажа на том же фоне.
    У Фримена и то и другое идёт очередями, и без разделения замер превращается
    в «каждый кадр — план». Блочная сетка разводит их по площади изменения.
    """
    h, w = frames.shape[1:]
    gh, gw = h // BLOCK, w // BLOCK
    grid = frames[:, :gh * BLOCK, :gw * BLOCK].astype(np.float32)
    grid = grid.reshape(len(frames), gh, BLOCK, gw, BLOCK).mean(axis=(2, 4))
    return (np.abs(np.diff(grid, axis=0)) > BLOCK_DELTA).mean(axis=(1, 2))


def find_cuts(frames):
    """(индексы начал планов, доля кадров со сменой рисунка).

    Кат — изменилось больше CUT_BLOCKS блоков. Смена рисунка (churn) — больше
    CHURN_BLOCKS, но меньше ката: фигура перерисована, фон стоит.
    """
    ch = block_change(frames)
    hot = np.flatnonzero(ch >= CUT_BLOCKS) + 1
    # Наплыв и затемнение дают ОЧЕРЕДЬ соседних срабатываний — это один переход,
    # а не десять катов. Схлопываем каждую непрерывную серию в её пик. На 24 к/с
    # это безопасно: настоящая врезка длиной в 2 кадра оставляет между
    # срабатываниями разрыв, наплыв — нет.
    starts = [0]
    for run in np.split(hot, np.flatnonzero(np.diff(hot) > 1) + 1):
        if not len(run):
            continue
        i = int(run[np.argmax(ch[run - 1])])
        if (i - starts[-1]) >= MIN_SHOT_S * SAMPLE_FPS:
            starts.append(i)
    churn = float(((ch >= CHURN_BLOCKS) & (ch < CUT_BLOCKS)).mean())
    return starts, churn


def subject_frames(seg):
    """[(доля высоты кадра, центр по x)] для КАЖДОГО кадра плана.

    Габарит на весь план разом не годится: внутри плана есть зум и проезд, и
    один габарит охватывает всю пройденную область — общий план с наездом
    читается как сверхкруп. Считаем покадрово.

    Фон плана — медианный кадр: декорация в нём стоит, персонаж размазывается.
    Вычитание медианы оставляет фигуру и на пустом поле, и в тюрьме, где маска
    «всё, что не фон» тянет в габарит стены и нары.

    Если движения в плане нет вовсе (статичная заставка, титр), медиана равна
    кадру и разница пуста — тогда откат на маску по моде яркости.
    """
    bg = np.median(seg, axis=0)
    out = []
    for f in seg:
        mask = np.abs(f.astype(np.float32) - bg) > MOTION_DELTA
        if mask.sum() < MOTION_MIN_PX:
            hist = np.bincount(f.ravel(), minlength=256)
            mask = np.abs(f.astype(np.int16) - int(np.argmax(hist))) > MASK_DELTA
            if mask.sum() < MOTION_MIN_PX:
                out.append(None)
                continue
        rows = mask.sum(axis=1).astype(float)
        cols = mask.sum(axis=0).astype(float)

        def extent(profile):
            # габарит по накопленной массе: отбрасываем EDGE_TRIM с каждого
            # конца, чтобы одиночная грязь не растягивала замер на весь кадр
            cum = np.cumsum(profile) / profile.sum()
            lo = int(np.searchsorted(cum, EDGE_TRIM))
            hi = int(np.searchsorted(cum, 1.0 - EDGE_TRIM))
            return lo, max(hi, lo + 1)

        r0, r1 = extent(rows)
        c0, c1 = extent(cols)
        out.append(((r1 - r0) / f.shape[0], ((c0 + c1) / 2.0) / f.shape[1]))
    return out


def scale_class(h):
    for name, lo, hi in SCALE_BINS:
        if lo <= h < hi:
            return name
    return "ecu"


def measure(path):
    dur = probe_duration(path)
    frames = load_gray(path)
    if len(frames) < 4:
        raise SystemExit(f"{path}: слишком короткое видео")
    starts, churn = find_cuts(frames)
    bounds = starts + [len(frames)]

    shots, per_frame = [], []
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = frames[a:b]
        subj = subject_frames(seg)
        per_frame.extend(subj)
        seen = [x for x in subj if x is not None]
        shots.append({
            "start": a / SAMPLE_FPS,
            "len": (b - a) / SAMPLE_FPS,
            # крупность плана = МЕДИАНА покадровых: наезд внутри плана не должен
            # переводить весь план в тот класс, где он закончился
            "height": float(np.median([h for h, _ in seen])) if seen else None,
        })

    lens = np.array([s["len"] for s in shots])
    heights = np.array([s["height"] for s in shots if s["height"] is not None])
    classes = [scale_class(s["height"]) for s in shots if s["height"] is not None]

    # смена класса крупности на кате
    jumps = sum(1 for a, b in zip(classes[:-1], classes[1:]) if a != b)
    # композиция и гистограмма крупностей — ПОКАДРОВО: так наезд внутри плана
    # честно распределяется по классам, а секундная врезка весит секунду, а не
    # столько же, сколько двадцатисекундный монолог
    seen = [x for x in per_frame if x is not None]
    off_t = sum(1 for _, c in seen if not 0.45 <= c <= 0.55)
    with_c = len(seen) or 1

    hist = {name: 0.0 for name, _, _ in SCALE_BINS}
    for h, _ in seen:
        hist[scale_class(h)] += 1.0
    total = sum(hist.values()) or 1.0

    return {
        "file": Path(path).name,
        "duration": round(dur, 1),
        "shots": len(shots),
        "shots_min": round(len(shots) * 60.0 / dur, 1),
        "shot_len_mean": round(float(lens.mean()), 2),
        "shot_len_p50": round(float(np.median(lens)), 2),
        "flash_share": round(float((lens < FLASH_MAX_S).mean()), 2),
        "long_share": round(float(lens[lens > LONG_MIN_S].sum() / dur), 2),
        "scale_wide": round(hist["wide"] / total, 2),
        "scale_medium": round(hist["medium"] / total, 2),
        "scale_close": round(hist["close"] / total, 2),
        "scale_ecu": round(hist["ecu"] / total, 2),
        "scale_var": round(float(heights.std()), 3) if len(heights) else 0.0,
        "scale_jump": round(jumps / max(len(classes) - 1, 1), 2),
        "off_center": round(off_t / with_c, 2),
        "churn": round(churn, 2),
    }


ROWS = [
    ("планов в минуту", "shots_min", "больше — плотнее монтаж"),
    ("медианный план, с", "shot_len_p50", "меньше — резче"),
    ("врезок (<0.4с)", "flash_share", "доля планов-ударов"),
    ("время в планах >6с", "long_share", "доля хронометража"),
    ("крупности: wide", "scale_wide", ""),
    ("            medium", "scale_medium", ""),
    ("            close", "scale_close", ""),
    ("            ecu", "scale_ecu", ""),
    ("разброс крупности", "scale_var", "СКО доли высоты"),
    ("кат меняет крупность", "scale_jump", "доля катов"),
    ("фигура не по центру", "off_center", "доля времени"),
    ("смена рисунка", "churn", "доля кадров"),
]


# --- Приёмка -------------------------------------------------------------
# Пороги сняты с оригинала (Mr. Freeman, part 00): ecu 0.26, воздух 0.74,
# смена крупности на кате 0.60. Ставим их с запасом — цель приёмщика не
# «сделай как оригинал по числу», а «не сползай обратно в сплошной сверхкруп».
#
# ГАТИМ ТОЛЬКО КРУПНОСТЬ. Ритм катов (shots_min, long_share) и churn считаются
# по доле изменившихся блоков кадра, а значит зависят от РАЗМЕРА фигуры: та же
# сцена с воздухом двигает меньше блоков, чем она же в обрезке. Сравнивать эти
# числа между разными кадрировками нельзя, и приёмщик на них не опирается —
# они остаются справочными. Крупность считается по габариту фигуры с вычетом
# фона и от размера не зависит.
ECU_MAX = 0.40
JUMP_MIN = 0.45


def gate(m):
    """Метрики приёмки в формате завода: value/target/unit/kind/pass."""
    return {
        "sverhkrup": {
            "value": m["scale_ecu"], "target": f"<= {ECU_MAX}",
            "unit": "доля времени, где фигура распирает кадр", "kind": "soft",
            "pass": m["scale_ecu"] <= ECU_MAX + 1e-9,
        },
        "smena_krupnosti": {
            "value": m["scale_jump"], "target": f">= {JUMP_MIN}",
            "unit": "доля катов, меняющих крупность", "kind": "soft",
            "pass": m["scale_jump"] >= JUMP_MIN - 1e-9,
        },
    }


def render_table(results, ref=None):
    """Колонки узкие и пронумерованы: имена файлов длинные и разъезжаются."""
    cols = ([("ОРИГ", ref)] if ref else []) + \
           [(str(i + 1), r) for i, r in enumerate(results)]
    w = 7
    lines = ["метрика".ljust(22) + "".join(t.rjust(w) for t, _ in cols)]
    lines.append("-" * len(lines[0]))
    for title, key, note in ROWS:
        row = title.ljust(22) + "".join(f"{r[key]:.2f}".rjust(w) for _, r in cols)
        lines.append(row + (f"   {note}" if note else ""))
    lines.append("")
    lines.append("длительность".ljust(22)
                 + "".join(f"{r['duration']:.0f}с".rjust(w) for _, r in cols))
    lines.append("")
    for t, r in cols:
        lines.append(f"  {t} = {r['file']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Замер монтажа и камеры по видео")
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--ref", help="эталонное видео (оригинал) для сравнения")
    ap.add_argument("--json", help="куда сложить численный результат")
    ap.add_argument("--gate", action="store_true",
                    help="режим приёмщика: один ролик, отчёт с pass/fail")
    a = ap.parse_args(argv)

    if a.gate:
        m = measure(a.videos[0])
        report = {"metrics": gate(m), "raw": m}
        if a.json:
            Path(a.json).write_text(
                json.dumps(report, ensure_ascii=False, indent=1),
                encoding="utf-8")
        for name, g in report["metrics"].items():
            mark = "OK " if g["pass"] else "НЕТ"
            print(f"{mark} {name}: {g['value']} (цель {g['target']}) — {g['unit']}")
        return 0

    ref = measure(a.ref) if a.ref else None
    results = [measure(v) for v in a.videos]
    print(render_table(results, ref))
    if a.json:
        Path(a.json).write_text(
            json.dumps({"ref": ref, "videos": results},
                       ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
