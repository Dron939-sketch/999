#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slovar.py — СЛОВАРЬ ПОВЕДЕНИЯ: чем персонаж занят, ПОКА ГОВОРИТ.

Замечание студии: «поведение персонажа однообразное». Приёмщик динамики
(`studio.lint_dinamika`) на это молчал, и не по недосмотру — он меряет другое:
сколько раз меняется СИЛУЭТ и сколько разных силуэтов за ролик. По его меркам
каталог здоров, и это правда: силуэт меняется, ролики разные.

Замер показал, где дефект живёт на самом деле — ВНУТРИ РЕПЛИКИ.

  · Речь занимает около 80% хронометража. Всё это время тело держит ОДНУ позу:
    полная поза внутри реплики сбрасывает липсинк, и это правило (речь важнее
    жеста). Менять можно только НАКЛАДКАМИ.
  · Накладок, которые не спорят с речью, в риге было мало: 25 ручных жестов —
    и РОВНО ОДНА мимическая, `blink`. Остальные 41 мимических слоя задают
    `mouth`, а рот принадлежит липсинку.
  · Отсюда счёт по каталогу: 8 смен ВЫРАЖЕНИЯ ЛИЦА внутри реплик на 16
    роликов. В четырнадцати из шестнадцати лицо стоит от первого слова до
    последнего — двигаются только рот по звуку и рука.

Однообразие, которое видит студия, — не бедность рига (в нём 140+ поз). Это
замороженное лицо на всю реплику плюс дежурная горстка жестов: восемь имён
(`calm`, `v_upor`, `point`, `open`, `smug`, `hips`, `raskryl`, `no`) стоят в
12–16 роликах из 16, а 36 телесных поз не использованы НИ РАЗУ.

ЧТО МЕРЯЕТСЯ ЗДЕСЬ — ровно то, чего не видит гейт динамики:

  1. ЛИЦО В РЕЧИ. Сколько раз выражение меняется внутри речевых блоков.
     Мера — на реплику, а не на минуту: длина реплик разная, а бит один.
  2. ЖЕСТ В РЕЧИ. То же для ручных накладок: сколько реплик проходят вообще
     без единого движения рукой.
  3. КОНЦЕНТРАЦИЯ СЛОВАРЯ. Доля событий, приходящаяся на пять самых частых
     имён ролика. Полсотни поз в риге ничего не стоят, если ролик собран из
     пяти.

ПОРОГИ СНЯТЫ С КАТАЛОГА, А НЕ ВЗЯТЫ ИЗ ГОЛОВЫ. Концентрация топ-5: медиана
44%, худший ролик 59% — порог 55%. Лицо и жест: нормы поставлены по тому,
что вообще возможно, потому что замер по каталогу тут нулевой, и любая
«медиана» была бы медианой дефекта.

ГЕЙТ МЯГКИЙ, И ЭТО НЕ ОСТОРОЖНОСТЬ. Долг не расчищен: по лицу в речи провалит
почти весь каталог. HARD-гейт с нерасчищенным долгом останавливает завод на
дефектах, которых сегодня никто не заказывал чинить, — на этом уже обжигались
(RABOTA-NAD-OSHIBKAMI §I).

Использование:
    python3 tools/slovar.py examples/lektorij/emocii.anim
    python3 tools/slovar.py --all
