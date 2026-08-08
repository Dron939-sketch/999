#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sfx.py — процедурный звукорежиссёр завода: SFX-дорожка из таблицы VO.md.

Никаких внешних библиотек и лицензий: каждый звук СИНТЕЗИРУЕТСЯ ffmpeg'ом
(lavfi) — капля, лязг, шаги, гул, тиканье, перелист, room tone. Таблица SFX
уже прописана в сценарии озвучки (`## Дорожка звуков (SFX)`):

    | 0:00.0 | Гулкая тишина камеры (room tone) + капля воды | ... |
    | 0:14.6 | Лязг (металл, приглушённо) | ... |

Скрипт парсит тайм-коды, по ключевым словам выбирает синтез, собирает дорожку
(adelay + amix) и пишет один mp3. Дальше studio подмешивает его к голосу.

Использование:
    python3 tools/sfx.py examples/lektorij/pereproshivka-intro-VO.md \
        -o videos/pereproshivka-intro-sfx.mp3 --duration 55
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

# --- синтез отдельных звуков (все через ffmpeg lavfi) -----------------------

def _run(args):
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + args, check=True)


def synth(kind, path):
    """Синтез одного звука `kind` в wav. Возвращает True/False."""
    if kind == "drop":
        # капля: короткий свип вниз + эхо бетонной камеры
        _run(["-f", "lavfi", "-i",
              "sine=frequency=1150:duration=0.09",
              "-af",
              "asetrate=44100*0.92,aresample=44100,"
              "afade=t=in:d=0.005,afade=t=out:st=0.05:d=0.04,"
              "aecho=0.7:0.5:60|130:0.35|0.2,volume=0.9",
              path])
    elif kind == "clang":
        # лязг: шумовой удар через металлические резонансы
        _run(["-f", "lavfi", "-i", "anoisesrc=d=0.5:c=white:a=0.7",
              "-af",
              "bandpass=f=780:w=90,bandpass=f=780:w=120,"
              "aecho=0.6:0.4:40|90:0.4|0.25,"
              "afade=t=out:st=0.06:d=0.42,volume=1.6",
              path])
    elif kind == "step":
        # шаг по бетону: низкий тумп + щелчок подошвы
        _run(["-f", "lavfi", "-i", "sine=frequency=75:duration=0.12",
              "-f", "lavfi", "-i", "anoisesrc=d=0.05:c=pink:a=0.5",
              "-filter_complex",
              "[0]afade=t=out:st=0.02:d=0.1,volume=1.2[a];"
              "[1]highpass=f=1200,afade=t=out:st=0.005:d=0.04,volume=0.35[b];"
              "[a][b]amix=inputs=2:duration=longest",
              path])
    elif kind == "hum":
        # низкий гул (нарастает): два расстроенных синуса
        _run(["-f", "lavfi", "-i", "sine=frequency=52:duration=6",
              "-f", "lavfi", "-i", "sine=frequency=55:duration=6",
              "-filter_complex",
              "[0][1]amix=inputs=2,afade=t=in:d=3,afade=t=out:st=4.5:d=1.5,volume=0.5",
              path])
    elif kind == "tick":
        # тиканье шестерёнок: щёлкающий меандр малой скважности
        _run(["-f", "lavfi", "-i", "anoisesrc=d=4:c=white:a=0.3",
              "-af",
              "highpass=f=2500,"
              "tremolo=f=2.2:d=0.95,"
              "afade=t=in:d=1.2,afade=t=out:st=3:d=1,volume=0.5",
              path])
    elif kind == "page":
        # перелист плотной бумаги: короткий свуш из шума
        _run(["-f", "lavfi", "-i", "anoisesrc=d=0.28:c=pink:a=0.6",
              "-af",
              "highpass=f=900,lowpass=f=6500,"
              "afade=t=in:d=0.06,afade=t=out:st=0.14:d=0.14,volume=0.7",
              path])
    elif kind == "room":
        # room tone: еле слышный низкий шум (постель тишины)
        _run(["-f", "lavfi", "-i", "anoisesrc=d=8:c=brown:a=0.5",
              "-af", "lowpass=f=300,volume=0.16,afade=t=in:d=0.6",
              path])
    elif kind == "tvnoise":
        # ТВ-ШУМ: белый шум с резким обрывом — фирменная склейка оригинала.
        _run(["-f", "lavfi", "-i", "anoisesrc=d=0.4:c=white:a=0.9",
              "-af", "highpass=f=600,volume=0.55,afade=t=out:st=0.3:d=0.1",
              path])
    elif kind == "thud":
        # ГЛУХОЙ УДАР (дверь, засов, штамп по бумаге): низкий импульс + щелчок.
        _run(["-f", "lavfi", "-i", "sine=frequency=58:duration=0.5",
              "-f", "lavfi", "-i", "anoisesrc=d=0.06:c=brown:a=0.8",
              "-filter_complex",
              "[0]lowpass=f=180,afade=t=out:st=0.06:d=0.4[a];"
              "[1]lowpass=f=900,volume=0.7[b];[a][b]amix=inputs=2:normalize=0,volume=0.8",
              path])
    elif kind == "chime":
        # ЗВОН на слове-ударе: короткий металлический призвук.
        _run(["-f", "lavfi", "-i", "sine=frequency=2200:duration=0.7",
              "-af", "tremolo=f=7:d=0.3,volume=0.32,afade=t=out:st=0.1:d=0.6",
              path])
    elif kind == "breath":
        # ВДОХ перед ударной репликой (MELOCHI гр.В): полоса розового шума,
        # быстро набирающая и обрывающаяся — «набрал воздуха и сказал».
        _run(["-f", "lavfi", "-i", "anoisesrc=d=0.42:c=pink:a=0.5",
              "-af", "bandpass=f=900:width_type=h:w=700,"
                     "volume=0.5,afade=t=in:d=0.28,afade=t=out:st=0.3:d=0.12",
              path])
    elif kind == "heart":
        # СЕРДЦЕБИЕНИЕ под финальным ударом: два глухих толчка, пауза, повтор.
        _run(["-f", "lavfi", "-i", "sine=frequency=48:duration=2.4",
              "-af", "tremolo=f=1.2:d=0.9,lowpass=f=110,"
                     "volume=0.5,afade=t=in:d=0.3,afade=t=out:st=2.0:d=0.4",
              path])
    else:
        return False
    return True


