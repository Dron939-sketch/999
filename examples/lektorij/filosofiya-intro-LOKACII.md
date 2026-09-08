# «Философия» — промты картинок к интро

Всё, что в ролике нарисовано, сейчас — ручная векторная графика по канону
`LOCATION_STYLE.md`. Она рабочая: геометрия точная, гейты зелёные, ролик
собран. Промты ниже — на случай, когда хочется поднять фон до уровня
генерированных локаций «Истории идей», и на то, чего в репозитории нет вовсе:
обложку для YouTube.

Разделы: локации (5), запасные подходы к двум ключевым (2), реквизит (1),
обложка и кей-арт (3), титр-карта (1). Всего двенадцать.

## Что генерируется, а что рисуется руками

Генератору отданы **четыре**: обложка (§9 — её в репозитории нет вовсе) и три
локации, где он даёт больше всего, — автомат (§1), голова (§4) и стол (§5).
Это хук, разворот и закрытие рифмы, то есть три кадра, которые зритель
запомнит.

Остальное остаётся ручной векторной графикой: очередь (§2), рупор (§3),
записка (§8) и титр-карта (§12). Причина не в экономии. **Записка обязана быть
одинаковой в пяти локациях**, а генератор такую сквозную деталь не держит: он
нарисует пять похожих бумажек, и рифма автомат ↔ стол развалится. Поэтому
записка рисуется руками, и под неё после генерации подгоняются те локации,
где она встречается, — включая сгенерированные.

Порядок работ такой: сначала приходят четыре картинки, потом записка на них
приводится к одному рисунку, и только затем прогон завода.

## Как это работает

1. Картинку генерирует пользователь по промту (Nano Banana / Flux) либо завод
   через `tools/image_gen.py -o <png> --prompt "..."` при ключе `IMAGE_API_KEY`.
2. `python3 tools/vectorize.py <png> examples/assets/sets/<имя>.svg`.
   Вектор обязателен: камера наезжает до 2.01×, растр на сверхкрупе плывёт.
   Инструмент сам меряет, обводить (`trace`) или вшивать растром (`embed`);
   рисованной туши он ставит обводку, фотографии — вставку.
3. Имя файла оставить прежним — сцена подхватит замену без правки сценария.

Генерировать лучше 1920×1080 и уменьшать до 1280×720: обводка по крупному
растру даёт чище контур.

## Три условия, без которых картинка не встанет в кадр

**Пол на y≈604** кадра 1280×720 (84% высоты). Туда встают ноги персонажа при
`place (x, 0.585) scales 0.80`. Выше — провалится в пол, ниже — повиснет, и
контактная тень ляжет в воздух.

**Место под фигуру свободно.** Персонаж стоит не по центру: автомат x≈0.36,
очередь x≈0.50, рупор x≈0.56, голова x≈0.34, стол x≈0.34. В этой трети кадра
не должно быть ничего, кроме пола.

**Крупные массы фона — не чёрные.** Персонаж сплошной чёрный; чёрная масса
рядом съедает его силуэт. В «Своём деле» пришлось перекрашивать большие
объёмы в средний тон с чёрным контуром — здесь просить сразу так: `dark grey
mass with a thick black outline, not solid black`. Исключение — голова из
сцены разворота: она чёрная намеренно, но фигура стоит перед светлым проёмом
и читается.

Четвёртое, не про геометрию: **записка одна и та же во всех кадрах.**
Квадратный листок со скруглёнными углами и одним завитком проходит через
четыре локации из пяти и на пятой лежит развёрнутым. Разъедется рисунок —
рифма перестанет читаться, и ролик развалится на пять несвязанных картинок.

## Общий стилевой суффикс (приписывать к каждому промту)

> hand-drawn 2D cartoon in the style of Mr. Freeman, thick wobbly hand-inked
> black outlines, flat light-gray paper background, stark high-contrast black
> and white, no gradients, no soft shading, flat fills only, three or four
> tonal planes separated by black contour, graphic and minimal, five strong
> black shapes rather than fifty small ones, no text or lettering anywhere,
> floor line at 84% of the image height, empty space left free for a
> character to stand in, 16:9

