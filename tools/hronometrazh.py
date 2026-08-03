#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hronometrazh.py — ПЕРЕПИСЫВАЕТ `speaks for` ПО ФАКТУ ОЗВУЧКИ.

Замечание студии: «липсинк не попадает в голос». Причина не в липсинке.

В раскадровке длительность реплики пишется РУКАМИ, по мерке 0.36 с на слово —
другого способа у автора нет: озвучки в этот момент ещё не существует. Мерка
снята с готовых дорожек серии и в среднем честная, но на КОНКРЕТНОЙ реплике
синтез длиннее расчёта на 0.2–0.45 с: диктор дышит между предложениями, ставит
паузу перед ударным словом, тянет последний слог. Разница у каждой реплики своя,
и по ролику она складывается.

ЧТО ИМЕННО ЛОМАЕТСЯ. Рот в готовом ролике всё-таки открывается по звуку:
`prep_lipsync` подменяет `speaks for` дорожкой рта РЕАЛЬНОЙ длины. Врёт всё
остальное, что считается от объявленного числа:

  · КАТЫ И ЖЕСТЫ СОСЕДНЕЙ ВЕТКИ `do{}`. Режиссёр ставит `wait 2.2s` внутри
    реплики, объявленной на 3.6 с, — плечи на «и всё равно сорвались», две
    трети фразы. Если реплика на деле идёт 4.4 с, жест приходит на середине:
    поставлен-то он на 2.2 с, а фраза стала длиннее. `prep_lipsync` это лечит
    растяжкой, но растяжка — заплатка поверх вранья: она тянет ветку на 22%
    ровно потому, что число в сценарии на 22% неверно.
  · ГЕЙТ ТИШИНЫ (`pauses.py`) считает таймлайн СЦЕНАРИЯ. Пока `speaks for`
    выдуман, гейт меряет выдуманный ролик — ровно ошибка «мерка снята не там,
    где живёт дефект» из RABOTA-NAD-OSHIBKAMI §I.2.
  · ТАЙМКОДЫ VO-ТАБЛИЦЫ идут цепочкой: старт следующей реплики = конец
    предыдущей плюс пауза. Ошибка каждой реплики складывается с предыдущими, и
    объявленный финал расходится с фактом на несколько секунд. Это и есть
    «расхождение копится».

ЧТО ДЕЛАЕТ ИНСТРУМЕНТ. Берёт готовые файлы озвучки (`<parts>/vo-N.mp3`, их
кладёт `voiceover.py --parts-dir`), меряет каждый и переписывает `speaks for`
фактическим числом. Заодно:

  · РАСТЯГИВАЕТ СОСЕДНЮЮ ВЕТКУ `do{}` на то же отношение — по той же формуле и
    тем же регулярным выражением, что и `prep_lipsync`. Каты остаются там же
    по ДОЛЕ реплики, где их поставил режиссёр;
  · ПЕРЕСЧИТЫВАЕТ ТАЙМКОДЫ VO-ТАБЛИЦЫ (`--vo`), сохраняя паузы между
    репликами: паузы — режиссёрское решение, длительности — факт.

После этого растяжка в `prep_lipsync` становится тождественной (k = 1.00). Она
никуда не делась и остаётся страховкой на случай, когда озвучку пересинтезируют
и она снова разъедется, — но в норме тянуть больше нечего.

ПОЧЕМУ ЭТО НЕ РАЗОВАЯ ПРАВКА РУКАМИ. Число, вписанное однажды, устаревает при
первой же переозвучке: синтез не детерминирован до миллисекунды, а правка
ремарки темпа («темп 0.88») меняет длину реплики на проценты. Поэтому мерка
снимается на каждом прогоне завода.

ГДЕ ЗАПУСКАЕТСЯ. В заводе (`studio.py`) — между озвучкой частями и липсинком:
единственный момент, когда mp3 уже есть, а сценарий ещё не отрендерен. Локально
без ключей Fish частей не существует и мерить нечего — инструмент честно
говорит об этом и не трогает файл.

Использование:
    # переписать сценарий и таймкоды VO по фактической озвучке
    python3 tools/hronometrazh.py examples/lektorij/emocii.anim \
        --parts videos/emocii-parts --vo examples/lektorij/emocii-VO.md

    # только показать расхождение, ничего не трогая (гейт)
    python3 tools/hronometrazh.py examples/lektorij/emocii.anim \
        --parts videos/emocii-parts --check
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# КОНВЕНЦИИ БЕРУТСЯ У prep_lipsync, А НЕ ПИШУТСЯ ЗАНОВО.
#
# Оба инструмента ходят по одному и тому же сценарию и обязаны видеть в нём
# одни и те же пары «маркер → реплика». Разъехавшись, они начнут спорить: этот
# перепишет длительность одной реплики, а тот подменит рот в другой — и ролик
# рассинхронится ТИШЕ, чем до починки, потому что оба отработают «успешно».
# Ровно так уже вышло с гейтом сверки, который не посмотрел на конвенцию
# закадровой реплики и уронил завод (RABOTA-NAD-OSHIBKAMI §I).
from prep_lipsync import (  # noqa: E402
    LIP, SPEAK, SCAFFOLD, TIMED, mp3_duration, process,
)

