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

Плюс ЗВУК, две мерки.

  · ГОЛОС ЗВУЧИТ В ГОТОВОМ ФАЙЛЕ. Fish отдал HTTP 500, голос не собрался, и
    сведение по своему запасному пути положило в ролик ОДНУ дорожку эффектов —
    комнатный тон. Мастеринг честно поднял её с −30.1 до −15.1 LUFS, и студия
    получила две минуты ровного низкочастотного гула вместо монолога. Прогон
    при этом был зелёный: гейт завода спрашивал «есть ли аудиодорожка», а она
    была. Меряем не наличие дорожки, а долю энергии в полосе разборчивости
    300–3400 Гц — замер по пяти сданным роликам: 0.19–0.24 у ролика с речью,
    0.075 у этого гула. Порог 0.13 посередине. Вторая половина мерки — доля
    пятисекундных блоков, в которых речь есть: 0.83–1.00 против 0.04. Она
    ловит то, чего общая доля не увидит, — половину реплик, потерянную
    поштучным синтезом.
  · НАЗНАЧЕННАЯ ТИШИНА. Если партитура назначила в этом месте тишину, тишина
    обязана быть на дорожке. В том же файле её не было ни одной секунды при
    двух назначенных, и обе несущие — обрыв на переломе и пауза, в которой
    зритель делает догадку.

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
LICO_ZANYATO = 0.30       # доля тёмного ВНУТРИ ОВАЛА маски (см. temno_v_ovale)
TISHINA = 0.02            # амплитуда, ниже которой это тишина
TISHINA_DLINA = 0.4       # сколько секунд тишины должно найтись
TISHINA_OKNO = 6.0        # на сколько секунд вокруг метки её искать:
                          # монтаж уезжает от плана на секунды
RECH_NIZ, RECH_VERH = 300, 3400   # полоса разборчивости речи, Гц
RECH_VSYA = (80, 7000)            # полоса, в долях которой считаем
RECH_DOLYA = 0.13         # доля энергии речевой полосы (см. шапку)
RECH_BLOK = 5.0           # блок, в котором ищем речь, с
RECH_BLOKOV = 0.50        # доля блоков, где речь обязана звучать


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


def szhat(m, raz=2):
    """Сжать светлое пятно на `raz` пикселей: тонкие перемычки рвутся.

    ЗАЧЕМ. Кисти обшиты светлой каймой в полтора пикселя (реестр §XXXIV), и
    когда кисть подходит к лицу, кайма КАСАЕТСЯ маски. Два светлых пятна
    становятся одним, у него нет ни формы яйца, ни дыр на месте глаз, — и
    приёмка сообщает «фигуры не видно» там, где лицо в кадре открыто. Перемычка
    тонкая, сама маска толстая: сжатие рвёт первую и не трогает вторую.
    """
    out = m
    for _ in range(raz):
        s = out
        s = s & np.roll(out, 1, 0) & np.roll(out, -1, 0)
        s = s & np.roll(out, 1, 1) & np.roll(out, -1, 1)
        s[0] = s[-1] = False
        s[:, 0] = s[:, -1] = False
        out = s
    return out


def temno_v_ovale(g, pyatno, y0, y1):
    """Доля тёмного ВНУТРИ маски: построчно между её крайними светлыми точками.

    Прямоугольник вокруг маски для этого не годится — в его углы попадает то,
    что лица не закрывает, и кисть, поднятая К ЩЕКЕ, давала ту же долю, что и
    кисть, легшая НА ЛИЦО. По овалу они расходятся: чистые кадры 0.05–0.16,
    кисть у щеки 0.17–0.29, кисть на лице 0.31–0.37.
    """
    vnutri = np.zeros_like(pyatno)
    for y in range(y0, y1 + 1):
        xs = np.nonzero(pyatno[y])[0]
        if len(xs):
            vnutri[y, xs.min():xs.max() + 1] = True
    if not vnutri.any():
        return 0.0
    return float(((g < TEMNO) & vnutri).sum() / vnutri.sum())


