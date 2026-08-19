# Обложка ролика «Привязанность и отношения» — промты

Референс студии: три ютуб-обложки (AI MOVIE / WEY 07 / бойцы). Что в них
общего и что отсюда взято:

- **ТЕКСТ ЗАНИМАЕТ ТРЕТЬ КАДРА И ЧИТАЕТСЯ С ТЕЛЕФОНА.** Не подпись под
  картинкой, а половина композиции. Крупно, в три-четыре строки, одно слово
  выделено цветом.
- **КАРТИНКА НЕ СПОРИТ С ТЕКСТОМ.** Слева текст — справа сюжет, и между ними
  пусто. В референсе с машиной левая треть просто залита чёрным.
- **СВЕТ РЕЗКИЙ, КОНТРАСТ ВЫКРУЧЕН.** Тёмный фон, светлый объект, обводка по
  силуэту. Обложка должна выживать в ленте размером с ноготь.
- **ОДИН АКЦЕНТНЫЙ ЦВЕТ.** Красный в двух референсах из трёх. Берём красный:
  он и так цвет серии.

## ГЛАВНОЕ ПРО ТЕКСТ — генератор его НЕ РИСУЕТ

Кириллицу генераторы пишут мусором: буквы похожи на русские, а слова
нечитаемы. Проверять это на обложке нельзя — она и есть текст. Поэтому:

1. генератор рисует ТОЛЬКО ПЛАСТИНУ — сюжет справа, пустое тёмное поле слева;
2. надпись ставится поверх отдельно (шрифтом), уже готовой.

Промты ниже это учитывают: в каждом стоит `NO text, NO letters, NO words,
NO logos, NO watermark` и требование оставить левую треть пустой. Надпись
кладёт `tools/thumb.py` — он же и проверяет, что она читается.

---

## РАЗБОР ПЕРВОЙ ПРИСЛАННОЙ ПЛАСТИНЫ

Пластина по варианту 1 пришла и по сути верна: левая половина пуста, маска —
самая светлая точка кадра, красный контровой лёг по капюшону и спинкам,
стулья стоят друг напротив друга и на них никто не сидит. Две вещи под
переделку, и обе меряются, а не обсуждаются.

**ФИГУРА СЛИШКОМ ДАЛЕКО.** Маска занимает около 5% высоты кадра. В ленте
обложка ужимается примерно до 320 px по ширине — маска превращается в белую
точку в девять пикселей. Во всех трёх присланных референсах лицо занимает
треть высоты и потому работает: обложку узнают по лицу, а не по мизансцене.
Камеру нужно подвести вплотную.

**КАДР КВАДРАТНЫЙ.** Просьба про 16:9 в промте была, генератор её проигнорировал.
`tools/thumb.py` квадрат вытянет — ищет светлое пятно и ставит окно 16:9 так,
чтобы сюжет уцелел, — но полоса из квадрата отрезает 44% высоты, и лучше не
доводить до кроп-лотереи. В промте v2 требование landscape продублировано
трижды и вынесено в первую фразу: это единственное, что на генераторы
действует.

Ещё одно, не про пластину: **стулья доходят до самого правого края**. Даже
после кропа им негде дышать, а обрезанный краем предмет читается как брак
съёмки. В v2 добавлен запас справа.

## ДЛИНА СТРОКИ — 7 ЗНАКОВ, И ЭТО ЗАМЕР

Кегль на обложке зажат длиной самой длинной строки: чем она длиннее, тем
мельче буквы. Порог читаемости — прописная не ниже 1/9 высоты кадра (80 px
при 720). Замер `tools/thumb.py` на нашей колонке даёт:

| знаков в строке | прописная | в ленте |
|-----------------|-----------|---------|
| 7 (`ЛЮБОВЬ.`)   | 82 px     | читается |
| 10 (`ЭТО ПАМЯТЬ`) | 61 px   | каша |
| 12 (`ВЛЮБЛЯЕТЕСЬ.`) | 38 px | не видно |

Отсюда исходный вариант надписи «ВЫ НЕ / ВЛЮБЛЯЕТЕСЬ. / ВЫ УЗНАЁТЕ» не
годится: он был написан на глаз и в ленте нечитаем. Русское слово длиннее
английского вдвое, и обложки вроде `I CREATED A HOLLYWOOD-STYLE AI MOVIE`
один в один не переносятся. Рабочая замена — та же мысль в семь знаков:

    ЭТО НЕ
    ЛЮБОВЬ.
    ПАМЯТЬ        ← красным

