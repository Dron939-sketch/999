# Промты для генерации локаций — «История религий»

Ролик собран и рендерится УЖЕ СЕЙЧАС: три недостающие локации нарисованы
вектором от руки (`detskaya.svg`, `cherdak.svg`, `derevo-pen.svg`). Эти промты —
чтобы заменить их сгенерированными картинками, когда будут готовы. Замена
безболезненная: кладёшь `.png` в `examples/assets/sets/` рядом с одноимённым
`.svg`, правишь одну строку `import set ...` — и всё, остальное (посадка фигуры,
тени, кадрирование) считается от карты поверхностей, а не от картинки.

ВАЖНО ПРО ЯРКОСТЬ. На локации накладывается монохромный проход с контрастом
2.2 — он растаскивает полутона к краям. Уже обжигались: `cafe-ruins` после
такого прохода давал среднюю яркость 1 из 255, кадр становился чёрным целиком,
и фигура повисала в «космосе». Поэтому в каждом промте требуется СВЕТЛЫЙ ПОЛ и
запрет на общий тёмный тон: пол — это то, на что ложится тень персонажа, и
если он тёмный, тени не видно, а фигура не стоит на земле.

## Общий стилевой суффикс (добавлять в КАЖДЫЙ промт)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> bold boiling outline, flat fills only (NO gradients, NO soft light, NO
> shading), extremely high contrast, limited palette — light grey paper
> (#d4d7cf) and black ink (#141410), no colour; graphic / illustrative, NOT
> photorealistic; slightly rough, redrawn-by-hand feel; minimal detail, few
> strong shapes; NO people, NO figures, NO text; empty light floor in the
> foreground so a character can stand on it and cast a shadow; 16:9.

## 1. ДЕТСКАЯ — «сюда вы вернётесь»
Первая и последняя локация ролика. Комната ждёт того, кто ещё не родился, и
поэтому она ПУСТАЯ, но обжитая: кровать застелена, велосипед прислонён. Это
не заброшенность, это ГОТОВНОСТЬ.

> An empty child's room seen straight on: bare walls, a narrow made bed
> against the left wall, a small child's bicycle leaning against the right
> wall, a single window with pale flat light, bare wooden floor kept light and
> empty in the foreground. Nobody in the room. The room feels waiting, not
> abandoned. Flat tones, bold ink edges. [+ стилевой суффикс]

Что важно: **велосипед обязателен и стоит справа** — он играет в финале, туда
подходит персонаж. Пол светлый и пустой по центру: там стоит фигура.

## 2. ЧЕРДАК — «чужое наследство»
Локация-вещдок: здесь лежит всё, что оставили ДО нас. Ящики закрыты — что
внутри, никто не проверял.

> A cluttered attic: stacks of cardboard boxes and an old trunk pushed against
> the sloping roof beams, a bare hanging light bulb on a wire, a small dusty
> dormer window at the far end, wide light floorboards kept clear in the
> foreground. Nobody there. Objects stacked and forgotten, never opened.
> Flat tones, bold ink edges, strong diagonal roof lines. [+ стилевой суффикс]

Что важно: **коробки идут вдоль стены слева направо** — персонаж проходит
мимо них на перечислении. Проход по центру свободен.

## 3. СКЛОН: ДЕРЕВО И ПЕНЬ — «посадил или спилил»
Главная метафора ролика в одном кадре: одно и то же место, два решения. Дерево
и пень стоят РЯДОМ и одного размера в основании — это подчёркивает, что выбор
был один и тот же.

> A bare open hillside under an empty sky: on the left a single lone tree with
> a sparse crown, on the right a fresh tree stump of the same thickness with
> splintered edges and a few wood chips around it. Nothing else on the hill.
> Light empty ground in the foreground. Flat tones, bold ink edges, the tree
> and the stump equally weighted in the composition. [+ стилевой суффикс]

Что важно: **дерево слева, пень справа, оба на одной линии земли**. Между ними
пустое место — туда встаёт персонаж, и оба варианта оказываются по бокам от
него.

## 4. (Опц.) МОГИЛЬНАЯ ПЛИТА — предмет, не локация
Сейчас играется предметом `plita.svg` поверх пустого поля: одинокая плита в
чистом поле сильнее целого кладбища — кладбище это про многих, а плита про
одного, и этот один — зритель.

> A single plain rough stone slab standing upright in empty ground, no
> inscription, no cross, no ornament, slightly tilted. Isolated object on a
> transparent background for cutout. Bold ink outline, flat fill.
> [+ стилевой суффикс, но БЕЗ требования пола — это вырезной предмет]

## Как подключить
- Растр кладём в `examples/assets/sets/` как `.png`/`.webp`, движок его грузит:
  `import set detskaya from "../assets/sets/detskaya.png"`.
- Рядом обязан лежать `<имя>.surfaces.json` с линией пола (`back_y` —
  нормализованная высота, на которой земля начинается). Без него `place ... on
  floor` молча не работает и фигура левитирует.
- После замены прогнать `python3 tools/studio.py --only istoriya-religij` и
  посмотреть, не ушёл ли кадр в черноту: средняя яркость локации после
  монохрома должна быть выше 60 из 255.
