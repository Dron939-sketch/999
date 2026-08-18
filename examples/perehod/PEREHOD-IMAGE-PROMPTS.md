# «Переход» — что генерируем, что рисуем, что уже есть

Ролик графичный, а не «комнатный»: чернота, коллаж, календарь, решётка,
интерфейс, лицо. Локаций почти нет, зато много надписей и чисел — «девять
тысяч четыреста», «нужно 35, у вас 23», числа календаря. Генератор надписи
превращает в кашу: буквы получаются похожими на буквы, но нечитаемыми, и в
кадре это читается как брак. Поэтому всё, где есть текст или точная
геометрия, рисуется вектором.

## Разбор по кадрам

| кадр | что нужно | откуда берём |
|---|---|---|
| 0:00 чернота, проступает лицо | персонаж на чёрном | движок |
| 0:14 гербарий: доска, булавки, подписи | доска, булавки, подписи мелким шрифтом | **вектор** (подписи должны читаться) |
| 0:14 четыре образца на доске | телефон у уха, витрина, кухня, ноутбук | **генерация — 4 картинки** |
| 0:33 «девять тысяч четыреста» / «двести четырнадцать тысяч» | два числа в кадре | движок, `text()` |
| 0:42 календарь месяца, числа выгорают | сетка месяца, 30 чисел | **вектор** (числа точные, гаснут по одному) |
| 0:55 скачок на 23-е, свет от телефона в лицо | крупный план, один флэт-полигон света | движок |
| 1:12 решётка из знаков вопроса растёт из земли | решётка | **вектор** (глифы как контуры, чтобы не зависеть от шрифта) |
| 1:12 «за ней — ничего» | пустое поле | **уже есть**: `sets/field-empty.svg` — канон завода |
| 1:38 интерфейс: четыре плитки, бегунок | UI | **вектор** |
| 2:00 «нужно 35, у вас 23», гаснущие варианты | UI с числами | **вектор** |
| 2:10 карта месяца: десять точек, часть провалилась | схема | **вектор** |
| 2:15 финал, титр `meysternlp.ru/fredi/?m=perehod` | чернота, титр | движок, `text()` |

Итого от вас — **четыре картинки**. Остальное на мне.

---

# Четыре образца в гербарий

Каждый — отдельная карточка, которая вылетает и застывает под булавкой.
Карточка **светлее доски**: доска средне-серая, карточка почти белая, тушь
чёрная. За счёт этого приколотый образец читается как вещдок, а не как часть
фона. Рамку карточки и булавку рисую вектором — от вас только рисунок.

## Общие требования

1. **Квадрат 1:1**, 1024×1024 или больше, непрозрачный PNG, **во всё поле, без
   рамки и белых полей**.
2. **Фон карточки — светлый** (почти белая бумага), рисунок — чёрная тушь.
   Это единственное место ролика, где фон светлее фигуры: карточка должна
   выпрыгивать из тёмного кадра.
3. **Ни одной надписи, ни одной цифры.** Ценники, экраны, календари — пустые.
   Подписи ставит движок, читаемым шрифтом.
4. **Ни одного лица.** Рука, ухо, плечо — можно и нужно; лицо — нет, лицо в
   этом ролике одно и его рисует движок.
5. **Предмет один, вокруг пусто.** Образец в гербарии не спорит с соседями:
   лишняя мебель, посуда, провода — вон.
6. **Без цвета.**

## Общий стилевой суффикс (дописывать к каждому промту)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> thick wobbly hand-inked outline, flat fills only (NO gradients, NO soft
> light, NO shading), stark high-contrast black and white, black ink
> (#141410) on a pale off-white background, NO colour at all; graphic and
> illustrative, NOT photorealistic; slightly rough, redrawn-by-hand feel;
> minimal detail, a lot of empty space around the object; full-bleed square
> composition, no border, no frame, no margin.

## Общий негативный промт

> text, letters, words, numbers, digits, price tag text, watermark,
> signature, face, head, eyes, person, people, crowd, colour, gradients,
> soft shadows, glow, photorealism, 3D render, clutter, background scenery,
> border, frame, white margin

---

## 1. ТЕЛЕФОН У УХА → `perehod-obr-telefon.png`

Реплика: «тебе позвонили и сказали, что одобрение сгорит в пятницу».

> A hand holding an old-fashioned mobile phone pressed against an ear, seen
> from the side. Only the hand, the phone and the edge of the ear and jaw are
> drawn — NO face, no eyes, no head above the ear, no body. The phone is a
> plain rectangle with a blank screen: nothing on the screen, no icons, no
> numbers. Everything else is empty pale background — the object floats alone
> with a lot of space around it, like a specimen on a card. [+ стилевой суффикс]

Что критично: кисть и ухо срезаны кадром, будто образец отрезали от целого.
Целая фигура в кадре превратит карточку во вторую сцену и отберёт внимание у
говорящего.

## 2. ВИТРИНА С ПОСЛЕДНЕЙ → `perehod-obr-vitrina.png`

Реплика: «на полке лежала последняя, и очередь дышала в затылок».

> A single shop shelf behind a pane of glass, seen straight on. On the shelf
> ONE plain rectangular box is left, standing alone; the rest of the shelf is
> empty, with clean gaps where the other boxes stood. A small blank price
> label sticks up beside it — the label is COMPLETELY EMPTY, no writing, no
> numbers. No people, no reflections of people. Everything around is empty
> pale background. [+ стилевой суффикс]

Что критично: пустые места на полке. Именно они говорят «последняя», а не
сама коробка — без них это просто товар.

## 3. КУХОННЫЙ СТОЛ С ТЕЛЕФОНОМ → `perehod-obr-kuhnya.png`

Реплика: «тебе просто напомнили, что нормальные дети звонят».

> A plain kitchen table seen from above at a slight angle. On it a mobile
> phone lies face up with a COMPLETELY BLANK screen — no text, no icons, no
> notification — and beside it one cup. Nothing else on the table at all: no
> plates, no crumbs, no cloth. No hands, no people. The table edges fade into
> empty pale background. [+ стилевой суффикс]

Что критично: экран пустой. Любой значок на нём — это надпись, а надписи в
этом ролике ставит движок.

## 4. НОУТБУК В ТЕМНОТЕ → `perehod-obr-noutbuk.png`

Реплика: «ты не спросил — они не показали».

> An open laptop seen head-on, standing alone on a bare surface. The screen is
> a plain pale rectangle with NOTHING on it: no text, no windows, no icons, no
> cursor. From the screen ONE hard-edged wedge of pale light falls forward
> onto the surface in front of the laptop — flat, with sharp straight edges,
> no glow, no bloom. Nothing else in the frame: no mouse, no cables, no cup,
> no hands, no people. Empty pale background around. [+ стилевой суффикс]

Что критично: клин света с жёсткой кромкой. Он единственный намекает, что
дело ночью, и он же рифмуется с кадром 0:55, где в лицо светит телефон.

---

## Куда класть

`examples/assets/sets/<имя>.png` — обёртку в SVG и врезку в сценарий делаю я.

## Отдельно: ролик придётся резать на две части

2:40 — это больше двух минут, а движок держит все кадры в памяти и растёт на
~800 МБ в минуту (замер в `OTK.md`). Трёхминутный ролик дважды ронял раннер
по OOM. Режу по смысловой границе — «Механизм» и «Игра», — части склеиваются
в один файл, зритель шва не видит.