Тянуть колонку вместо того, чтобы резать текст, нельзя: колонка отъедает
место у сюжета, ради которого обложку и рисовали.

## Сборка

    python3 tools/thumb.py пластина.png обложка.png \
        --line "ЭТО НЕ" --line "ЛЮБОВЬ." --line "ПАМЯТЬ:red" --col 0.52

Инструмент приводит к 16:9 по сюжету, подкладывает скрим (глубина считается
из замера яркости под текстом, а не берётся на глаз), набирает Montserrat
ExtraBold и валит прогон по трём меркам: кегль, темнота фона, заход в правый
нижний угол — там ютуб рисует хронометраж. Рядом с обложкой кладётся
`*.lenta.png` 320 px — как её увидят на самом деле.

---

## ВАРИАНТ 1 (основной) — ДВА ПУСТЫХ СТУЛА

Тот же образ, которым ролик открывается и закрывается: двое, которых нет.
На обложке он работает как загадка — стулья стоят друг напротив друга, а
между ними никого, и зритель невольно достраивает, кто там должен сидеть.

**Промт целиком (v2 — камера вплотную, landscape продублирован):**

> WIDE 16:9 LANDSCAPE COMPOSITION, horizontal frame 1280x720 pixels, much
> wider than tall. Cinematic YouTube thumbnail. A dark room at night, deep
> black background. Medium close-up: the camera is CLOSE to the subject. In
> the RIGHT HALF of the frame, a tall figure in a dark hooded cloak stands
> facing the viewer, cropped at the waist, filling the full height of the
> frame; the face is hidden by a smooth featureless glossy WHITE mask, and the
> mask is LARGE — about one third of the frame height — brightly lit, the
> single brightest point of the whole image. In front of the figure, in the
> lower right corner, the tops of two plain wooden chair backs are visible,
> turned toward each other, empty, nobody sitting on them, with clear empty
> space between them and the right edge of the frame. Hard dramatic side
> lighting, strong red rim light along the edge of the hood and along the
> chair backs, deep black shadows, extremely high contrast, saturated
> cinematic colour grade, slight cold blue haze in the air. The ENTIRE LEFT
> HALF of the image is empty flat darkness with no objects and no detail,
> reserved as clean space. Dramatic, unsettling, premium look. Photorealistic
> render, sharp, detailed, high production value. Horizontal landscape aspect
> ratio 16:9, NOT square, NOT vertical. NO text, NO letters, NO words, NO
> captions, NO logos, NO watermark, NO signature, NO frame or border, NO
> people other than the masked figure, NO visible face or eyes.

