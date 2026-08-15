# Промты локаций — «Управление людьми», ролик номер 24

Курс: https://meysternlp.ru/blog/lektorij/upravlenie-lyudmi/ — десять лекций о
переходе от работы своими руками к работе через других.

**Новых картинок ДВЕ.** Третья и четвёртая локации ролика берутся как есть:
`pustota-bumaga` (кадр без комнаты, если понадобится разворот вне помещения) и
`lektorij-zal` (презентация курса звучит в другом месте — это не его комната).

---

## ЗРИТЕЛЬ, ПОД КОТОРОГО РИСУЮТСЯ ЛОКАЦИИ

Курс сам называет своего человека в первой же строке первой лекции:

> «Лучшего мастера делают начальником — и через полгода он сидит до одиннадцати
> вечера, переделывая чужую работу. Это не невезение с людьми. Это смена
> профессии, о которой человеку забыли сообщить.»

**ЦА: вчерашний лучший специалист, которого повысили полгода назад.** Он до сих
пор считает себя мастером и гордится этим. Он остаётся после всех, потому что
«объяснять дольше, чем сделать самому», и считает это временным — пока команда
не подтянется. Никого ещё не увольнял, задачу ставит на бегу, обратную связь
откладывает. Слово «управление» к себе не относит: он не управляет, он «тянет».

**Чего в этом определении нет намеренно.** Отрасли, возраста, размера компании.
Мастер цеха, тимлид и шеф-повар в этой точке неразличимы: их объединяет не
работа, а ЧАС и ПОСТУПОК — одиннадцать вечера и чужая работа, которую он
переделывает.

**Отсюда узнавание.** «Офис» вообще — это ничей кадр, как «кухня» вообще.
Отсекает не помещение, а время суток и состояние: пустой офис в одиннадцать
вечера, где темно везде, кроме одного стола. Тот, кто уходит в шесть, такого
кадра не видел ни разу. Тот, для кого курс, узнаёт его мгновенно — и узнаёт не
офис, а себя в нём.

**Несущий тезис курса, из которого растёт весь ролик:** повышение — не награда
за прежнюю работу, а смена профессии. Инструмент сменился: раньше руки, теперь
чужие руки. Круг «проще сделать самому» — механизм, который держит человека в
прежней профессии и выглядит как трудолюбие.

---

## ГЛАВНОЕ: ЕДИНИЦА МАСШТАБА (реестр §XXVII)

> ### 1 метр = 26% высоты кадра.
> При 1280×720 — 187 пикселей на метр. Стоящий взрослый занимает 44% кадра.

| предмет | реальная высота | доля кадра | px при 720 |
|---|---|---|---|
| столешница письменного стола | 0,74 м | 19% | 139 |
| спинка офисного стула | 1,15 м | 30% | 216 |
| монитор на столе (верх) | 1,20 м | 31% | 225 |
| дверной проём | 2,05 м | 53% | 384 |

**НО КАДР БЕРЁТСЯ БЛИЖЕ ОБЫЧНОГО.** По §XL реестра локация, в которой стоящий
взрослый занимает меньше половины кадра, для говорящей сцены не годится: гейт
масштаба требует человеческого роста, а гейт готового файла — фигуры не мельче
35% кадра, и в просторном помещении эти требования не пересекаются. Поэтому
офис рисуется НЕ ПАНОРАМОЙ: три-четыре стола, а не тридцать, и камера стоит
близко. Ориентир — стоящий человек занял бы примерно 60% высоты кадра.

**ЧИСЛА В КАРТИНКЕ НЕ РИСУЮТСЯ** (реестр §XXX). Генератор однажды принял
проценты за часть композиции и написал «78%» тушью на стене. Масштаб задан
отношениями предметов, проценты — только в служебных скобках.

**Каждый промт ниже самодостаточен**: стиль вшит внутрь, копируется целиком.
Отдельного суффикса «добавлять к каждому» больше нет — промт, который надо
собирать из двух кусков, копируют одним куском, и картинка приезжает цветной.

---

## 1. ОФИС В ОДИННАДЦАТЬ ВЕЧЕРА — `nachalnik-ofis-noch.png`

**Где стоит:** первая сцена ролика и финал — кольцо замыкается здесь же.
**Это главная картинка**, её зритель обязан узнать раньше первого слова.

**Что доказывает.** Что это он и есть: все ушли, а он остался. Час и одинокая
лампа делают кадр его — не «офисом», а тем самым вечером, который он считает
временным уже полгода.

**Промт:**

