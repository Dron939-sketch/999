# Промты для локаций — ролики про Фреди

Ролики про приложение (не Лекторий) живут в `examples/fredi/`. Локации здесь
не «пустое поле», а бытовые интерьеры: зритель должен узнать свою комнату.

## Общий стилевой суффикс

> in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> thick wobbly hand-inked outline, flat fills only (NO gradients, NO soft
> light, NO shading), stark high-contrast black and white, black ink
> (#141410) only, NO colour at all; graphic and illustrative, NOT
> photorealistic; slightly rough, redrawn-by-hand feel; minimal detail.

## 1. СПАЛЬНЯ В ТРИ ЧАСА НОЧИ (`sets/fredi-spalnya.png`)

Файл: **16:9**, 1920×1080 или 2560×1440, непрозрачный PNG.

> A small ordinary bedroom at three in the morning, seen straight on from the
> side of the room. On the RIGHT stands a low simple bed, seen from its side:
> the top of the mattress sits at about three quarters of the image height, the
> blanket is thrown back and rumpled. The bed is COMPLETELY EMPTY — no person
> in it, nobody in the room, the frame is empty of people. On the LEFT there is
> open empty floor and a bare wall. A window on the left wall is uncovered, and
> through it the streetlight throws ONE hard-edged pale rectangle of light onto
> the left wall and the floor below it — a clean light patch, flat, with sharp
> straight edges and no glow. Walls, ceiling and floor are MID-GREY, not black:
> only the far corners and the space under the bed go to solid black. The
> ceiling is visible along the top of the frame. Nothing else: no lamp on, no
> clutter, no pictures, no plants, no phone, no clock. [+ стилевой суффикс]

**Негативный промт:**

> person, people, man, woman, figure, silhouette in bed, sleeping person, text,
> letters, watermark, colour, red, blue, warm light, glow, bloom, gradients,
> soft shadows, photorealism, 3D render, clutter, plants, posters, lamps on

### Что критично и почему

| требование | зачем |
|---|---|
| **кровать ПУСТАЯ** | лежащего рисует движок (второй персонаж в позе `lezhit`). Нарисованный человек даст двух людей в кадре |
| **верх матраса на ~3/4 высоты** | по этой линии сажается лежащая фигура. Выше — она повиснет над кроватью, ниже — утонет в ней |
| **стены СРЕДНЕ-СЕРЫЕ, чёрное только в углах** | персонажи — сплошные чёрные силуэты. На тёмной комнате они исчезнут; светлые плоскости — единственное, на чём они читаются |
| **светлое пятно от фонаря СЛЕВА** | на нём стоит и говорит Фреди. Это его «сцена»: жесты и мимика видны только на светлом |
| **свет плоский, с жёсткой кромкой** | по LOCATION_STYLE.md §7: луч — один флэт-полигон, а не свечение. Мягкий свет читается как «фото» и спорит с тушью |
| **потолок в кадре** | лежащий смотрит в потолок — если его не видно, взгляд героя упирается в пустоту |
| **без цвета** | ролик монохромный; цветной акцент уйдёт в серый, но на превью будет спорить с тушью |

### Куда класть

`examples/assets/sets/fredi-spalnya.png` → оборачиваю в SVG-сет тем же именем
`.svg` (сценарий уже ссылается на него, менять ничего не придётся).

---

# Смена локаций: 7 наборов вместо одного

Ролик идёт 2:46 в одной комнате — глаз устаёт раньше, чем кончается монолог.
Разбиваем на планы по 11–27 секунд, каждый в своей локации.

**Жёсткое ограничение:** лежащий (`sleeper`) привязан к кровати. Значит любой
план, где он в кадре, — только спальня. Спальня и остаётся домом ролика:
из неё уходят и в неё возвращаются. Остальные локации — вылазки, там Фреди
один.

Уходы мотивированы текстом, а не «чтобы мелькало»:

| план | тайм (часть) | реплики | локация | почему туда |
|---|---|---|---|---|
| 1 | 0:00–0:26.6 ч.1 | VO-1…VO-6 | **спальня** (есть) | лежащий в кадре, «смотри, как он работает» |
| 2 | 0:26.6–0:38.3 ч.1 | VO-7, VO-8 | **переговорка** | тот самый «разговор, который был во вторник» — уходим туда, где он был |
| 3 | 0:38.3–0:48.9 ч.1 | VO-9, VO-10 | **спальня** | круг замкнулся, крупные планы лежащего |
| 4 | 0:49.3–1:06.8 ч.1 | VO-11…VO-13 | **приёмная психолога** | «к психологу? дорого, страшно» — стоим ровно в том месте, куда он не пошёл |
| 5 | 1:07.6–1:22.3 ч.1 | VO-14, VO-15 | **офис ночью** | «каждому что-то изображал: начальнику — рвение, коллегам — что всё под контролем» |
| 6 | 1:24.0–1:32.6 ч.1 | VO-16, VO-17 | **прихожая** | «живым нельзя иначе» — место, где лицо снимают вместе с пальто |
| 7 | 1:33.3–1:44.7 ч.1 | VO-18, VO-19 | **ночная кухня** | «первый честный разговор за день» — где такие и случаются |
| 8 | 0:00–0:15.9 ч.2 | VO-1, VO-2 | **ночная кухня** | шов частей проходит внутри локации: зритель его не заметит |
| 9 | 0:17.2–0:23.7 ч.2 | VO-3 | **спальня** | «в три часа ночи он не спит» — лежащий всё ещё там |
| 10 | 0:25.0–0:42.7 ч.2 | VO-4, VO-5 | **коридор поликлиники** | бит ПРЕДЕЛ: живой врач. Единственное место без иронии — и локация должна быть буквальной |
| 11 | 0:42.7–0:50.9 ч.2 | VO-6…VO-8 | **спальня** | жало там же, где начали. «Пип.» в темноту |

Нужно **6 новых картинок**. Спальня уже лежит.

## Что общего у всех шести

Требования не стилистические, а техническо-обязательные — каждое куплено
пересъёмкой:

1. **16:9**, 1920×1080 или 2560×1440, непрозрачный PNG, **без рамки и полей**
   (картинка идёт в кадр целиком, белая «бумажная» окантовка вылезет).
2. **Плоскости средне-серые, не чёрные.** Оба персонажа — сплошные чёрные
   силуэты. На тёмной локации они исчезают. Чёрное — только контур, мебель и
   углы.
3. **Одно светлое пятно с жёсткой кромкой в левой нижней трети** — там стоит
   и говорит Фреди. Это его сцена: жест и мимика видны только на светлом.
   Пятно плоское, без свечения и растушёвки (LOCATION_STYLE.md §7).
4. **Пол в левой трети свободен** — никакой мебели, куда встанет фигура.
5. **Ни одного человека.** Люди в кадре — только нарисованные движком.
6. **Ни одной надписи.** Таблички, вывески, бумаги — пустые: любой текст
   на генерации выходит бессмысленной кашей и читается как брак.
7. **Без цвета.** Ролик монохромный, цветное пятно уйдёт в серый, но на
   превью будет спорить с тушью.

## Общий стилевой суффикс (дописывать к каждому промту)

> in the style of the animated series "Mr. Freeman": hand-drawn black ink,
> thick wobbly hand-inked outline, flat fills only (NO gradients, NO soft
> light, NO shading), stark high-contrast black and white, black ink
> (#141410) on mid-grey planes, NO colour at all; graphic and illustrative,
> NOT photorealistic; slightly rough, redrawn-by-hand feel; minimal detail;
> full-bleed composition, no border, no frame, no margin.

## Общий негативный промт

> person, people, man, woman, figure, silhouette, crowd, text, letters,
> words, signage, watermark, signature, colour, red, blue, warm light, glow,
> bloom, gradients, soft shadows, photorealism, 3D render, clutter, plants,
> posters, border, frame, white margin, vignette

---

## 2. ПЕРЕГОВОРКА ВО ВТОРНИК (`sets/fredi-peregovorka.png`)

> A small bare meeting room at night, seen straight on from the end of the
> room. Across the middle of the frame stands a long plain table with plain
> chairs around it. ONE chair on the far side is pushed back and turned away
> at an angle, as if the person who sat there got up and left. The room is
> COMPLETELY EMPTY — no people anywhere. A blank whiteboard on the far wall
> with nothing written on it. A plain round clock high on the wall with no
> numbers. Walls, floor and ceiling are MID-GREY, not black: only the table
> top, the chairs and the outlines are solid black. In the LEFT THIRD of the
> frame the floor is completely clear and empty, and a tall window on the
> left throws ONE hard-edged pale rectangle of light onto that empty floor —
> flat, with sharp straight edges, no glow. [+ стилевой суффикс]

Зачем именно так: пустой стул, отвёрнутый в сторону, — вещдок разговора,
который кончился. Зритель не должен думать «это совещание», он должен думать
«здесь во вторник что-то сказали».

## 3. ПРИЁМНАЯ ПСИХОЛОГА (`sets/fredi-priemnaya.png`)

> A bare waiting room seen straight on. Against the far wall a closed plain
> door with a small blank plaque beside it — the plaque is EMPTY, no writing.
> To the right of the door two plain chairs stand against the wall, both
> empty. A bare coat stand with nothing on it. A low table with nothing on
> it. The room is COMPLETELY EMPTY — no people. Walls, floor and ceiling are
> MID-GREY, not black; only the door frame, the chairs and the outlines are
> solid black. The LEFT THIRD of the floor is completely clear and empty, and
> ONE hard-edged pale rectangle of light falls onto it from a window out of
> frame — flat, sharp edges, no glow. Cold, plain, institutional, nothing
> comforting. [+ стилевой суффикс]

Зачем: на этом бите Фреди передразнивает — «дорого, страшно». Комната должна
быть настолько безобидной, чтобы отговорка выглядела смешной.

## 4. ОФИС НОЧЬЮ (`sets/fredi-ofis.png`)

> An open-plan office at night, seen straight on. Three or four plain desks
> in a row across the frame, each with a dark switched-off monitor. Swivel
> chairs pushed in at careless angles. The room is COMPLETELY EMPTY — no
> people. A closed glass partition behind the desks. Walls, floor and ceiling
> are MID-GREY, not black; only the monitors, the chair bases and the
> outlines are solid black. In the LEFT THIRD the floor is completely clear
> and empty, and ONE hard-edged pale rectangle of light falls onto it from a
> window out of frame — flat, sharp edges, no glow. No papers, no mugs, no
> cables, no plants. [+ стилевой суффикс]

Зачем: реплика перечисляет, кому он что изображал днём. Локация — сцена, где
это игралось, и её пустота говорит, что представление кончилось.

## 5. ПРИХОЖАЯ (`sets/fredi-prihozhaya.png`)

> A narrow apartment hallway seen straight on. At the far end a closed front
> door with a plain handle and a lock. On the right wall a coat hook with ONE
> coat hanging on it. A pair of shoes on the floor by the door. The hallway
> is COMPLETELY EMPTY — no people. Walls, floor and ceiling are MID-GREY, not
> black; only the door frame, the coat and the outlines are solid black. A
> thin hard-edged pale strip of light lies on the floor under the front door,
> and ONE hard-edged pale rectangle falls on the floor in the LEFT THIRD from
> a doorway out of frame — both flat, sharp edges, no glow. The left third of
> the floor is clear and empty. Nothing else: no mirror, no shelf, no bags.
> [+ стилевой суффикс]

Зачем: «живым нельзя иначе — они запомнят, обидятся». Прихожая — граница между
двумя лицами: одно осталось на лестнице, другое ещё не надето.

## 6. НОЧНАЯ КУХНЯ (`sets/fredi-kuhnya.png`)

> A small ordinary kitchen at night, seen straight on. On the right a plain
> table with ONE mug on it and one chair pulled out. A single lamp hangs low
> over the table and throws ONE hard-edged pale trapezoid of light onto the
> table top and the floor beneath it — flat, sharp straight edges, no glow,
> no bloom. Behind, a plain counter with a sink, cupboards with plain doors.
> The room is COMPLETELY EMPTY — no people. Walls, floor and cupboards are
> MID-GREY, not black — the room away from the lamp stays clearly readable
> grey, NOT plunged into darkness; only the outlines, the chair and the lamp
> are solid black. The LEFT THIRD of the floor is clear and empty, with a
> second hard-edged pale rectangle of light on it. No clutter, no bottles, no
> magnets, no notes. [+ стилевой суффикс]

Зачем: на этой кухне «первый честный разговор за день» и звучит. И через неё
проходит шов между частями — локация обязана быть одна и та же в конце первой
и в начале второй.

Отдельно: **тёмная кухня не подойдёт.** Генерации обычно заливают всё вокруг
лампы чёрным — на такой кухне оба персонажа пропадут. Комната должна остаться
серой, лампа даёт не единственный свет, а самое яркое пятно.

## 7. КОРИДОР ПОЛИКЛИНИКИ (`sets/fredi-poliklinika.png`)

> A plain clinic corridor seen straight on. A row of empty chairs along the
> right wall. At the far end a closed door with a frosted glass panel, lit
> from behind. A hard bare floor. The corridor is COMPLETELY EMPTY — no
> people. No signs, no numbers, no writing anywhere — any plaque is BLANK.
> Walls, floor and ceiling are MID-GREY, not black; only the chairs, the door
> frame and the outlines are solid black. The frosted panel throws ONE
> hard-edged pale rectangle of light onto the floor in front of the door, and
> a second hard-edged pale rectangle lies in the LEFT THIRD, where the floor
> is completely clear and empty — both flat, sharp edges, no glow. Cold,
> plain, ordinary — a real clinic, not a hospital drama. [+ стилевой суффикс]

Зачем: бит ПРЕДЕЛ — единственный в ролике, где нет иронии. Метафора здесь
навредит: сказано «к живому врачу, сегодня», и в кадре должна быть дверь,
в которую входят.

---

## Что в итоге собрано

Пять наборов пришли и легли в `examples/assets/sets/` (кроп до 16:9, серая
шкала, 1376×768, обёртка SVG с запасом 10%):

| файл | сцена |
|---|---|
| `fredi-peregovorka.png` | ч.1 VO-7, VO-8 |
| `fredi-prihozhaya.png` | ч.1 VO-11…VO-13 |
| `fredi-ofis.png` | ч.1 VO-14…VO-17 |
| `fredi-kuhnya.png` | ч.1 VO-18, VO-19 и ч.2 VO-1, VO-2 |
| `fredi-poliklinika.png` | ч.2 VO-4, VO-5 |

**Приёмной психолога в наборе не оказалось,** и отдельная локация под неё в
итоге не понадобилась: бит «К психологу? Дорого. Страшно» переехал в
прихожую — стоять у закрытой входной двери, из которой так и не вышел,
для этой реплики точнее, чем стоять уже внутри приёмной. Освободившийся
кусок «живым нельзя иначе» присоединён к офисному плану. Планов стало
десять вместо одиннадцати, самый длинный — 25 секунд.

Кропы: квадратные генерации 1024×1024 срезаны так, чтобы в кадре остались
светлое пятно на полу слева и линия пола под фигурой. У переговорки срезаны
настенные часы (в кадр 16:9 они попадали половиной), у прихожей — потолок.

## Что уже лежит в репозитории

В корне репозитория есть подходящие по стилю генерации с прошлых заходов:

| файл | под какую локацию | вердикт |
|---|---|---|
| `NanoBanana_a-small-bare-meeting-room-seen-straight-on_-in-the-middle-a-.png` | переговорка (2) | **композиция готовая:** 16:9, во всё поле, стены средне-серые, линия та самая, людей и надписей нет. Два минуса — 688×384 (движок рисует 1280×720, апскейл в 1.9 раза даст мыло) и нет светлого пятна слева. Перегенерить тем же промтом в 1920×1080 |
| `NanoBanana_a-narrow-apartment-hallway-seen-straight-on_-a-closed-front-.png` | прихожая (5) | стиль и тон в точку, но **1:1 и в белой рамке**. Кадрирование в 16:9 съест низ, а низ несущий — там пол под фигурой. Перегенерить |
| `NanoBanana_a-bare-room-with-two-plain-wooden-chairs-facing-each-other-a.png` | приёмная (3) | **не годится:** мягкая карандашная линия вместо туши, цветное дерево, стены почти белые. Чужой стиль, в монтаже будет виден |
| `NanoBanana_a-dark-night-kitchen-seen-head-on_-all-lights-off-except-one.png` | ночная кухня (6) | **не годится:** комната залита чёрным, чёрные силуэты в ней пропадут |

Если проще перегенерить в 16:9 без рамки — перегенерить: кадрирование квадрата
съедает верх и низ, а низ здесь несущий (там пол, на котором стоит фигура).

## Куда класть

`examples/assets/sets/<имя>.png`. SVG-обёртку с полями делаю я, сценарии
переписываю на сцены сам — от вас только PNG.
