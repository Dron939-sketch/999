# Промты для растровых картинок — «Лазейка»

Векторный `shlagbaum.svg` рисовался кодом и получился сухим: блоки стрелы
читаются как «лего», живой линии нет. Здесь промт на замену — но не пропа, а
ЦЕЛОЙ ЛОКАЦИИ: шлагбаум вписан в кадр вместе с полем и небом, и подключается
как `set`, а не как предмет поверх фона.

## Общий стилевой суффикс (добавлять в КАЖДЫЙ промт)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> thick wobbly hand-inked outline, flat fills only (NO gradients, NO soft
> light, NO shading, NO hatching), stark high-contrast pure black and white,
> black ink (#141410) only; graphic and illustrative, NOT photorealistic;
> slightly rough, redrawn-by-hand feel; minimal detail, few strong shapes.

## 1. ЛОКАЦИЯ: ШЛАГБАУМ В ПУСТОМ ПОЛЕ (замена `sets/field-empty.svg` в этом ролике)

Файл: `examples/assets/sets/lazejka-shlagbaum.png`, **16:9** (2560×1440 или
1920×1080), фон НЕ прозрачный — это полный кадр.

> A wide empty field under a bare sky, seen straight on from ground level. A
> single closed road barrier (boom barrier) stands alone in the middle of this
> emptiness — there is NO road, no gate, no fence, nothing to guard: just the
> barrier absurdly blocking open ground. A short thick vertical post stands on
> the LEFT with a round counterweight near its top; from it a long horizontal
> boom extends to the RIGHT and STOPS at about 70% of the image width — the
> whole right third of the frame is completely open empty field, nothing
> continues there. The boom is a straight bar of alternating solid black
> blocks and empty gaps, joined by a thin axis line (striped barrier in pure
> black and white — NO red, NO colour). Hanging under the boom on two thin
> straps: a rectangular warning sign — a bold black frame with a COMPLETELY
> BLANK light plate inside. The sign must be EMPTY: no text, no letters, no
> numbers, no symbols, no icons. Composition: the upper two thirds is a flat
> plain darker sky, the horizon line sits at about two thirds of the image
> height, and the lower third is LIGHT, PALE and EMPTY ground with sparse thin
> ink strokes for texture — this bottom area must stay clean and uncluttered.
> No people, no animals, no vehicles, no buildings, no trees, no grass tufts,
> no clouds. [+ стилевой суффикс]

**Негативный промт** (если провайдер поддерживает):

> text, letters, numbers, watermark, signature, red colour, any colour,
> gradients, soft shadows, sun, clouds, 3D render, photorealism, people,
> cars, road, asphalt, markings, buildings, trees, busy texture, clutter

### Что критично и почему

| требование | зачем |
|---|---|
| **стрела кончается на ~70% ширины** | правая треть — ПРОХОД: на взлёте герой обходит шлагбаум сбоку и встаёт справа. Дойдёт стрела до края — взлёт станет нечитаемым |
| **столб слева** | герой стоит слева у столба и оттуда идёт направо; столб в центре — он пойдёт «сквозь» опору |
| **нижняя треть светлая и пустая** | персонаж — сплошной чёрный силуэт. На тёмной или пёстрой земле он пропадёт; там же лежит его тень |
| **горизонт на ~2/3 высоты** | совпадает с `field-empty.svg`, по которому выставлены рост и посадка персонажа |
| **табличка ПУСТАЯ** | надпись «ПРОЕЗД ЗАПРЕЩЁН» впечатывает движок (`text`) на развороте. Нарисованный текст даст двойную надпись и отнимет у разворота удар |
| **ни дороги, ни забора** | в этом и абсурд: перекрыто чистое поле. Запрет реален, но он ни к чему не приложен — ровно то, о чём ролик |
| **без красного** | ролик монохромный (`monochrome: true`); цвет уйдёт в серый, но на превью «поспорит» с тушью |

### Вариант Б (если пустое поле покажется слишком голым)

Тот же кадр, но вместо поля — просёлочная колея, уходящая к горизонту, и
шлагбаум поперёк неё; правая треть по-прежнему открыта — колею можно обойти
по обочине. Абсурд слабее, зато привычнее глазу.

### Куда класть и что дальше

1. PNG → `examples/assets/sets/lazejka-shlagbaum.png`;
2. я оборачиваю его в SVG-сет (`resvg` рендерит `<image>` — правок движка не
   нужно), подключаю в сценарии вместо `field-empty.svg`, убираю проп
   `shlagbaum` и пересчитываю позицию надписи под реальную табличку;
3. прогон CI с маркером `[only: lazejka-chuzhoe-intro]` пересобирает ролик.

Пришлите картинку как есть — подгонка координат моя.
