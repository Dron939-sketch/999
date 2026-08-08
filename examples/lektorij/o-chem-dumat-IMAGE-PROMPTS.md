# Промты локаций — «О чём думать»

Замечание студии: **размер персонажа не соответствует локации, и его позиция
тоже**. Замер по готовому ролику это подтверждает, и цифры такие:

| предмет в кадре | нарисован | должен быть | промах |
|---|---|---|---|
| чайник на плите | 290 px | ~45 px | **6,4×** |
| кружка на столе | 79 px | ~17 px | **4,6×** |

Фигура в том же кадре — около 315 px. То есть чайник почти с человека ростом, а
кружка ему по колено. Локации рисовались без человека в качестве меры, поэтому
персонаж в них читается не хозяином кадра, а куклой, которую туда поставили.

Ниже — мера, три новых локации и правила посадки фигуры.

---

## ГЛАВНОЕ: ЕДИНИЦА МАСШТАБА

Персонаж ростом примерно 1,7 м занимает **44% высоты кадра**, когда стоит на
переднем плане. Отсюда единственное число, которое надо помнить:

> ### 1 метр = 26% высоты кадра.
> При кадре 1280×720 это **187 пикселей на метр**.

Всё остальное считается из него. Таблица для сверки — её достаточно приложить
линейкой к готовому рисунку:

| предмет | реальная высота | доля кадра | пикселей при 720 |
|---|---|---|---|
| кружка | 0,10 м | 2,6% | 19 |
| чайник | 0,25 м | 6,5% | 47 |
| ноутбук раскрытый | 0,25 м | 6,5% | 47 |
| стул (сиденье от пола) | 0,45 м | 12% | 84 |
| стол (столешница от пола) | 0,75 м | 19% | 140 |
| спинка стула | 0,95 м | 25% | 178 |
| кухонная тумба | 0,90 м | 23% | 168 |
| подоконник от пола | 0,85 м | 22% | 159 |
| холодильник | 1,80 м | 47% | 337 |
| дверной проём | 2,00 м | 52% | 375 |
| потолок в комнате | 2,60 м | 68% | 490 |

**ПРОВЕРКА НА ГЛАЗ, ЕСЛИ ЛИНЕЙКИ НЕТ.** Столешница должна приходиться человеку
чуть выше пояса, спинка стула — по грудь, холодильник — по макушку, дверь — на
голову выше. Если чайник на плите крупнее человеческой головы — рисунок в
масштабе не сходится, и это видно без замеров.

---

## КАК ПОДКЛЮЧАЕТСЯ РАСТР

Движок грузит только SVG: `import set` разбирает файл через usvg и на PNG падает
с «provided data has not an UTF-8 encoding». Растр заворачивается в SVG:

    python3 tools/raster_set.py вход.png examples/assets/sets/имя.svg --drop 0.55

Рядом обязан лежать `<имя>.surfaces.json` с линией пола — **её ставлю руками по
рисунку**, автомат её не берёт: у комнаты стена и пол одинаково светлые.

**ВАЖНО ПРО ЯРКОСТЬ.** На локацию накладывается монохромный проход с контрастом
2.2, он растаскивает полутона к краям. Уже обжигались: `cafe-ruins` после него
давал среднюю яркость 1 из 255, кадр становился чёрным целиком и фигура повисала
в космосе. Поэтому в каждом промте требуется СВЕТЛЫЙ ПУСТОЙ ПОЛ на переднем
плане: на него ложится тень, и без него персонаж не стоит на земле.

**ВАЖНО ПРО ЦВЕТ.** Монохромный проход цвет ПРОПУСКАЕТ. В нынешней кухне под
чайником горит красное пламя, и оно держится в трёх самых заметных кадрах —
я его не заказывал и не заметил. В новых локациях цвета быть не должно вовсе:
цветное пятно на ролик назначается отдельно и осознанно.

**Класть в ветку `claude/mr-freeman-lipsync-duration-sthvvw`, не в `main`** —
завод собирает ролик из рабочей ветки и картинок в `main` не видит.

