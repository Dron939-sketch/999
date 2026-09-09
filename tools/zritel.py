#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zritel.py — ЗРИТЕЛЬНЫЙ ЗАЛ: смотровой лист для приёмки ролика зрителями.

ЗАЧЕМ. Все приёмщики завода меряют РЕМЕСЛО: попадает ли жест в слово, меняется
ли крупность на кате, не распирает ли фигура кадр. Ни один не отвечает на
вопрос, ради которого ролик сняли: захочет ли человек пройти курс и решит ли,
что это ему надо. Такого числа нет и не будет — на него отвечают зрители.

Этот инструмент НЕ СУДИТ. Он готовит то, по чему судят:

  * кадр на каждую реплику — чтобы смотреть, а не вспоминать;
  * дорожку текста с тайм-кодами;
  * факты, которые можно проверить счётом, а не вкусом (см. ниже).

Приговор выносит зал — пять зрителей из `ZRITELNYJ-ZAL.md`, каждый со своей
причиной смотреть. Их вердикты и то, что по ним поправлено, ложатся в
`<id>-ZAL.md` рядом со сценарием: раунд, претензии, правка, следующий раунд.

ЧЕГО ЗДЕСЬ НЕТ И НЕ БУДЕТ. Числа «интерес», «желание», «восторг». Гейт,
угадывающий смысл по словам, врёт увереннее, чем помогает, — репозиторий это
уже проходил на приборе, который «измерил» сходство персонажа и увёл работу на
день (`RULES.md`, «Сломан был прибор»). Здесь машина считает только то, что
можно пересчитать руками: сказано слово или не сказано, на какой секунде,
сколько раз.

Использование:
    python3 tools/zritel.py filosofiya-intro                 # факты + лист
    python3 tools/zritel.py filosofiya-intro --sheet out.png # только лист
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import script_lint as L  # noqa: E402

# Слова, которыми зритель снимает свои возражения. Проверяется НАЛИЧИЕ в
# тексте, а не убедительность: «сколько это стоит», «сколько это займёт»,
# «в каком виде» — три вопроса, на которые человек отвечает себе сам, если
# ролик не ответил, и отвечает обычно не в пользу курса.
VOZRAZHENIYA = {
    "цена": r"беспла́?тн|да́?ром|ни рубля́?",
    "объём": r"\bде́?сять ле́?кций|\d+\s*ле́?кци|часа́?|часо́?в|мину́?т",
    "формат": r"слу́?шать|чита́?ть|подка́?ст|аудио|нау́?шник",
    "имя курса": r"«[^»]+»",
}


def prod(pid):
    man = json.loads((ROOT / "tools" / "productions.json").read_text(encoding="utf-8"))
    for p in man["productions"]:
        if p["id"] == pid:
            return p
    raise SystemExit(f"нет продакшена «{pid}» в tools/productions.json")


def temy_kursa(vo_text):
    """Темы курса из шапки VO: строка «Курс: <url> — N лекций, ~T: a, b, c…».

    Нужны, чтобы проверить простую вещь: назвал ли ролик хоть одну настоящую
    тему курса. Зритель узнаёт СВОЙ вопрос, а не слово «вопросы».
    """
    m = re.search(r"Ку́?рс:.*?—.*?:(.*?)\n\n", vo_text, re.S | re.I)
    if not m:
        return []
    body = re.sub(r"\s+", " ", m.group(1))
    return [t.strip(" .") for t in body.split(",") if len(t.strip()) > 3]


