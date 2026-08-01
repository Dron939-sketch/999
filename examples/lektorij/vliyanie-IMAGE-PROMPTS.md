# Промты локаций — «Влияние и манипуляции»

Замечание студии: локации те же, нужны новые и такие, которые **усиливают
мысль**. Ниже четыре новых. Каждая не фон, а довод: она доказывает ровно ту
реплику, под которой стоит.

Оставлены прежними ровно две вещи, и обе — не локации:
- **ПУСТОТА** (`void-black.svg`) — чёрный кадр с белой маской. Это приём серии,
  как затемнение: он означает «ни отговорок, ни обстоятельств» и должен
  повторяться от ролика к ролику, иначе перестанет читаться;
- **зал Лектория** и **титры** — фирменные кадры, по ним узнают серию.

---

## КАК ПОДКЛЮЧАЕТСЯ РАСТР

Движок грузит только SVG: `import set` разбирает файл через usvg и на PNG
падает с «provided data has not an UTF-8 encoding». Растр заворачивается в SVG:

    python3 tools/raster_set.py вход.png examples/assets/sets/имя.svg --drop 0.55

Инструмент снимает нарисованную рамку, кадрирует под 16:9 и квантует палитру.
Рядом обязан лежать `<имя>.surfaces.json` с линией пола — **её ставлю руками по
рисунку**, автомат её не берёт: у комнаты стена и пол одинаково светлые.

**ВАЖНО ПРО ЯРКОСТЬ.** На локацию накладывается монохромный проход с контрастом
2.2, он растаскивает полутона к краям. Уже обжигались: `cafe-ruins` после него
давал среднюю яркость 1 из 255, кадр становился чёрным целиком и фигура повисала
в космосе. Поэтому в каждом промте требуется СВЕТЛЫЙ ПУСТОЙ ПОЛ на переднем
плане: на него ложится тень, и без него персонаж не стоит на земле.

**Класть в ветку `claude/mr-freeman-character-tu82rw`, не в `main`** — завод
собирает ролик из рабочей ветки и картинок в `main` не видит. На этом уже
теряли прогон.

