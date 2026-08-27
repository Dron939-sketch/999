# Лекция 1 «Чью жизнь вы живёте» — видеоряд. Пилот на первый раздел

Новый для завода продукт: не интро к курсу, а **видеоряд под готовую
аудиозапись лекции**. Формат выбран студией — иллюстрации с Фрименом на стыках;
делаем сначала пилот на один раздел, смотрим, потом решаем про остальные.

---

## ЧТО ЭТО И ЧЕМ ОТЛИЧАЕТСЯ ОТ РОЛИКА

| | ролик-интро | видеоряд лекции |
|---|---|---|
| длина | 60–90 с | 18–22 мин целиком, пилот ~1 мин |
| голос | синтез по VO-таблице | ГОТОВАЯ аудиозапись, синтеза нет |
| персонаж | говорит весь ролик | появляется на стыках разделов, 3–5 с |
| кадров | 2 300 | 32 000 на всю лекцию |
| приёмка | 26 гейтов | к лекции неприменимы (см. ниже) |

**ДВАДЦАТЬ ШЕСТЬ ГЕЙТОВ К ЛЕКЦИИ НЕ ПРИМЕНЯЮТСЯ, И ЭТО НЕ ПОБЛАЖКА.** Они
меряют устройство интро: крючок на третьей секунде, первый удар к седьмой,
перелом в окне 14–28, кольцо, жало, разрыв, станок шутки, «минута — цель».
У лекции нет ни жала, ни кольца, ни разрыва — у неё есть тема и порядок мыслей.
Гонять на ней `pered_renderom.py` — значит получить два десятка осмысленных на
вид провалов, которые ничего не значат. Список проверок для лекции короткий и
свой, он в конце файла.

---

## ЧТО ПРОВЕРЕНО НА ДВИЖКЕ

**Сцена без персонажа рендерится.** Это была главная техническая неизвестность:
весь завод построен вокруг говорящей фигуры. Проба: сцена с одним сетом, без
`place`, с `camera pan-to` — 48 кадров, движение камеры отработало. Значит
иллюстрированная лекция собирается НЫНЕШНИМ движком, дописывать ничего не надо.

**Чего пока никто не мерил:** рендер длиннее двух минут. Минутный ролик — 2 300
кадров и около шести минут работы шага `Studio`; двадцать две минуты — это
32 000 кадров, то есть примерно полтора часа. В лимит прогона (шесть часов)
укладывается, но проверять это надо на пилоте, а не на полной лекции.

---

## ЧТО НУЖНО ОТ СТУДИИ

**1. САМА АУДИОЗАПИСЬ.** Её нет ни в одном репозитории: лекции на сайте звучат
серверной озвучкой (Frederick), а сеть на неё из песочницы закрыта. Нужен файл
`.mp3` или `.wav` — коммитом в ветку или в чат. Без него пилот собрать нельзя:
вся раскладка кадров считается от РЕАЛЬНЫХ времён, а не от прикидки по словам.

**2. ТРИ КАРТИНКИ** по промтам ниже.

---

## РАЗДЕЛ 1 «АНКЕТА, КОТОРУЮ ВЫ НЕ ЗАПОЛНЯЛИ» — РАСКЛАДКА ПИЛОТА

Раздел — 141 слово, около минуты звучания. Три кадра плюс два появления
персонажа:

| # | что в кадре | под какие слова | ход камеры |
|---|---|---|---|
| 0 | Фримен в комнате с колеёй (сет уже есть) | до начала раздела, 3–4 с | общий |
| 1 | **АНКЕТА** — лист с шестью строками | «Представьте анкету… Работа? График? Место? Отдых? Люди? Темп?» | медленный проезд сверху вниз по строкам |
| 2 | **ГАЛОЧКА** — те же строки крупно: две отмечены от руки, остальные впечатаны типографски | «сколько граф вы заполняли сами?.. две-три графы из десятка» | наезд на границу между рукописным и печатным |
| 3 | **ТЕЛЕФОН** — новый аппарат с заводскими настройками | «как в новом телефоне, где рингтон, обои и язык уже выбраны производителем» | лёгкий отъезд |
| 4 | Фримен там же, что в кадре 0 | стык со вторым разделом, 3–4 с | общий |

Персонаж на стыках берётся из существующего сета `koleya-komnata` — это и
экономия, и связь с интро курса: зритель, пришедший с ролика, узнаёт комнату.

---

## ПРОМТЫ

