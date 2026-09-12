# «Гнев и агрессия» — промты локаций

Локации ролика — ручная векторная графика. Она читается (четыре раунда зала
это чинили), но заказчик посмотрел готовое и сказал: **слабые локации.** С этим
не спорят: кухня, кастрюля и дверь — это один предмет, линия пола и большое
белое поле. У «Философии» и «Истории идей» фон другой, потому что там рисовал
генератор.

Здесь — промты, по которым фон поднимается до того же уровня, и правила, без
которых сгенерированная картинка в кадр не встанет.

## Что отдаётся генератору, а что нет

Генератору отданы **две** локации: кастрюля (§1) и дверь (§2). Это пулемёт и
разворот — два кадра, которые зритель запомнит, и оба самодостаточны.

**Кухня вечером и кухня утром остаются ручными, и это не экономия.** Они
зарифмованы кадр в кадр: тот же стол, та же лампа, та же линия пола, и
единственная разница — кружка лежит или стоит, кружек одна или две, стулья
врозь или друг к другу. Генератор такую сквозную геометрию не держит: он
нарисует две похожие кухни, рифма развалится, и ролик потеряет то, ради чего
снят финал. То же было в «Философии» с запиской — там её тоже рисовали руками.

Порядок работ: приходят две картинки → под них подгоняются позиции предметов
(камень, створка) → прогон завода → раунд зала.

## Как это работает

1. Картинку генерит завод (`tools/image_gen.py` при ключе `IMAGE_API_KEY` в
   секретах CI) по объявлению в `tools/productions.json`, либо пользователь
   руками по промту ниже.
2. `tools/vectorize.py` обводит растр в пути: камера наезжает до 2.01×, растр
   на сверхкрупе плывёт.
3. **Сгенерённое видно в релизе.** Раньше картинка ложилась в дерево раннера и
   исчезала вместе с ним — принять или отбраковать её было нельзя. Теперь
   копия каждой объявленной картинки уезжает в релиз рядом с роликом
   (`videos/gnev-intro-<имя>.png`).

## Четыре условия, без которых картинка не встанет в кадр

**Пол на y≈604** кадра 1280×720 (84% высоты). Туда встают ноги персонажа при
`place (x, 0.585) scales 0.80`.

**Место под фигуру свободно.** В «Гневе» персонаж стоит: кастрюля — x≈0.30,
дверь — x≈0.56. В этой трети кадра не должно быть ничего, кроме пола.

**Крупные массы фона — не чёрные.** Персонаж сплошной чёрный; чёрная масса
рядом съедает его силуэт. Просить сразу: `dark grey mass with a thick black
outline, not solid black`.

**Место под движущийся предмет пустое.** Это условие «Гнева», и его нет у
других роликов. Камень и створка — не часть фона, а предметы, которые ИГРАЮТ:
камень вдавливается, подскакивает и снимается с крышки, дверь закрывается всю
реплику. Нарисованные в картинке, они окаменеют. Поэтому:

- у кастрюли **крышка свободна: на ней ничего не лежит**;
- у двери **створки нет вовсе: только косяк и светлый проём**.

## Общий стилевой суффикс (приписывать к каждому промту)

> hand-drawn 2D cartoon in the style of Mr. Freeman, thick wobbly hand-inked
> black outlines, flat light-gray paper background, stark high-contrast black
> and white, no gradients, no soft shading, flat fills only, three or four
> tonal planes separated by black contour, graphic and minimal, five strong
> black shapes rather than fifty small ones, no text or lettering anywhere,
> floor line at 84% of the image height, empty space left free for a
> character to stand in, 16:9

Про «no text» отдельно: генераторы уродуют кириллицу, а надписи в этом ролике
ставит движок.

---

# Локации

## 1. `gnev-kryshka-gen.svg` — кастрюля на огне, крышка свободна

> a huge battered cooking pot with a thick black outline standing on a squat
> dark grey gas stove in the right half of an empty kitchen, the pot taller
> than a man's waist, two heavy side handles, its flat lid lying loose and
> slightly askew on top with nothing on it, six flat black flame tongues
> licking up the front face of the stove, three thick jets of steam forcing
> their way out from under the lid and bending in the air, a scorched wall
> behind, the left third of the frame completely empty floor

Что читается: под крышкой кипит и лезет наружу. Персонаж стоит слева (x≈0.30).
**Крышка обязана быть пустой** — камень на неё кладёт движок, и он же её
вдавливает, подбрасывает и снимает.

## 2. `gnev-dver-gen.svg` — коридор, дверь без створки

> a narrow apartment hallway at night, on the right a massive black door frame
> with the door itself absent, showing a tall bright rectangle of light from
> the room beyond, a small child sitting on the floor inside that lit
> rectangle seen in profile, knees pulled up, arms around them, head lowered;
> on the left wall a coat rack with three hooks, a small child's jacket
> hanging on the far hook and the two near hooks empty; a toy brick lying on
> the floor between the rack and the door, the middle of the frame empty floor

Что читается: тот, кто мог уйти, ушёл; остался тот, кто уйти не может.
Персонаж стоит чуть правее центра (x≈0.56). **Створки в картинке нет** — её
кладёт движок отдельным предметом и закрывает всю реплику.

## 3. `gnev-kuhnya.svg` — вечерняя кухня (остаётся ручной)

Промт записан на случай, если рифму когда-нибудь решат генерить парой — тогда
обе кухни надо делать ОДНИМ заходом и одной композицией.

> an evening kitchen, a long dark grey table with a thick black outline in the
> right half, a white mug lying on its side on the table with a black pool of
> spilled tea spreading from it to the near edge, a thin black drip running
> off the edge into a black puddle on the floor, a child's chair toppled on
> its back on the left with its four legs in the air, a bare lamp hanging on a
> cord above the table, an open doorway at the far right, the left third of
> the frame empty floor

## 4. `gnev-utro.svg` — утренняя кухня (остаётся ручной)

> the same kitchen in the morning, the same long dark grey table in the same
> place, the same bare lamp on a cord above it, two white mugs standing
> upright side by side on the table, two chairs turned to face each other
> across it, a bright window with a simple cross frame on the right wall, the
> floor clean and empty, the left third of the frame empty floor

Разница с §3 — только предметы. Стол, лампа и линия пола обязаны совпасть
пиксель в пиксель: на этом держится весь финал.

---

# Обложка

## 5. `gnev-intro-cover.png` — обложка для YouTube

> a huge battered cooking pot with a heavy rough stone pressing its lid down,
> three thick jets of steam forcing out from under the lid, a small black
> figure of a man in a ragged coat standing in front of it with his back to
> the viewer, tiny against the pot, stark high-contrast black and white,
> hand-inked outlines, flat fills, empty light-gray background, no text
> anywhere, 16:9

Надпись ставится редактором поверх: заголовок ролика («Держаться? Не
работает») набирается тем же кеглем, что на обложке «Философии».
