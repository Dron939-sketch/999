#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
novye_pozy.py — позы, добавленные под «Эмоции», в виде исходника.

ПОЗЫ ЖИВУТ В rig.json, А ЗАВОДЯТСЯ ОТСЮДА — по той же причине, по которой
пропорции скелета заводит `apply_sculpt_proportions.py`, а не рука: рядом с
числами должно стоять, ПОЧЕМУ они такие. В `rig.json` 160 поз и ни одного
комментария; вернуться через месяц к «почему тут 116, а не 84» можно только
сюда.

Скрипт идемпотентен: имя, которое уже есть, перезаписывается. Прогонять после
любой правки углов и СМОТРЕТЬ КОНТАКТНЫЙ ЛИСТ — поза, не проверенная рендером,
в риг не кладётся (MIMICRY_LIBRARY.md).

    python3 tools/novye_pozy.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = ROOT / "examples/assets/characters/freeman_rig/rig.json"

# ============================================================================
#  РЕЧЕВЫЕ ЖЕСТЫ: только руки (+ голова). НИ РТА, НИ ГЛАЗ.
# ============================================================================
#  Рот принадлежит липсинку (mouth_ownership), поэтому этот класс — один из
#  двух, которые можно ставить ВНУТРИ реплики. Глаз тоже не трогаем: жест и
#  эмоция должны накладываться НЕЗАВИСИМО (слои копятся на последнюю полную
#  позу), иначе каждый жест тащит с собой одно выражение и комбинаций нет.
#
#  ЧТОБЫ ЖЕСТ ЧИТАЛСЯ, РУКА ДОЛЖНА ОТОРВАТЬСЯ ОТ ПЛАЩА. Первая партия это
#  показала на контактном листе: при `upper_arm` меньше ~45° кисть остаётся
#  внутри чёрного пятна балахона и жеста в кадре нет вовсе, как бы точно ни
#  был выставлен локоть. Плащ у Фримена — сплошная заливка, силуэт читается
#  только по тому, что из неё торчит.
RUKI = {
  # ── указание и адрес ──────────────────────────────────────────────────────
  "palec_vverh": (0.28, {                      # «одна мысль», «внимание»
    "upper_arm_right": {"rotation": -58, "z_order": 6},
    "forearm_right": {"rotation": -104, "z_order": 6},
    "hand_right": {"part": "hand_point_r", "z_order": 7, "rotation": 8},
    "upper_arm_left": {"rotation": 28}, "forearm_left": {"rotation": -12},
    "head": {"rotation": 2}}),
  "vniz": (0.3, {                              # «здесь и сейчас», к земле
    "upper_arm_right": {"rotation": -58, "z_order": 6},
    "forearm_right": {"rotation": 62, "z_order": 6},
    "hand_right": {"part": "hand_point_r", "z_order": 7, "rotation": -46},
    "upper_arm_left": {"rotation": 30}, "forearm_left": {"rotation": -14},
    "head": {"rotation": -7}}),
  "manit": (0.26, {                            # «подойди-ка сюда»
    "upper_arm_right": {"rotation": -68, "z_order": 7},
    "forearm_right": {"rotation": -78, "z_order": 7},
    "hand_right": {"part": "hand_point_r", "z_order": 8, "rotation": 96},
    "upper_arm_left": {"rotation": 28}, "forearm_left": {"rotation": -12}}),
  # ── категоричность ────────────────────────────────────────────────────────
  "rubit": (0.16, {                            # ребром ладони — «отрезал»
    "upper_arm_right": {"rotation": -116, "z_order": 7},
    "forearm_right": {"rotation": 48, "z_order": 7},
    "hand_right": {"part": "hand_relax_r", "z_order": 8, "rotation": -24},
    "upper_arm_left": {"rotation": 30}, "forearm_left": {"rotation": -14},
    "head": {"rotation": -4}}),
  "stop_ladon": (0.22, {                       # ладонь вперёд — «стоп, погоди»
    "upper_arm_right": {"rotation": -82, "z_order": 7},
    "forearm_right": {"rotation": -30, "z_order": 7},
    "hand_right": {"part": "hand_open_r", "z_order": 8, "scale": [1.12, 1.12]},
    "upper_arm_left": {"rotation": 28}, "forearm_left": {"rotation": -12}}),
  # ── оценка, счёт, цена ────────────────────────────────────────────────────
  "dengi": (0.28, {                            # цена: кулак у груди, трёт
    "upper_arm_right": {"rotation": -74, "z_order": 7},
    "forearm_right": {"rotation": -72, "z_order": 7},
    "hand_right": {"part": "hand_fist_r", "z_order": 8},
    "upper_arm_left": {"rotation": 28}, "forearm_left": {"rotation": -12},
    "head": {"rotation": 3}}),
  "dve_storony": (0.34, {                      # «с одной стороны — с другой»
    "upper_arm_left": {"rotation": 34, "z_order": 5},
    "forearm_left": {"rotation": 44, "z_order": 5},
    "hand_left": {"part": "hand_offer", "z_order": 6},
    "upper_arm_right": {"rotation": -104, "z_order": 6},
    "forearm_right": {"rotation": -22, "z_order": 6},
    "hand_right": {"part": "hand_offer_r", "z_order": 7},
    "head": {"rotation": 4}}),
  # ── закрытость, ожидание, отстранение ─────────────────────────────────────
  "zakrylsya": (0.36, {                        # закрытая стойка: руки сомкнуты
    "upper_arm_left": {"rotation": 46, "z_order": 5},
    "forearm_left": {"rotation": -118, "z_order": 5},
    "hand_left": {"part": "hand_relax", "z_order": 5},
    "upper_arm_right": {"rotation": -46, "z_order": 6},
    "forearm_right": {"rotation": 118, "z_order": 6},
    "hand_right": {"part": "hand_relax_r", "z_order": 6}}),
  "ruki_za_spinu": (0.4, {                     # лекторская стойка, руки убраны
    "upper_arm_left": {"rotation": -16, "z_order": 1},
    "forearm_left": {"rotation": -54, "z_order": 1},
    "hand_left": {"part": "hand_relax", "z_order": 1},
    "upper_arm_right": {"rotation": 16, "z_order": 1},
    "forearm_right": {"rotation": 54, "z_order": 1},
    "hand_right": {"part": "hand_relax_r", "z_order": 1},
    "head": {"rotation": 3}}),
  "razvel": (0.3, {                            # «а что я могу» — слоем, без корпуса
    "upper_arm_left": {"rotation": 44, "z_order": 4},
    "forearm_left": {"rotation": 24, "z_order": 4},
    "hand_left": {"part": "hand_offer", "z_order": 5},
    "upper_arm_right": {"rotation": -44, "z_order": 4},
    "forearm_right": {"rotation": -24, "z_order": 4},
    "hand_right": {"part": "hand_offer_r", "z_order": 5}}),
  "u_viska": (0.26, {                          # у виска — «ты серьёзно?»
    "upper_arm_right": {"rotation": -96, "z_order": 7},
    "forearm_right": {"rotation": -84, "z_order": 7},
    "hand_right": {"part": "hand_point_r", "z_order": 8, "rotation": 54},
    "upper_arm_left": {"rotation": 28}, "forearm_left": {"rotation": -12},
    "head": {"rotation": 6}}),
}

