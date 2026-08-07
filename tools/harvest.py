#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harvest.py — БИБЛИОТЕКА КАДРОВ ИЗ ОРИГИНАЛА: позы, ракурсы, мимика.

ЗАЧЕМ. Ракурсы и позы мы до сих пор либо рисовали, либо вычисляли, и оба пути
сегодня подвели: профиль остался анфасом с повёрнутым телом, три четверти не
отличается от четверти, затылок висит обручем. Между тем в репозитории лежит
семь с половиной минут ОРИГИНАЛА — около одиннадцати тысяч кадров, и в них
персонаж стоит в сотнях положений, включая те самые ракурсы.

Этот сборщик проходит видео, находит кадры с целой фигурой, меряет их и
складывает в библиотеку с описью. Дальше из неё можно выбирать — обводить
нужный ракурс, брать форму жеста, сверять мимику.

ЧТО МЕРЯЕТСЯ У КАЖДОГО КАДРА
  · рост фигуры и ширина плаща (доля роста) — по ним считается РАКУРС:
    анфас ≈1.0, профиль ≈0.7 от анфасной ширины;
  · маска: размер, доля роста, смещение от оси фигуры — на промежуточных
    ракурсах маска уезжает вбок, это и отличает 45° от 22°;
  · ЧИСЛО ТЁМНЫХ ПЯТЕН ВНУТРИ МАСКИ — это глаза и рот. Два-три = лицо к нам,
    один = профиль, ноль = спина. Тот же признак, по которому судит приёмщик
    разворота, поэтому числа сравнимы с нашими.

ОТБОР. Кадр берётся, только если фигура видна целиком (не касается кромок —
иначе рост неизвестен и все доли считать не от чего), выше, чем шире, и маска
найдена в верхней части тела. Эти условия отсеивают сверхкрупные планы,
предметы и надписи; без них в выборку лезли телефон и мясорубка — проверено.

ДЕДУПЛИКАЦИЯ. Соседние кадры почти одинаковы. Кадр пропускается, если его
силуэт отличается от предыдущего взятого меньше чем на порог: библиотека
должна быть набором РАЗНЫХ положений, а не поминутной раскадровкой.

Использование:
    python3 tools/harvest.py                       # все видео из корня
    python3 tools/harvest.py --fps 6 --out videos/harvest
    python3 tools/harvest.py --sheets              # контактные листы по ракурсам
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from karta import ROOT  # noqa: E402
from turnaround import label  # noqa: E402

INK = 90
LIGHT = 190
MIN_BODY = 0.004
DEDUP = 0.12          # доля изменившегося силуэта, ниже которой кадр — дубль


def flood_bg(light):
    lab = label(light)
    if not lab.max():
        return np.zeros_like(light, bool)
    edge = set(lab[0]) | set(lab[-1]) | set(lab[:, 0]) | set(lab[:, -1])
    edge.discard(0)
    return np.isin(lab, list(edge)) if edge else np.zeros_like(light, bool)


def analyse(g):
    """Кадр → замер фигуры или None. Условия отбора — в шапке файла."""
    h, w = g.shape
    dark = g < INK
    lab = label(dark)
    if not lab.max():
        return None
    n, i = max((int((lab == k).sum()), k) for k in range(1, lab.max() + 1))
    if n < MIN_BODY * h * w:
        return None
    body = lab == i
    ys, xs = np.nonzero(body)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    if y0 <= 1 or y1 >= h - 2:          # обрезана — рост неизвестен
        return None
    H = y1 - y0 + 1
    if H < 0.25 * h or (x1 - x0 + 1) > H:
        return None

    light = g > LIGHT
    inner = light & ~flood_bg(light)
    lw = label(inner)
    if not lw.max():
        return None
    _, j = max((int((lw == k).sum()), k) for k in range(1, lw.max() + 1))
    mask = lw == j
    my, mx = np.nonzero(mask)
    if len(my) < 40:
        return None
    mh, mw = my.max() - my.min() + 1, mx.max() - mx.min() + 1
    if not 0.12 <= mw / H <= 0.45:
        return None
    if (my.mean() - y0) / H > 0.45:     # маска должна быть в верхней части
        return None

    # ЧЕРТЫ ЛИЦА — тёмные пятна ВНУТРИ габарита маски, НЕ КАСАЮЩИЕСЯ его края.
    #
    # Первая версия искала тёмное «внутри маски», где маской было множество
    # СВЕТЛЫХ пикселей. Но глаза и рот — это ДЫРЫ в маске: тёмное по
    # определению не принадлежит светлому множеству, и условие было пустым
    # всегда. Все 39 собранных кадров получили ноль черт и метку «спина», хотя
    # на каждом видно лицо с двумя глазами.
    #
    # Правильный признак: берём габарит маски, в нём тёмные связные пятна, и
    # оставляем те, что НЕ касаются границы габарита — касающиеся это фон и
    # плащ вокруг овала, а не черты.
    y0m, y1m, x0m, x1m = my.min(), my.max(), mx.min(), mx.max()
    sub = g[y0m:y1m + 1, x0m:x1m + 1]
    feats = label(sub < INK)
    edge = set(feats[0]) | set(feats[-1]) | set(feats[:, 0]) | set(feats[:, -1])
    big = [k for k in range(1, feats.max() + 1)
           if k not in edge and (feats == k).sum() > 0.004 * mw * mh]

    # ширина плаща без рук — самый длинный сплошной тёмный отрезок на 45% роста
    row = y0 + int(H * 0.45)
    idx = np.flatnonzero(body[row])
    if not len(idx):
        return None
    cuts = np.flatnonzero(np.diff(idx) > 1)
    st = np.concatenate(([0], cuts + 1))
    en = np.concatenate((cuts, [len(idx) - 1]))
    cw = int((idx[en] - idx[st]).max()) + 1

    return {
        "h": H, "cloak_w": cw / H,
        "mask_w": mw / H, "mask_h": mh / H,
        # смещение маски от оси ФИГУРЫ — на промежуточных ракурсах она уезжает
        "mask_dx": (mx.mean() - (x0 + x1) / 2) / H,
        "feats": len(big),
        "box": [x0, y0, x1, y1],
        "body": body,
    }


