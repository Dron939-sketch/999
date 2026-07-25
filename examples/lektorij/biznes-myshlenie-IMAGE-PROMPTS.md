# Промты для растровых картинок — «Бизнес-мышление» (опционально)

Локации собраны как **графичные SVG** (`biznes-street.svg`, `card-biznes.svg`) —
их достаточно, растр НЕ обязателен. Эти промты — на случай, если хочешь более
богатый фон/кей-арт. ВАЖНО: держим единый стиль, иначе растр «поспорит» с
векторным персонажем.

## Общий стилевой суффикс (добавлять в КАЖДЫЙ промт)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> bold boiling outline, flat fills only (NO gradients, NO soft light),
> extremely high contrast, limited palette — light grey paper (#d4d7cf),
> black ink (#141410), ONE spot accent of deep red (#c31a1a); graphic /
> illustrative, NOT photorealistic; slightly rough, redrawn-by-hand feel;
> minimal detail, few strong shapes; 16:9.

## 1. Фон-локация: серая деловая улица (замена biznes-street.svg)
> A grey faceless business street: a row of blank office towers with empty dark
> windows, an empty light sidewalk in the foreground, cold and impersonal, a
> place where a hurried crowd passes without looking. Flat tones, bold ink
> edges. Foreground floor kept light and empty so a character's cast shadow can
> fall on it. [+ стилевой суффикс]

## 2. Реквизит: красная «проблема/куш» (замена red-problem.svg)
> A single small angular red object lying on grey asphalt — reads as discarded
> junk from far, but as a rough gem / prize up close. Deep spot-red only,
> everything else greyscale. Bold ink outline, flat facets, no gradient.
> Transparent/neutral background for cutout. [+ стилевой суффикс]

## 3. Кей-арт / титр-карта (замена card-biznes.svg)
> Key art for a course titled «Бизнес-мышление» (Business Thinking): a large
> ink-drawn eye/lens with a red pupil — "the optics of an entrepreneur" — on
> light paper, room below for a bold title. One red accent (the pupil), rest
> black ink on grey. Iconic, poster-like, minimal. [+ стилевой суффикс]

## 4. (Опц.) Метафора-кадр: толпа-тени
> A grey crowd of identical faceless hunched figures trudging in one direction,
> long hard-edged black cast shadows on a light floor, one figure standing
> still facing the viewer. Silhouette storytelling, flat black shapes, high
> contrast. [+ стилевой суффикс]

## Как подключить (если сгенеришь)
- Растровые фоны кладём в `examples/assets/sets/` как `.png`/`.webp` и
  импортируем `import set street from "...png"` (движок грузит и растр).
- Красный реквизит — в `examples/assets/props/`.
- Либо впиши пути в `tools/productions.json` → поле `images` для авто-генерации
  через `image_gen.py` (Nano Banana) на заводе.
- ВАЖНО: после растра прогнать глазами — не спорит ли с векторным Фрименом;
  движок сверху всё равно кладёт ч/б + зерно + виньетку.