"""

import argparse
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = ROOT / "examples/assets/characters/freeman_rig/rig.json"

# Кости ТЕЛА — те же, что у приёмщика динамики: силуэт держат руки, ноги,
# корпус. Список продублирован осознанно: `studio.py` тянет за собой манифест,
# ffmpeg и ключи озвучки, а этот гейт обязан считаться мгновенно и без них.
BODY_BONES = frozenset((
    "torso", "cloak",
    "upper_arm_left", "forearm_left", "hand_left",
    "upper_arm_right", "forearm_right", "hand_right",
    "thigh_left", "shin_left", "thigh_right", "shin_right",
))
# Рты липсинка: это не мимика, а речь. В словарь поведения не идут.
VISEMES = frozenset(("visA", "visB", "visC", "visD", "visE", "visF",
                     "visC_acc", "visD_acc", "visE_acc", "talk", "gab"))

LICO_NA_REPLIKU = 0.5      # смен выражения на реплику
NEMYH_REPLIK_MAX = 0.34    # доля реплик вообще без движения рукой
TOP5_MAX = 0.55            # доля событий на пять самых частых имён


def rig_classes(rig_path=RIG):
    """(жесты рукой, выражения лица) — имена поз по тому, что они трогают.

    Оба класса — НАКЛАДКИ, которые не спорят с липсинком: у жеста нет `mouth`
    по построению (гейт `mouth_ownership`), у выражения — потому что его сюда
    пускают только без рта.
    """
    poses = json.loads(Path(rig_path).read_text(encoding="utf-8"))["poses"]
    ruki, lico = set(), set()
    for name, p in poses.items():
        if name in VISEMES:
            continue
        bones = set(p.get("bones", {}))
        if "mouth" in bones:
            continue                       # спорит с речью — внутрь реплики нельзя
        (ruki if bones & BODY_BONES else lico).add(name)
    return ruki, lico


def code(text):
    """Текст сценария без комментариев (в шапках те же слова стоят прозой)."""
    return re.sub(r"//[^\n]*", "", text)


def repliki(text):
    """Речевые блоки: [(список слоёв внутри блока)] по одному на реплику.

    Реплика в сценарии — это `together { X speaks for …; do { … } }`. Всё, что
    стоит в этом блоке накладками, звучит ОДНОВРЕМЕННО с речью; всё, что вне,
    играет между репликами. Разница принципиальная: между репликами доступен
    весь риг, внутри — только накладки.
    """
    out = []
    for m in re.finditer(r"together\s*\{", text):
        i, depth = m.end(), 1
        while i < len(text) and depth:
            depth += (text[i] == "{") - (text[i] == "}")
            i += 1
        blk = text[m.end():i - 1]
        if re.search(r"\bspeaks\s+for\b", blk):
            out.append(re.findall(r'overlays\s+"([a-z_0-9]+)"', blk))
    return out


def check(path):
    """→ (метрики, список претензий) по одному сценарию."""
    text = code(Path(path).read_text(encoding="utf-8"))
    ruki, lico = rig_classes()
    seq = [n for _, n in re.findall(r'(pose|overlays)\s+"([a-z_0-9]+)"', text)]
    seq = [n for n in seq if n not in VISEMES]
    blocks = repliki(text)
    if not seq or not blocks:
        return None, []

    n_lico = sum(1 for b in blocks for x in b if x in lico)
    nemyh = sum(1 for b in blocks if not any(x in ruki for x in b))
    c = Counter(seq)
    top5 = sum(v for _, v in c.most_common(5)) / len(seq)
    m = {"replik": len(blocks), "lico": n_lico, "nemyh": nemyh,
         "top5": top5, "imyon": len(c)}

    bad = []
    if n_lico < LICO_NA_REPLIKU * len(blocks):
        bad.append(
            f"выражение меняется {n_lico} раз(а) на {len(blocks)} реплик при норме "
            f"{LICO_NA_REPLIKU:.1f} на реплику — лицо стоит всю речь. Внутрь реплики "
            f"идут слои БЕЗ рта ({', '.join(sorted(lico)[:6])}…): рот занят липсинком")
    if nemyh > NEMYH_REPLIK_MAX * len(blocks):
        bad.append(
            f"{nemyh} из {len(blocks)} реплик без единого движения рукой при потолке "
            f"{NEMYH_REPLIK_MAX * 100:.0f}% — персонаж проговаривает их столбом")
    if top5 > TOP5_MAX:
        bad.append(
            f"пять самых частых имён держат {top5 * 100:.0f}% событий при потолке "
            f"{TOP5_MAX * 100:.0f}% (имён в ролике {len(c)}) — ролик собран из горстки поз")
    return m, bad


def main(argv):
    ap = argparse.ArgumentParser(description="Словарь поведения: чем занят персонаж во время речи")
    ap.add_argument("anim", nargs="*")
    ap.add_argument("--all", action="store_true", help="весь каталог сценариев")
    args = ap.parse_args(argv)

    files = args.anim or []
    if args.all:
        files = sorted(glob.glob(str(ROOT / "examples/**/*.anim"), recursive=True))
        files = [f for f in files if not Path(f).name.startswith((".", "_"))]
    if not files:
        ap.error("нужен .anim или --all")

    print("\n  СЛОВАРЬ ПОВЕДЕНИЯ — ЧЕМ ПЕРСОНАЖ ЗАНЯТ, ПОКА ГОВОРИТ\n")
    bad_total = 0
    for f in files:
        m, bad = check(f)
        if m is None:
            continue
        name = Path(f).name
        mark = "OK" if not bad else "──"
        print(f"    [{mark}] {name}: реплик {m['replik']}, смен лица в речи "
              f"{m['lico']}, немых реплик {m['nemyh']}, топ-5 {m['top5'] * 100:.0f}%, "
              f"имён {m['imyon']}")
        for b in bad:
            bad_total += 1
            print(f"         · {b}")
    if bad_total:
        print(f"\n  Претензий: {bad_total}. Гейт МЯГКИЙ — завод не останавливает.")
        print("  Разбор, почему так вышло и что с этим делать: RABOTA-NAD-OSHIBKAMI §XII.\n")
    else:
        print("\n  Персонаж живёт и во время речи, а не только между репликами.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
