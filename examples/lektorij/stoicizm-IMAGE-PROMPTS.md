# Промты локаций — «Стоицизм на практике»

**Новых картинок ДВЕ.** Остальные четыре локации ролика уже лежат в репо и
берутся как есть: `void-black` (перелом), `vannaya-zerkalo` (внутренняя речь),
`field-empty` (взлёт), `lektorij-zal` (презентация курса).

Каждая новая локация — не фон, а довод: она доказывает ту реплику, под которой
стоит.

## ГЛАВНОЕ: ЕДИНИЦА МАСШТАБА (реестр §XXVII)

> ### 1 метр = 26% высоты кадра.
> При 1280×720 — 187 пикселей на метр. Стоящий взрослый занимает 44% кадра.

| предмет | реальная высота | доля кадра | px при 720 |
|---|---|---|---|
| ящик / коробка | 0,30 м | 8% | 56 |
| стол | 0,90 м | 23% | 168 |
| крыша легковой машины | 1,45 м | 38% | 273 |
| светофор (голова) | 3,00 м | 78% | 562 |

Проверка без линейки: крыша легковой машины человеку по плечо, стол — чуть
выше пояса, светофор — вдвое выше человека.

**ЧИСЛА В КАРТИНКЕ НЕ РИСУЮТСЯ** (реестр §XXX). Генератор однажды принял
проценты за часть композиции и написал «78%» тушью на стене. Поэтому масштаб в
промте задан ОТНОШЕНИЯМИ ПРЕДМЕТОВ, а проценты стоят только в служебных
скобках — если они всё-таки проступят на картинке, лист бракуется.

**К каждой новой локации я допишу `chelovek` в `<сет>.surfaces.json`** — долю
кадра, которую занимает в ней стоящий взрослый. Её проверяет гейт
`tools/masshtab.py`, рендеря кадр с фигурой и без.

## Общий стилевой суффикс (добавлять в КАЖДЫЙ промт)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink, bold
> boiling outline, flat fills only (NO gradients, NO soft light, NO shading),
> extremely high contrast, limited palette — light grey paper (#d4d7cf) and
> black ink (#141410), STRICTLY NO COLOUR anywhere in the image; graphic /
> illustrative, NOT photorealistic; slightly rough, redrawn-by-hand feel;
> minimal detail, few strong shapes; NO people, NO figures, NO text, NO letters,
> NO numbers, NO logos; the lower quarter of the frame is EMPTY LIGHT FLOOR so a
> character can stand on it and cast a shadow; everything drawn to human scale —
> a standing adult would be a bit under half the image height, a car roof
> reaches such an adult's shoulder, a table is just above the waist; wide 16:9
> landscape composition, horizontal frame, NOT square.

---

## 1. ТРОТУАР ВДОЛЬ СТОЯЩЕЙ ПРОБКИ, ВЕЧЕР — `stoicizm-probka.png`

**Где стоит:** хук и вся первая часть (VO-1…VO-5), удар после перелома (VO-8),
шутка с пределом (VO-17, VO-18), жало и подпись (VO-21…VO-23). **Пять заходов
из шести — это главная картинка ролика**, и кольцо ленты замыкается на ней.

**Что доказывает.** Вещь, о которой идёт речь, стоит в двух метрах и никуда не
едет. Пробка не злая и не виноватая — она просто стоит. Зритель видит это
раньше, чем услышит «ни один из них об этом не узнал».

**Чего в кадре быть не должно.** Людей, лиц в стёклах, водителей. Кадр должен
быть про НЕПОДВИЖНОСТЬ, а не про толпу.

> A city pavement at dusk seen along its length: on the RIGHT a line of cars
> stopped bumper to bumper, receding into the distance and out of frame; their
> rear lights drawn as small solid black rectangles (no glow, no colour). On the
> LEFT a plain kerb and a bare building wall with no windows at street level.
> Far ahead, at the end of the queue, a single traffic light on a tall post,
> twice as tall as a standing adult would be, its three lamps drawn as three
> plain black circles. Empty pavement fills the lower quarter of the frame,
> clean and unobstructed, wide enough for a person to stand on. The car roofs
> reach only to about shoulder height of an adult standing on that pavement. No
> people anywhere, no drivers, no faces in the windows. Deep one-point
> perspective down the street.

---

## 2. СТОЛ, ДВА ЯЩИКА И ГОРСТЬ МЕЛОЧЕЙ МЕЖДУ НИМИ — `stoicizm-dva-yaschika.png`

**Где стоит:** VO-12…VO-15 — «злиться вы не разучитесь», «стоики делили всё
надвое», «и работали только с первой половиной».

**Что доказывает.** Дихотомия контроля показана как ДЕЙСТВИЕ, а не как термин:
на столе разбор, вещи ещё не разложены. Персонаж будет стоять за столом и
водить руками над ящиками — правая ладонь над своим, левая над чужим.

**Почему два ящика, а не две двери и не развилка.** Двери и тропы означают
ВЫБОР пути; здесь выбора нет, здесь сортировка того, что уже свалилось на
стол. Разница смысловая, и картинка обязана её держать.

**Чего в кадре быть не должно.** Ярлыков, надписей, стрелок, знаков вопроса.
Никаких подсказок, что в какой ящик: это скажет голос.

> A plain wooden table seen straight on, standing alone in an empty room with a
> bare wall behind it. On the table two shallow open crates side by side with a
> clear gap between them: the LEFT crate holds a few small ordinary objects
> (a key, a folded note, a spoon), the RIGHT crate is completely empty. Between
> the two crates, on the bare table top, a small scattered handful of similar
> little objects not yet sorted. The table top is just above the waist height of
> an adult who would stand behind it; each crate is about a third as tall as the
> table is high. The floor in front of the table is empty and light, filling the
> lower quarter of the frame. No labels, no writing, no arrows, no symbols
> anywhere. No people. Calm, frontal, almost diagrammatic composition.

---

## После загрузки

Кладите оба файла в `examples/assets/sets/` под именами `stoicizm-probka.png` и
`stoicizm-dva-yaschika.png`. Дальше я:

1. прогоняю `tools/raster_set.py` — обрезка в 16:9, обёртка в SVG, снятие
   нарисованной рамки;
2. снимаю карту поверхностей (`back_y`, `chelovek`) и вписываю в
   `<сет>.surfaces.json`;
3. добавляю обе в `examples/assets/sets/KATALOG.md`;
4. собираю раскадровку и гоняю пятнадцать гейтов, включая `masshtab`.