**Про «no text» отдельно.** Генераторы уродуют кириллицу: вместо «ЧЬЯ МЫСЛЬ?»
выходит похожая на русский бессмыслица, и это видно на обложке в первую
очередь. Все надписи ставит движок или редактор, из картинки текст просить
не надо — даже на обложке.

---

# Локации

## 1. `filo-avtomat.svg` — автомат готовых ответов

> a huge dark grey vending machine with a thick black outline filling the
> right third of an empty room, its glass front showing four shelves of
> identical small rolled-up paper notes in neat rows, a vertical column of six
> round buttons on the right side with the third button from the top larger
> and lit white, an empty pickup tray at the bottom; on the floor in front of
> the machine a heap of crumpled paper notes; one bare lamp on a cord throwing
> a hard-edged flat cone of light onto the empty floor, not onto the machine

Что читается: ответы покупают, а не думают; третья кнопка сверху.
Персонаж стоит слева от автомата (x≈0.36). Лоток обязан быть пустым: в него
на 12,4 секунде падает записка, и если там уже что-то лежит, выстрел ружья
пропадает.

## 2. `filo-ochered.svg` — очередь за ответом

> an empty street between blank windowless facades; a long queue of identical
> dark human silhouettes stretching from the center of the frame to the right
> edge and beyond, each one holding the same small rolled-up paper note raised
> above its head like a ticket; at the far left a small vending machine the
> queue is heading for, with three more silhouettes at its front seen from
> behind; a gap in the middle of the queue left free; nobody looks sideways

Что читается: «утро, работа, лента, так надо» — все стоят за одним и тем же.
Персонаж в разрыве очереди по центру, единственный лицом к нам. Силуэты
должны расти к правому краю: очередь уходит на зрителя, а не мимо него.

## 3. `filo-rupor.svg` — рупор на столбе

> a wide empty town square with a low blank parapet at the far edge; one tall
> black pole at the left third rising out of the frame, a big black
> loudspeaker horn mounted on it pointing down and right over the square,
> three thick curved arcs drawn in front of the horn widening outward; the
> ground scattered with identical small paper notes like fallen leaves; not a
> single person in the square

Что читается: кто сказал — кто-то; говорит давно, слушают все, никого нет.
Персонаж под рупором, чуть правее центра (x≈0.56). Дуги звука — рисованные
скобки, а не свечение: мягкий свет сразу выдаёт генератор.

## 4. `filo-golova.svg` — голова с дверцей

> a giant solid black profile of a human head filling the right half of an
> empty room, standing on the floor on its neck, facing right away from the
> viewer; in the back of the head a rectangular door flung wide open toward
> the viewer, and inside a bright storage closet with three shelves, each
> shelf holding a row of identical small rolled-up paper notes; the head casts
> one flat solid black shadow on the floor; nothing else in the room

Что читается: голова своя, внутри чужое; дверца открыта — заглянуть можно, и
это страшнее запертой. Персонаж перед дверцей, слева (x≈0.34). Проём внутри
обязан быть светлым: он единственное, что отделяет чёрную фигуру от чёрной
головы.

## 5. `filo-stol.svg` — чистый лист

> a plain wooden table in a bright empty room, on it one single paper note
> unrolled flat and completely blank, its edges still slightly curled from
> having been rolled, and one pencil lying diagonally beside it with its tip
> toward the note; a window with a hard-edged flat beam of daylight falling
> onto the table; nothing else — no shelves, no machine, no decoration

Что читается: та же бумажка, развёрнутая, — и на ней пусто; ответ пишете вы.
Персонаж слева от стола (x≈0.34), лицом к листу. Лист крупный: на общем плане
он должен читаться как чистый, а не как белое пятнышко.

---

# Запасные подходы к двум ключевым локациям

Автомат и голова несут хук и разворот. Если основной вариант выйдет мелким
или суетливым, вот другой заход к той же мысли — не украшение, а другая
метафора того же.

## 6. Автомат, вариант «раздатчик» (замена `filo-avtomat.svg`)

> a wall of two hundred identical small square mail slots covering the entire
> right two thirds of the frame from floor to ceiling, every slot holding the
> same rolled-up paper note sticking out halfway, one single slot at chest
> height empty and dark; a bare floor in front, a few crumpled notes near the
> wall; one bare lamp on a cord lighting the empty floor