# ============================================================================
#  ЭМОЦИИ ГЛАЗАМИ: ни рта, ни тела. КЛАСС, КОТОРОГО НЕ БЫЛО.
# ============================================================================
#  Замер рига: из 43 мимических слоёв 41 задаёт `mouth`, и потому НИ ОДИН из
#  них нельзя поставить внутри реплики — рот принадлежит липсинку, и слой либо
#  сдерётся ближайшей виземой, либо перебьёт её. Внутри реплики работал ровно
#  один слой: `blink`. То есть всю реплику — а это 80% хронометража — лицо
#  персонажа СТОЯЛО. Менялись только рот по звуку и руки.
#
#  Это и читается как однообразие: не «мало поз в риге» (их 141), а «во время
#  речи лицо недоступно».
#
#  Библиотека мимики (MIMICRY_LIBRARY.md §1) говорит прямо: ГЛАЗА — главный
#  носитель эмоции, рот вторичен, брови — акцент. Значит слой из одних глаз и
#  бровей — не обрезок полноценной мимики, а её ядро; рот в это время честно
#  занят речью.
#
#  АСИММЕТРИЯ — ТОЖЕ ОТТУДА (§4): «Клин слева и щель справа читаются как
#  перекос лица; симметричная пара — как ровный дежурный прищур. Асимметрия и
#  делает выражение живым, а не состоянием интерфейса.»
GLAZA = {
  "vzglyad": (0.3, {                           # ровно, прямо — возврат к нейтрали
    "eye_left": {"part": "eye_left"}, "eye_right": {"part": "eye_right"},
    "brow_left": {"part": "blank"}, "brow_right": {"part": "blank"}}),
  "prishchur": (0.26, {                        # снисхождение, «поймал»
    "eye_left": {"part": "eye_squint"}, "eye_right": {"part": "eye_squint"},
    "head": {"rotation": -3}}),
  "poimal": (0.24, {                           # ПЕРЕКОС: клин + щель (§4)
    "eye_left": {"part": "eye_angry_left"}, "eye_right": {"part": "eye_squint"},
    "head": {"rotation": -4}}),
  "klin": (0.2, {                              # приговор, угроза
    # БЕЗ БРОВЕЙ. Библиотека разрешает бровь в трёх группах (гнев, печаль,
    # скепсис), и я на это разрешение сослался — а студия, посмотрев кадр,
    # сказала коротко: брови не нужны. Кадр главнее правила, которое писалось
    # по другим кадрам. Клин глаза несёт приговор сам; бровь на белой маске
    # добавляет вторую чёрную отметку и превращает лицо в пиктограмму.
    "eye_left": {"part": "eye_angry_left"}, "eye_right": {"part": "eye_angry_right"},
    "brow_left": {"part": "blank"}, "brow_right": {"part": "blank"},
    "head": {"rotation": -5}}),
  "teplo": (0.34, {                            # дуга: нежность, издёвка-ласка
    "eye_left": {"part": "eye_arc"}, "eye_right": {"part": "eye_arc"},
    "head": {"rotation": 3}}),
  "doshlo": (0.16, {                           # шар: «до тебя дошло»
    "eye_left": {"part": "eye_shock"}, "eye_right": {"part": "eye_shock"},
    "head": {"rotation": 2}}),
  "gorech": (0.36, {                           # опущенный внешний угол, сочувствие
    "eye_left": {"part": "eye_sad"}, "eye_right": {"part": "eye_sad"},
    "head": {"rotation": 6}}),
  "somnenie": (0.28, {                         # скепсис, недоверие
    # Тоже БЕЗ БРОВИ (см. `klin`). Скепсис держится АСИММЕТРИЕЙ: щель слева,
    # ровный овал справа. Библиотека сама говорит, что перекос и делает
    # выражение живым, — бровь тут была подпоркой, без которой лучше.
    "eye_left": {"part": "eye_squint"}, "eye_right": {"part": "eye_right"},
    "brow_left": {"part": "blank"}, "brow_right": {"part": "blank"},
    "head": {"rotation": -2}}),
  "ostyl": (0.3, {                             # сузил: холод без злости
    "eye_left": {"scale": [0.729, 0.62]}, "eye_right": {"scale": [0.689, 0.58]}}),
  "raspahnul": (0.14, {                        # распахнул: интерес, «ого»
    "eye_left": {"scale": [0.82, 1.30]}, "eye_right": {"scale": [0.78, 1.24]},
    "head": {"rotation": 1}}),
}