**Надпись поверх** (левая колонка, флаговый набор влево, три строки):

    ЭТО НЕ
    ЛЮБОВЬ.             ← белым
    ПАМЯТЬ              ← красным (#e02020)

## ВАРИАНТ 2 — ЗАКАТАННЫЕ ГЛАЗА

Самый сильный факт ролика вынесен на обложку: убивает не измена, а презрение.
Работает на любопытстве — зритель не верит, что мелочь решает, и открывает
проверить.

**Промт целиком:**

> WIDE 16:9 LANDSCAPE COMPOSITION, horizontal frame 1280x720 pixels, much
> wider than tall. Cinematic YouTube thumbnail. A cramped kitchen at night,
> deep black background, a single bare lamp hanging low. Medium close-up: the
> camera is CLOSE to the subject. In the RIGHT HALF of the frame, a tall figure
> in a dark hooded cloak stands beside a kitchen table, cropped at the waist,
> filling the full height of the frame; the face is hidden by a smooth
> featureless glossy WHITE mask turned slightly away, and the mask is LARGE —
> about one third of the frame height — brightly lit, the single brightest
> point of the image. In the lower right corner, the near edge of the table set
> for two: two plates and two mugs, with clear empty space between them and the
> right edge of the frame. Harsh lamp light from above, strong red rim light
> along the hood and the table edge, everything else swallowed by black,
> extremely high contrast, saturated cinematic colour grade, cold blue shadows
> against the warm lamp. The ENTIRE LEFT HALF of the image is empty flat
> darkness with no objects and no detail, reserved as clean space.
> Photorealistic render, sharp, detailed, tense and claustrophobic, high
> production value. Horizontal landscape aspect ratio 16:9, NOT square, NOT
> vertical. NO text, NO letters, NO words, NO captions, NO logos, NO watermark,
> NO signature, NO frame or border, NO people other than the masked figure, NO
> visible face or eyes.

**Надпись поверх** (`--col 0.56`, две строки, кегль 84 px):

    УБИВАЮТ             ← белым
    ГЛАЗА               ← красным

Задуманное «УБИВАЕТ / НЕ ИЗМЕНА / 9 ИЗ 10» мерку не проходит — 66 px: строка
в девять знаков зажимает кегль. «Убивают глаза» говорит то же самое и
интригует сильнее, потому что не объясняет.

## ВАРИАНТ 3 — РАЗВИЛКА

Обещание выхода, а не диагноза: тип привязанности меняется. Ставить, если
первые два покажутся слишком мрачными для ленты.

**Промт целиком:**

> WIDE 16:9 LANDSCAPE COMPOSITION, horizontal frame 1280x720 pixels, much
> wider than tall. Cinematic YouTube thumbnail. An open field at dusk
> under a heavy dark sky. Medium close-up: the camera is CLOSE to the subject.
> In the RIGHT HALF of the frame, a tall figure in a dark hooded cloak stands
> facing the viewer, cropped at the waist, filling the full height of the
> frame; the face is hidden by a smooth featureless glossy WHITE mask, and the
> mask is LARGE — about one third of the frame height — brightly lit, the
> single brightest point of the image. Behind and below the figure, in the
> lower right corner, a dirt path forks into two — one deep old rutted track
> continuing straight ahead into the dark, one faint fresh trail branching to
> the right toward a brighter horizon, with clear empty space between the fork
> and the right edge of the frame. Dramatic low sun, strong red rim light along the hood and along
> the ridge of both paths, deep black foreground shadows, extremely high
> contrast, saturated cinematic colour grade, wind in the dry grass. The
> ENTIRE LEFT HALF of the image is empty flat darkness with no objects and no
> detail, reserved as clean space. Photorealistic render, sharp, detailed,
> epic, high production value. Horizontal landscape aspect ratio 16:9, NOT
> square, NOT vertical. NO text, NO letters, NO words, NO captions, NO
> logos, NO watermark, NO signature, NO frame or border, NO people other than
> the masked figure, NO visible face or eyes.

**Надпись поверх** (`--col 0.52`, две строки, кегль 85 px):

    ТРОПА               ← белым
    НЕ ОДНА             ← красным

«ПРОТОПТАННАЯ / НЕ ЗНАЧИТ / ЕДИНСТВЕННАЯ» — двенадцать знаков в строке,
38 px, в ленте не видно вовсе. Мысль та же, слов втрое меньше.

---

## Как ставить текст (если делать руками)

- **Кадр** 1280×720. Текстовый блок — левые 34% ширины, поля по 40 px.
- **Шрифт** тяжёлый гротеск с сильным контрастом веса: Montserrat ExtraBold,
  Bebas Neue, Oswald Bold. Всё капсом.
- **Кегль** ведущей строки — не меньше 1/6 высоты кадра (≈120 px). Проверка
  одна: уменьшить обложку до 320 px по ширине; если строка не читается —
  кегль мал, а не «зритель приглядится».
- **Обводка** 6–8 px чёрным по каждой строке плюс мягкая тень: текст должен
  держаться, даже если пластина под ним окажется светлее ожидаемого.
- **Акцент** — одна строка красным #e02020 или белым на красной плашке. Две
  красные строки убивают акцент.
- **Куда не залезать**: правый нижний угол — там ютуб рисует хронометраж.

## Чего на обложке НЕ делать

- Не ставить логотип «Лекторий» и адрес сайта: в ленте это нечитаемо и
  съедает место у текста, а ссылка и так в описании.
- Не тащить сюда стиль самого ролика (серая бумага, чёрные чернила). Ролик
  графичный, обложка — рекламная: у них разная работа. В ленте плоский серый
  кадр проигрывает соседям с контрастом.
- Не показывать лицо. Маска — весь смысл персонажа, а сгенерированное лицо
  под капюшоном ломает серию.