Чем берёт: не «купи ответ», а «ответ уже выдан всем». Пустая ячейка на уровне
груди — место, откуда взяли его ответ. Годится, если автомат в кадре читается
как техника, а не как метафора.

## 7. Голова, вариант «стеллаж» (замена `filo-golova.svg`)

> a giant black head in profile filling the right half of the frame, but the
> whole back of the skull is missing, cut away like a doll's house, revealing
> five bright library shelves packed with identical rolled-up paper notes,
> each shelf with a small ladder leaning against it; the head stands on the
> floor on its neck; the room around is empty

Чем берёт: не дверца, а срез — библиотека вместо чулана, и лесенки говорят,
что туда ходили. Сильнее по мысли, слабее по страху: у распахнутой дверцы
есть тот, кто её открыл, у среза — нет.

---

# Реквизит

## 8. `zapiska.svg` — записка из автомата

> a single small square piece of paper with rounded corners, rolled up into a
> tight scroll seen from the side, one visible spiral curl in the middle,
> thick black ink outline, flat white fill, isolated on a plain neutral
> background for cutout, no shadow, no text

Это тот самый предмет, который проходит весь ролик. Просить его отдельно и
одинаковым во всех локациях: если генератор нарисует пять разных бумажек,
рифма автомат ↔ стол не сработает. Размер в кадре — около 30 пикселей на
1280: крупнее выглядит подушкой, что уже случалось на первом прогоне и было
исправлено масштабом 0.4.

---

# Обложка YouTube и кей-арт

Обложка — 1280×720, и её смотрят размером с ноготь. Значит: одна форма, одно
лицо, никакого мелкого сора. Текст ставится поверх в редакторе, не в
генераторе.

## 9. Обложка, вариант «рука тянется к кнопке»

> extreme close-up: a thin black cartoon hand reaching toward a single large
> white round button on a dark grey panel, the button lit and waiting; behind
> the hand, out of focus but flat and graphic, rows of identical rolled-up
> paper notes; the composition leaves the entire left third empty light grey
> for a title; bold ink outline, stark black and white, no text

Под название «Смысл жизни — третья кнопка сверху». Работает на ногте: рука,
кнопка, ряды. Место под текст слева оставлено промтом, а не обрезкой.

## 10. Обложка, вариант «голова изнутри»

> a giant black head in profile on light grey paper, a rectangular door in the
> back of the skull flung wide open, bright shelves of identical paper notes
> inside; a small black cartoon figure with a pale oval mask stands in front
> of the open door looking straight at the viewer, tiny beside the head;
> empty light space above for a title; flat fills, thick ink outline, no text

Под название «Вы живёте своей головой. А чья в ней мысль?». Самый сильный
кадр ролика — он же и лучшая обложка: контраст масштабов, и фигура смотрит в
зрителя.

## 11. Кей-арт курса: пять вопросов

> a single large ink-drawn question mark on light grey paper, and inside its
> curve, drawn as small flat black icons: an eye, a stone, a heart, two
> figures side by side, and a pair of scales; the shapes are simple and
> graphic, arranged along the stroke of the question mark; wide margins,
> poster-like, no text

Пять значков — пять вопросов курса: что я могу знать, что существует, как
жить хорошо, как жить вместе, как рассуждать. Годится на карточку курса на
сайте и на превью плейлиста. Значки не подписывать: подписи ставит вёрстка.

---

# Титр-карта

## 12. Финальная карточка (замена `lektorij-final.svg`)

> a dark empty stage with a small lectern in the center lit by one hard-edged
> flat cone of light from above, a black cartoon figure in a top hat standing
> behind it; wide empty dark space in the upper half of the frame for a title
> and in the lower half for a line of small print; heavy film grain feel,
> flat black shapes, no text

Общая для всего Лектория, менять только вместе со всеми роликами: карточка
узнаётся зрителем и работает как подпись студии.

---

## Проверка после замены

```bash
./target/release/animdsl check examples/lektorij/filosofiya-intro.anim
python3 tools/studio.py filosofiya-intro --strict
```

Плюс глазами один кадр из каждой сцены: ноги на полу, тень на полу, фигура не
слилась с фоном, записка одна и та же. Приёмщик локаций (`studio.lint_location`)
ловит только надписи и их вылет за кадр — слияние силуэта с фоном не ловит
никто, это на человеке.