# ============================================================================
#  ЗЕРКАЛА: тот же жест ДРУГОЙ РУКОЙ.
# ============================================================================
#  Самый дешёвый и самый честный способ перестать повторяться. В риге двадцать
#  односторонних жестов, и каждый умеет только свою сторону: `vdal` показывает
#  вправо, `k_sebe` бьёт себя в грудь левой, `u_viska` крутит справа. Режиссёр,
#  которому нужен второй указательный жест подряд, вынужден брать ДРУГОЙ жест —
#  или повторить тот же.
#
#  Для зрителя смена стороны — новый удар, а не повтор: силуэт другой,
#  композиция кадра другая, взгляд переезжает. Мерка это подтверждает
#  численно — зеркальная пара даёт низкий IoU силуэтов (tools/pozy_lint.py).
#
#  СЧИТАЕТСЯ, А НЕ ПИШЕТСЯ РУКАМИ. Двадцать поз по шесть костей — это сто
#  двадцать чисел, и одна опечатка в знаке даёт вывернутый локоть, который
#  никто не заметит до контактного листа. Отражение — механическая операция,
#  и делать её должна машина.
_PARY_KISTEJ = {
    "hand_open": "hand_open_r", "hand_point": "hand_point_r",
    "hand_relax": "hand_relax_r", "hand_offer": "hand_offer_r",
    "hand_fist": "hand_fist_r",
}
_KIST = {**_PARY_KISTEJ, **{v: k for k, v in _PARY_KISTEJ.items()}}


