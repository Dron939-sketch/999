# «Самооценка» — промты локаций для генерации

Пять локаций ролика сейчас — **ручная векторная графика** (плоские заливки,
четыре тона, жирный контур). Они рабочие: геометрия точная, гейты зелёные,
ролик снят. Но по фактуре они проще, чем локации «Истории идей», которые
делались генерацией с последующей обводкой, — и вот промты, чтобы поднять их до
того же уровня.

## Как это работает

1. Картинку генерирует пользователь по промту ниже (Nano Banana / Flux — что
   удобнее), 1280×720.
2. `python3 tools/vectorize.py <png> -o examples/assets/sets/<имя>.svg` —
   уплощает до нескольких тонов и обводит. **Вектор обязателен:** камера в
   ролике наезжает до 2.01×, и растровая фактура на сверхкрупе рассыпается в
   кашу (сверено двумя прогонами одного кадра на прошлом ролике).
3. Имя файла оставить прежним — сцена подхватит замену без правки сценария.

## ДВА ЖЁСТКИХ УСЛОВИЯ ГЕОМЕТРИИ

Их нельзя нарушить, иначе ролик сломается, а не «станет иначе выглядеть»:

1. **Верх плиты пьедестала и верх камня-опоры — на y≈480** кадра 1280×720
   (ровно две трети высоты). Туда встают ноги персонажа при
   `place (0.5, 0.585) scales 0.80`. Ниже — он повиснет в воздухе, и
   `ground-shadow` нарисует контактную тень под пустотой; выше — провалится
   ногами в камень.
2. **Обе плиты на ОДНОЙ высоте.** Рифма ролика в том, что персонаж в кадре
   хука и в кадре взлёта стои́т одинаково высоко, а держится по-разному:
   десятью приставленными палками против корней. Поднять опору выше значит
   продать «поднять самооценку» — ровно то, против чего курс написан.

## Общая часть промта (приписывать к каждому)

> hand-drawn 2D cartoon in the style of Mr. Freeman, thick wobbly hand-inked
> black outlines, flat light-gray paper background, stark high-contrast black
> and white, no gradients, no soft shading, no photorealism, flat fills only,
> three or four tonal planes separated by black contour, graphic and minimal,
> five strong black shapes rather than fifty small ones, empty center-bottom of
> the frame left free for a character to stand in, 16:9

## 1. `samo-pedestal.svg` — пьедестал на подпорках

> a tall narrow stone pedestal seen from below, its flat top slab occupying the
> middle of the frame at two thirds of the image height, the shaft running down
> and out of the bottom edge so the ground is never visible; the slab is
> propped from every side by about ten crooked wooden poles of different
> thickness, all steeply angled, two of them snapped in half and hanging;
> wedges hammered under the slab, two ropes lashed around the shaft, one corner
> of the slab chipped off; empty pale sky with three thin horizon strokes,
> nothing else in the frame

Что должно читаться без подписи: высоко — не значит устойчиво; чинили не раз.

**Осторожно:** подпорки не положе 40° к горизонту. В первой ручной версии три
палки шли под 15°, и на готовом кадре они слились с плитой в одну фигуру —
читался стол во всю ширину, а не шаткая тумба.

## 2. `samo-zarubki.svg` — косяк с зарубками роста

> an interior wall with a tall dark doorframe post running from the floor
> beyond the top edge of the frame, covered with about forty horizontal growth
> notches marking a child's height over years; every notch drawn by a DIFFERENT
> hand — different thickness, different tilt, different length — a third of
> them crossed out and re-drawn lower; a second post on the right with a few
> notches placed higher than any of the left ones; a wooden ruler leaning
> against the wall, a pencil lying on the floor; dark ceiling band, plain
> floor, no furniture

Что должно читаться: отметки ставили другие, и не по разу.

## 3. `samo-sud.svg` — суд, в котором нет никого

> a courtroom seen from the dock: a massive black judge's bench looming across
> the upper half of the frame, behind it a tall empty high-backed chair turned
> away, a gavel lying on its block, a single lamp on a long cord throwing one
> hard-edged flat cone of light straight down onto the empty floor; a low
> railing across the foreground enclosing the viewer; rows of empty seats
> visible at both edges; nobody in the room

Что должно читаться: заседание идёт, а судьи нет — обвинитель и подсудимый один
человек. Кресло обязано остаться ПУСТЫМ: любая фигура на месте судьи говорит
зрителю «критик снаружи», то есть противоположное тому, о чём курс.

## 4. `samo-zerkala.svg` — коридор зеркал

> a corridor of tall mirror frames in one-point perspective receding to a
> vanishing point at the horizon, four frames on each side; each mirror holds a
> dark human silhouette with both arms raised in triumph, and the FURTHER the
> mirror, the LARGER the figure inside it — perspective deliberately reversed;
> the nearest frame on the left is empty; converging floor lines; a small black
> mirror closing the corridor at the far end

Что должно читаться: чем дальше от вас человек, тем крупнее он выглядит.
Перевёрнутая перспектива — единственная неправда в кадре и делается нарочно;
генератор будет пытаться её исправить, поэтому «reversed» стоит повторить.

## 5. `samo-opora.svg` — камень, вросший в землю

> a single massive flat stone slab half-sunk into the ground in an open empty
> landscape, its top surface flat and at two thirds of the image height, wide
> and heavy, with thick roots growing out from under it into the soil on both
> sides; grass tufts where earth meets stone; one wooden pole lying discarded
> on the ground nearby, not propping anything; low horizon with two distant
> ridges, wide pale sky

Что должно читаться: та же высота, что и у пьедестала, но держится корнями, а
не палками. Единственная подпорка лежит рядом за ненадобностью — она же
пасхалка: та самая, которую сняли с пьедестала.

## Проверка после замены

```bash
./target/release/animdsl check examples/lektorij/samoocenka-intro.anim
python3 tools/studio.py samoocenka-intro
```

Плюс глазами один кадр из каждой сцены: ноги персонажа должны стоять на
поверхности, а контактная тень — лежать на ней, а не в воздухе.
