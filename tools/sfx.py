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
KEYWORDS = [
    ("капля", "drop"), ("лязг", "clang"), ("шаги", "step"), ("шаг", "step"),
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

ROW = re.compile(r"\|\s*(\d+):(\d+(?:\.\d+)?)\s*\|([^|]+)\|")


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
    return cues


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
                  "-af", "lowpass=f=260,highpass=f=40,volume=0.055,"
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
    args = ap.parse_args(argv)

    cues = parse_sfx_table(args.vo_md)
    if not cues:
        print("SFX-таблица пуста или не найдена — дорожка не создана.")
        return 1
    ok = build_track(cues, args.output, args.duration)
    print(f"OK: {args.output} — {len(cues)} звуков" if ok else "СБОЙ синтеза")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
