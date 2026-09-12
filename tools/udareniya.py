#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
udareniya.py — УДАРЕНИЯ: где они стоят в сценарии и читает ли их синтез.

ДВЕ РАЗНЫЕ БЕДЫ, и их всё время путали.

  1) МЕСТО УДАРЕНИЯ В ТЕКСТЕ. `script_lint.accent_problems` проверяет, что знак
     ЕСТЬ и стоит после гласной, — и молчит о том, после КАКОЙ. Так в «Гневе»
     полгода прожило «полно́чи» вместо «по́лночи», в первой же строке хука.
     Здесь это ловится сверкой со словарём `udareniya-slovar.json`: он собран
     из всех VO-сценариев репозитория и вычитан руками. Слово, размеченное не
     так, как в словаре, — ошибка; слово, которого в словаре нет, — повод
     проверить и внести, а не молча пропустить.

  2) ЧИТАЕТ ЛИ РАЗМЕТКУ СИНТЕЗ. Это вопрос не к тексту, а к движку, и ответа
     на него у нас не было: первая проба («одна фраза в четырёх разметках»)
     требовала ушей и вердикта человека, вердикта не случилось, а ролики ушли
     в релиз с чужими ударениями. `--proba` отвечает измерением.

КАК МЕРЯЕТСЯ. Минимальная пара — два слова, отличающиеся ТОЛЬКО местом
ударения («за́мок» и «замо́к»). Если разметка работает, две записи обязаны
звучать по-разному, и тяжесть слова обязана переехать на второй слог. Если
разметку выбрасывают — записи совпадут с точностью до шума.

  · РАСХОЖДЕНИЕ — средняя разница огибающих двух записей, приведённых к общей
    длине и громкости. 0.00 — записи неотличимы, значит знак выброшен.
  · ТЯЖЕСТЬ — центр масс энергии в долях длины слова. У «за́мок» он левее, у
    «замо́к» правее. Рабочая разметка обязана двигать его ВПРАВО, когда знак
    переехал на второй слог.

Мера грубая и честно грубая: она не «слышит» ударение, а видит, что запись
изменилась и в какую сторону поехала тяжесть. Этого хватает, чтобы выбрать
разметку из четырёх, и не хватает, чтобы судить о качестве речи.

Использование:
    python3 tools/udareniya.py                       # сверка всех сценариев
    python3 tools/udareniya.py examples/lektorij/gnev-intro-VO.md
    python3 tools/udareniya.py --proba videos/udarenie-proba2-voice.mp3
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SLOVAR = Path(__file__).resolve().parent / "udareniya-slovar.json"
ACCENT = "́"
VOWELS = "аеиоуыэюяёАЕИОУЫЭЮЯЁ"

# Порядок реплик стенда `udarenie-proba2` — менять только вместе с его VO.
PARY = [("замок", 0), ("мука", 7), ("стоит", 14)]
RAZMETKI = [("A акута", 0, 1), ("B плюс", 2, 3), ("C заглавная", 4, 5)]
BEZ = 6                       # седьмая реплика пары — без разметки
ODNOSLOZHNOE = (21, 22)       # «ва́с» и «вас»


# ─────────────────────────── часть 1: текст ────────────────────────────────

def slovar():
    return json.loads(SLOVAR.read_text(encoding="utf-8"))


def slova_repliki(raw):
    """Слова реплики с разметкой, как они уйдут в синтез."""
    return re.findall(rf"[А-Яа-яЁё{ACCENT}-]+", raw)


def proverit(path, sl=None):
    """Ошибки места ударения в одном VO: [(реплика, слово, что не так)]."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from script_lint import parse                              # noqa: E402
    sl = sl or slovar()
    oshibki, novye = [], []
    for r in parse(path):
        for w in slova_repliki(r["raw"]):
            if ACCENT not in w:
                continue
            base = w.replace(ACCENT, "").lower()
            if sum(c in VOWELS for c in base) < 2:
                continue                                       # односложное
            variants = sl.get(base)
            if variants is None:
                novye.append((r["n"], w))
            elif w.lower() not in variants:
                oshibki.append((r["n"], w, "в словаре " + " / ".join(variants)))
    return oshibki, novye


# ─────────────────────────── часть 2: звук ─────────────────────────────────

def pcm(path, sr=16000):
    """Дорожка как моно float32 [-1, 1]."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le",
         "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0, sr


def ogibayushchaya(x, sr, hop_s=0.005):
    """RMS по окнам hop_s."""
    hop = max(1, int(sr * hop_s))
    n = len(x) // hop
    if n == 0:
        return np.zeros(1)
    return np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-12)


def slova_dorozhki(x, sr, n_ozhidaem, porog_rel=0.06, pauza_s=0.35):
    """Дорожка → куски со словами. Режем по тишине между репликами."""
    env = ogibayushchaya(x, sr)
    porog = porog_rel * env.max()
    zvuk = env > porog
    hop = int(sr * 0.005)
    kuski, i = [], 0
    while i < len(zvuk):
        if not zvuk[i]:
            i += 1
            continue
        j = i
        tishina = 0
        while j < len(zvuk):
            if zvuk[j]:
                tishina = 0
            else:
                tishina += 1
                if tishina * 0.005 > pauza_s:
                    break
            j += 1
        konec = j - tishina
        if (konec - i) * 0.005 > 0.12:
            kuski.append((i * hop, konec * hop))
        i = j
    if len(kuski) != n_ozhidaem:
        return None, kuski
    return [x[a:b] for a, b in kuski], kuski