def guess_view(m):
    """Грубая классификация ракурса по числу черт и ширине плаща."""
    f, cw = m["feats"], m["cloak_w"]
    if f == 0:
        return "спина"
    if f == 1:
        return "профиль"
    if abs(m["mask_dx"]) > 0.045:
        return "три четверти"
    return "анфас"


def scan(video, fps, out, seen):
    rows = []
    # РАЗБОР НА МЕЛКОМ КАДРЕ, ВЫРЕЗКА ИЗ ПОЛНОГО. Поиск связных компонент на
    # 1280×720 в чистом numpy съедал всё время: первый прогон убился по
    # таймауту, успев 19 кадров из нескольких тысяч. Для классификации ракурса
    # хватает 480×270 — маска и черты лица там ещё различимы, — а вырезка
    # делается из полноразмерного кадра, чтобы библиотека годилась для обводки.
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
                        "-vf", f"fps={fps},scale=480:270", f"{d}/s%06d.png"],
                       check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
                        "-vf", f"fps={fps},scale=1280:720", f"{d}/f%06d.png"],
                       check=True)
        prev = None
        for f in sorted(Path(d).glob("s*.png")):
            g = np.asarray(Image.open(f).convert("L"))
            m = analyse(g)
            if m is None:
                prev = None
                continue
            if prev is not None and prev.shape == m["body"].shape:
                diff = (prev ^ m["body"]).sum() / max(prev.sum(), 1)
                if diff < DEDUP:
                    continue
            prev = m["body"]
            view = guess_view(m)
            idx = len(seen)
            x0, y0, x1, y1 = m["box"]
            pad = int(m["h"] * 0.06)
            K = 1280 / 480                      # мелкий кадр -> полный
            full = Path(str(f).replace("/s", "/f"))
            crop = Image.open(full).convert("RGB").crop(
                (max(int((x0 - pad) * K), 0), max(int((y0 - pad) * K), 0),
                 int((x1 + pad) * K), int((y1 + pad) * K)))
            name = f"{idx:04d}_{view}.png"
            crop.save(out / name)
            rows.append({"file": name, "video": Path(video).name,
                         "frame": int(f.stem[1:]), "t": round(int(f.stem[1:]) / fps, 2),
                         "view": view, "feats": m["feats"],
                         "cloak_w": round(m["cloak_w"], 3),
                         "mask_w": round(m["mask_w"], 3),
                         "mask_h": round(m["mask_h"], 3),
                         "mask_dx": round(m["mask_dx"], 3)})
            seen.append(name)
    return rows


def sheets(out, index):
    """Контактные листы по ракурсам — чтобы выбирать глазами, а не по числам."""
    from PIL import ImageDraw
    by = {}
    for r in index:
        by.setdefault(r["view"], []).append(r)
    for view, rows in by.items():
        rows = rows[:40]
        cols, TW, TH = 8, 150, 200
        n = len(rows)
        sh = Image.new("RGB", (cols * TW, ((n + cols - 1) // cols) * (TH + 14)), "white")
        d = ImageDraw.Draw(sh)
        for i, r in enumerate(rows):
            im = Image.open(out / r["file"]).convert("RGB")
            im.thumbnail((TW, TH))
            x, y = (i % cols) * TW, (i // cols) * (TH + 14)
            sh.paste(im, (x, y))
            d.text((x + 2, y + TH + 1), f"{r['t']}с", fill="black")
        p = out / f"_sheet_{view}.png"
        sh.save(p)
        print(f"  лист «{view}»: {len(rows)} кадров -> {p.name}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Библиотека кадров из оригинала")
    ap.add_argument("videos", nargs="*")
    ap.add_argument("--fps", type=float, default=6.0)
    ap.add_argument("--out", default="videos/harvest")
    ap.add_argument("--sheets", action="store_true")
    args = ap.parse_args(argv)

    vids = args.videos or [str(p) for p in ROOT.glob("*.mp4")]
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    index, seen = [], []
    for v in vids:
        rows = scan(v, args.fps, out, seen)
        print(f"  {Path(v).name[:44]:44} кадров в библиотеку: {len(rows)}")
        index += rows

    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    by = {}
    for r in index:
        by[r["view"]] = by.get(r["view"], 0) + 1
    print(f"\n  ВСЕГО {len(index)} кадров: " +
          ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda x: -x[1])))
    if args.sheets:
        sheets(out, index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