def zerkalo(bones):
    """Кости позы, отражённые слева направо.

    Меняются местами имена костей, знак поворота и рисунок кисти (у нас на
    каждую кисть два файла — левый и правый). Всё остальное — z-порядок,
    масштаб, смещение — стороны не имеет и переносится как есть.
    """
    out = {}
    for name, track in bones.items():
        novoe = (name.replace("_left", "_right") if name.endswith("_left")
                 else name.replace("_right", "_left") if name.endswith("_right")
                 else name)
        t = dict(track)
        if "rotation" in t:
            t["rotation"] = -t["rotation"]
        if "part" in t and t["part"] in _KIST:
            t["part"] = _KIST[t["part"]]
        if "offset" in t:
            t["offset"] = [-t["offset"][0], t["offset"][1]]
        out[novoe] = t
    return out


# Что отражаем. `gladit_grud*` НЕ отражается намеренно: это подпись-кольцо, она
# обязана быть одинаковой во всех роликах и в обоих концах каждого — иначе шов
# при зацикливании станет виден, ради чего всё и затевалось. `*_ochki` — не
# жесты, а варианты в очках.
ZERKALIT = [
    "vdal", "palec_vverh", "vniz", "manit", "rubit", "stop_ladon", "u_viska",
    "dengi", "zatylok", "dve_storony",
    "k_sebe", "otmahnulsya", "ruka_vverh", "wave", "vzves", "think",
]