def tyazhest(w, sr):
    """Центр масс энергии в долях длины слова: 0.0 — начало, 1.0 — конец."""
    env = ogibayushchaya(w, sr)
    t = np.arange(len(env))
    e = env ** 2
    return float((t * e).sum() / (e.sum() + 1e-12) / max(1, len(env) - 1))


def rashozhdenie(a, b, sr, n=48):
    """Разница огибающих двух слов: 0 — неотличимы, 1 — совсем разные."""
    ea, eb = ogibayushchaya(a, sr), ogibayushchaya(b, sr)
    xa = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(ea)), ea)
    xb = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(eb)), eb)
    xa = xa / (xa.max() + 1e-12)
    xb = xb / (xb.max() + 1e-12)
    return float(np.abs(xa - xb).mean())


def proba(mp3):
    """Стенд `udarenie-proba2`: какую разметку синтез действительно читает."""
    x, sr = pcm(mp3)
    n = 23
    slova, kuski = slova_dorozhki(x, sr, n)
    if slova is None:
        print(f"  дорожка разобралась на {len(kuski)} слов вместо {n} — "
              f"стенд собран не тем сценарием или паузы съехали")
        return 1

    print(f"\n  ПРОБА РАЗМЕТКИ УДАРЕНИЙ: {mp3}\n")
    itog = {name: {"двигает": 0, "молчит": 0} for name, _, _ in RAZMETKI}
    for para, ofs in PARY:
        d_bez = slova[ofs + BEZ]
        print(f"    ── пара «{para}» " + "─" * 46)
        print(f"       без разметки: тяжесть {tyazhest(d_bez, sr):.3f}, "
              f"длина {len(d_bez) / sr:.2f}с")
        for name, i1, i2 in RAZMETKI:
            a, b = slova[ofs + i1], slova[ofs + i2]
            r = rashozhdenie(a, b, sr)
            t1, t2 = tyazhest(a, sr), tyazhest(b, sr)
            sdvig = t2 - t1
            rabotaet = r > 0.05 and sdvig > 0.01
            itog[name]["двигает" if rabotaet else "молчит"] += 1
            print(f"       {name:<14} расхождение {r:.3f}  "
                  f"тяжесть {t1:.3f} → {t2:.3f}  сдвиг {sdvig:+.3f}  "
                  f"{'работает' if rabotaet else 'НЕТ'}")

    a, b = slova[ODNOSLOZHNOE[0]], slova[ODNOSLOZHNOE[1]]
    r = rashozhdenie(a, b, sr)
    print(f"\n    ── односложное «вас» " + "─" * 41)
    print(f"       с акутой против без: расхождение {r:.3f}  "
          f"{'ЗНАК МЕНЯЕТ СЛОВО' if r > 0.05 else 'знак ничего не делает'}")

    print("\n  ИТОГ")
    for name, _, _ in RAZMETKI:
        d = itog[name]["двигает"]
        print(f"    {name:<14} двигает ударение в {d} парах из {len(PARY)}")
    luchshaya = max(RAZMETKI, key=lambda m: itog[m[0]]["двигает"])
    if itog[luchshaya[0]]["двигает"] == 0:
        print("\n    Ни одна разметка не двигает ударение: синтез читает текст "
              "как есть,\n    и место ударения задаётся только выбором слова "
              "и контекстом.")
    else:
        print(f"\n    Рабочая разметка: {luchshaya[0]} — её и ставить во все "
              f"сценарии.")
    return 0


# ────────────────────────────── запуск ─────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description="Ударения: словарь и проба")
    ap.add_argument("vo", nargs="*", help="VO-файлы (по умолчанию все)")
    ap.add_argument("--proba", help="дорожка стенда udarenie-proba2")
    a = ap.parse_args(argv)

    if a.proba:
        return proba(a.proba)

    files = [Path(p).resolve() for p in a.vo] or sorted(
        (ROOT / "examples" / "lektorij").glob("*-VO.md"))
    sl = slovar()
    vsego_o, vsego_n = 0, 0
    for f in files:
        oshibki, novye = proverit(f, sl)
        if not oshibki and not novye:
            continue
        print(f"\n  {f.relative_to(ROOT)}")
        for n, w, why in oshibki:
            print(f"    ОШИБКА {n}: «{w}» — {why}")
        for n, w in novye:
            print(f"    новое   {n}: «{w}» — проверь и внеси в словарь")
        vsego_o += len(oshibki)
        vsego_n += len(novye)
    print(f"\n  ударения: {vsego_o} ошибок, {vsego_n} слов вне словаря "
          f"({len(sl)} в словаре)\n")
    return 1 if vsego_o else 0


if __name__ == "__main__":
    raise SystemExit(main())
