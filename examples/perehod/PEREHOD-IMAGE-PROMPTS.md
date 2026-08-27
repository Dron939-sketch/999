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

## Про стиль в промтах

Раньше стиль задавался отсылкой «в стиле сериала Mr. Freeman». Генератор может
её не знать — тогда он берёт что-то своё, и карточки приезжают в чужой манере.
Поэтому ниже промты ПОЛНЫЕ: стиль описан словами, отсылок нет, каждый промт
самодостаточен и копируется целиком.

## Общий негативный промт (один на все четыре)

```
colour, color, coloured, tinted, sepia, warm tones, blue tones, gradient,
gradients, airbrush, soft shading, cross-hatching, hatching, stippling,
texture, paper texture, grain, drop shadow, glow, bloom, lens flare,
photorealistic, photograph, 3D render, CGI, painterly, watercolour, oil
painting, sketchy pencil lines, text, letters, words, numbers, digits,
labels, captions, signage, logo, watermark, signature, face, head, eyes,
mouth, person, people, figure, crowd, hands everywhere, clutter, extra
objects, background scenery, room, furniture, border, frame, white margin,
vignette
```

---

## 1. ТЕЛЕФОН У УХА → `perehod-obr-telefon.png`

Реплика: «тебе позвонили и сказали, что одобрение сгорит в пятницу».

```
A black and white hand-drawn ink illustration of a hand holding an
old-fashioned mobile phone pressed against an ear, seen from the side. Only
the hand, the phone, and the edge of the ear and jawline are drawn — there is
NO face, no eyes, no mouth, no head above the ear, no body, no shoulder. The
wrist and the ear are cut off by empty space, as if this fragment was clipped
out of a larger drawing and mounted alone. The phone is a plain rectangle and
its screen is completely blank: no icons, no numbers, no letters, nothing on
it.

Drawing style: pure black ink on plain pale off-white paper, monochrome,
absolutely no colour of any kind. One thick, slightly uneven, hand-inked
outline that wobbles and changes width along its length, like a brush pen
drawing. Fills are flat and solid — solid black or flat mid-grey — with no
gradients, no soft shading, no cross-hatching, no texture, no drop shadows.
Extremely high contrast, only three tones in the whole image: pale background,
one mid-grey, solid black. Bold, graphic, poster-like, very few details.

Composition: square 1:1, the subject sits alone in the middle with a great
deal of empty pale background around it. No border, no frame, no margin, no
caption, no text anywhere in the image.
```

Что критично: кисть и ухо срезаны пустотой — это делает карточку образцом, а
не второй сценой. Целая фигура в кадре отберёт внимание у говорящего.

---

## 2. ВИТРИНА С ПОСЛЕДНЕЙ → `perehod-obr-vitrina.png`

Реплика: «на полке лежала последняя, и очередь дышала в затылок».

```
A black and white hand-drawn ink illustration of a single shop shelf behind a
pane of glass, seen straight on. On the shelf ONE plain rectangular box stands
alone. The rest of the shelf is empty, with clear gaps where other boxes used
to stand — those gaps are the point of the picture and must be obvious. A
small blank price label sticks up from the shelf edge beside the box: the
label is completely EMPTY, no writing, no numbers, no symbols. No people, no
hands, no reflections of people in the glass.

Drawing style: pure black ink on plain pale off-white paper, monochrome,
absolutely no colour of any kind. One thick, slightly uneven, hand-inked
outline that wobbles and changes width along its length, like a brush pen
drawing. Fills are flat and solid — solid black or flat mid-grey — with no
gradients, no soft shading, no cross-hatching, no texture, no drop shadows.
Extremely high contrast, only three tones in the whole image: pale background,
one mid-grey, solid black. Bold, graphic, poster-like, very few details. The
glass is shown by two or three straight black lines, not by reflections or
transparency effects.

Composition: square 1:1, the shelf sits alone with a great deal of empty pale
background above and below it. No border, no frame, no margin, no caption, no
text anywhere in the image.
```

Что критично: пустые места на полке. Именно они говорят «последняя», а не сама
коробка — без них это просто товар.

---

## 3. КУХОННЫЙ СТОЛ С ТЕЛЕФОНОМ → `perehod-obr-kuhnya.png`

Реплика: «тебе просто напомнили, что нормальные дети звонят».

```
A black and white hand-drawn ink illustration of a plain kitchen table seen
from above at a slight angle. On the table a mobile phone lies face up with a
completely BLANK screen — no text, no icons, no notification, nothing on it —
and beside the phone stands one plain cup. There is nothing else on the table
at all: no plates, no crumbs, no cloth, no cutlery, no food. No hands, no
people, no chairs. The far edges of the table dissolve into empty background.

Drawing style: pure black ink on plain pale off-white paper, monochrome,
absolutely no colour of any kind. One thick, slightly uneven, hand-inked
outline that wobbles and changes width along its length, like a brush pen
drawing. Fills are flat and solid — solid black or flat mid-grey — with no
gradients, no soft shading, no cross-hatching, no texture, no drop shadows.
Extremely high contrast, only three tones in the whole image: pale background,
one mid-grey, solid black. Bold, graphic, poster-like, very few details.

Composition: square 1:1, the table top sits alone with a great deal of empty
pale background around it. No border, no frame, no margin, no caption, no text
anywhere in the image.
```

Что критично: экран пустой. Любой значок на нём — это надпись, а надписи в
этом ролике ставит движок читаемым шрифтом.

---

## 4. НОУТБУК В ТЕМНОТЕ → `perehod-obr-noutbuk.png`

Реплика: «ты не спросил — они не показали».

```
A black and white hand-drawn ink illustration of an open laptop seen head-on,
standing alone on a bare flat surface. The screen is a plain pale rectangle
with NOTHING on it: no text, no windows, no icons, no cursor, no menu bar. From
the screen ONE hard-edged wedge of pale light falls forward onto the surface in
front of the laptop — the wedge is a flat pale shape with sharp straight
edges, like a cut-out piece of paper, with no glow, no blur, no bloom and no
soft falloff. The surface around the wedge stays plain and untouched. Nothing
else is in the picture: no mouse, no cables, no cup, no papers, no hands, no
people, no room behind.

Drawing style: pure black ink on plain pale off-white paper, monochrome,
absolutely no colour of any kind. One thick, slightly uneven, hand-inked
outline that wobbles and changes width along its length, like a brush pen
drawing. Fills are flat and solid — solid black or flat mid-grey — with no
gradients, no soft shading, no cross-hatching, no texture, no drop shadows.
Extremely high contrast, only three tones in the whole image: pale background,
one mid-grey, solid black. Bold, graphic, poster-like, very few details.

Composition: square 1:1, the laptop sits alone with a great deal of empty pale
background around it. No border, no frame, no margin, no caption, no text
anywhere in the image.
```

Что критично: клин света с жёсткой кромкой, без свечения. Он единственный
намекает, что дело ночью, и рифмуется с кадром 0:55, где телефон светит в лицо.

---

## Куда класть

`examples/assets/sets/<имя>.png` — обёртку в SVG и врезку в сценарий делаю я.

## Отдельно: ролик придётся резать на две части

2:40 — это больше двух минут, а движок держит все кадры в памяти и растёт на
~800 МБ в минуту (замер в `OTK.md`). Трёхминутный ролик дважды ронял раннер
по OOM. Режу по смысловой границе — «Механизм» и «Игра», — части склеиваются
в один файл, зритель шва не видит.
