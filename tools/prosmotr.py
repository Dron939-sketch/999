#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prosmotr.py — ПРИЁМКА ПО ГОТОВОМУ ФАЙЛУ. Единственная, которая смотрит на то,
что увидит зритель.

ПОЧЕМУ ЗАВЕДЕНА. Студия посмотрела «Девяносто девятый день» и назвала три
дефекта картинки подряд. Все двадцать четыре гейта на нём были зелёные — и это
не сбой гейтов, а их устройство: они читают СЦЕНАРИЙ, РИГ и отрисованные
СТЕНДЫ, то есть то, из чего кадр делается, а не сам кадр.

Единственное место с глазами — контактный лист мизансцен — рисует ОДИН кадр на
сцену, всегда базовой позой, всегда общим планом: семь кадров из трёх тысяч ста
шестидесяти восьми, две десятых процента хронометража. Каждый из трёх дефектов
в эти семь кадров не попадал ПО УСТРОЙСТВУ ЛИСТА:

  · в чёрной сцене лист рисует `calm` с руками вниз — а в ролике там подняты
    руки, и на чёрном фоне от фигуры остаётся маска и две светлые проволоки;
  · в библиотеке лист рисует позу ДО того, как кисть уходит на лицо;
  · масштаб гейт меряет относительно объявленного роста человека в локации, а
    не относительно КАДРА, и «фигура-точка посреди общего плана» проходит.

Замер по готовому файлу: восемьдесят секунд из ста тридцати пяти несли видимый
дефект. Больше половины ролика.

ЧТО ПРОВЕРЯЕТСЯ. Четыре мерки, и все — по кадрам готового файла, раз в секунду.

  1. ФОН СЪЕЛ ФИГУРУ. Доля тёмного в кадре. Больше 55% — локация темнее
     персонажа, и силуэт в ней не отделяется ничем.
  2. ФИГУРЫ НЕ ВИДНО. Маска не находится вовсе: либо она мельче различимого,
     либо её съел фон.
  3. ФИГУРА МЕЛЬЧЕ НОРМЫ КАДРА. Рост считается из высоты маски по карте рига
     (маска — 0.2177 роста, полный рост — 0.600 на единицу `scales`), поэтому
     не зависит ни от плана, ни от локации. Меньше трети кадра — точка.
  4. КИСТЬ НА ЛИЦЕ. Доля тёмного ВНУТРИ маски. Глаза и рот дают 27–34%; кисть,
     легшая на лицо, — 48–51%. Порог 45% посередине, снят с готового файла.

Плюс ЗВУК: если партитура назначила в этом месте тишину, тишина обязана быть в
миксе. В том же файле её не было ни одной секунды при двух назначенных, и обе
несущие — обрыв на переломе и пауза, в которой зритель делает догадку.

ЛИСТ СОБИРАЕТСЯ ВСЕГДА, даже когда мерки чисты: мерок четыре, а испортить кадр
можно сотней способов, и глаз пока остаётся последней инстанцией. Отличие от
листа мизансцен в том, что здесь кадры НАСТОЯЩИЕ и их сто тридцать пять, а не
семь.

Использование:
    python3 tools/prosmotr.py videos/chernyj-lebed.mp4
    python3 tools/prosmotr.py videos/chernyj-lebed.mp4 --vo examples/lektorij/lebed-VO.md
    python3 tools/prosmotr.py videos/chernyj-lebed.mp4 --list /tmp/list  # куда листы
