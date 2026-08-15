# Промты локаций — «Стресс-менеджмент», ролик «Освободите линию»

**Новых картинок ДВЕ**, и это одна и та же кухня: утром и ночью. Остальные две
локации ролика берутся как есть — `pustota-bumaga` (опыт на зрителе ставится вне
помещения) и `lektorij-zal` (презентация звучит в другом месте, и она не должна
быть узнаваемой: это не его комната, а зал).

## ЗРИТЕЛЬ, ПОД КОТОРОГО РИСУЕТСЯ КУХНЯ

Работающий взрослый, тридцать — сорок пять, город, наёмная работа с людьми или
экраном. Дом — работа — дом, вечер уходит на дела, усталость считается нормой и
поводом для врача не считается. К психологу не ходит, о выгорании слышал и
относит его к другим.

**Кухня — то место, где его день начинается раньше всех остальных**, и это
единственная комната, где он бывает один. Поэтому ролик открывается ею, и
поэтому она обязана быть УЗНАВАЕМОЙ, а не красивой. Разрыв (горящая настольная
лампа при дневном свете) существует только относительно узнанной комнаты: в
безымянной кухне лампа — просто рисунок.

## ГЛАВНОЕ: ЕДИНИЦА МАСШТАБА (реестр §XXVII)

> ### 1 метр = 26% высоты кадра.
> При 1280×720 — 187 пикселей на метр. Стоящий взрослый занимает 44% кадра.

| предмет | реальная высота | доля кадра | px при 720 |
|---|---|---|---|
| кружка | 0,09 м | 2% | 17 |
| столешница / стол | 0,90 м | 23% | 168 |
| холодильник | 1,80 м | 47% | 337 |
| дверной проём | 2,05 м | 53% | 384 |

**НО КАДР БЕРЁТСЯ БЛИЖЕ ОБЫЧНОГО.** По §XL реестра локация, в которой стоящий
взрослый занимает меньше половины кадра, не годится для говорящей сцены: гейт
масштаба требует человеческого роста, а гейт готового файла — фигуры не мельче
35% кадра, и в просторной комнате эти требования не пересекаются. Поэтому кухня
рисуется ТЕСНОЙ: от стены до стены три с половиной метра, не больше. Ориентир —
стоящий человек занял бы примерно 60% высоты кадра.

**ЧИСЛА В КАРТИНКЕ НЕ РИСУЮТСЯ** (реестр §XXX). Генератор однажды принял
проценты за часть композиции и написал «78%» тушью на стене. Масштаб задан
отношениями предметов, проценты — только в служебных скобках.

## Общий стилевой суффикс (добавлять в КАЖДЫЙ промт)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink, bold
> boiling outline, flat fills only (NO gradients, NO soft light, NO shading),
> extremely high contrast, limited palette — light grey paper (#d4d7cf) and
> black ink (#141410), STRICTLY NO COLOUR anywhere in the image; graphic /
> illustrative, NOT photorealistic; slightly rough, redrawn-by-hand feel;
> minimal detail, few strong shapes; NO people, NO figures, NO text, NO letters,
> NO numbers, NO logos; the lower quarter of the frame is EMPTY LIGHT FLOOR so a
> character can stand on it and cast a shadow; wide 16:9 landscape composition,
> horizontal frame, NOT square.

**Цвет в кадре не нужен, и это не упущение.** Единственное цветное пятно ролика
— тёплая лужа лампового света на столе — накладывается мной поверх готовой
картинки плоской заливкой (0.13% кадра). Генератору цвет не заказывается: он
даёт градиент там, где нужна плоская заливка, и не попадает в место, где стоит
проп лампы.

---

## 1. КУХНЯ УТРОМ — `stress-kuhnya-utro.png`

**Где стоит:** первая сцена (VO-1…VO-4), возврат из пустоты (VO-7), финал с
возвратом якоря и кольцом (VO-17…VO-19). **Четыре захода из шести — это главная
картинка ролика**, и кольцо ленты замыкается на ней.

**Что доказывает.** Что это его утро, а не декорация: комната узнаётся раньше,
чем прозвучит первое слово. Дальше на этот узнанный фон ставится лампа, которой
здесь гореть незачем, — и только поэтому она читается как неправильность.

**Промт:**

> A small cramped ordinary apartment kitchen seen straight on, morning. Left:
> a simple four-burner gas stove with a plain stovetop kettle on it. Centre-right:
> a small square kitchen table pushed against the wall, its top clearly visible,
> with one used mug and a folded newspaper on it. Behind the table a plain wall
> with a modest window; daylight, the window is bright and plain. Right edge: the
> corner of a fridge with a single magnet. The room is narrow — wall to wall about
> three and a half metres — so the furniture nearly fills the width; the table top
> sits a bit above waist height, the stove the same, the fridge is twice the table
> height. Everyday and lived-in, not styled: no plants, no decor, no shelves of
> jars. The lower quarter of the frame is empty light floor.

**Чего в кадре быть не должно.** Телефона, радиоприёмника, любого аппарата со
шнуром и вообще всего, что похоже на связь: зритель слышит «Освободите линию» и
не должен получить на картинке готовый ответ. По этой же причине снята
переговорка с селектором на прошлой сборке. Ещё: никаких настольных ламп — лампу
я ставлю пропом поверх, и вторая в кадре убьёт разрыв.

**Место под лужу света.** На столешнице должно остаться пустое место размером с
блюдце между кружкой и газетой — туда лягут свет и проп лампы.

---

## 2. ТА ЖЕ КУХНЯ НОЧЬЮ — `stress-kuhnya-noch.png`

**Где стоит:** сцена ночи и перелом (VO-5, VO-6).

**Что доказывает.** Что ничего не изменилось, кроме темноты: та же комната, та
же посуда, тот же стол. Ночь узнаётся окном, а не другой мебелью — если кухня
окажется другой, реплика «Ночь» прозвучит про чужую квартиру.

**Промт:**

> THE SAME cramped apartment kitchen as the previous image, same camera position,
> same furniture in the same places — the gas stove with the kettle on the left,
> the small square table with a mug and a newspaper centre-right, the fridge
> corner at the right edge. Only the time of day differs: it is night, the window
> is a solid black rectangle, and a single bare ceiling bulb hangs over the table
> casting a plain cone of light. Everything else identical. The lower quarter of
> the frame is empty light floor.

**Чего в кадре быть не должно.** Того же, что и в утренней: связи, аппаратов,
настольных ламп. И никакой кровати — «тело в кровати» сказано словом, а
персонаж по правилам серии не ложится и не садится.

---

## ЧТО Я ДЕЛАЮ, КОГДА КАРТИНКИ ПРИДУТ

1. Кладу `.png` в `examples/assets/sets/`, оборачиваю в `.svg` (base64 внутрь —
   так лежат все сеты серии).
2. Накладываю тёплую лужу света на столешницу плоской заливкой и проверяю
   `tools/cvet.py`: одно цветное пятно на ролик, не больше 3% кадра.
3. Снимаю меру человека в `<сет>.surfaces.json` по столу или холодильнику и
   сверяю `tools/masshtab.py`. Если мера окажется ниже 0.5 — картинку придётся
   перерисовать теснее (реестр §XL), и я скажу об этом сразу.
4. Ставлю линию пола `floor.back_y` и пересобираю контактный лист.