def maska(g):
    """Два прохода, и это не перестраховка.

    СТРОГИЙ (без сжатия) находит маску, только когда она стоит одна. Он и
    меряет лицо: если кисть легла НА лицо, она внутри овала и доля тёмного
    растёт. Если светлая кайма кисти лишь КАСАЕТСЯ маски, пятно теряет форму
    яйца и строгий проход не находит ничего.

    СЖАТЫЙ рвёт тонкую перемычку каймы и находит маску всегда — но вместе с
    перемычкой отрезает и саму кисть, поэтому мерить лицо им нельзя: на кадрах,
    где кисть заведомо стоит на лице, он даёт 0.19 вместо 0.31.

    Поэтому: лицо меряет строгий, присутствие фигуры и её рост — сжатый. Там,
    где строгий молчит, лицо в этом кадре просто НЕ ИЗМЕРЕНО, и это честнее,
    чем измерить не то.
    """
    strogo = najti(g, szhimat=False)
    myagko = najti(g, szhimat=True)
    if myagko is None:
        return None
    return {
        "vysota": myagko["vysota"],
        "temno_vnutri": strogo["temno_vnutri"] if strogo else None,
    }


def najti(g, szhimat=True):
    """Маска лица: светлое пятно-яйцо с дырами (глаза и рот), не у кромки.

    Отбор именно такой, а не «самое большое светлое», потому что небо над полем
    и стена кухни светлее маски и крупнее её в десятки раз.
    """
    svet = g > SVETLO
    if not svet.any():
        return None
    lab = label(szhat(svet) if szhimat else svet)
    kromka = set(lab[0]) | set(lab[-1]) | set(lab[:, 0]) | set(lab[:, -1])
    ids, cnt = np.unique(lab[lab > 0], return_counts=True)
    luchshee = None
    for k, c in zip(ids, cnt):
        if k in kromka or c > MASKA_MAKS * g.size or c < MASKA_MIN * g.size:
            continue
        ys, xs = np.nonzero(lab == k)
        h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
        # НИЖНЯЯ ГРАНИЦА 0.95, А НЕ 1.05. Маска — яйцо стоймя, но под наклоном
        # головы и на приближении она читается круглой: в библиотеке гейт
        # мерил 1.00–1.04 и три секунды подряд сообщал «фигуры не видно»
        # там, где лицо занимает четверть кадра.
        if not (0.95 < h / w < 2.0):
            continue
        if c >= 0.80 * h * w:             # без дыр — значит не лицо
            continue
        if luchshee is None or c > luchshee[0]:
            luchshee = (c, (ys.min(), ys.max(), xs.min(), xs.max()), lab == k)
    if luchshee is None:
        return None
    _, (y0, y1, x0, x1), pyatno = luchshee
    return {
        "vysota": (y1 - y0 + 1) / g.shape[0],
        "temno_vnutri": temno_v_ovale(g, pyatno, y0, y1),
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
    """Секунда → «2:05». Округляем, потому что приходят и дробные.

    Номер кадра целый, а метка тишины — середина окна из партитуры, и она
    дробная. Печать падала на ней `ValueError: Unknown format code 'd'`, то
    есть на КАЖДОМ ролике, где назначенная тишина не прозвучала: вместо
    замечания приёмка отдавала трейсбек. На «Двигателе», «Счёте» и
    «Экзистенциальных» — ровно это.
    """
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def pechat(nazvanie, seki, hvost):
    """Брак — это ДВЕ секунды подряд и больше; одиночная показывается заметкой.

    ЗАЧЕМ. Кадры берутся раз в секунду, и одна засечка честно попадает в
    склейку: у ролика есть объявленный переход снежной рябью на 0.2 с, и в
    рябь фигуре провалиться положено. Две секунды подряд в склейку не
    попадают — столько длится уже дефект, а не приём. Заметка при этом
    печатается: одиночную секунду видно, просто она не роняет прогон.
    """
    if not seki:
        return 0
    kuski = intervaly(seki)
    odinochki = [k for k in kuski if k[0] == k[1]]
    kuski = [k for k in kuski if k[1] > k[0]]
    for a, b in odinochki:
        print(f"  · {nazvanie}: {vremya(a)} — одиночная секунда, "
              f"это склейка или рябь, а не дефект")
    if not kuski:
        return 0
    vsego = sum(b - a + 1 for a, b in kuski)
    print(f"  ✗ {nazvanie}: {vsego} с")
    for a, b in kuski:
        print(f"      · {vremya(a)}–{vremya(b)}" + (f" ({b - a + 1} с)" if b > a else ""))
    print(f"      {hvost}")
    return vsego


def tishiny_iz_vo(vo, dlina=None):
    """Окна тишины берём У СБОРЩИКА ЗВУКА, а не разбираем таблицу заново.

    ЗАЧЕМ. Строка «| 1:55 | кухня, чайник; на паузе после VO-26 — ТИШИНА |»
    стоит на 1:55, а пауза, которую она называет, — на 2:01, после конца
    VO-26. Приёмка искала тишину у метки строки, промахивалась на десять
    секунд и сообщала брак на ролике, где тишина лежала ровно там, где
    назначена. `sfx.parse_tishiny` разрешает «после VO-N» в настоящий зазор
    между репликами — тем же кодом, которым дорожка и построена, так что
    приёмка и сборка больше не читают партитуру по-разному.

    И ВСЁ РАВНО ЧИТАЛИ ПО-РАЗНОМУ — НА ОДИН ШАГ ПОЗЖЕ. Разбирать партитуру
    одним кодом оказалось мало: сборщик после разбора ПЕРЕВОДИТ окна с
    планового монтажа на фактический (`sfx.remap_cues`), а приёмка сравнивала
    фактическую дорожку с ПЛАНОВЫМИ метками. На ролике 25 сборщик заглушил
    76.5–81.1с и 133.0–162.0с — ровно там, где пауза и стоит, — а приёмка
    искала тишину на 99.0с и сообщила брак: промах 22 секунды при окне
    поиска, рассчитанном на две (в комментарии ниже так и написано: «128 с
    против 130»).

    ЭТО ЛОВИЛО КАЖДЫЙ ПЕРВЫЙ РЕНДЕР. Числа `speaks for` в свежей раскадровке
    — прогноз по слогам; на факт их переписывает шаг, который идёт ПОСЛЕ
    просмотра готового файла. Пока прогноз расходился с фактом больше, чем на
    окно поиска, просмотр валил корректный файл, а шаг, который убрал бы
    расхождение, до работы не доходил. Круг замыкался, и разорвать его правкой
    ролика было нельзя.

    Поэтому окна переводятся тем же `remap_cues` и по тем же опорам, что у
    сборщика: `.<id>.lipsynced.anim.times.json` — факт от `animdsl timing`,
    `.map.json` — какой блок какой репликой озвучен. Файлов нет (просмотр
    гоняют на скачанном ролике без рабочей папки) — работаем по плану, как
    раньше, и говорим об этом вслух.
    """
    if not vo:
        return []
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from sfx import parse_tishiny, parse_vo_times, remap_cues, sfx_table_span
    except Exception:                                # noqa: BLE001
        return []
    okna = parse_tishiny(vo)
    if not okna:
        return []
    okna = _na_fakt(vo, okna, dlina, parse_vo_times, remap_cues, sfx_table_span)
    return [(a + b) / 2 for a, b in okna]


def _na_fakt(vo, okna, dlina, parse_vo_times, remap_cues, sfx_table_span):
    """Перевести окна тишины с плана на факт по часам движка. Нет часов — план."""
    import json as _json
    anim = None
    try:
        d = _json.loads((ROOT / "tools/productions.json").read_text(encoding="utf-8"))
        for prod in d["productions"]:
            if prod.get("vo") and Path(prod["vo"]).name == Path(vo).name:
                anim = ROOT / prod["anim"]
                break
    except Exception:                                # noqa: BLE001
        return okna
    if anim is None:
        return okna
    times = anim.parent / f".{anim.stem}.lipsynced.anim.times.json"
    karta = anim.parent / f".{anim.stem}.lipsynced.anim.map.json"
    if not times.is_file():
        print(f"      [тишина] часов движка нет ({times.name}) — метки "
              f"остались плановыми, промах возможен")
        return okna
    try:
        blocks = _json.loads(times.read_text(encoding="utf-8")).get("blocks", [])
        real_all = [(b["start"], b["end"]) for b in blocks]
        planned_all = parse_vo_times(vo)
        if karta.is_file():
            order = _json.loads(karta.read_text(encoding="utf-8"))
            pary = [(planned_all[n - 1], real_all[i])
                    for i, n in enumerate(order)
                    if i < len(real_all) and 1 <= n <= len(planned_all)]
            planned = [a for a, _ in pary]
            real = [b for _, b in pary]
        else:
            planned, real = planned_all, real_all
        if not real or len(real) != len(planned):
            print(f"      [тишина] реплик в плане {len(planned)}, в факте "
                  f"{len(real)} — метки остались плановыми")
            return okna
        plan_total = sfx_table_span(vo) or planned[-1][1]
        kraya = [(x, "t") for para in okna for x in para]
        kraya = remap_cues(kraya, planned, real, plan_total,
                           dlina or real[-1][1])
        tochki = [x for x, _ in kraya]
        novye = list(zip(tochki[0::2], tochki[1::2]))
        sdvig = max((abs(a[0] - b[0]) for a, b in zip(okna, novye)), default=0.0)
        if sdvig >= 0.05:
            print(f"      [тишина] метки переведены на фактический монтаж "
                  f"(максимальный сдвиг {sdvig:.1f}с)")
        return novye
    except Exception as e:                           # noqa: BLE001
        print(f"      [тишина] перевод не выполнен ({e}) — метки плановые")
        return okna


def zvuk_tishina(video, metki, rab):
    """Тишину меряем на ДОРОЖКЕ ЗВУКА, а не в готовом миксе.

    ЗАЧЕМ. «Глухая тишина» в партитуре — это обрыв КОМНАТНОГО ТОНА, а не пауза
    в речи: на переломе рассказчик говорит поверх выключенной комнаты, и в
    общем миксе там честно стоит голос. Замер по миксу сообщал брак дважды на
    ролике, где обе тишины лежали на месте: на дорожке `<имя>-sfx.mp3` в тех же
    точках 5.5 с и 0.4 с абсолютного нуля.

    Окно шире, чем кажется нужным, и это не запас на всякий случай: фактический
    монтаж короче плана (128 с против 130), сборщик звука переносит метки на
    факт, и метка из таблицы уезжает от своего места на несколько секунд.
    """
    if not metki:
        return []
    dorozhka = Path(str(Path(video).with_suffix("")) + "-sfx.mp3")
    istochnik = dorozhka if dorozhka.exists() else Path(video)
    wav = rab / "z.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(istochnik), "-ac", "1",
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


def dolya_rechi(a, sr, N=2048):
    """Доля энергии в полосе разборчивости от всей слышимой полосы.

    Речь опознаётся ПОЛОСОЙ, а не громкостью, и это принципиально: гул,
    поднятый мастерингом до −15 LUFS, громче иной реплики, но живёт целиком
    ниже 300 Гц. Считаем спектр окнами по 2048 отсчётов и складываем энергию —
    отношение полос от абсолютного уровня не зависит, поэтому мерка одинаково
    читает и сырую дорожку, и сведённую, и пережатую кодеком.
    """
    f = np.fft.rfftfreq(N, 1 / sr)
    rech = (f >= RECH_NIZ) & (f < RECH_VERH)
    vsya = (f >= RECH_VSYA[0]) & (f < RECH_VSYA[1])
    chislitel = znamenatel = 0.0
    for i in range(0, len(a) - N, N):
        sp = np.abs(np.fft.rfft(a[i:i + N] * np.hanning(N))) ** 2
        chislitel += sp[rech].sum()
        znamenatel += sp[vsya].sum()
    return float(chislitel / znamenatel) if znamenatel else 0.0


def zvuk_rech(video, rab):
    """Звучит ли РЕЧЬ в готовом файле. Возвращает (доля, доля блоков) или None.

    Меряем дорожку САМОГО mp4, а не дорожки-исходники рядом с ним. Мерка
    тишины ходит в `<имя>-sfx.mp3` заслуженно — там она проверяет партитуру, —
    но из-за этого приёмка ни разу не открывала звук того файла, который уедет
    зрителю. Ровно в эту щель и прошёл ролик без голоса: sfx на месте, тишины
    на месте, гейты зелёные, монолога нет.
    """
    if not _ffprobe_audio(video):
        return None
    wav = rab / "rech.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1",
                    "-ar", "16000", "-f", "wav", str(wav), "-y"], check=True)
    w = wave.open(str(wav))
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    sr = w.getframerate()
    if len(a) < sr:
        return None
    blok = int(sr * RECH_BLOK)
    bloki = [dolya_rechi(a[i:i + blok], sr) for i in range(0, len(a) - blok, blok)]
    if not bloki:
        bloki = [dolya_rechi(a, sr)]
    s_rechyu = sum(1 for b in bloki if b >= RECH_DOLYA) / len(bloki)
    return dolya_rechi(a, sr), s_rechyu