def facts(pid):
    p = prod(pid)
    vo_path = ROOT / p["vo"]
    vo = vo_path.read_text(encoding="utf-8")
    rows = L.parse(vo_path)
    text = " ".join(r["text"] for r in rows)
    low = text.lower()

    out = {"id": pid, "реплик": len(rows)}

    mp4 = ROOT / "videos" / f"{pid}-final.mp4"
    if mp4.exists():
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", str(mp4)],
                           capture_output=True, text=True).stdout.strip()
        out["длина, с"] = round(float(d), 1) if d else None

    out["первое слово, с"] = L.first_time(rows[0]["time"]) if rows else None
    for beat, name in (("ХУК", "хук, с"), ("РАЗВОРОТ", "разворот, с"), ("ЖАЛО", "жало, с")):
        r = next((r for r in rows if beat in r["beat"].upper()), None)
        out[name] = L.first_time(r["time"]) if r else None

    # Возражения зрителя: сказано или не сказано.
    out["снятые возражения"] = {k: bool(re.search(v, low)) for k, v in VOZRAZHENIYA.items()}

    # Названа ли хоть одна НАСТОЯЩАЯ тема курса — не слово «вопросы», а вопрос.
    #
    # ПЕРВАЯ ВЕРСИЯ ЭТОЙ ПРОВЕРКИ ВРАЛА, и это стоит помнить. Она искала любое
    # из первых трёх длинных слов темы и засчитала «что такое философия»,
    # «философия как образ жизни» и «свобода воли» — потому что слово
    # «Философия» стоит в НАЗВАНИИ КУРСА в жале, а «свобода» попалась в
    # «это и есть свобода». Ролик не назвал ни одну из этих тем; прибор
    # отрапортовал четыре из десяти и был бы принят на веру.
    #
    # Поэтому: имя курса из текста вычёркивается, и тема засчитывается только
    # при совпадении ДВУХ значимых слов (у односложных тем — точного слова).
    temy = temy_kursa(vo)
    bez_imeni = re.sub(r"«[^»]+»", " ", low)
    hit = []
    for t in temy:
        klyuch = re.findall(r"[а-яё]{5,}", t.lower())
        if not klyuch:
            continue
        nashli = sum(1 for k in klyuch if k[:6] in bez_imeni)
        if nashli >= (1 if len(klyuch) == 1 else 2):
            hit.append(t)
    # ЭТО СОВПАДЕНИЯ СЛОВ, А НЕ НАЗВАННЫЕ ТЕМЫ, и поле названо так нарочно.
    # «свобода воли» засчитывается по слову «свобода» из «это и есть свобода» —
    # тема не названа, слово встретилось. Отличить одно от другого счётом
    # нельзя; это решает зал, глядя на текст. Число здесь — подсказка, где
    # смотреть, а не оценка.
    out["слова тем в тексте"] = {"тем в курсе": len(temy), "совпало": hit}

    # Обращение и вопросы — чем ролик втягивает зрителя внутрь.
    out["реплик с «вы/ты»"] = sum(1 for r in rows if L.ADDRESS.search(r["text"]))
    out["вопросов к зрителю"] = text.count("?")
    return out, rows


def sheet(pid, rows, dst):
    """Кадр на каждую реплику: зал смотрит, а не вспоминает."""
    mp4 = ROOT / "videos" / f"{pid}-final.mp4"
    if not mp4.exists():
        return None
    tmp = Path(dst).parent / f".{pid}-frames"
    tmp.mkdir(parents=True, exist_ok=True)
    files = []
    for i, r in enumerate(rows, 1):
        t0 = L.first_time(r["time"]) or 0
        f = tmp / f"{i:02d}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t0 + 0.9),
                        "-i", str(mp4), "-frames:v", "1", "-vf", "scale=420:-1",
                        str(f)], check=True)
        files.append(f)
    if not files:
        return None
    n = len(files)
    cols = 3
    rows_n = (n + cols - 1) // cols
    ins = []
    for f in files:
        ins += ["-i", str(f)]
    parts, labels = [], []
    for r_i in range(rows_n):
        idx = [i for i in range(r_i * cols, min(n, (r_i + 1) * cols))]
        if len(idx) < cols:                      # добить пустыми не выйдет — режем
            idx = idx[:len(idx)]
        lab = f"r{r_i}"
        parts.append("".join(f"[{i}]" for i in idx) + f"hstack={len(idx)}[{lab}]")
        labels.append(f"[{lab}]")
    if len(labels) > 1:
        # строки разной ширины склеить нельзя — берём только полные
        full = [l for l, r_i in zip(labels, range(rows_n)) if (r_i + 1) * cols <= n]
        parts.append("".join(full) + f"vstack={len(full)}")
    fc = ";".join(parts)
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins +
                   ["-filter_complex", fc, str(dst)], check=True)
    return dst


def main(argv=None):
    ap = argparse.ArgumentParser(description="Смотровой лист для зрительного зала")
    ap.add_argument("id")
    ap.add_argument("--sheet", help="куда положить контактный лист (png)")
    a = ap.parse_args(argv)

    f, rows = facts(a.id)
    print(f"\n  СМОТРОВОЙ ЛИСТ: {a.id}\n")
    for k, v in f.items():
        if isinstance(v, dict):
            print(f"    {k}:")
            for kk, vv in v.items():
                mark = "да " if vv is True else ("НЕТ" if vv is False else "   ")
                print(f"      {mark} {kk}: {vv if not isinstance(vv, bool) else ''}")
        else:
            print(f"    {k}: {v}")
    print("\n  ДОРОЖКА ТЕКСТА")
    for r in rows:
        print(f"    {r['n']:<6}{r['time']:<16}{r['beat']:<16}{r['raw']}")
    if a.sheet:
        p = sheet(a.id, rows, a.sheet)
        print(f"\n  кадры по репликам: {p}" if p else "\n  видео не собрано — кадров нет")
    print("\n  Приговор выносит зал, а не этот вывод: пять зрителей из\n"
          "  examples/lektorij/ZRITELNYJ-ZAL.md, протокол — в <id>-ZAL.md.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
