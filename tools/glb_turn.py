#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
glb_turn.py — РАЗВОРОТ ИЗ 3D: силуэт под любым углом считается по геометрии.

ЗАЧЕМ. До сих пор ракурсы у нас либо рисовались руками (и девять рисунков не
обязаны быть одним телом), либо приближались эллипсом по двум видам
(`proxy3d.py`). Теперь есть настоящая модель-болван из Blender, и проекцию
можно считать точно: повернуть вершины вокруг вертикали и взять габарит.

Читает .glb (glTF 2.0 binary) чистым Python — Blender для этого не нужен, он
нужен был только чтобы модель СОЗДАТЬ.

ЧТО СЧИТАЕТСЯ. Для каждого угла — ширина силуэта в той же строке, по которой
меряет приёмщик разворота (45% высоты фигуры), нормированная на анфас. Тот же
ряд углов, что в `turnaround.py`, чтобы числа были сравнимы строка в строку с
тем, что нарисовано в риге.

ЧЕГО НЕ СЧИТАЕТСЯ. Это ПРОКСИ: плащ — гладкий конус, конечности — прямые
капсулы. Рваный подол, щетинистые плечи и настоящая форма маски здесь
отсутствуют, поэтому сравнивать надо ШИРИНЫ и ПРОПОРЦИИ, а не силуэт целиком.

Использование:
    python3 tools/glb_turn.py модель.glb
    python3 tools/glb_turn.py модель.glb --part cloak
