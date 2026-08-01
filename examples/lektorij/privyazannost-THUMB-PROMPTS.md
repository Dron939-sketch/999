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
NO logos, NO watermark` и требование оставить левую треть пустой. Скажи —
соберу пластину с текстом скриптом, шрифт и раскладка уже описаны ниже.

---

## ВАРИАНТ 1 (основной) — ДВА ПУСТЫХ СТУЛА

Тот же образ, которым ролик открывается и закрывается: двое, которых нет.
На обложке он работает как загадка — стулья стоят друг напротив друга, а
между ними никого, и зритель невольно достраивает, кто там должен сидеть.

**Промт целиком:**

> Cinematic YouTube thumbnail, 16:9 landscape, 1280x720. A dark empty room at
> night, deep black background. In the RIGHT HALF of the frame: two plain
> wooden chairs standing directly facing each other, empty, nobody sitting on
> them, a narrow gap of bare floor between them. Behind the chairs stands a
> tall motionless figure in a dark hooded cloak, face hidden by a smooth
> featureless glossy WHITE mask, the mask brightly lit and being the single
> brightest point of the whole image. Hard dramatic side lighting, strong red
> rim light along the edge of the hood and along the backs of both chairs,
> deep black shadows, very high contrast, saturated cinematic colour grade,
> slight cold blue haze in the air, shallow depth of field with the chairs in
> sharp focus. The ENTIRE LEFT THIRD of the image is empty flat darkness with
> no objects and no detail, reserved as clean space. Dramatic, unsettling,
> premium look. Photorealistic render, sharp, detailed, high production value.
> NO text, NO letters, NO words, NO captions, NO logos, NO watermark, NO
> signature, NO frame or border, NO people other than the masked figure, NO
> visible face or eyes.

**Надпись поверх** (левая треть, флаговый набор влево, три строки):

    ВЫ НЕ
    ВЛЮБЛЯЕТЕСЬ.        ← белым
    ВЫ УЗНАЁТЕ          ← красным (#e02020), на плашке

## ВАРИАНТ 2 — ЗАКАТАННЫЕ ГЛАЗА

Самый сильный факт ролика вынесен на обложку: убивает не измена, а презрение.
Работает на любопытстве — зритель не верит, что мелочь решает, и открывает
проверить.

**Промт целиком:**

> Cinematic YouTube thumbnail, 16:9 landscape, 1280x720. A cramped kitchen at
> night, deep black background, a single bare lamp hanging low over a small
> table. In the RIGHT HALF of the frame: the corner of a kitchen table set for
> two — two plates, two mugs, one chair pulled out and empty. Standing beside
> the table, a tall figure in a dark hooded cloak, face hidden by a smooth
> featureless glossy WHITE mask turned slightly away, the mask brightly lit and
> the single brightest point of the image. Harsh lamp light from above, strong
> red rim light along the hood and the table edge, everything else swallowed by
> black, extremely high contrast, saturated cinematic colour grade, cold blue
> shadows against the warm lamp. The ENTIRE LEFT THIRD of the image is empty
> flat darkness with no objects and no detail, reserved as clean space.
> Photorealistic render, sharp, detailed, tense and claustrophobic, high
> production value. NO text, NO letters, NO words, NO captions, NO logos, NO
> watermark, NO signature, NO frame or border, NO people other than the masked
> figure, NO visible face or eyes.

**Надпись поверх:**

    УБИВАЕТ
    НЕ ИЗМЕНА.          ← белым
    9 ИЗ 10             ← красным, крупнее всего

## ВАРИАНТ 3 — РАЗВИЛКА

Обещание выхода, а не диагноза: тип привязанности меняется. Ставить, если
первые два покажутся слишком мрачными для ленты.

**Промт целиком:**

> Cinematic YouTube thumbnail, 16:9 landscape, 1280x720. An open field at dusk
> under a heavy dark sky. In the RIGHT HALF of the frame: a dirt path forking
> into two — one deep old rutted track continuing straight ahead into the dark,
> one faint fresh trail branching to the right toward a brighter horizon. A
> tall figure in a dark hooded cloak stands exactly at the fork with its back
> to the split, face turned to the viewer, face hidden by a smooth featureless
> glossy WHITE mask, the mask brightly lit and the single brightest point of
> the image. Dramatic low sun, strong red rim light along the hood and along
> the ridge of both paths, deep black foreground shadows, extremely high
> contrast, saturated cinematic colour grade, wind in the dry grass. The
> ENTIRE LEFT THIRD of the image is empty flat darkness with no objects and no
> detail, reserved as clean space. Photorealistic render, sharp, detailed,
> epic, high production value. NO text, NO letters, NO words, NO captions, NO
> logos, NO watermark, NO signature, NO frame or border, NO people other than
> the masked figure, NO visible face or eyes.

**Надпись поверх:**

    ПРОТОПТАННАЯ
    НЕ ЗНАЧИТ          ← белым
    ЕДИНСТВЕННАЯ       ← красным

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