# Порог, ниже которого править нечего. 0.05 с — меньше кадра на 24 fps и меньше
# шага округления дорожки рта: такую разницу не слышно, а переписывать её значит
# гонять сценарий по кругу на каждом прогоне.
TOLERANCE = 0.05

# Строка VO-таблицы: `| VO-3 | 0:08.3–0:13.7 | ОБРАЗ | «...» | ... |`.
# Времена ловятся ОТДЕЛЬНЫМИ группами, чтобы переписать ровно их и не тронуть
# ни реплику, ни служебные колонки.
VO_ROW = re.compile(
    r"^(\s*\|\s*VO-(\d+)\s*\|\s*)(\d+):(\d+(?:\.\d+)?)(\s*[–-]\s*)"
    r"(\d+):(\d+(?:\.\d+)?)(\s*\|)"
)
# Абзац-шапка над таблицей: откуда взяты времена. Пока в нём написано «по мерке
# 0.36 с на слово», читатель вправе верить числам как расчётным; после пересчёта
# они факт, и сказать об этом должен сам файл.
VO_NOTE = re.compile(r"^Тайм (?:РАСЧЁТНЫЙ|ПО ФАКТУ).*?(?=\n\n)", re.S | re.M)
VO_NOTE_FACT = (
    "Тайм ПО ФАКТУ ОЗВУЧКИ: длительность каждой реплики снята с её `vo-N.mp3`\n"
    "(`tools/hronometrazh.py`), а не посчитана по мерке 0.36 с на слово. Паузы\n"
    "между репликами — режиссёрские, они сохранены как были."
)


def real_duration(parts_dir, n):
    """Фактическая длина реплики VO-n. → (секунды|None, причина отсутствия)."""
    p = os.path.join(parts_dir or "", f"vo-{n}.mp3")
    if not (parts_dir and os.path.isfile(p) and os.path.getsize(p) > 0):
        return None, f"нет vo-{n}.mp3"
    d = mp3_duration(p)
    if not d or d <= 0:
        return None, "ffprobe не смерил"
    return d, ""


def speech_lines(text):
    """Пары «маркер `//lip N` → строка `speaks for`» в порядке появления.

    → [(индекс строки, номер N, отступ, объявленная длительность)].

    Ходьба ровно та же, что у `prep_lipsync.process`: маркер ПЕРЕЖИВАЕТ
    строительные строки (`together {`, комментарии, пустые), но не больше шести
    подряд. Совпадение результата с `process` проверяется явно — см. `agrees`.
    """
    out, pending, skipped = [], None, 0
    for i, line in enumerate(text.splitlines()):
        m = LIP.match(line)
        if m:
            pending, skipped = int(m.group(1)), 0
            continue
        s = SPEAK.match(line)
        if s and pending is not None:
            out.append((i, pending, s.group(1), float(s.group(3))))
            pending, skipped = None, 0
            continue
        if pending is not None and SCAFFOLD.match(line) and skipped < 6:
            skipped += 1
            continue
        pending, skipped = None, 0
    return out


def agrees(text, pairs):
    """Тот ли набор реплик, что увидит `prep_lipsync`. Иначе — стоп.

    Дешёвая страховка от расхождения двух ходилок по одному файлу: `process`
    без каталога частей ничего не подменяет, но честно отдаёт карту блоков —
    те самые номера vo-N в порядке речевых блоков. Если карты не совпали,
    инструменты читают сценарий по-разному, и трогать его нельзя: рассинхрон
    от такой «починки» будет тише прежнего, потому что оба отработают успешно.
    """
    order = process(text, None)[3]
    mine = [n for _, n, _, _ in pairs]
    if mine != order:
        raise SystemExit(
            f"РАСХОЖДЕНИЕ С ЛИПСИНКОМ: hronometrazh видит реплики {mine}, "
            f"prep_lipsync — {order}. Пока карты не совпадут, править сценарий "
            f"нельзя."
        )