# слова из VO-таблицы → синтезы (порядок важен: первое совпадение)
# ДВОЙНОГО СРАБАТЫВАНИЯ НЕ БЫВАЕТ: строка даёт ОДИН звук, по первому
# совпавшему слову. Раньше «белый ТВ-шум» ловился и на «тв-шум», и на «шум» —
# один и тот же синтез ложился в дорожку дважды, вдвое громче задуманного.
# Поэтому список идёт от частного к общему, а поиск обрывается на первом
# попадании (см. parse_sfx_table).
KEYWORDS = [
    ("капля", "drop"), ("лязг", "clang"), ("шаги", "step"), ("шаг", "step"),
    # «щелчок» и «обрыв» стояли в таблицах всех роликов и не звучали никогда:
    # слов не было в списке, а молчание никто не ловил.
    ("щелч", "clang"), ("клац", "clang"),
    ("гул", "hum"), ("тикань", "tick"), ("шестер", "tick"),
    ("перелист", "page"), ("страниц", "page"), ("переворот", "page"),
    ("room tone", "room"), ("тишина камеры", "room"),
    ("вдох", "breath"), ("дыхан", "breath"),
    ("тв-шум", "tvnoise"), ("тв шум", "tvnoise"), ("белый шум", "tvnoise"),
    ("шум", "tvnoise"), ("помех", "tvnoise"),
    ("штамп", "thud"), ("удар", "thud"), ("засов", "thud"), ("хлопок", "thud"),
    ("звон", "chime"), ("колокол", "chime"),
    ("сердц", "heart"), ("пульс", "heart"),
]

# ДИАПАЗОН В ТАЙМ-КОДЕ ТОЖЕ СЧИТАЕТСЯ. Первые две строки любой SFX-таблицы
# написаны диапазоном («0:00–0:00.4», «0:00.4–0:02»), а регэксп требовал
# закрывающую палку сразу за числом — и врыв ТВ-шумом и низкий гул
# пустого поля не звучали НИ В ОДНОМ ролике. Берём начало диапазона.
ROW = re.compile(r"\|\s*(\d+):(\d+(?:\.\d+)?)\s*(?:[–-]\s*[\d:.]+\s*)?\|([^|]+)\|")


def parse_sfx_table(md_path):
    """SFX-таблица → [(секунда, kind)] (одна строка может дать несколько кий)."""
    cues, in_sfx = [], False
    for line in open(md_path, encoding="utf-8"):
        if line.startswith("##"):
            in_sfx = "SFX" in line or "звук" in line.lower()
            continue
        if not in_sfx:
            continue
        m = ROW.match(line.strip())
        if not m:
            continue
        t = int(m.group(1)) * 60 + float(m.group(2))
        desc = m.group(3).lower()
        for word, kind in KEYWORDS:
            if word in desc:
                cues.append((t, kind))
                # «шаги ×2» — второй шаг через 0.5с
                if kind == "step" and ("×2" in desc or "x2" in desc):
                    cues.append((t + 0.5, "step"))
                break          # один звук на строку, см. комментарий у KEYWORDS
    return cues


