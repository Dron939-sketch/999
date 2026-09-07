# «Философия» — промты локаций для генерации

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

Второе условие — **бумажка**. Одна и та же скрученная записка проходит через
четыре локации из пяти (автомат → очередь → рупор → голова) и на пятой
(стол) лежит развёрнутой и пустой. Если генерировать, рисовать её одинаково
во всех кадрах: квадратный листок со скруглёнными углами и одним завитком.

## Общая часть промта (приписывать к каждому)

> hand-drawn 2D cartoon in the style of Mr. Freeman, thick wobbly hand-inked
> black outlines, flat light-gray paper background, stark high-contrast black
> and white, no gradients, no soft shading, flat fills only, three or four
> tonal planes separated by black contour, graphic and minimal, five strong
> black shapes rather than fifty small ones, no text or lettering anywhere,
> floor line at 84% of the image height, empty space left free for a
> character to stand in, 16:9

## 1. `filo-avtomat.svg` — автомат готовых ответов

> a huge black vending machine filling the right third of an empty room, its
> glass front showing four shelves of identical small rolled-up paper notes in
> neat rows, a vertical column of six round buttons on the right side with the
> third button from the top larger and lit, an empty pickup tray at the bottom;
> on the floor in front of the machine a heap of crumpled paper notes; one bare
> lamp on a cord throwing a hard-edged flat cone of light onto the empty floor,
> not onto the machine

Что читается: ответы покупают, а не думают; третья кнопка сверху.
Персонаж стоит слева от автомата (x≈0.36).

## 2. `filo-ochered.svg` — очередь за ответом

> an empty street between blank windowless facades; a long queue of identical
> dark human silhouettes stretching from the center of the frame to the right
> edge and beyond, each one holding the same small rolled-up paper note raised
> above its head like a ticket; at the far left a small black vending machine
> the queue is heading for, with three more silhouettes at its front seen from
> behind; a gap in the middle of the queue left free; nobody looks sideways

Что читается: «утро, работа, лента, так надо» — все за одним и тем же.
Персонаж в разрыве очереди по центру, единственный лицом к нам.

## 3. `filo-rupor.svg` — рупор на столбе

> a wide empty town square with a low blank parapet at the far edge; one tall
> black pole at the left third rising out of the frame, a big black
> loudspeaker horn mounted on it pointing down and right over the square,
> three thick curved arcs drawn in front of the horn widening outward; the
> ground scattered with identical small paper notes like fallen leaves; not a
> single person in the square

Что читается: кто сказал — кто-то; говорит давно, слушают все, никого нет.
Персонаж под рупором, чуть правее центра (x≈0.56).

## 4. `filo-golova.svg` — голова с дверцей

> a giant solid black profile of a human head filling the right half of an
> empty room, standing on the floor on its neck, facing right away from the
> viewer; in the back of the head a rectangular door flung wide open toward
> the viewer, and inside a bright storage closet with three shelves, each
> shelf holding a row of identical small rolled-up paper notes; the head casts
> one flat solid black shadow on the floor; nothing else in the room

Что читается: голова своя, внутри чужое; дверца открыта — заглянуть можно.
Персонаж перед дверцей, слева (x≈0.34).

## 5. `filo-stol.svg` — чистый лист

> a plain wooden table in a bright empty room, on it one single paper note
> unrolled flat and completely blank, its edges still slightly curled from
> having been rolled, and one pencil lying diagonally beside it with its tip
> toward the note; a window with a hard-edged flat beam of daylight falling
> onto the table; nothing else — no shelves, no machine, no decoration

Что читается: та же бумажка, развёрнутая, — и на ней пусто; ответ пишете вы.
Персонаж слева от стола (x≈0.34), лицом к листу.

## Проверка после замены

```bash
./target/release/animdsl check examples/lektorij/filosofiya-intro.anim
python3 tools/studio.py filosofiya-intro
```

Плюс глазами один кадр из каждой сцены: ноги на полу, тень на полу, бумажка
одна и та же.