def _ffprobe_audio(video):
    """Есть ли в файле звуковая дорожка вообще."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                          "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                          str(video)], capture_output=True, text=True)
    return "audio" in out.stdout


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
        if m["temno_vnutri"] is not None and m["temno_vnutri"] > LICO_ZANYATO:
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
        # ГОЛОС — ПЕРВОЙ МЕРКОЙ ЗВУКА. Ролик заявлен с монологом (есть VO),
        # значит монолог обязан звучать в файле, который уедет зрителю.
        rech = zvuk_rech(a.video, rab)
        if rech is None:
            plohih += 1
            print("  ✗ в готовом файле НЕТ ЗВУКОВОЙ ДОРОЖКИ, а ролик заявлен с "
                  "озвучкой")
        else:
            dolya, blokov = rech
            if dolya < RECH_DOLYA:
                plohih += 1
                print(f"  ✗ в готовом файле НЕ ЗВУЧИТ РЕЧЬ: доля полосы "
                      f"{RECH_NIZ}–{RECH_VERH} Гц = {dolya:.3f} при норме "
                      f"{RECH_DOLYA} (у сданных роликов 0.19–0.24)")
                print("      Дорожка есть, монолога в ней нет. Обычная причина — "
                      "синтез не отдал голос, и в ролик ушли одни эффекты, "
                      "поднятые мастерингом до громкости речи.")
            elif blokov < RECH_BLOKOV:
                plohih += 1
                print(f"  ✗ РЕЧЬ ПРОПАДАЕТ КУСКАМИ: она есть только в "
                      f"{blokov:.0%} блоков по {RECH_BLOK:.0f} с при норме "
                      f"{RECH_BLOKOV:.0%} (у сданных роликов 83–100%)")
                print("      Общая доля речи в норме, но держится на части "
                      "ролика: похоже, поштучный синтез потерял часть реплик.")

        # Длина готового файла нужна переводу меток: хвост после последней
        # реплики тянется по ОБЩЕЙ длине, а не по концу речи. Листы снимаются
        # раз в секунду, поэтому их число и есть длина в секундах.
        bed = zvuk_tishina(a.video, tishiny_iz_vo(a.vo, len(fajly)), rab)
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