def sfx_table_span(md_path):
    """Самый поздний тайм-код SFX-таблицы — плановая длина ролика.

    Берутся ВСЕ строки, включая те, для которых синтеза нет: последняя строка
    таблицы («резкий обрыв в тишину») звука не даёт, но именно она отмечает
    конец ролика. Без неё хвост тянулся до последнего ЗВУЧАЩЕГО кия, и склейка
    на титры уезжала на самый конец видео.
    """
    last, in_sfx = 0.0, False
    for line in open(md_path, encoding="utf-8"):
        if line.startswith("##"):
            in_sfx = "SFX" in line or "звук" in line.lower()
            continue
        if not in_sfx:
            continue
        m = ROW.match(line.strip())
        if m:
            last = max(last, int(m.group(1)) * 60 + float(m.group(2)))
    return last


def parse_vo_times(md_path):
    """Плановые времена реплик из VO-таблицы: [(старт, конец)] по порядку VO-n."""
    rows = []
    for line in open(md_path, encoding="utf-8"):
        m = re.match(r"\|\s*VO-(\d+)\s*\|\s*(\d+):(\d+(?:\.\d+)?)\s*[–-]\s*"
                     r"(\d+):(\d+(?:\.\d+)?)\s*\|", line.strip())
        if m:
            rows.append((int(m.group(1)),
                         int(m.group(2)) * 60 + float(m.group(3)),
                         int(m.group(4)) * 60 + float(m.group(5))))
    rows.sort()
    return [(a, b) for _, a, b in rows]


def remap_cues(cues, planned, real, plan_total, real_total):
    """Перевести тайм-коды звука с ПЛАНОВОГО монтажа на фактический.

    Тайм-коды в таблице проставлены по сценарию, а диктор говорит не ровно
    столько, сколько заявлено: ролик растягивается, и звук, поставленный на
    абсолютную секунду, отъезжает от того, что он озвучивает. В «Теориях
    личности» звон битого стекла так звучал, когда очки ещё сидели на маске,
    а ТВ-шум склейки — за четыре секунды до самой склейки.

    Опорные точки — начала и концы реплик: они известны и в плане (VO-таблица),
    и в факте (`animdsl timing` по подготовленному сценарию). Между опорами
    время тянется линейно, до первой и после последней — пропорционально
    остатку. Звук остаётся привязан к РЕЧИ, а не к секунде.
    """
    if not planned or not real or len(planned) != len(real):
        return cues
    src = [0.0] + [t for p in planned for t in p] + [max(plan_total, planned[-1][1])]
    dst = [0.0] + [t for p in real for t in p] + [max(real_total, real[-1][1])]
    # Опоры обязаны монотонно расти, иначе интерполяция даёт отрицательный шаг.
    for i in range(1, len(src)):
        src[i] = max(src[i], src[i - 1] + 1e-3)
        dst[i] = max(dst[i], dst[i - 1] + 1e-3)

    def at(t):
        if t <= src[0]:
            return dst[0]
        for i in range(1, len(src)):
            if t <= src[i]:
                k = (t - src[i - 1]) / (src[i] - src[i - 1])
                return dst[i - 1] + k * (dst[i] - dst[i - 1])
        return dst[-1] + (t - src[-1])

    return [(round(at(t), 2), kind) for t, kind in cues]