def stretch_cuts(lines, speaks_at, indent, k):
    """Растянуть соседнюю ветку `do{}` на то же отношение, что и речь.

    Реплика с катами внутри пишется так:

        together {
            freeman speaks for 3.6s      ← строка `speaks_at`
            do {
                camera medium freeman
                wait 2.2s
                freeman overlays "shrug"
            }
        }

    Когда `speaks for` становится длиннее, `wait`-ы соседней ветки обязаны
    поехать вместе с ней, иначе жест приходит раньше своего слова, а камера
    потом стоит до конца реплики: в «Теориях личности» так вышел неподвижный
    план на 12.2 секунды при среднем 1.7. Формула и регулярное выражение — те
    же, что в `prep_lipsync`, чтобы каты остались на своей ДОЛЕ реплики.

    → число подправленных строк.
    """
    i = speaks_at + 1
    while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("//")):
        i += 1
    if i >= len(lines) or not re.match(rf"^{indent}do\s*\{{\s*$", lines[i]):
        return 0                                   # соседнего блока катов нет
    depth, i, touched = 1, i + 1, 0
    while i < len(lines) and depth > 0:
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= 0:
            break
        fixed = TIMED.sub(
            lambda mm: f"{mm.group(1)}{round(float(mm.group(2)) * k, 2)}s", lines[i])
        if fixed != lines[i]:
            lines[i] = fixed
            touched += 1
        i += 1
    return touched


def retime_anim(text, parts_dir):
    """Переписать `speaks for` по факту. → (новый текст, отчёт по репликам)."""
    pairs = speech_lines(text)
    agrees(text, pairs)
    lines = text.splitlines()
    report = []
    for idx, n, indent, declared in pairs:
        real, why = real_duration(parts_dir, n)
        report.append({"vo": n, "declared": declared, "real": real,
                       "why": why, "cuts": 0})
        if real is None or abs(real - declared) < TOLERANCE:
            continue
        lines[idx] = SPEAK.sub(
            lambda m: f"{m.group(1)}{m.group(2)} speaks for {real:.2f}s", lines[idx])
        # Растяжка идёт от ОБЪЯВЛЕННОГО числа к факту — то самое отношение, на
        # которое разъехалась речь. Считается до правки соседней ветки: после
        # неё сравнивать уже не с чем.
        report[-1]["cuts"] = stretch_cuts(lines, idx, indent, real / declared)
    return "\n".join(lines) + "\n", report


def vo_rows(text):
    """Строки VO-таблицы: [(индекс строки, номер, старт, конец, match)]."""
    out = []
    for i, line in enumerate(text.splitlines()):
        m = VO_ROW.match(line)
        if m:
            out.append((i, int(m.group(2)),
                        int(m.group(3)) * 60 + float(m.group(4)),
                        int(m.group(6)) * 60 + float(m.group(7)), m))
    return out


def mmss(t):
    """Секунды → `1:05.6` в том же виде, в каком времена стоят в таблице."""
    return f"{int(t // 60)}:{t % 60:04.1f}"


def retime_vo(text, parts_dir):
    """Пересчитать таймкоды VO-таблицы по факту, сохранив паузы. → (текст, n)."""
    rows = vo_rows(text)
    if not rows:
        return text, 0
    # voiceover.py раздаёт файлы частей ПО ПОРЯДКУ СТРОК (vo-1 — первая строка
    # таблицы), а не по номеру в ячейке. Пока номера идут подряд, это одно и то
    # же; разъехавшись, они молча поставят чужой звук на чужую реплику. Та же
    # сверка живёт в tools/sverka.py — здесь она просто ближе к делу.
    for pos, (_, num, _, _, _) in enumerate(rows, start=1):
        if pos != num:
            raise SystemExit(
                f"Номера VO-таблицы идут не подряд: {pos}-я строка помечена "
                f"VO-{num}. Части озвучки раздаются по порядку строк — пересчёт "
                f"таймкодов поставил бы чужие времена."
            )
    lines = text.splitlines()
    cursor, touched = rows[0][2], 0
    for i, (idx, num, start, end, m) in enumerate(rows):
        real, _ = real_duration(parts_dir, num)
        length = real if real is not None else end - start
        # ЦЕПОЧКА СЧИТАЕТСЯ В ТОЙ ЖЕ ТОЧНОСТИ, В КАКОЙ ПЕЧАТАЕТСЯ. Таблица
        # держит десятые доли; если вести курсор в полной точности mp3, остаток
        # округления утекает в следующую строку, и повторный прогон по тем же
        # файлам даёт другие числа — инструмент правит то, что сам же и
        # написал. Ролик от этого не меняется, а diff шумит на каждом прогоне.
        new_start = round(cursor, 1)
        new_end = round(new_start + length, 1)
        # ПАУЗА МЕЖДУ РЕПЛИКАМИ — РЕЖИССЁРСКОЕ РЕШЕНИЕ, а не остаток от
        # арифметики: она объявлена в разделе «Паузы» и держится гейтом тишины.
        # Пересчёт двигает реплики, но зазоры между ними оставляет ровно
        # такими, какими их поставил автор.
        if i + 1 < len(rows):
            cursor = round(new_end + (rows[i + 1][2] - end), 1)
        fixed = (f"{m.group(1)}{mmss(new_start)}{m.group(5)}"
                 f"{mmss(new_end)}{m.group(8)}" + lines[idx][m.end():])
        if fixed != lines[idx]:
            lines[idx] = fixed
            touched += 1
    out = "\n".join(lines) + "\n"
    if touched:
        out = VO_NOTE.sub(VO_NOTE_FACT, out, count=1)
    return out, touched