**КИРИЛЛИЦУ ГЕНЕРАТОР НЕ РИСУЕТ — И НЕ НАДО.** Русские буквы приезжают
исковерканными всегда; это не придирка, а свойство. Поэтому во всех трёх промтах
стоит запрет на читаемый текст, а строки анкеты просят изобразить ГРАФИЧЕСКИ —
рамка плюс волнистый штрих вместо слов. Подписи «Работа», «График», «Место»,
«Отдых», «Люди», «Темп» я впишу сам вектором поверх картинки: так они будут
правильными и одинаковыми во всех кадрах.

### Кадр 1 — АНКЕТА

> WIDE 16:9 LANDSCAPE FRAME, twice as wide as it is tall — a cinema still, NOT a
> square and NOT a vertical picture. A single sheet of paper lying flat, seen
> straight from above, filling most of the frame: a printed FORM with SIX
> horizontal rows, one under another, evenly spaced. Each row has a small label
> box on the left and a long answer line on the right. EVERY row is already
> filled in — the answer lines carry wavy ink strokes that read as handwriting
> from a distance. IMPORTANT: NO readable letters, NO words, NO numbers
> anywhere — the writing must be abstract wavy strokes only, suggestion of
> handwriting, never actual text. The paper is plain, slightly worn, with a
> visible fold. Nothing else in the frame: no hands, no pen, no desk clutter.
> Drawn in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> BOLD heavy boiling outline, thick confident strokes, flat fills only (NO
> gradients, NO soft light, NO shading), extremely high contrast, STRICTLY BLACK
> AND WHITE — monochrome only, limited palette of light grey paper (#d4d7cf) and
> black ink (#141410), NO COLOUR anywhere in the image, not a single coloured
> object; graphic / illustrative, NOT photorealistic; slightly rough,
> redrawn-by-hand feel; minimal detail, few strong shapes; NO people, NO figures,
> NO text, NO letters, NO numbers, NO logos; the drawing FILLS the whole canvas
> edge to edge, wide 16:9 landscape, NO borders, NO frame, NO margins, NOT square.

### Кадр 2 — ГАЛОЧКА

> WIDE 16:9 LANDSCAPE FRAME, twice as wide as it is tall — a cinema still, NOT a
> square and NOT a vertical picture. EXTREME CLOSE-UP of part of a paper form:
> only THREE rows visible, very large, filling the frame. THE WHOLE POINT OF THE
> PICTURE: the top row is filled in by a HUMAN HAND — a big, confident, slightly
> crooked hand-drawn TICK in its box and a wavy ink stroke on its line; the two
> rows below are filled MECHANICALLY — their boxes carry identical, perfectly
> regular printed marks and their lines carry perfectly even machine strokes, all
> exactly alike. The contrast between the one crooked human mark and the
> identical machine marks must be immediate and obvious. NO readable letters, NO
> words, NO numbers anywhere — marks and strokes only, never actual text. Drawn
> in the style of the animated series "Mr. Freeman": hand-drawn black ink, BOLD
> heavy boiling outline, thick confident strokes, flat fills only (NO gradients,
> NO soft light, NO shading), extremely high contrast, STRICTLY BLACK AND WHITE —
> monochrome only, limited palette of light grey paper (#d4d7cf) and black ink
> (#141410), NO COLOUR anywhere in the image, not a single coloured object;
> graphic / illustrative, NOT photorealistic; slightly rough, redrawn-by-hand
> feel; minimal detail, few strong shapes; NO people, NO hands, NO figures, NO
> text, NO letters, NO numbers, NO logos; the drawing FILLS the whole canvas edge
> to edge, wide 16:9 landscape, NO borders, NO frame, NO margins, NOT square.

### Кадр 3 — ТЕЛЕФОН

> WIDE 16:9 LANDSCAPE FRAME, twice as wide as it is tall — a cinema still, NOT a
> square and NOT a vertical picture. A brand-new mobile phone lying flat on a
> plain empty surface, seen straight from above, large in the frame. Its screen
> is ON and shows a SETTINGS LIST: four or five identical rows, each with a small
> square icon on the left, a blank label bar, and a toggle switch on the right.
> EVERY toggle is already switched to the same side — all set, none touched. The
> rows are perfectly regular and identical, machine-made. The phone still has a
> protective film with a peeling corner. NO readable letters, NO words, NO
> numbers anywhere on the screen or the phone — bars, icons and switches only,
> never actual text. Nothing else in the frame: no hands, no box, no cables.
> Drawn in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> BOLD heavy boiling outline, thick confident strokes, flat fills only (NO
> gradients, NO soft light, NO shading), extremely high contrast, STRICTLY BLACK
> AND WHITE — monochrome only, limited palette of light grey paper (#d4d7cf) and
> black ink (#141410), NO COLOUR anywhere in the image, not a single coloured
> object; graphic / illustrative, NOT photorealistic; slightly rough,
> redrawn-by-hand feel; minimal detail, few strong shapes; NO people, NO figures,
> NO text, NO letters, NO numbers, NO logos; the drawing FILLS the whole canvas
> edge to edge, wide 16:9 landscape, NO borders, NO frame, NO margins, NOT square.

---

## ЧЕГО В ЭТИХ КАДРАХ БЫТЬ НЕ ДОЛЖНО

**Читаемых букв и цифр.** Причина выше: кириллица приезжает исковерканной, а
латиница в кадре русской лекции — смешение алфавитов на экране. Подписи вписываю
я.

**Рук и людей.** Кадр 2 — про то, что галочку кто-то поставил, а не про того,
кто ставил. Появись в кадре рука, зритель начнёт смотреть на неё.

**Цвета.** В отличие от роликов, здесь цветного предмета НЕТ вообще: правило
«одно цветное пятно» — приём удержания в шестидесятисекундном ролике, а на
двадцати двух минутах повторённое двадцать раз пятно превращается в манерность.
Решение можно пересмотреть на просмотре пилота.

**Перспективы и наклона.** Все три кадра — фронтально или строго сверху. Проезды
камеры по наклонному кадру дают ощущение болтанки.

---

## СПИСОК ПРОВЕРОК ДЛЯ ЛЕКЦИИ (не для ролика)

Список правился ПОСЛЕ пилота: два пункта из пяти оказались неверны, и
пилот прошёл их зелёным, будучи бракованным. Что именно было не так —
ниже, в самих пунктах.

1. **Длительности сходятся**: картинка, звук и выданный файл — с точностью до
   десятой. Ровно на этом ролик 25 собрался без финала.

2. **Звук поднят до слышимого, но НЕ передавлен.** ~~Идёт без мастеринга,
   проверяю побитово.~~ Пункт был неправ: запись лежит на −25.4 LUFS, это
   заметно тише всего, рядом с чем её будут слушать, и «не трогать» означало бы
   сдать глухой файл. Но и `loudnorm` не годится — при LRA 3.6 он уходит в
   динамический режим и даёт 85 скачков усиления больше 2.5 dB между соседними
   секундами; на шестнадцати минутах это слышно как дыхание. Годится постоянное
   усиление плюс лимитер на редких пиках. **Мерка теперь такая:** LRA готового
   файла не ниже исходного минус 0.2 LU, сигма посекундного усиления ниже
   0.4 dB, скачков усиления выше 2.5 dB — ноль.

3. **Смена кадра попадает в мысль**, а не в середину фразы: тайм-коды склеек
   сверяются с картой пауз. Карта снимается своей огибающей: `silencedetect` на
   этой записи молчит даже на −20 dB, потому что под речью идёт ровный шум и
   абсолютного порога нет.

4. **Кадр не стоит мёртвым.** На иллюстрации без персонажа глазу не за что
   зацепиться дольше пятнадцати секунд: у каждого кадра обязано быть медленное
   движение камеры.

5. **Проезд не вытаскивает подложку.** Новый пункт, и появился он потому, что
   пилот был сдан именно с этим браком. Сет натянут на кадр край в край,
   `camera wide` — зум 1.0, запаса нет ни пикселя, и любой `pan-to` показывает
   голый `background` из конфига: серая полоса снизу и справа на каждом ходе
   камеры. При зуме z запас с каждой стороны — (1 − 1/z)/2: у `wide` ноль, у
   `two-shot` 0.083, у `over-shoulder` 0.222. Держит `tools/proezd.py`.

6. **Контактный лист по готовому файлу — глазами.** Кадры берутся НЕ в начале
   сцен, а в КОНЦЕ проездов: пилот прошёл эту проверку зелёным ровно потому,
   что я смотрел первые кадры сцен, где камера ещё стоит в центре и никакого
   брака не видно.

---

## ПОРЯДОК

1. Студия присылает аудиозапись и три картинки.
2. Я укладываю картинки в `examples/assets/sets/`, вписываю кириллические
   подписи вектором, раскладываю кадры по РЕАЛЬНЫМ временам аудио.
3. Собираю пилот, проверяю по списку выше, показываю.
4. Смотрим вместе и решаем: делать остальные пять разделов тем же способом,
   менять плотность кадров или менять формат.