## Общий стилевой суффикс (добавлять в КАЖДЫЙ промт)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink, bold
> boiling outline, flat fills only (NO gradients, NO soft light, NO shading),
> extremely high contrast, limited palette — light grey paper (#d4d7cf) and
> black ink (#141410), no colour; graphic / illustrative, NOT photorealistic;
> slightly rough, redrawn-by-hand feel; minimal detail, few strong shapes; NO
> people, NO figures, NO text, NO letters, NO logos; empty light floor in the
> foreground so a character can stand on it and cast a shadow; wide 16:9
> landscape composition, horizontal frame, NOT square.

---

## 1. ПРИХОЖАЯ С ПАКЕТАМИ — хук и жало

**Что доказывает.** Первая реплика: «Вы зашли за хлебом, а вышли с тремя
пакетами». Локация показывает НЕ момент покупки, а её результат — то, что уже
стоит у двери и никуда не денется. Зритель узнаёт свою прихожую раньше, чем
понимает тему ролика.

Ею же ролик и закрывается: он уходит, пакеты остаются. Кольцо замыкается на
предмете, а не на фразе.

> A narrow apartment hallway seen straight on: a closed front door in the back
> wall, a coat hook with one coat, and THREE bulging paper grocery bags standing
> on the floor beside the door, a long baguette sticking out of one of them.
> Nobody in the hallway. The bags look just dropped and forgotten. Bare light
> floor kept clear and empty in the foreground. Flat tones, bold ink edges.
> [+ стилевой суффикс]

**Что важно:** пакетов ровно ТРИ и они у двери справа; батон торчит — по нему
кадр читается за полсекунды. Центр пола пуст: там встаёт фигура.

## 2. РЯДЫ СУПЕРМАРКЕТА — притча и пулемёт

**Что доказывает.** Здесь звучит пулемёт из четырёх чужих голосов, и персонаж
идёт ВДОЛЬ РЯДА: полки с ценниками проезжают мимо, как улики. Место, где кнопки
нажимают профессионально и открыто — и потому зритель соглашается легко, не
подозревая, что через двадцать секунд разговор переедет к нему домой.

> Interior of a supermarket aisle seen along its length, shelves receding into
> perspective on both sides, packed with identical boxes and cans, rows of blank
> price tags clipped to the shelf edges, harsh flat ceiling light. Nobody in the
> aisle. The aisle floor runs down the middle of the frame, light and completely
> empty. Flat tones, bold ink edges, strong perspective lines. [+ стилевой суффикс]

**Что важно:** проход по центру СВОБОДЕН по всей длине — по нему идёт персонаж.
Ценники пустые: любая надпись сгенерируется мусором и будет читаться как брак.

## 3. СТОЛ ПОСЛЕ ГОСТЕЙ — разворот

**Что доказывает.** Самая важная замена. Разворот говорит: «чаще всего кнопку
нажимает не продавец, а тот, кто рядом». Кухня как место близости — верно, но
слишком спокойно. Стол после гостей точнее: здесь только что старались, кормили,
угощали — и ровно отсюда растёт «я же для тебя старалась». Услуга и долг в одном
кадре.

> A dining table after guests have left, seen slightly from the side: crumpled
> napkins, dirty plates stacked askew, half-empty glasses, a cake with one slice
> missing, chairs pushed back at odd angles, one chair turned away from the
> table. Nobody there. A single low lamp above the table. The room beyond is
> dark. Bare light floor kept clear in the foreground. Flat tones, bold ink
> edges. [+ стилевой суффикс]

**Что важно:** один стул РАЗВЁРНУТ ОТ СТОЛА — по нему видно, что разговор
кончился нехорошо. Стулья не заняты: ролик про то, чего не говорят вслух.

## 4. ПЕРЕКРЁСТОК БЕЗ ЗНАКОВ — взлёт

**Что доказывает.** Реплика: «Влияние оставляет вам свободу. Манипуляция делает
свободу дорогой». Пустой перекрёсток, где нет ни одного указателя и ни одной
стрелки, — это и есть оставленный выбор: идти можно куда угодно, и никто не
подталкивает. Разница с предыдущей сценой не в словах, а в том, что здесь ничего
не стоит развернуться.

> An empty crossroads in open flat country under a wide pale sky: two dirt roads
> crossing at right angles, running to the horizon in all four directions. No
> signposts, no arrows, no traffic signs, no markings — an empty signpost pole
> would be wrong, there is nothing at all. A single bare tree far off to one
> side. Light empty ground in the foreground where the roads meet. Flat tones,
> bold ink edges, strong horizon line. [+ стилевой суффикс]

**Что важно:** знаков нет СОВСЕМ, даже пустого столба — пустой столб читается
как «указатель сняли», а нужен мир, где указателя и не было. Центр перекрёстка
свободен: там встаёт фигура.

---

## Куда что встаёт

| Реплика | Локация | Темп |
|---|---|---|
| VO-1, VO-2 хук | прихожая с пакетами | 1.42 / 1.38 |
| VO-3 притча, VO-4 пулемёт | ряды супермаркета (проход вдоль полок) | 1.42 / **1.58** |
| VO-5 разворот | стол после гостей | **1.25** |
| VO-6 удар, VO-7 дно | ПУСТОТА (прежняя) | 1.32 / **1.25** |
| VO-8 взлёт | перекрёсток без знаков | 1.33 |
| VO-9 презентация | зал Лектория (прежний) | 1.38 |
| VO-10 жало | снова прихожая | 1.42 |

Перепад между пулемётом (1.58) и разворотом (1.25) — четверть скорости, и он
стоит ровно на склейке «супермаркет → стол после гостей». Смена мира и смена
темпа в одной точке: это и есть перелом ролика.

## Что делаю, когда картинки придут

1. `raster_set.py` на каждую, с подобранным кропом;
2. `*.surfaces.json` руками по рисунку — линию пола снимаю глазом;
3. подмена локаций в `vliyanie.anim`, пересчёт точек `place` под новые полы;
4. `python3 tools/pered_renderom.py vliyanie` — все десять гейтов;
5. пуш с маркером `[only: vliyanie]` и замер готовой дорожки.