## Общий стилевой суффикс (добавлять в КАЖДЫЙ промт)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink, bold
> boiling outline, flat fills only (NO gradients, NO soft light, NO shading),
> extremely high contrast, limited palette — light grey paper (#d4d7cf) and
> black ink (#141410), STRICTLY NO COLOUR anywhere in the image; graphic /
> illustrative, NOT photorealistic; slightly rough, redrawn-by-hand feel;
> minimal detail, few strong shapes; NO people, NO figures, NO text, NO letters,
> NO logos; the lower quarter of the frame is EMPTY LIGHT FLOOR so a character
> can stand on it and cast a shadow; everything drawn to human scale — a
> standing adult would be 44% of the image height, so a mug is 2.6% of image
> height, a table top 19%, a door opening 52%; wide 16:9 landscape composition,
> horizontal frame, NOT square.

---

## 1. КУХНЯ УТРОМ: ХОЛОДИЛЬНИК С ЗАПИСКАМИ — хук, список, жало, подпись

**Что доказывает.** Реплики VO-3…VO-5: «А список есть. Пять тем, и годами одни
и те же. Вы его не составляли». Записки под магнитами — это и есть список: их
кто-то принёс, они пожелтели, и никто не помнит, когда они появились. Зритель
узнаёт свой холодильник раньше, чем понимает тему ролика.

Эта же локация закрывает ролик (VO-18…VO-20): он уходит, записки остаются.
Она будет в кадре четыре раза из двадцати реплик — **это самая важная картинка
ролика, и масштаб в ней критичен**.

> A plain kitchen in the early morning seen straight on: a tall fridge standing
> against the left wall with FIVE small curled paper notes held on its door by
> magnets, a low counter with a sink to the right of it, a window above the
> counter with grey daylight, and a bare wall in the middle. The fridge is 47%
> of the image height — a standing adult would reach its top. The counter top is
> 23% of the image height. The notes are tiny, about 5% of the image height each.
> No objects larger than a fridge anywhere. The middle and right-hand floor is
> completely EMPTY light floor, at least a third of the frame width free — a
> character will stand there.

**Посадка фигуры:** между холодильником и тумбой, в пустом центре, `x ≈ 0.42`.
В нынешнем ролике фигура стояла вплотную к плите и резалась ею по пояс — здесь
между ней и любым предметом должно оставаться не меньше своей ширины.

---

## 2. ЦЕХ С ТОКАРНЫМ СТАНКОМ — закон: вопрос вытачивает человека

**Что доказывает.** Реплики VO-8…VO-10: «И каждый день — один и тот же вопрос.
Он делает не ответ, он делает вас… Десять лет — это не стаж. Это срок
изготовления». Станок не иллюстрирует мысль, он её ДОКАЗЫВАЕТ: заготовку никто
не спрашивал, какой формы она хочет быть, — её просто десять лет точили одним
резцом. Стружка на полу — это прожитые годы, и она видна.

Локация в серии не использовалась ни разу.

> The interior of a small empty workshop seen straight on: a single old metal
> lathe standing left of centre, with a half-turned cylindrical metal blank
> clamped in its chuck and a cutting tool resting against it. A heap of curled
> metal shavings lies on the floor under the machine. A bare workshop wall
> behind, one shuttered window high on the wall, nothing else. The lathe is
> about 40% of the image height — a standing adult would look down at its bed.
> The blank in the chuck is about 8% of the image height. The right half of the
> floor is completely EMPTY light concrete floor.

**Посадка фигуры:** справа от станка, `x ≈ 0.62`, так чтобы станок был у неё по
пояс, а не выше плеча. Если станок в кадре выше человека — масштаб не сошёлся.

---

## 3. РАЗВИЛКА ДВУХ ТРОП — взлёт и шутка

**Что доказывает.** Реплика VO-13, единственное высокое место ролика: «Свобода —
это когда вы выбираете вопрос, а не жуёте тот, что достался». Развилка
показывает не свободу как понятие, а то, что выбор ФИЗИЧЕСКИ существует и стоит
прямо под ногами.

Такая локация в каталоге есть (`dve-tropy.svg`), но в ней горизонт уходит почти
под верх кадра, фигура оказывается у самой дали и выходит ростом с палец.
**Нужна перерисовка с низким горизонтом**, а не новая идея.

> A wide flat field seen from ground level: two dirt paths diverge from a single
> point in the NEAR foreground, at the bottom third of the frame, and run away
> to the left and to the right. Dry grass between them. The horizon line is LOW —
> at 40% of the image height from the top — so the sky occupies the upper third
> and the near ground occupies the lower half. No trees, no buildings, no poles.
> The fork itself is close to the viewer: the two paths are already a full frame
> width apart at the bottom edge. The ground in the foreground is EMPTY and light.

**Посадка фигуры:** ровно в точке развилки, `x ≈ 0.40`, ноги на стыке троп.
В нынешнем ролике фигура стояла в стороне от тропы, и кадр читался как «человек
в поле», а не «человек перед выбором».

---

## ЧТО ОСТАЁТСЯ ПРЕЖНИМ

- **ПУСТОТА** (`void-black.svg`) — чёрный кадр на переломе. Приём серии, должен
  повторяться. Но **фигуру там надо ставить крупно**: в нынешнем ролике карта
  пола отправила её к горизонту, и главный вопрос ролика играла точка размером с
  ноготь. Ставим средний план сразу, а не через реплику.
- **окно с веткой** (`okno-vetka.svg`) — масштаб в ней сошёлся, оставляем.
- **зал Лектория** и **титры** — фирменные кадры, по ним узнают серию.

## ЧТО Я БУДУ ПРОВЕРЯТЬ, КОГДА КАРТИНКИ ПРИДУТ

Не на глаз. Пробным рендером с фигурой в кадре и замером в пикселях:

1. **яркость** превью после монохромного прохода — 150…230 из 255;
2. **цвет** — ноль насыщенных пикселей;
3. **масштаб** — высота опорного предмета в кадре против таблицы выше;
4. **посадка** — зазор между фигурой и ближайшим предметом не меньше её ширины,
   и ни один предмет не режет её по пояс.

Первые три из этих четырёх я в прошлый раз не сделал: проверял только яркость.
