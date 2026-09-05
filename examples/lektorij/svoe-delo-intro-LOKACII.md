# «Своё дело» — промты локаций для генерации

Пять локаций ролика сейчас — ручная векторная графика (плоские заливки,
четыре тона, жирный контур). Они рабочие: геометрия точная, гейты зелёные.
Промты ниже — чтобы поднять их до уровня генерированных локаций «Истории
идей».

## Как это работает

1. Картинку генерирует пользователь по промту (Nano Banana / Flux), 1280×720.
2. `python3 tools/vectorize.py <png> -o examples/assets/sets/<имя>.svg`.
   Вектор обязателен: камера наезжает до 2.01×, растр на сверхкрупе плывёт.
3. Имя файла оставить прежним — сцена подхватит замену без правки сценария.

## Условие геометрии

**Пол на y≈604** кадра 1280×720 (84% высоты). Туда встают ноги персонажа при
`place (x, 0.585) scales 0.80`. Выше — провалится в пол, ниже — повиснет, и
контактная тень ляжет в воздух.

## Общая часть промта (приписывать к каждому)

> hand-drawn 2D cartoon in the style of Mr. Freeman, thick wobbly hand-inked
> black outlines, flat light-gray paper background, stark high-contrast black
> and white, no gradients, no soft shading, flat fills only, three or four
> tonal planes separated by black contour, graphic and minimal, five strong
> black shapes rather than fifty small ones, no text or lettering anywhere,
> floor line at 84% of the image height, empty space left free for a
> character to stand in, 16:9

## 1. `delo-sejf.svg` — сейф с идеей

> a huge black steel safe filling the right third of an empty room, its heavy
> door ajar by a hand's width, inside on a single shelf one bare light bulb
> and nothing else; three torn-off calendar pages lying on the floor in front
> of it; a trail of dust marks across the floor from the safe toward the left
> edge; one bare lamp on a cord throwing a hard-edged flat cone of light onto
> the empty floor, not onto the safe

Что читается: идею хранят, а не проверяют; третий год.
Персонаж стоит слева от дверцы (x≈0.36).

## 2. `delo-vyveska.svg` — вывеска раньше клиента

> a freshly renovated small shop front on an empty street: an enormous blank
> black signboard hanging on chains above a wide display window with nothing
> behind the glass but a bare wall; a stepladder leaning at the left edge,
> paint cans and a brush on the pavement, a half-unrolled banner with a plain
> circle emblem; not a single passer-by anywhere on the street

Что читается: всё, что можно купить ДО первого клиента, — куплено.
Персонаж перед витриной по центру.

## 3. `delo-prilavok.svg` — два прилавка

> an outdoor market: on the left a fancy black stall with a scalloped awning,
> three identical boxes on the counter and one tiny price tag on a string —
> and nobody in front of it; further right and smaller, a plain wooden cart
> with no awning at all, and a queue of six dark human silhouettes trailing
> off the right edge of the frame; empty ground in front of the fancy stall

Что читается: спрос есть — не там, где его не спросили.
Персонаж ЗА нашим прилавком, слева (x≈0.30).

## 4. `delo-tri-dveri.svg` — чинить, поворачивать, закрывать

> a bare corridor with three identical black door frames in a row: the first
> door ajar into darkness with a hammer and a large key leaning against its
> frame; the second door closed, with a big curved arrow drawn where the
> handle should be; the third door boarded up with two thick planks nailed in
> a cross; plain floorboards, nothing else in the corridor

Что читается: за любой дверью ответ; ни одна не открыта.
Персонаж перед средней дверью по центру.

## 5. `delo-stol.svg` — первый клиент

> a plain wooden table in a bright empty room, on it one bare light bulb
> standing upright and a single coin; across the table one simple chair with
> one dark human silhouette seated on it, seen from the side; a window with a
> hard-edged flat beam of daylight falling onto the table; nothing else — no
> sign, no shop window, no decoration

Что читается: та же лампочка, вынутая из сейфа; один клиент — это уже дело.
Персонаж слева от стола (x≈0.34), лицом к стулу. Стул и клиент — справа.

## Проверка после замены

```bash
./target/release/animdsl check examples/lektorij/svoe-delo-intro.anim
python3 tools/studio.py svoe-delo-intro
```

Плюс глазами один кадр из каждой сцены: ноги на полу, тень на полу.
