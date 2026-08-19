#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rasshifrovka.py — РАСПОЗНАВАНИЕ ЗАПИСИ ЛЕКЦИИ ПО СЛОВАМ, с таймкодами.

ЗАЧЕМ. Видеоряд лекции строится под речь, а не под текст статьи на сайте, — и
это выяснилось дорого. Первая сборка раскладывала кадры по долям слов СТАТЬИ,
считая, что запись её начитывает. Запись оказалась устной лекцией Фреди:
начинается «здравствуйте, с вами Фреди», кончается «всего доброго» — другой
текст, другой порядок, другой темп. Раздел «Откуда берутся настройки» уехал
на МИНУТУ.

Проверить это можно было и раньше, не распознаванием: если разложить текст по
записи пропорционально и посмотреть, попадают ли границы абзацев в паузы, —
выходит 26–39% при случайном уровне 33%. То есть выравнивание не работало
вовсе, и мерка это показывала. Мерку я тогда не сделал.

ПОЧЕМУ ДО ЭТОГО «СЕТИ НЕТ». В заводских заметках записано, что сеть из
песочницы закрыта. Закрыта она на meysternlp.ru и на амверу — то есть на СВОИ
хосты; pypi.org и alphacephei.com открыты. Я принял частное за общее и полдня
строил раскладку вслепую, имея под рукой распознавание.

Модель — vosk-model-small-ru (46 МБ), точность по словам достаточная: нужен не
идеальный текст, а тайминг. Средняя уверенность на этой записи 0.90.

    python3 tools/rasshifrovka.py examples/assets/audio-lekciya-koleya-1.mp3
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.environ.get("VOSK_MODEL", "/opt/vosk-model-small-ru-0.22")


def raspoznat(audio, model_dir=MODEL):
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "a.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(audio),
                        "-ac", "1", "-ar", "16000", wav], check=True)
        w = wave.open(wav, "rb")
        r = KaldiRecognizer(Model(model_dir), w.getframerate())
        r.SetWords(True)
        slova = []
        while True:
            d = w.readframes(8000)
            if not d:
                break
            if r.AcceptWaveform(d):
                slova += json.loads(r.Result()).get("result", [])
        slova += json.loads(r.FinalResult()).get("result", [])
    return slova


def frazy(slova, razryv=0.45):
    """Речь, разбитая на фразы по паузам. Единица раскладки видеоряда."""
    if not slova:
        return []
    out, cur = [], [slova[0]]
    for a, b in zip(slova, slova[1:]):
        if b["start"] - a["end"] > razryv:
            out.append(cur)
            cur = [b]
        else:
            cur.append(b)
    out.append(cur)
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("-o", "--out", default="examples/lektorij/lekciya-koleya-1-slova.json")
    a = ap.parse_args(argv)
    slova = raspoznat(ROOT / a.audio if not os.path.isabs(a.audio) else a.audio)
    (ROOT / a.out).write_text(json.dumps(slova, ensure_ascii=False), encoding="utf-8")
    fr = frazy(slova)
    print(f"  слов {len(slova)}, фраз {len(fr)}, "
          f"последнее слово на {slova[-1]['end']:.1f}с")
    print(f"  средняя уверенность {sum(w.get('conf',1) for w in slova)/len(slova):.3f}")
    print(f"  записано: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