"""

import argparse
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np

# Тот же ряд, что у приёмщика разворота.
ANGLES = [0, 22, 45, 90, 135, 180]
ROW_45 = 0.45

COMP = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
NUM = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load_glb(path):
    b = Path(path).read_bytes()
    magic, ver, _ = struct.unpack_from("<4sII", b, 0)
    if magic != b"glTF":
        sys.exit(f"{path}: не glTF-файл (magic={magic!r})")
    if ver != 2:
        sys.exit(f"{path}: версия glTF {ver}, поддерживается 2")
    off, js, bin_ = 12, None, b""
    while off < len(b):
        clen, ctype = struct.unpack_from("<I4s", b, off)
        data = b[off + 8: off + 8 + clen]
        t = ctype.strip(b"\x00")
        if t == b"JSON":
            js = json.loads(data)
        elif t == b"BIN":
            bin_ = data
        off += 8 + clen
    if js is None:
        sys.exit(f"{path}: нет JSON-чанка")
    return js, bin_


def accessor(js, bin_, idx):
    acc = js["accessors"][idx]
    bv = js["bufferViews"][acc["bufferView"]]
    fmt = COMP[acc["componentType"]]
    n = NUM[acc["type"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    count = acc["count"]
    size = struct.calcsize(fmt)
    stride = bv.get("byteStride") or size * n
    out = np.empty((count, n), dtype=np.float64)
    for i in range(count):
        o = start + i * stride
        out[i] = struct.unpack_from("<" + fmt * n, bin_, o)
    return out


def trs(node):
    """Матрица узла из translation/rotation/scale (или готовая matrix)."""
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    m = np.eye(4)
    s = node.get("scale", [1, 1, 1])
    m[:3, :3] = np.diag(s)
    if "rotation" in node:
        x, y, z, w = node["rotation"]
        r = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ])
        m[:3, :3] = r @ np.diag(s)
    t = node.get("translation", [0, 0, 0])
    m[:3, 3] = t
    return m


def gather(js, bin_, only=None):
    """Все вершины сцены в мировых координатах. {имя узла: (N,3)}."""
    parts = {}

    def walk(i, parent):
        node = js["nodes"][i]
        m = parent @ trs(node)
        if "mesh" in node:
            pts = []
            for prim in js["meshes"][node["mesh"]]["primitives"]:
                pi = prim["attributes"].get("POSITION")
                if pi is None:
                    continue
                v = accessor(js, bin_, pi)
                h = np.hstack([v, np.ones((len(v), 1))])
                pts.append((m @ h.T).T[:, :3])
            if pts:
                parts[node.get("name", f"node{i}")] = np.vstack(pts)
        for c in node.get("children", []):
            walk(c, m)

    roots = js["scenes"][js.get("scene", 0)].get("nodes", range(len(js["nodes"])))
    for r in roots:
        walk(r, np.eye(4))
    if only:
        parts = {k: v for k, v in parts.items() if k in only}
    return parts


# ВЕРТИКАЛЬ В glTF — ЭТО Y, А НЕ Z. Blender работает в Z-вверх, но экспортёр
# конвертирует в соглашение glTF (Y-вверх), и координаты в файле уже повёрнуты.
# Первый прогон мерил по Z и выдал абсурд: глубина 1.70 при росте 0.48 и голова
# шириной 0.77 роста. Абсурд был виден, а мог и не быть — если бы фигура
# случайно оказалась близка к кубу, ошибка прошла бы незамеченной.
UP = 1          # Y — вертикаль
SIDE = 0        # X — ширина кадра
DEPTH = 2       # Z — глубина


def widest(pts):
    """Наибольшая ширина проекции по всем вершинам части.

    СРЕЗ ПО ВЫСОТЕ ЗДЕСЬ НЕ РАБОТАЕТ, и это свойство модели, а не недосмотр:
    у конуса вершины лежат только на двух торцевых кольцах, между ними их нет.
    Тонкий срез на 45% высоты попадал в пустоту, и первый прогон выдал нули по
    всем углам. Резать по-настоящему значит пересекать треугольники плоскостью;
    для наших целей это лишнее.

    Берём наибольшую ширину части целиком. Для плаща-конуса она приходится на
    самое широкое кольцо, а проекция этого кольца при повороте следует ровно
    той формуле, которую мы и проверяем: sqrt(a²cos²θ + b²sin²θ). Мера одна и
    та же на всех углах, поэтому ОТНОШЕНИЯ сравнимы — а именно они и нужны.
    """
    if not len(pts):
        return 0.0
    return float(pts[:, SIDE].max() - pts[:, SIDE].min())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Разворот по 3D-модели")
    ap.add_argument("glb")
    ap.add_argument("--part", help="мерить только эту часть (напр. cloak)")
    args = ap.parse_args(argv)

    js, bin_ = load_glb(args.glb)
    parts = gather(js, bin_)
    if not parts:
        sys.exit("в модели нет вершин")

    allpts = np.vstack(list(parts.values()))
    z0, z1 = allpts[:, UP].min(), allpts[:, UP].max()
    H = z1 - z0
    W = allpts[:, SIDE].max() - allpts[:, SIDE].min()
    D = allpts[:, DEPTH].max() - allpts[:, DEPTH].min()
    print(f"\n  МОДЕЛЬ: {Path(args.glb).name}")
    print(f"  частей {len(parts)}: {', '.join(sorted(parts))}")
    print(f"  рост {H:.4f}, ширина {W:.4f} ({W/H:.3f} роста), "
          f"глубина {D:.4f} ({D/H:.3f} роста)")

    # пропорции, которые мы мерили по видео и по листу
    if "head" in parts:
        hp = parts["head"]
        hw = hp[:, SIDE].max() - hp[:, SIDE].min()
        hh = hp[:, UP].max() - hp[:, UP].min()
        print(f"\n  голова: ширина {hw/H:.3f} роста, высота {hh/H:.3f} роста, "
              f"H/W {hh/hw:.3f}")
        print(f"     замер видео:  0.202 / 0.287 / 1.425")
        print(f"     замер листа:  0.157 / 0.257 / 1.635")
        print(f"     наш риг:      0.272 / 0.420 / 1.546")

    # ПЛАЩ, А НЕ ВСЯ ФИГУРА. Приёмщик разворота меряет именно корпус: руки
    # тонкие и при повороте машут, их размах к ширине тела не относится.
    target = parts[args.part] if args.part else parts.get("cloak", allpts)
    print(f"\n  РАЗВОРОТ ПЛАЩА (наибольшая ширина, доля от анфаса)\n")
    print("  угол   доля    нарисовано в риге   расхождение")
    drawn = {0: 1.000, 22: 0.960, 45: 0.805, 90: 0.715, 135: 0.790, 180: 1.000}
    base = None
    for a in ANGLES:
        t = math.radians(a)
        # поворот вокруг ВЕРТИКАЛИ (Y в glTF): X и Z смешиваются, Y цел
        rot = np.array([[math.cos(t), 0, math.sin(t)],
                        [0, 1, 0],
                        [-math.sin(t), 0, math.cos(t)]])
        w = widest(target @ rot.T)
        if base is None:
            base = w
        frac = w / base if base else 0.0
        d = frac - drawn[a]
        print(f"  {a:4}°  {frac:.3f}      {drawn[a]:.3f}          {d:+.3f}"
              + ("   <<<" if abs(d) > 0.03 else ""))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ============================================================================
#  СИЛУЭТ КАРТИНКОЙ
# ============================================================================
#
#  Меры мерами, но форму судят глазом. Здесь модель растеризуется по-настоящему:
#  берутся ТРЕУГОЛЬНИКИ меша (не только вершины), проецируются ортографически и
#  заливаются. Это честный силуэт, а не облако точек — у примитивов вершины
#  стоят редко, и по ним форма читалась бы дырявой.

def triangles(js, bin_, only=None):
    """Треугольники сцены в мировых координатах: [(N,3,3)] по частям."""
    out = {}

    def walk(i, parent):
        node = js["nodes"][i]
        m = parent @ trs(node)
        if "mesh" in node:
            tris = []
            for prim in js["meshes"][node["mesh"]]["primitives"]:
                pi = prim["attributes"].get("POSITION")
                if pi is None:
                    continue
                v = accessor(js, bin_, pi)
                h = np.hstack([v, np.ones((len(v), 1))])
                w = (m @ h.T).T[:, :3]
                if "indices" in prim:
                    idx = accessor(js, bin_, prim["indices"]).astype(int).ravel()
                else:
                    idx = np.arange(len(w))
                tris.append(w[idx[: len(idx) // 3 * 3]].reshape(-1, 3, 3))
            if tris:
                out[node.get("name", f"node{i}")] = np.vstack(tris)
        for c in node.get("children", []):
            walk(c, m)

    roots = js["scenes"][js.get("scene", 0)].get("nodes", range(len(js["nodes"])))
    for r in roots:
        walk(r, np.eye(4))
    if only:
        out = {k: v for k, v in out.items() if k in only}
    return out


def silhouette(js, bin_, angle_deg, size=(420, 720), margin=0.06):
    """Залитый силуэт модели под углом. Возвращает PIL.Image (L)."""
    from PIL import Image, ImageDraw
    tris = triangles(js, bin_)
    allt = np.vstack(list(tris.values()))
    t = math.radians(angle_deg)
    rot = np.array([[math.cos(t), 0, math.sin(t)],
                    [0, 1, 0],
                    [-math.sin(t), 0, math.cos(t)]])
    p = allt.reshape(-1, 3) @ rot.T
    # рамка считается по АНФАСУ, одна на все углы: иначе каждый ракурс
    # масштабируется по себе и сравнивать их между собой нельзя.
    ref = allt.reshape(-1, 3)
    y0, y1 = ref[:, UP].min(), ref[:, UP].max()
    W, H = size
    span = (y1 - y0) * (1 + margin * 2)
    scale = H / span
    cx = W / 2.0

    img = Image.new("L", size, 235)
    d = ImageDraw.Draw(img)
    for tri in p.reshape(-1, 3, 3):
        pts = [(cx + v[SIDE] * scale, H - (v[UP] - y0 + span * margin) * scale)
               for v in tri]
        d.polygon(pts, fill=20)
    return img
