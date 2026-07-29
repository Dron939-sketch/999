#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
affected.py — какие продакшены задеты правкой.

Завод по умолчанию гнал ВЕСЬ манифест на каждый push: правка одного интро
стоила сорока минут раннера и переозвучки девяти чужих роликов. Этот модуль
отвечает на вопрос «что реально задето», чтобы CI рендерил только это.

Зависимости продакшена собираются ПО ФАКТУ, а не по списку в манифесте:
сценарий читается, из него достаются `import ... from "путь"` и вторые
аргументы `prop("id", "путь")`. Список в манифесте пришлось бы обновлять
руками при каждой новой декорации — и он бы врал ровно тогда, когда важен.

Глобальные пути (движок, сам завод, workflow) задевают ВСЁ: их правка меняет
каждый ролик, и выборочный рендер там опасен — регрессию заметят в релизе, а
не в CI. На них ответ `ALL`.

Использование:
    python3 tools/affected.py f1 f2 ...        # список изменённых файлов
    git diff --name-only A B | python3 tools/affected.py -
    python3 tools/affected.py --deps           # карта зависимостей (отладка)

Печатает по одному id продакшена в строку; `ALL` — гнать весь манифест;
пустой вывод — гнать нечего (правка не задела ни одного ролика).
"""

import argparse
import json
import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "tools" / "productions.json"

# Правка этих путей меняет ЛЮБОЙ ролик — выборочный рендер тут не экономит, а
# прячет регрессию. `tools/` сюда входит целиком: это и завод, и приёмщики, и
# сам манифест. Порог намеренно грубый — ложное «ALL» стоит раннера, ложное
# «ничего» стоит незамеченного дефекта в релизе.
GLOBAL_PREFIXES = ("src/", "tools/", "tests/")
GLOBAL_FILES = ("Cargo.toml", "Cargo.lock", ".github/workflows/render.yml")

# `import character freeman from "../assets/characters/freeman_rig"` и
# `import set pole from "../assets/sets/field-empty.svg"`.
RE_IMPORT = re.compile(r'\bfrom\s+"([^"]+)"')
# `prop("ochki", "../assets/props/glasses-alien.svg")` — нужен ВТОРОЙ аргумент.
RE_PROP = re.compile(r'\bprop\(\s*"[^"]*"\s*,\s*"([^"]+)"')


def _rel(path):
    """Путь относительно корня репозитория, в posix-виде."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None


def scene_deps(anim_rel, _seen=None):
    """Файлы, от которых зависит сценарий: он сам + его ассеты (транзитивно).

    Ассет может быть папкой (риг персонажа — это каталог с svg и позами), тогда
    в зависимости уходит префикс папки: правка любой её детали задевает ролик.
    """
    seen = _seen if _seen is not None else set()
    if anim_rel in seen:
        return seen
    seen.add(anim_rel)
    src = ROOT / anim_rel
    if not src.exists():
        return seen
    text = src.read_text(encoding="utf-8", errors="replace")
    for m in list(RE_IMPORT.finditer(text)) + list(RE_PROP.finditer(text)):
        target = (src.parent / m.group(1)).resolve()
        rel = _rel(target)
        if rel is None:
            continue
        seen.add(rel)
        # Сценарий может импортировать сценарий — идём вглубь.
        if rel.endswith(".anim"):
            scene_deps(rel, seen)
    return seen


def deps_map(manifest=DEFAULT_MANIFEST):
    """id продакшена → множество путей, правка которых его задевает."""
    prods = json.loads(Path(manifest).read_text(encoding="utf-8"))["productions"]
    out = {}
    for p in prods:
        deps = scene_deps(p["anim"])
        if p.get("vo"):
            deps.add(p["vo"])
        for img in p.get("images", []):
            if img.get("out"):
                deps.add(img["out"])
        out[p["id"]] = deps
    return out


def affected(changed, manifest=DEFAULT_MANIFEST):
    """Список id по изменённым путям. `["ALL"]` — гнать всё."""
    # `git diff --name-only` отдаёт пути от корня репо и уже нормализованными,
    # но руками этот модуль зовут и с «./», и с «a/../b» — нормализуем, иначе
    # «tools/../README.md» попадёт под префикс `tools/` и даст ложное ALL.
    changed = [posixpath.normpath(c.strip()).lstrip("./")
               for c in changed if c.strip()]
    for c in changed:
        if c in GLOBAL_FILES or c.startswith(GLOBAL_PREFIXES):
            return ["ALL"]
    dmap = deps_map(manifest)
    hit = []
    for pid, deps in dmap.items():
        for c in changed:
            # Совпадение по файлу ИЛИ по префиксу папки (риг — каталог).
            if any(c == d or c.startswith(d.rstrip("/") + "/") for d in deps):
                hit.append(pid)
                break
    return hit


def main(argv=None):
    ap = argparse.ArgumentParser(description="Какие продакшены задеты правкой")
    ap.add_argument("paths", nargs="*", help="изменённые файлы; '-' — читать stdin")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--deps", action="store_true", help="печатать карту зависимостей")
    args = ap.parse_args(argv)

    if args.deps:
        for pid, deps in sorted(deps_map(Path(args.manifest)).items()):
            print(f"{pid}:")
            for d in sorted(deps):
                print(f"    {d}")
        return 0

    paths = args.paths
    if paths == ["-"] or not paths:
        paths = sys.stdin.read().splitlines()
    for pid in affected(paths, Path(args.manifest)):
        print(pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