# ============================================================================
#  НОВЫЕ КАТЕГОРИИ: то, чего в библиотеке не было ни на одну сторону.
# ============================================================================
#  Отбор тот же: рука обязана ТОРЧАТЬ ИЗ СИЛУЭТА, иначе жеста в кадре нет.
#  Всё, что происходит перед грудью, в этом риге не существует.
ESCHO = {
  "oba_vverh": (0.22, {                        # «ну и что теперь?» / сдаюсь
    "upper_arm_left": {"rotation": 134, "z_order": 4},
    "forearm_left": {"rotation": 22, "z_order": 4},
    "hand_left": {"part": "hand_open", "z_order": 5},
    "upper_arm_right": {"rotation": -134, "z_order": 4},
    "forearm_right": {"rotation": -22, "z_order": 4},
    "hand_right": {"part": "hand_open_r", "z_order": 5},
    "head": {"rotation": -2}}),
  "ladoni_vniz": (0.3, {                       # «тише», «спокойно»
    "upper_arm_left": {"rotation": 62, "z_order": 5},
    "forearm_left": {"rotation": 46, "z_order": 5},
    "hand_left": {"part": "hand_relax", "z_order": 6},
    "upper_arm_right": {"rotation": -62, "z_order": 5},
    "forearm_right": {"rotation": -46, "z_order": 5},
    "hand_right": {"part": "hand_relax_r", "z_order": 6}}),
  "razmer": (0.3, {                            # «вот столько» — величина
    "upper_arm_left": {"rotation": 76, "z_order": 6},
    "forearm_left": {"rotation": -50, "z_order": 6},
    "hand_left": {"part": "hand_relax", "z_order": 7},
    "upper_arm_right": {"rotation": -102, "z_order": 6},
    "forearm_right": {"rotation": 46, "z_order": 6},
    "hand_right": {"part": "hand_relax_r", "z_order": 7},
    "head": {"rotation": -3}}),
  "kulaki": (0.2, {                            # решимость, «взялись»
    "upper_arm_left": {"rotation": 54, "z_order": 5},
    "forearm_left": {"rotation": -62, "z_order": 5},
    "hand_left": {"part": "hand_fist", "z_order": 6},
    "upper_arm_right": {"rotation": -54, "z_order": 5},
    "forearm_right": {"rotation": 62, "z_order": 5},
    "hand_right": {"part": "hand_fist_r", "z_order": 6},
    "head": {"rotation": -4}}),
  "smel": (0.24, {                             # смёл в сторону: «это в сторону»
    "upper_arm_left": {"rotation": 96, "z_order": 6},
    "forearm_left": {"rotation": -20, "z_order": 6},
    "hand_left": {"part": "hand_open", "z_order": 7},
    "upper_arm_right": {"rotation": 34, "z_order": 5},
    "forearm_right": {"rotation": -34, "z_order": 5},
    "hand_right": {"part": "hand_relax_r", "z_order": 5},
    "head": {"rotation": 5}}),
  "za_uho": (0.26, {                           # «что-что?» — рука к уху
    "upper_arm_right": {"rotation": -112, "z_order": 7},
    "forearm_right": {"rotation": -92, "z_order": 7},
    "hand_right": {"part": "hand_open_r", "z_order": 8, "rotation": 40},
    "upper_arm_left": {"rotation": 28}, "forearm_left": {"rotation": -12},
    "head": {"rotation": 7}}),
  "kozyrek": (0.3, {                           # козырёк ко лбу: высматривает
    "upper_arm_left": {"rotation": 116, "z_order": 7},
    "forearm_left": {"rotation": -66, "z_order": 7},
    "hand_left": {"part": "hand_relax", "z_order": 8, "rotation": -30},
    "upper_arm_right": {"rotation": -28}, "forearm_right": {"rotation": 12},
    "head": {"rotation": -4}}),
  "oba_tuda": (0.28, {                         # обе указывают в одну точку
    "upper_arm_left": {"rotation": 92, "z_order": 6},
    "forearm_left": {"rotation": -8, "z_order": 6},
    "hand_left": {"part": "hand_point", "z_order": 7, "rotation": 66},
    "upper_arm_right": {"rotation": 40, "z_order": 5},
    "forearm_right": {"rotation": -46, "z_order": 5},
    "hand_right": {"part": "hand_point_r", "z_order": 6, "rotation": 60},
    "head": {"rotation": 6}}),
  "lokti": (0.32, {                            # локти в стороны, кисти вниз
    "upper_arm_left": {"rotation": 92, "z_order": 4},
    "forearm_left": {"rotation": -134, "z_order": 4},
    "hand_left": {"part": "hand_relax", "z_order": 4},
    "upper_arm_right": {"rotation": -92, "z_order": 4},
    "forearm_right": {"rotation": 134, "z_order": 4},
    "hand_right": {"part": "hand_relax_r", "z_order": 4}}),
  "mahnul_oboimi": (0.18, {                    # обе отмашки: «да бросьте»
    "upper_arm_left": {"rotation": 58, "z_order": 5},
    "forearm_left": {"rotation": -28, "z_order": 5},
    "hand_left": {"part": "hand_relax", "z_order": 6},
    "upper_arm_right": {"rotation": -58, "z_order": 5},
    "forearm_right": {"rotation": 28, "z_order": 6},
    "hand_right": {"part": "hand_relax_r", "z_order": 6},
    "head": {"rotation": 4}}),
  "vpered_nizko": (0.28, {                     # «вот оно, здесь» — вперёд-вниз
    "upper_arm_left": {"rotation": 40, "z_order": 6},
    "forearm_left": {"rotation": 52, "z_order": 6},
    "hand_left": {"part": "hand_offer", "z_order": 7},
    "upper_arm_right": {"rotation": -40, "z_order": 6},
    "forearm_right": {"rotation": -52, "z_order": 6},
    "hand_right": {"part": "hand_offer_r", "z_order": 7},
    "head": {"rotation": -6}}),
  "odna_v_bok": (0.3, {                        # одна в бок, вторая свободна
    "upper_arm_left": {"rotation": 86, "z_order": 4},
    "forearm_left": {"rotation": -98, "z_order": 4},
    "hand_left": {"part": "hand_relax", "z_order": 4},
    "upper_arm_right": {"rotation": -30}, "forearm_right": {"rotation": 14},
    "head": {"rotation": 4}}),
}


