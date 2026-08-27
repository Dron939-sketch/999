# Промты локаций — «Парус»

Три новые локации. Каждая не фон, а довод: она доказывает ту реплику, под
которой стоит.

## ГЛАВНОЕ: ЕДИНИЦА МАСШТАБА (реестр §XXVII)

Прошлый ролик студия забраковала за то, что персонаж не соответствовал локации:
чайник был нарисован в 6,4 раза крупнее нормы, и человек читался куклой.
Поэтому мера идёт первой строкой:

> ### 1 метр = 26% высоты кадра.
> При 1280×720 — 187 пикселей на метр. Стоящий взрослый занимает 44% кадра.

| предмет | реальная высота | доля кадра | px при 720 |
|---|---|---|---|
| стул (сиденье) | 0,45 м | 12% | 84 |
| стол / стойка | 0,90 м | 23% | 168 |
| легковая машина (крыша) | 1,45 м | 38% | 273 |
| дверной проём | 2,00 м | 52% | 375 |
| ворота мойки | 3,00 м | 78% | 562 |

Проверка без линейки: крыша легковой машины человеку по плечо, стойка — чуть
выше пояса, ворота мойки — вдвое выше человека.

**К каждой локации я допишу `chelovek` в `<сет>.surfaces.json`** — долю кадра,
которую занимает в ней стоящий взрослый. Её считает гейт `tools/masshtab.py`,
рендеря кадр с фигурой и без.

## Общий стилевой суффикс (добавлять в КАЖДЫЙ промт)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink, bold
> boiling outline, flat fills only (NO gradients, NO soft light, NO shading),
> extremely high contrast, limited palette — light grey paper (#d4d7cf) and
> black ink (#141410), STRICTLY NO COLOUR anywhere in the image; graphic /
> illustrative, NOT photorealistic; slightly rough, redrawn-by-hand feel;
> minimal detail, few strong shapes; NO people, NO figures, NO text, NO letters,
> NO logos; the lower quarter of the frame is EMPTY LIGHT FLOOR so a character
> can stand on it and cast a shadow; everything drawn to human scale — a
> standing adult would be 44% of the image height, so a car roof is 38% of image
> height, a counter 23%, a door opening 52%; wide 16:9 landscape composition,
> horizontal frame, NOT square.

---

## 1. УЛИЦА: МОЙКА И ПУСТОЕ ПОМЕЩЕНИЕ НАПРОТИВ — хук, ответ на перелом, жало

**Что доказывает.** Главную мысль ролика целиком, и до единого слова. Мойка
работает — ворота открыты, машина внутри. Напротив, через дорогу, помещение с
witness-окном и решёткой: пустое, сдаётся. Зритель видит ответ раньше, чем
услышит вопрос «чего вы напротив своей мойки не открыли».

Локация в кадре ТРИЖДЫ: хук, ответ на переломе и кольцо в жале. Это самая
важная картинка ролика.

> A narrow city street seen straight on from the opposite pavement: on the LEFT
> a small single-bay car wash with its roller door open and one car standing
> inside; on the RIGHT, across the road, a small EMPTY commercial unit with a
> bare shop window, a roller shutter half down and nothing inside. Between them
> a plain road with kerbs. The car wash gate is 78% of the image height; the car
> roof inside is 38%; the empty unit's door opening is 52%. Nothing else in the
> frame — no signs, no traffic, no trees. The pavement in the foreground is
> completely EMPTY light concrete, at least a third of the frame width free.

**Посадка фигуры:** на переднем тротуаре по центру, между мойкой и пустым
помещением, `x ≈ 0.50`. Обе постройки должны оставаться видны по бокам от неё.

---

## 2. ЗАЛ ОЖИДАНИЯ АВТОМОЙКИ — час, который уже отнят

**Что доказывает.** Реплики VO-7 и VO-8: «ваш клиент сидит там час и не знает,
куда себя деть. Этот час у него уже отнят». Час нельзя нарисовать — можно
нарисовать место, где его теряют: четыре стула, часы, стол с мятым журналом,
никого.

Пустота здесь обязательна: если посадить кого-то, кадр станет про людей, а он
про ВРЕМЯ.

> The tiny waiting room of a car wash seen straight on: FOUR plastic chairs in
> a row against the back wall, a low table with one crumpled magazine, a round
> wall clock above the chairs, and a window in the side wall through which the
> wash bay is visible as a blur of shapes. Nobody there. A vending machine
> stands in the corner, unplugged. The chairs' seats are 12% of the image
> height, the table 23%, the door opening 52%, the clock small — 7%. The floor
> in the foreground is EMPTY light tile.

**Посадка фигуры:** справа от стульев, в проходе, `x ≈ 0.62`. Между ней и
стульями — не меньше её ширины: в прошлом ролике фигура резалась мебелью, и
студия это забраковала.

---

## 3. НОЧНАЯ КУХНЯ КАФЕ, КОТОРАЯ СТОИТ — ноль, который не мало

**Что доказывает.** Реплики VO-9 и VO-10: «час, когда чужая техника стоит,
приносит владельцу ноль». Это самая абстрактная часть ролика, и ей нужна самая
конкретная картинка: исправное дорогое оборудование, выключенное на ночь.
Работать может — не работает.

> The kitchen of a small cafe at night, seen straight on: a stainless steel
> range with six burners, a tall fridge, a steel prep table with clean empty
> trays stacked on it, pans hanging in a row. Everything switched off, spotless
> and still. One narrow window high on the back wall shows night outside. The
> range top is 23% of the image height, the fridge 47%, the door opening 52%.
> No food, no people, no mess — the room is ready and unused. The floor in the
> foreground is EMPTY light tile.

**Посадка фигуры:** в проходе справа, `x ≈ 0.66`, плита у неё чуть выше пояса.

---

## ЧТО ОСТАЁТСЯ ПРЕЖНИМ

- **ПУСТОТА** (`void-black.svg`) — чёрный кадр на переломе; фигура ставится у
  ПЕРЕДНЕГО края пола, иначе карта пола отправляет её к горизонту.
- **развилка двух троп** (`razvilka-trop.svg`) — открытое место под реплику про
  ветер: «он идёт туда, где уже дует». Локация свежая, масштаб в ней проверен.
- **зал Лектория** и **титры** — фирменные кадры серии.

## ЧТО Я ПРОВЕРЮ, КОГДА КАРТИНКИ ПРИДУТ

Четырьмя замерами, а не глазом: яркость превью после монохромного прохода
(150…230 из 255), ноль цветных пикселей, высота опорного предмета против
таблицы, зазор между фигурой и ближайшим предметом. Плюс гейт масштаба — он
теперь считает рост фигуры рендером.
