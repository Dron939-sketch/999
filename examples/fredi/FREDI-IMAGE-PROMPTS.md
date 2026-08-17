# Промты для локаций — ролики про Фреди

Ролики про приложение (не Лекторий) живут в `examples/fredi/`. Локации здесь
не «пустое поле», а бытовые интерьеры: зритель должен узнать свою комнату.

## Общий стилевой суффикс

> in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> thick wobbly hand-inked outline, flat fills only (NO gradients, NO soft
> light, NO shading), stark high-contrast black and white, black ink
> (#141410) only, NO colour at all; graphic and illustrative, NOT
> photorealistic; slightly rough, redrawn-by-hand feel; minimal detail.

## 1. СПАЛЬНЯ В ТРИ ЧАСА НОЧИ (`sets/fredi-spalnya.png`)

Файл: **16:9**, 1920×1080 или 2560×1440, непрозрачный PNG.

> A small ordinary bedroom at three in the morning, seen straight on from the
> side of the room. On the RIGHT stands a low simple bed, seen from its side:
> the top of the mattress sits at about three quarters of the image height, the
> blanket is thrown back and rumpled. The bed is COMPLETELY EMPTY — no person
> in it, nobody in the room, the frame is empty of people. On the LEFT there is
> open empty floor and a bare wall. A window on the left wall is uncovered, and
> through it the streetlight throws ONE hard-edged pale rectangle of light onto
> the left wall and the floor below it — a clean light patch, flat, with sharp
> straight edges and no glow. Walls, ceiling and floor are MID-GREY, not black:
> only the far corners and the space under the bed go to solid black. The
> ceiling is visible along the top of the frame. Nothing else: no lamp on, no
> clutter, no pictures, no plants, no phone, no clock. [+ стилевой суффикс]

**Негативный промт:**

> person, people, man, woman, figure, silhouette in bed, sleeping person, text,
> letters, watermark, colour, red, blue, warm light, glow, bloom, gradients,
> soft shadows, photorealism, 3D render, clutter, plants, posters, lamps on

### Что критично и почему

| требование | зачем |
|---|---|
| **кровать ПУСТАЯ** | лежащего рисует движок (второй персонаж в позе `lezhit`). Нарисованный человек даст двух людей в кадре |
| **верх матраса на ~3/4 высоты** | по этой линии сажается лежащая фигура. Выше — она повиснет над кроватью, ниже — утонет в ней |
| **стены СРЕДНЕ-СЕРЫЕ, чёрное только в углах** | персонажи — сплошные чёрные силуэты. На тёмной комнате они исчезнут; светлые плоскости — единственное, на чём они читаются |
| **светлое пятно от фонаря СЛЕВА** | на нём стоит и говорит Фреди. Это его «сцена»: жесты и мимика видны только на светлом |
| **свет плоский, с жёсткой кромкой** | по LOCATION_STYLE.md §7: луч — один флэт-полигон, а не свечение. Мягкий свет читается как «фото» и спорит с тушью |
| **потолок в кадре** | лежащий смотрит в потолок — если его не видно, взгляд героя упирается в пустоту |
| **без цвета** | ролик монохромный; цветной акцент уйдёт в серый, но на превью будет спорить с тушью |

### Куда класть

`examples/assets/sets/fredi-spalnya.png` → оборачиваю в SVG-сет тем же именем
`.svg` (сценарий уже ссылается на него, менять ничего не придётся).