def main():
    rig = json.loads(RIG.read_text(encoding="utf-8"))
    poses = rig["poses"]
    # tychok из первой партии снят: тычок В ЗРИТЕЛЯ ригом не строится. Кисть
    # уходит в перспективное сокращение, которого у плоских частей нет, и на
    # листе он прочёлся как «держит предмет сбоку». В серии этот удар делается
    # ПРОПОМ (`hand-point`, `giant-hand`) — конвенция уже есть, и спорить с ней
    # ради лишнего имени в риге незачем.
    # СНЯТЫ ПОСЛЕ КОНТАКТНОГО ЛИСТА, а не задуманы и забыты.
    #   tychok   — тычок В ЗРИТЕЛЯ ригом не строится: кисть уходит в
    #              перспективное сокращение, которого у плоских частей нет, и на
    #              листе он прочёлся как «держит предмет сбоку». В серии этот
    #              удар делается ПРОПОМ (`hand-point`, `giant-hand`).
    #   schet    — счёт по пальцам требует кисти ПЕРЕД грудью, а там она тонет
    #              в сплошной заливке плаща. На листе прочёлся как `open`.
    #   potiraet — та же причина: ладони сходятся перед корпусом и пропадают;
    #              осталась пара торчащих локтей, то есть `hips`.
    # Позу, которая на листе повторяет соседнюю, класть в риг нельзя: она не
    # добавляет разнообразия, а пополняет кладбище неиспользуемых имён — их в
    # риге и так 36.
    for snyato in ("tychok", "schet", "potiraet"):
        poses.pop(snyato, None)
    added, upd = [], []
    for group in (RUKI, GLAZA, ESCHO):
        for name, (td, bones) in group.items():
            (upd if name in poses else added).append(name)
            poses[name] = {"name": name, "transition_duration": td, "bones": bones}
    # ЗЕРКАЛА СЧИТАЮТСЯ ПОСЛЕ ВСЕХ: отражать надо готовую позу, какой бы она ни
    # была на этот прогон, а не ту, что лежала в риге с прошлого раза.
    for name in ZERKALIT:
        src = poses.get(name)
        if not src:
            print(f"  ! нечего отражать: {name}")
            continue
        # СТОРОНА БЕРЁТСЯ ПО ВЕДУЩЕЙ РУКЕ, а не по наличию кости. У почти
        # каждого жеста ОБЕ руки названы: ведущая делает жест, вторая держит
        # покой. Судить по «есть ли в позе upper_arm_right» — значит назвать
        # зеркало `k_sebe` (бьёт себя левой) именем `k_sebe_l`, хотя отражённая
        # версия ведёт ПРАВОЙ. Ведущая — та, у которой плечо отведено сильнее.
        b = src["bones"]
        vedet_levaya = (abs(b.get("upper_arm_left", {}).get("rotation", 0))
                        > abs(b.get("upper_arm_right", {}).get("rotation", 0)))
        imya = name + ("_r" if vedet_levaya else "_l")
        (upd if imya in poses else added).append(imya)
        poses[imya] = {"name": imya,
                       "transition_duration": src.get("transition_duration", 0.3),
                       "bones": zerkalo(src["bones"])}
    RIG.write_text(json.dumps(rig, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"новых: {len(added)} — {', '.join(added)}")
    if upd:
        print(f"переписано: {len(upd)} — {', '.join(upd)}")
    print(f"поз в риге: {len(poses)}")


if __name__ == "__main__":
    main()
