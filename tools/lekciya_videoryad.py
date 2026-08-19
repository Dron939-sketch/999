#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lekciya_videoryad.py — раскладка видеоряда под ГОТОВУЮ аудиозапись лекции.

ЗАЧЕМ ГЕНЕРАТОР, А НЕ РУЧНОЙ .anim. Шестнадцать минут — это три десятка планов,
и у каждого длительность считается от предыдущего. Одна поправка в середине
уводит все склейки после неё, а склейка, уехавшая из паузы в середину фразы,
и есть главный брак этого формата. Числа тут пересчитываются, а не вписываются
руками, — ровно по правилу сайта «не вписывать числа руками».

ТРИ ВЕЩИ, КОТОРЫЕ ДЕЛАЕТ СКРИПТ:

1. СНИМАЕТ КАРТУ ПАУЗ С САМОЙ ЗАПИСИ. `silencedetect` на этой дорожке молчит
   даже на −20 dB: под речью идёт ровный шум, и абсолютного порога нет. Поэтому
   огибающая RMS считается своя, а порогом берётся доля от МЕДИАНЫ речи (12%) —
   мерка относительная и потому работает на любой записи, тихой или громкой.

2. САЖАЕТ КАЖДУЮ СКЛЕЙКУ В НАСТОЯЩУЮ ПАУЗУ. Границы разделов приходят планом
   (доли слов), но план — это оценка; в файл идёт ближайшая к плану пауза.
   Смена кадра в середине слова читается обрывом, даже если зритель не понимает,
   что именно его дёрнуло.

3. СЧИТАЕТ ДЛИТЕЛЬНОСТЬ КАЖДОЙ СЦЕНЫ ПОД ЭТИ СКЛЕЙКИ и печатает раскладку
   таблицей — её положено посмотреть глазами до сборки.

ПРОЕЗД ИДЁТ НЕ НА `wide`. Сет натянут на кадр край в край, `wide` — это зум 1.0,
и любой проезд вытаскивает из-под картинки голую подложку. Так был испорчен
пилот: серая полоса снизу и справа на каждом ходе камеры. Планы здесь только
`two-shot` (запас 0.083) и `over-shoulder` (запас 0.222), а гейт
`tools/proezd.py` не пускает обратно.

    python3 tools/lekciya_videoryad.py            # раскладка + .anim
    python3 tools/lekciya_videoryad.py --tolko-tablica