"""

import argparse
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from karta import label                                  # noqa: E402

SHAG = 2                  # прореживание при разборе кадра (скорость)
TEMNO = 90                # порог туши
SVETLO = 245              # порог бумаги: маска ярче стен локации
DOLYA_TMY = 0.55          # больше — фон темнее персонажа
MASKA_MAKS = 0.35         # светлое пятно крупнее — это небо, а не лицо.
#  Было 0.15, и на КРУПНОМ ПЛАНЕ маска в этот предел не помещалась: гейт
#  сообщал «фигуры не видно» там, где лицо занимает полкадра. Небо и стены
#  предел не спасал и не спасает — они касаются кромки и отбрасываются раньше.
MASKA_MIN = 0.0004
ROST_MASKI = 0.2177       # высота маски в долях роста (карта рига)
ROST_MIN = 0.35           # рост фигуры в долях кадра, ниже — точка
LICO_ZANYATO = 0.45       # доля тёмного внутри маски
TISHINA = 0.02            # амплитуда, ниже которой это тишина
TISHINA_DLINA = 0.4       # сколько секунд тишины должно найтись
TISHINA_OKNO = 3.0        # на сколько секунд вокруг метки её искать


def kadry(istochnik, rab):
    """Кадры раз в секунду. На вход — mp4 или уже готовая папка с png."""
    p = Path(istochnik)
    if p.is_dir():
        return sorted(p.glob("*.png"))
    out = rab / "kadry"
    out.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vf", "fps=1",
                    str(out / "k_%04d.png"), "-y"], check=True)
    return sorted(out.glob("*.png"))


def maska(g):
    """Маска лица: светлое пятно-яйцо с дырами (глаза и рот), не у кромки.

    Отбор именно такой, а не «самое большое светлое», потому что небо над полем
    и стена кухни светлее маски и крупнее её в десятки раз.
    """
    svet = g > SVETLO
    if not svet.any():
        return None
    lab = label(svet)
    kromka = set(lab[0]) | set(lab[-1]) | set(lab[:, 0]) | set(lab[:, -1])
    ids, cnt = np.unique(lab[lab > 0], return_counts=True)
    luchshee = None
    for k, c in zip(ids, cnt):
        if k in kromka or c > MASKA_MAKS * g.size or c < MASKA_MIN * g.size:
            continue
        ys, xs = np.nonzero(lab == k)
        h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
        if not (1.05 < h / w < 2.0):      # яйцо стоймя, а не полоса стены
            continue
        if c >= 0.80 * h * w:             # без дыр — значит не лицо
            continue
        if luchshee is None or c > luchshee[0]:
            luchshee = (c, (ys.min(), ys.max(), xs.min(), xs.max()))
    if luchshee is None:
        return None
    _, (y0, y1, x0, x1) = luchshee
    box = g[y0:y1 + 1, x0:x1 + 1]
    return {
        "vysota": (y1 - y0 + 1) / g.shape[0],
        "temno_vnutri": float((box < TEMNO).sum() / box.size),
    }


def razobrat(fajly):
    besede = []
    for i, f in enumerate(fajly):
        g = np.asarray(Image.open(f).convert("L"))[::SHAG, ::SHAG]
        tma = float((g < TEMNO).mean())
        m = maska(g)
        besede.append((i, tma, m))
    return besede


def intervaly(sekundy):
    """Список секунд → человеческие отрезки «12–34 с»."""
    if not sekundy:
        return []
    out, a, b = [], sekundy[0], sekundy[0]
    for s in sekundy[1:]:
        if s == b + 1:
            b = s
        else:
            out.append((a, b)); a = b = s
    out.append((a, b))
    return out


def vremya(s):
    return f"{s // 60}:{s % 60:02d}"


def pechat(nazvanie, seki, hvost):
    if not seki:
        return 0
    kuski = intervaly(seki)
    vsego = sum(b - a + 1 for a, b in kuski)
    print(f"  ✗ {nazvanie}: {vsego} с")
    for a, b in kuski:
        print(f"      · {vremya(a)}–{vremya(b)}" + (f" ({b - a + 1} с)" if b > a else ""))
    print(f"      {hvost}")
    return vsego


def tishiny_iz_vo(vo):
    """Метки тишины из партитуры звука: «| 0:27 | обрыв — глухая тишина | …»."""
    if not vo:
        return []
    text = Path(vo).read_text(encoding="utf-8")
    metki = []
    for stroka in text.splitlines():
        if not stroka.startswith("|") or "ишин" not in stroka:
            continue
        m = re.search(r"\|\s*(\d+):(\d\d)\s*\|", stroka)
        if m:
            metki.append(int(m.group(1)) * 60 + int(m.group(2)))
    return metki


def zvuk_tishina(video, metki, rab):
    if not metki:
        return []
    wav = rab / "z.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1",
                    "-ar", "8000", "-f", "wav", str(wav), "-y"], check=True)
    w = wave.open(str(wav))
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    sr = w.getframerate()
    okno = int(sr * 0.1)
    env = np.array([np.abs(a[i:i + okno]).max() for i in range(0, len(a) - okno, okno)])
    nado = int(TISHINA_DLINA / 0.1)
    bed = []
    for t in metki:
        lo = max(0, int((t - TISHINA_OKNO) * 10))
        hi = min(len(env), int((t + TISHINA_OKNO) * 10))
        tiho = env[lo:hi] < TISHINA
        # ищем подряд идущую тишину нужной длины
        podryad, mx = 0, 0
        for v in tiho:
            podryad = podryad + 1 if v else 0
            mx = max(mx, podryad)
        if mx < nado:
            bed.append((t, mx * 0.1, float(env[lo:hi].min()) if hi > lo else 1.0))
    return bed


def listy(fajly, kuda, imya):
    kuda.mkdir(parents=True, exist_ok=True)
    NA_LIST, KOL = 45, 9
    puti = []
    for nach in range(0, len(fajly), NA_LIST):
        kusok = fajly[nach:nach + NA_LIST]
        obr = [Image.open(f).convert("RGB") for f in kusok]
        w = 320
        obr = [o.resize((w, int(w * o.height / o.width))) for o in obr]
        h = obr[0].height
        ryadov = (len(obr) + KOL - 1) // KOL
        sh = Image.new("RGB", (KOL * (w + 4) + 4, ryadov * (h + 16) + 4), (240, 240, 240))
        dr = ImageDraw.Draw(sh)
        for i, o in enumerate(obr):
            r, c = divmod(i, KOL)
            x, y = 4 + c * (w + 4), 4 + r * (h + 16)
            sh.paste(o, (x, y + 12))
            dr.text((x + 2, y + 1), vremya(nach + i), fill=(0, 0, 0))
        p = kuda / f"{imya}-prosmotr-{nach // NA_LIST + 1}.png"
        sh.save(p)
        puti.append(p)
    return puti


def main(argv):
    ap = argparse.ArgumentParser(description="Приёмка по готовому файлу")
    ap.add_argument("video", nargs="?", help="mp4 или папка с png")
    # Имя готового файла — это СЛАГ КУРСА, а VO лежит у продакшена под коротким
    # рабочим id. Связывает их манифест, и спрашивать его удобнее отсюда, чем
    # разбирать json в шелле прогона.
    ap.add_argument("--vo-po-kursu", metavar="СЛАГ",
                    help="напечатать путь к VO по слагу курса и выйти")
    ap.add_argument("--vo", help="VO-сценарий: откуда взять метки тишины")
    ap.add_argument("--list", dest="kuda", help="куда положить листы")
    a = ap.parse_args(argv)

    if a.vo_po_kursu:
        import json
        d = json.loads((ROOT / "tools/productions.json").read_text(encoding="utf-8"))
        for prod in d["productions"]:
            if (prod.get("kurs") or prod["id"]) == a.vo_po_kursu:
                print(prod.get("vo", ""))
                return 0
        return 1

    if not a.video:
        raise SystemExit("укажи готовый файл")

    rab = Path(tempfile.mkdtemp(prefix="prosmotr-"))
    fajly = kadry(a.video, rab)
    if not fajly:
        print("  кадров нет", file=sys.stderr)
        return 1
    imya = Path(a.video).stem
    kuda = Path(a.kuda) if a.kuda else Path(a.video).resolve().parent
    puti = listy(fajly, kuda, imya)

    besede = razobrat(fajly)
    tmy, net_figury, melko, lico = [], [], [], []
    for i, tma, m in besede:
        if tma > DOLYA_TMY:
            tmy.append(i)
            continue                      # чёрный кадр: остальное мерить нечем
        if m is None:
            net_figury.append(i)
            continue
        if m["vysota"] / ROST_MASKI < ROST_MIN:
            melko.append(i)
        if m["temno_vnutri"] > LICO_ZANYATO:
            lico.append(i)

    print(f"\n╔══ ПРОСМОТР ГОТОВОГО ФАЙЛА: {imya}, {len(fajly)} с")
    plohih = 0
    plohih += pechat("фон съел фигуру — локация темнее персонажа", tmy,
                     "Силуэт в такой локации не отделяется ничем: кайма спасает "
                     "руки, но тело остаётся чёрным на чёрном. Менять локацию "
                     "или давать фигуре светлую кромку целиком.")
    plohih += pechat("фигуры не видно — маска не находится", net_figury,
                     "Либо фигура мельче различимого, либо её съел фон.")
    plohih += pechat(f"фигура мельче {ROST_MIN:.0%} кадра — точка посреди плана", melko,
                     "Рост считается по высоте маски и от плана не зависит. "
                     "Поднять `scales` или взять план крупнее.")
    plohih += pechat("кисть на лице", lico,
                     f"Тёмного внутри маски больше {LICO_ZANYATO:.0%} при норме "
                     "27–34% (глаза и рот). Рука закрывает лицо — сменить слой "
                     "или увести кисть за силуэт.")

    if a.vo and Path(a.video).suffix == ".mp4":
        bed = zvuk_tishina(a.video, tishiny_iz_vo(a.vo), rab)
        for t, bylo, mn in bed:
            plohih += 1
            print(f"  ✗ назначенная тишина на {vremya(t)} не звучит: самая "
                  f"длинная тихая дыра рядом {bylo:.1f} с при норме "
                  f"{TISHINA_DLINA} с, тише всего {mn:.3f}")
        if bed:
            print("      Комнатный тон играет поверх тишины. Тишина в партитуре "
                  "стоит на переломе и на догадке — это рабочие места, а не воздух.")

    print("╚══")
    print("  ЛИСТЫ — СМОТРЕТЬ ГЛАЗАМИ (мерок четыре, а испортить кадр можно "
          "сотней способов):")
    for p in puti:
        print(f"      {p}")
    if plohih:
        print(f"\n  БРАК В ГОТОВОМ ФАЙЛЕ. Не отдавать.")
        return 1
    print("\n  По меркам чисто. Листы всё равно посмотреть.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
