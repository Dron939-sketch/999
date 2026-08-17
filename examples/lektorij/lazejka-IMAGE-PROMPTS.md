# Промты для растровых картинок — «Лазейка»

Векторный `shlagbaum.svg` рисовался кодом и получился сухим: блоки стрелы
читаются как «лего», живой линии нет. Здесь промт на замену — растр
генерируется отдельно и кладётся в репозиторий руками.

## Общий стилевой суффикс (добавлять в КАЖДЫЙ промт)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> thick wobbly hand-inked outline, flat fills only (NO gradients, NO soft
> light, NO shading, NO hatching), stark high-contrast pure black and white,
> black ink (#141410) only; graphic and illustrative, NOT photorealistic;
> slightly rough, redrawn-by-hand feel; minimal detail, few strong shapes.

## 1. ШЛАГБАУМ С ПУСТОЙ ТАБЛИЧКОЙ (замена `props/shlagbaum.svg`)

Файл: `examples/assets/props/shlagbaum.png`, **10:3** (напр. 2100×630),
**прозрачный фон** (PNG с альфой).

> A closed road barrier (boom barrier), side view, straight on, isolated on a
> fully transparent background. A short thick vertical post stands at the far
> LEFT edge, with a round counterweight near its top and a small base plate at
> its foot. From the post a long horizontal boom extends to the RIGHT and
> STOPS at about 90% of the image width — the remaining right part of the
> image is EMPTY: nothing continues, no fence, no wall, no second post. The
> boom is a straight bar made of alternating solid black blocks and empty
> gaps, joined by a thin axis line (a striped barrier reading in pure black
> and white — NO red, NO colour). Hanging under the boom, slightly left of
> centre, on two thin straps: a rectangular warning sign — a bold black frame
> with a COMPLETELY BLANK light plate inside. The sign must be EMPTY: no text,
> no letters, no numbers, no symbols, no icons, no pictogram. Nothing else in
> the image: no road, no ground line, no vehicles, no people, no buildings, no
> background scenery. [+ стилевой суффикс]

**Негативный промт** (если провайдер поддерживает):

> text, letters, numbers, watermark, signature, red colour, any colour,
> gradients, soft shadows, 3D render, photorealism, people, cars, road,
> asphalt, markings, background scenery, second barrier, fence

### Что критично и почему

| требование | зачем |
|---|---|
| **стрела кончается на ~90% ширины** | справа заложен ПРОХОД: на взлёте герой обходит шлагбаум сбоку. Если стрела дойдёт до края, обход станет нечитаемым |
| **столб слева, не в центре** | герой стоит слева у столба, обход идёт направо — иначе он пойдёт «сквозь» опору |
| **табличка ПУСТАЯ** | надпись «ПРОЕЗД ЗАПРЕЩЁН» впечатывает движок (`text`) на развороте. Нарисованный текст даст двойную надпись, а на развороте нечему будет «впечататься» |
| **прозрачный фон** | это проп поверх поля `field-empty.svg`. Непрозрачный фон даст прямоугольную заплату поверх локации |
| **10:3** | под текущие координаты сцены. Другая пропорция — не страшно, пересчитаю позицию и масштаб под неё |
| **без красного** | ролик монохромный (`monochrome: true`), цвет всё равно уйдёт в серый, но в цвете он «поспорит» с тушью на превью |

### Куда класть и что дальше

1. PNG → `examples/assets/props/shlagbaum.png`;
2. дальше я оборачиваю его в SVG (движок рендерит `<image>` через resvg,
   правок движка не нужно) и пересчитываю в сценарии позицию таблички под
   реальную геометрию картинки;
3. прогон CI с маркером `[only: lazejka-chuzhoe-intro]` пересобирает ролик.

Если прозрачный фон не получается — пришлите на ровном светлом фоне
(#d4d7cf), вырежу фон при обёртке.