def report_table(report, anim, vo_touched=0):
    """Таблица расхождения. Столбец «копится» — тот самый уезжающий синхрон."""
    print(f"Хронометраж по факту: {anim}")
    print("  реплика  заявлено    факт   разница   копится")
    drift, hits, mute = 0.0, 0, 0
    for r in report:
        if r["real"] is None:
            mute += 1
            print(f"  VO-{r['vo']:<4}    {r['declared']:5.2f}s       —         —"
                  f"         —   ({r['why']})")
            continue
        d = r["real"] - r["declared"]
        drift += d
        if abs(d) >= TOLERANCE:
            hits += 1
        cuts = (f"  каты ×{r['real'] / r['declared']:.2f} ({r['cuts']} строк)"
                if r["cuts"] else "")
        print(f"  VO-{r['vo']:<4}    {r['declared']:5.2f}s  {r['real']:5.2f}s  "
              f"{d:+6.2f}s  {drift:+7.2f}s{cuts}")
    print(f"  ─── разошлось реплик: {hits}; накопленный сдвиг к финалу: "
          f"{drift:+.2f}s" + (f"; без озвучки: {mute}" if mute else ""))
    if vo_touched:
        print(f"  ─── таймкодов VO-таблицы пересчитано: {vo_touched}")
    return hits


def main(argv):
    ap = argparse.ArgumentParser(
        description="Переписать `speaks for` по фактической длине озвучки")
    ap.add_argument("anim")
    ap.add_argument("--parts", required=True,
                    help="каталог с vo-<N>.mp3 (его делает voiceover.py --parts-dir)")
    ap.add_argument("--vo", help="VO-сценарий: пересчитать и таймкоды таблицы")
    ap.add_argument("-o", "--output", help="куда писать .anim (по умолчанию — на место)")
    ap.add_argument("--check", action="store_true",
                    help="ничего не писать; ненулевой код, если сценарий разошёлся "
                         "с озвучкой")
    args = ap.parse_args(argv)

    anim = Path(args.anim)
    text = anim.read_text(encoding="utf-8")
    # Без частей мерить нечего, и это НЕ ошибка: немой ролик, прогон без ключей
    # Fish, локальный запуск — законные состояния завода. Молчать тоже нельзя,
    # иначе «инструмент отработал» будет значить «инструмент ничего не сделал».
    if not os.path.isdir(args.parts):
        print(f"  [хронометраж] нет каталога озвучки {args.parts} — "
              f"`speaks for` остаётся расчётным.")
        return 0
    if not shutil.which("ffprobe"):
        print("  [хронометраж] ffprobe не найден — длительности не снять, "
              "`speaks for` остаётся расчётным.")
        return 0

    fixed, report = retime_anim(text, args.parts)
    vo_text = vo_fixed = None
    vo_touched = 0
    if args.vo and os.path.isfile(args.vo):
        vo_text = Path(args.vo).read_text(encoding="utf-8")
        vo_fixed, vo_touched = retime_vo(vo_text, args.parts)

    hits = report_table(report, anim, vo_touched)

    if args.check:
        if hits:
            print(f"  ✗ {hits} реплик(и) расходятся с озвучкой — прогони без "
                  f"--check, чтобы переписать по факту.")
            return 1
        print("  ✓ сценарий сходится с озвучкой.")
        return 0

    out = Path(args.output) if args.output else anim
    if fixed != text or args.output:
        out.write_text(fixed, encoding="utf-8")
        print(f"OK: {out} — `speaks for` по факту озвучки.")
    else:
        print(f"OK: {anim} — править нечего, сценарий уже сходится с озвучкой.")
    if vo_fixed is not None and vo_fixed != vo_text:
        Path(args.vo).write_text(vo_fixed, encoding="utf-8")
        print(f"OK: {args.vo} — таймкоды по факту озвучки.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