> A small open-plan office at night, seen straight on. Three or four plain desks
> in a row, all of them empty and dark, chairs pushed in, monitors switched off
> and black. On ONE desk in the centre a desk lamp is switched on, throwing a
> plain pool of light onto the desktop; on that lit desk two separate stacks of
> paper sit side by side, one noticeably taller than the other. Behind the desks
> a plain wall with a large dark window; outside it is night, the window is a
> solid black rectangle. The room is small and close — only three or four desks,
> camera near, not a wide panorama of a hundred workplaces. The bottom sixth of
> the frame is EMPTY FLOOR, clear of furniture, so a character can stand on it
> and cast a shadow. Drawn in the style of the animated series "Mr. Freeman":
> hand-drawn black ink, BOLD heavy boiling outline, thick confident strokes,
> flat fills only (NO gradients, NO soft light, NO shading), extremely high
> contrast, STRICTLY BLACK AND WHITE — monochrome only, limited palette of light
> grey paper (#d4d7cf) and black ink (#141410), NO COLOUR anywhere in the image,
> not a single coloured object; graphic / illustrative, NOT photorealistic;
> slightly rough, redrawn-by-hand feel; minimal detail, few strong shapes; NO
> people, NO figures, NO text, NO letters, NO numbers, NO logos; the drawing
> FILLS the whole canvas edge to edge, wide 16:9 landscape, NO borders, NO frame,
> NO margins, NOT square.

**Чего в кадре быть не должно.** Людей и силуэтов. Часов на стене — время
сказано темнотой за окном и одной лампой, а нарисованный циферблат объяснит
кадр буквально и убьёт узнавание. Открытых ноутбуков со светящимися экранами:
светится ровно одна лампа, остальное темно. Никаких табличек, надписей и
логотипов.

**Две стопки — не украшение.** Это его работа и чужая работа, которую он
переделывает; на них потом ляжет разрыв. Они должны быть отчётливо видны и
стоять рядом, чтобы читались как пара.

---

## 2. СТОЛ НА ДВОИХ — `nachalnik-stol-na-dvoih.png`

**Где стоит:** середина ролика — там, где называется новая профессия. Место, в
котором теперь делается его работа: не за станком, а напротив человека.

**Что доказывает.** Что инструмент сменился. Два стула друг напротив друга —
это всё, чем он теперь работает; на прошлой работе такого места у него не было
вовсе, и потому кадр читается как чужой, пока не поймёшь, что он твой.

**Промт:**

> A small bare meeting room seen straight on. In the middle a plain rectangular
> table with exactly TWO chairs, one on each side, facing each other across the
> table. The table top is completely empty — nothing on it at all. Plain walls,
> one closed door on the right, no window. The room is small and close, the
> table nearly fills the width of the frame; camera near, not a wide panorama.
> The bottom sixth of the frame is EMPTY FLOOR, clear of furniture, so a
> character can stand on it and cast a shadow. Drawn in the style of the animated
> series "Mr. Freeman": hand-drawn black ink, BOLD heavy boiling outline, thick
> confident strokes, flat fills only (NO gradients, NO soft light, NO shading),
> extremely high contrast, STRICTLY BLACK AND WHITE — monochrome only, limited
> palette of light grey paper (#d4d7cf) and black ink (#141410), NO COLOUR
> anywhere in the image, not a single coloured object; graphic / illustrative,
> NOT photorealistic; slightly rough, redrawn-by-hand feel; minimal detail, few
> strong shapes; NO people, NO figures, NO text, NO letters, NO numbers, NO
> logos; the drawing FILLS the whole canvas edge to edge, wide 16:9 landscape,
> NO borders, NO frame, NO margins, NOT square.

**Чего в кадре быть не должно.** Третьего стула — их ровно два, и это весь
смысл кадра. Проектора, доски, флипчарта: это не совещание, это разговор. Ничего
на столе — пустая столешница здесь работает как пауза.

---

## ЧТО Я ДЕЛАЮ, КОГДА КАРТИНКИ ПРИДУТ

1. Кладу `.png` в `examples/assets/sets/` (если кадр придёт квадратным — обрежу
   до 16:9 и запишу это в комментарий сета).
2. Оборачиваю в `.svg` c base64 внутри — так лежат все сеты серии.
3. Снимаю меру человека в `<сет>.surfaces.json` по столу или спинке стула и
   сверяю `tools/masshtab.py`. Ниже 0.5 — попрошу кадр теснее (реестр §XL), и
   скажу об этом сразу, а не после сборки.
4. Ставлю линию пола `floor.back_y`, собираю контактный лист и смотрю глазами.
5. Только после этого пишу монолог: локация под зрителя определена, значит есть
   на что ставить разрыв.