def build_track(cues, out_path, duration):
    """Собрать дорожку: каждый синтез на своём тайм-коде + room-постель.

    ПОСТЕЛЬ (MELOCHI.md гр.В): комнатный тон стелется под ВСЮ длину ролика, а
    не ставится разовым звуком. Иначе в паузах — абсолютный цифровой ноль, и
    зритель слышит «выключенный звук» вместо тишины комнаты. Уровень низкий
    (едва на грани слышимости) — работает подсознательно, речь не глушит.
    """
    with tempfile.TemporaryDirectory() as td:
        inputs, delays = [], []
        bed = os.path.join(td, "roomtone.wav")
        try:
            _run(["-f", "lavfi", "-i", f"anoisesrc=d={max(duration, 1):.2f}:c=brown:a=0.5",
                  # ПОСТЕЛЬ ГРОМЧЕ, ЧЕМ БЫЛА (0.055 → 0.16). Замечание студии:
                  # «от реплики до реплики акустический вакуум, между репликами
                  # пустота». Так и было: постель стояла на грани слышимости, и
                  # в паузах дорожка проваливалась в цифровой ноль — а цифровой
                  # ноль слышно как обрыв записи, а не как тишину комнаты.
                  #
                  # Раньше поднять её было нельзя: SFX и так лез поверх речи.
                  # Теперь можно — голос прижимает фон боковой цепью
                  # (studio.py), поэтому под речью постель уходит вниз сама, а в
                  # паузах возвращается и держит комнату. Полоса та же: ниже
                  # 260 Гц, речи не мешает даже неприжатая.
                  "-af", "lowpass=f=260,highpass=f=40,volume=0.16,"
                         "afade=t=in:d=0.8,afade=t=out:st="
                         f"{max(duration - 0.8, 0.1):.2f}:d=0.8",
                  bed])
            inputs.append(bed); delays.append(0)
        except subprocess.CalledProcessError:
            pass  # без постели дорожка всё равно соберётся
        for i, (t, kind) in enumerate(cues):
            wav = os.path.join(td, f"cue{i}.wav")
            if not synth(kind, wav):
                continue
            inputs.append(wav)
            delays.append(int(t * 1000))
        if not inputs:
            return False
        args = []
        for wav in inputs:
            args += ["-i", wav]
        chains = []
        for i, ms in enumerate(delays):
            chains.append(f"[{i}]adelay={ms}|{ms}[d{i}]")
        mix = "".join(f"[d{i}]" for i in range(len(inputs)))
        chains.append(
            f"{mix}amix=inputs={len(inputs)}:duration=longest:normalize=0,"
            f"apad=whole_dur={duration},atrim=0:{duration}[out]"
        )
        _run(args + ["-filter_complex", ";".join(chains),
                     "-map", "[out]", "-b:a", "128k", out_path])
    return True


def main(argv):
    ap = argparse.ArgumentParser(description="SFX-дорожка из VO.md (синтез ffmpeg)")
    ap.add_argument("vo_md")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--duration", type=float, default=55.0)
    ap.add_argument("--map-json", help="карта блоков (.map.json): какой блок какой "
                                       "репликой VO озвучен — нужна, когда есть "
                                       "дикторские реплики без речевого блока")
    ap.add_argument("--times-json", help="`animdsl timing` подготовленного сценария: "
                                         "фактические времена реплик. Есть — тайм-коды "
                                         "звука переводятся с плана на факт.")
    args = ap.parse_args(argv)

    cues = parse_sfx_table(args.vo_md)
    if not cues:
        print("SFX-таблица пуста или не найдена — дорожка не создана.")
        return 1
    if args.times_json and os.path.isfile(args.times_json):
        try:
            with open(args.times_json, encoding="utf-8") as f:
                blocks = json.load(f)
            real_all = [(b["start"], b["end"]) for b in blocks.get("blocks", [])]
            planned_all = parse_vo_times(args.vo_md)
            # ДИКТОРСКИЕ РЕПЛИКИ ЛОМАЛИ ПАРУ. У реплики за кадром нет речевого
            # блока (рот открывать некому), поэтому реплик в таблице больше,
            # чем блоков у движка, и сверка «поровну» отключала перевод целиком
            # — в «Перепрошивке» с двумя дикторскими звук так и остался бы на
            # плановых секундах. Пары строим по КАРТЕ блоков (`.map.json`,
            # тот же файл, по которому собирается голос): каждый блок знает
            # свой номер VO, дикторские просто не участвуют в опорах.
            if args.map_json and os.path.isfile(args.map_json):
                with open(args.map_json, encoding="utf-8") as f:
                    order = json.load(f)
                pairs = [(planned_all[n - 1], real_all[i])
                         for i, n in enumerate(order)
                         if i < len(real_all) and 1 <= n <= len(planned_all)]
                planned = [a for a, _ in pairs]
                real = [b for _, b in pairs]
            else:
                planned, real = planned_all, real_all
            if real and len(real) == len(planned):
                before = list(cues)
                # Хвост после последней реплики (титры, точка) тянется по
                # ОБЩЕЙ длине, а не по концу речи: иначе звук склейки уезжает
                # за конец ролика. План хвоста — самый поздний тайм-код таблицы,
                # факт — реальная длина видео.
                cues = remap_cues(cues, planned, real,
                                  sfx_table_span(args.vo_md) or max(t for t, _ in cues),
                                  args.duration)
                moved = max((abs(a[0] - b[0]) for a, b in zip(before, cues)), default=0.0)
                print(f"  тайм-коды звука переведены на фактический монтаж "
                      f"(максимальный сдвиг {moved:.1f}с)")
            else:
                print(f"  [sfx] реплик в плане {len(planned)}, в факте {len(real)} — "
                      "перевод тайм-кодов пропущен, звук встанет по плану.")
        except Exception as e:                       # noqa: BLE001
            print(f"  [sfx] тайминг не прочитан ({e}) — звук встанет по плану.")
    ok = build_track(cues, args.output, args.duration)
    print(f"OK: {args.output} — {len(cues)} звуков" if ok else "СБОЙ синтеза")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