"""

import argparse
import math
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "examples/assets/audio-lekciya-koleya-1.mp3"
OUT = ROOT / "examples/lektorij/lekciya-koleya-1.anim"
FPS = 24

#  ─────────────────────────────────────────────────────────────────────────
#  РАЗДЕЛЫ ЛЕКЦИИ. Границы — плановые, по долям слов текста лекции при темпе
#  124 слова в минуту; в файл идут не они, а ближайшие к ним НАСТОЯЩИЕ паузы.
RAZDELY = [
    ("ВСТУПЛЕНИЕ",              72.0),
    ("1. Анкета",              142.5),
    ("2. Откуда настройки",    307.3),
    ("3. Почему колея не жмёт", 395.3),
    ("4. Торо: аудит вручную",  471.6),
    ("5. Три признака",         565.5),
    ("6. Что дальше",           683.1),
    ("ЧаВо",                    808.0),
    ("Итоги",                   874.2),
    ("Вопросы для самопроверки", 911.0),
    ("Литература",              None),   # до конца записи
]

#  ХОДЫ КАМЕРЫ. (план, откуда, куда) — оба конца внутри запаса своего плана:
#  two-shot ±0.083, over-shoulder ±0.222 (гейт tools/proezd.py).
HOD = {
    "vdol":      ("over-shoulder", (0.32, 0.50), (0.68, 0.50)),
    "vdol_nazad":("over-shoulder", (0.68, 0.50), (0.32, 0.50)),
    "vniz":      ("two-shot",      (0.50, 0.435), (0.50, 0.565)),
    "vverh":     ("two-shot",      (0.50, 0.565), (0.50, 0.435)),
    "vpravo":    ("two-shot",      (0.437, 0.50), (0.563, 0.50)),
    "vlevo":     ("two-shot",      (0.563, 0.50), (0.437, 0.50)),
    "po_stupenyam": ("over-shoulder", (0.32, 0.64), (0.68, 0.38)),
    "naiskos":   ("over-shoulder", (0.34, 0.36), (0.66, 0.64)),
    "k_razvilke":("two-shot",      (0.46, 0.56), (0.565, 0.452)),
    "k_stopke":  ("two-shot",      (0.44, 0.565), (0.56, 0.44)),
}

#  РАСКАДРОВКА: по разделам, (имя сета, ход камеры).
#  Повтор кадра допустим и работает как возврат мотива — но ход камеры у
#  повтора ДРУГОЙ, иначе склейка читается заеданием плёнки.
KADRY = {
    "ВСТУПЛЕНИЕ": [("lek1-obychnaya-zhizn", "vdol"),
                   ("lek1-shest-osej", "vniz")],
    "1. Анкета": [("lekciya-koleya-1-anketa", "vniz"),
                  ("lekciya-koleya-1-galochka", "naiskos"),
                  ("lekciya-koleya-1-telefon", "vverh")],
    "2. Откуда настройки": [("lek1-semya", "vniz"),
                            ("lek1-sreda", "vdol"),
                            ("lek1-pokolenie", "po_stupenyam"),
                            ("lek1-ringtone", "vpravo")],
    "3. Почему колея не жмёт": [("lek1-vse-ryadom", "vverh"),
                                ("lek1-tak-vse", "vdol")],
    "4. Торо: аудит вручную": [("lek1-hizhina", "vlevo"),
                               ("lek1-spisok-toro", "vniz")],
    "5. Три признака": [("lek1-zavist", "vdol"),
                        ("lek1-voskresnyj-vecher", "vdol"),
                        ("lek1-tak-vse", "vdol_nazad")],
    "6. Что дальше": [("lek1-chto-dalshe", "k_razvilke"),
                      ("lek1-shag", "vverh"),
                      ("lek1-spisok-toro", "vpravo")],
    "ЧаВо": [("lek1-chavo", "naiskos"),
             ("lek1-chasy", "vlevo"),
             ("lek1-vesy", "vdol")],
    "Итоги": [("lek1-fundament", "vniz"),
              ("lek1-chto-dalshe", "vverh")],
    "Вопросы для самопроверки": [("lek1-shest-osej", "vdol")],
    "Литература": [("lek1-knigi", "k_stopke"),
                   ("lek1-hizhina", "vpravo")],
}

#  ШВЫ. Персонаж встаёт между разделами и МОЛЧИТ — это знак, что мысль
#  сменилась. Пары поз не повторяются: десять появлений одинаковой фигурой
#  превращают приём в заставку. Сидячих поз нет (гейт осанки).
SHVY = [("vzglyad", "point"), ("think", "palec_vverh"), ("razvel", "k_sebe"),
        ("vdal", "smel"), ("shrug", "open"), ("vzves", "raspahnul"),
        ("otschet", "dve_storony"), ("doubt", "vozzvanie"),
        ("chelo", "ladon_pusta"), ("prishchur", "rubit")]
SHOV = 3.4      # длительность шва, с
MIN_PLAN = 12.0  # короче — кадр не успевает прочитаться


# ─────────────────────────────────────────────────────────── карта пауз
def pauzy(audio, minimum=0.36):
    """Окна тишины записи. Порог — доля от медианы речи, а не абсолют."""
    sr, win = 16000, 320
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "a.raw")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(audio),
                        "-ac", "1", "-ar", str(sr), "-f", "s16le", raw],
                       check=True)
        import array
        a = array.array("h")
        a.frombytes(open(raw, "rb").read())
    env = []
    for i in range(0, len(a) - win, win):
        blok = a[i:i + win]
        env.append(math.sqrt(sum(x * x for x in blok) / win))
    thr = statistics.median(env) * 0.12
    shag = win / sr
    out, run = [], 0
    for i, v in enumerate(env):
        if v < thr:
            run += 1
        else:
            if run * shag >= minimum:
                out.append(((i - run) * shag, i * shag))
            run = 0
    return out, len(a) / sr


def v_pauzu(t, ps, posle):
    """Ближайший к t центр паузы, но строго позже `posle`."""
    god = [p for p in ps if (p[0] + p[1]) / 2 > posle + MIN_PLAN]
    if not god:
        return None
    return min(((p[0] + p[1]) / 2 for p in god), key=lambda c: abs(c - t))


# ─────────────────────────────────────────────────────────── раскладка
def razlozhit():
    ps, dlina = pauzy(AUDIO)
    plany, t = [], 0.0

    for n, (imya, plan_konec) in enumerate(RAZDELY):
        if n:                                    # шов перед каждым разделом
            konec_shva = v_pauzu(t + SHOV, ps, t) if False else t + SHOV
            plany.append({"vid": "shov", "imya": f"шов {n}",
                          "pozy": SHVY[(n - 1) % len(SHVY)],
                          "ot": t, "do": konec_shva})
            t = konec_shva

        konec = dlina if plan_konec is None else v_pauzu(plan_konec, ps, t)
        konec = dlina if konec is None else konec
        if n == len(RAZDELY) - 1:
            konec = dlina

        kadry = KADRY[imya]
        #  Внутренние склейки делят раздел поровну — и тоже садятся в паузы.
        granicy, prev = [], t
        for k in range(len(kadry) - 1):
            cel = t + (konec - t) * (k + 1) / len(kadry)
            g = v_pauzu(cel, ps, prev)
            if g is None or g >= konec - MIN_PLAN:
                g = prev + (konec - prev) / (len(kadry) - k)
            granicy.append(g)
            prev = g
        granicy.append(konec)

        for (kadr, hod), g in zip(kadry, granicy):
            plany.append({"vid": "kadr", "imya": imya, "kadr": kadr,
                          "hod": hod, "ot": t, "do": g})
            t = g
    return plany, dlina, ps


# ─────────────────────────────────────────────────────────── .anim
def sobrat(plany, dlina):
    sety = sorted({p["kadr"] for p in plany if p["vid"] == "kadr"})
    L = []
    A = L.append
    A("// " + "=" * 75)
    A("//  ВИДЕОРЯД ЛЕКЦИИ 1 «Чью жизнь вы живёте». Собран")
    A("//  tools/lekciya_videoryad.py — РУКАМИ НЕ ПРАВИТЬ, правится генератор.")
    A("//")
    A("//  Голос — готовая аудиозапись лекции, синтеза нет, персонаж не говорит.")
    A("//  Двадцать шесть гейтов приёмки ролика сюда не применяются: они меряют")
    A("//  устройство интро (крючок, кольцо, разрыв, жало), а у лекции есть тема")
    A("//  и порядок мыслей. Свой список проверок — в lekciya-koleya-1-VIDEO.md.")
    A("//")
    A(f"//  Длина записи: {dlina:.2f}с. Планов: {len(plany)}.")
    A("//  Каждая склейка стоит в НАСТОЯЩЕЙ паузе записи, снятой с огибающей.")
    A("//")
    A("//  Проезд идёт на two-shot и over-shoulder, но НИКОГДА на wide: сет")
    A("//  натянут на кадр край в край, wide — зум 1.0, и проезд вытаскивает")
    A("//  из-под картинки голую подложку (так был испорчен пилот). Держит")
    A("//  tools/proezd.py.")
    A("// " + "=" * 75)
    A('import character freeman from "../assets/characters/freeman_rig"')
    A('import set komnata from "../assets/sets/koleya-komnata.svg"')
    for s in sety:
        A(f'import set {s.replace("-", "_")} from "../assets/sets/{s}.svg"')
    A("")
    A("config {")
    for k, v in (("width", 1280), ("height", 720), ("fps", FPS),
                 ("background", "#b0b3ab"), ("monochrome", "true"),
                 ("mono-contrast", 2.2), ("snow", 0.12), ("on-twos", 2),
                 ("line-boil", 0.55), ("film-grain", 0.05), ("vignette", 0.12),
                 ("film-flicker", 0.025), ("gate-weave", 0.35),
                 ("film-scratch", 0.25), ("film-dust", 0.5),
                 ("light-angle", 45), ("form-shadow", 0.0), ("rim-light", 0.0),
                 ("ground-shadow", "true"), ("cast-shadow", 0.32)):
        A(f"    {k}: {v}")
    A("}")
    A("")

    for i, p in enumerate(plany):
        d = p["do"] - p["ot"]
        mm, ss = int(p["ot"] // 60), p["ot"] % 60
        if p["vid"] == "shov":
            a, b = p["pozy"]
            A(f'// ── {p["imya"]}: {mm}:{ss:05.2f}, {d:.2f}с — персонаж молчит')
            A(f'scene "shov{i:02d}" (duration: 1s, set: komnata) {{')
            A("    transition static 0.12s")
            A("    place freeman at (0.50, 0.99) facing front on floor")
            A("    freeman scales 0.90 over 0.01s")
            A("    camera wide")
            A('    freeman pose "calm"')
            A("    wait 0.50s")
            A(f'    freeman pose "{a}"')
            A("    wait 1.10s")
            A(f'    freeman pose "{b}"')
            A("    wait 1.10s")
            A('    freeman pose "calm"')
            A(f"    wait {d - 0.12 - 0.01 - 0.50 - 1.10 - 1.10:.2f}s")
            A("}")
        else:
            plan, ot, do = HOD[p["hod"]]
            hod_t = d - 0.12 - 0.01 - 0.80 - 0.90
            A(f'// ── {p["imya"]} / {p["kadr"]}: {mm}:{ss:05.2f}, {d:.2f}с, '
              f'{p["hod"]} на {plan}')
            A(f'scene "s{i:02d}_{p["kadr"].replace("-", "_")}" '
              f'(duration: 1s, set: {p["kadr"].replace("-", "_")}) {{')
            A("    transition static 0.12s")
            A(f"    camera {plan}")
            A(f"    camera pan-to ({ot[0]:.3f}, {ot[1]:.3f}) over 0.01s")
            A("    wait 0.80s")
            A(f"    camera pan-to ({do[0]:.3f}, {do[1]:.3f}) "
              f"over {hod_t:.2f}s ease-in-out")
            A("    wait 0.90s")
            A("}")
        A("")
    return "\n".join(L)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolko-tablica", action="store_true")
    a = ap.parse_args(argv)

    plany, dlina, ps = razlozhit()

    print(f"\n  ВИДЕОРЯД ЛЕКЦИИ 1 — раскладка\n")
    print(f"  запись {dlina:.2f}с, пауз найдено {len(ps)}, планов {len(plany)}\n")
    print(f"  {'начало':>9}  {'длина':>7}  кадр")
    korotkie = []
    for p in plany:
        d = p["do"] - p["ot"]
        mm, ss = int(p["ot"] // 60), p["ot"] % 60
        imya = "ФРИМЕН — " + p["imya"] if p["vid"] == "shov" else p["kadr"]
        print(f"  {mm:>5}:{ss:05.2f}  {d:>6.2f}с  {imya}")
        if p["vid"] == "kadr" and d > 50:
            korotkie.append(f"{imya} висит {d:.0f}с — глазу долго")
    hvost = plany[-1]["do"]
    print(f"\n  сумма планов {hvost:.2f}с против записи {dlina:.2f}с "
          f"(расхождение {hvost - dlina:+.2f}с)")
    for k in korotkie:
        print(f"  [ВНИМАНИЕ] {k}")

    if not a.tolko_tablica:
        OUT.write_text(sobrat(plany, dlina) + "\n", encoding="utf-8")
        print(f"\n  записано: {OUT.relative_to(ROOT)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
