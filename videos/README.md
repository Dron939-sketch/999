# Готовые видео

Сюда CI автоматически складывает отрендеренные ролики (MP4, 1280×720, немые —
озвучка накладывается отдельно по сценариям из `examples/lektorij/*-VO.md`).

**Скачать:** открой файл на GitHub → кнопка **Download raw file** (справа сверху).

## Как это работает — «завод»

Один оркестратор `tools/studio.py` по манифесту `tools/productions.json`
для каждого ролика делает всё сам: **картинки → рендер → озвучка → сведение**
и кладёт готовый MP4 со звуком сюда.

Workflow `.github/workflows/render.yml`:
- запускается на push в `main`/`master` **и в рабочие ветки `claude/**`**
  (и вручную: **Actions → Render Videos → Run workflow**);
- ставит ffmpeg, собирает движок, вызывает `python3 tools/studio.py`
  и коммитит результат (`*.mp4`, `*.mp3`) в эту папку.

Любой шаг без ключа/инструмента пропускается с понятным логом — конвейер
всегда отдаёт хотя бы немой рендер. Локально: `python3 tools/studio.py`
(нужен ffmpeg для звука; без него — только немые mp4).

Добавить ролик в завод — дописать объект в `productions` внутри
`tools/productions.json` (id, anim, vo, title, images).

## Ролики

| Файл | Источник | Что это |
|------|----------|---------|
| `pereproshivka-intro.mp4` | `examples/lektorij/pereproshivka-intro.anim` | Подводка к курсу «Перепрошивка»: камера-хук, книга, оживающая картинка |
| `freeman-monologue.mp4` | `examples/freeman-monologue.anim` | Мистер Фримен: монолог в камеру (витрина стиля) |
| `fredi-expressions.mp4` | `examples/lektorij/fredi-expressions-demo.anim` | Фреди: библиотека мимики |
| `lekciya-2-frejd.mp4` | `examples/lektorij/lekciya-2-frejd-psihodinamika.anim` | Пилот лекции (Фрейд, курс «Теории личности») |

Добавить ролик в конвейер — дописать строку в список `RENDERS` в
`.github/workflows/render.yml`.

## Озвучка (Fish Audio) — приходит в эту же папку

Если в секретах репозитория задан ключ Fish Audio, CI после рендера сам:
1. генерит голос по VO-сценарию (`tools/voiceover.py`): каждая реплика
   ставится на свой таймкод, между ними тишина → `<имя>-voice.mp3`;
2. склеивает дубль с видео (`tools/compose_video.sh`) → `<имя>-final.mp4`.

Озвучка идёт **через Frederick** (источник правды): его сервер синтезирует
голосом Фреди (Fish) и кэширует mp3 у себя — **ключ Fish не хранится в этом
репо**. Заводу нужен только общий токен.

**Настройка (один раз):** Settings → Secrets and variables → Actions.
Секреты хранятся ТОЛЬКО здесь — никогда в коде/чате:

| Секрет | Для чего | Обяз. |
|--------|----------|:-----:|
| `FREDERICK_ADMIN_TOKEN` | доступ к видео-озвучке Frederick (тот же `ADMIN_TOKEN`, что в Frederick) | да, для звука |
| `FREDERICK_TTS_URL`     | база Frederick (по умолч. `https://ffred-ddd989.amvera.io`) | опц. |
| `IMAGE_API_KEY`         | генерация картинок (Nano Banana / провайдер) | опц. |
| `IMAGE_API_PROVIDER`    | `gemini` (по умолч.) или `openai` | опц. |
| `FISH_AUDIO_API_KEY` / `FISH_AUDIO_VOICE_ID` | запасной путь: синтез Fish напрямую в заводе (если не через Frederick) | опц. |

> В Frederick для этого должен быть задан `ADMIN_TOKEN` (и уже настроен Fish:
> `FISH_AUDIO_API_KEY`/`FISH_AUDIO_VOICE_ID`). Эндпоинт: `POST /api/tts/video/say`.

Как только ключи заданы — при следующем push в ветку завод сам озвучит и
сведёт финальные ролики. Генерация картинок (`tools/image_gen.py`): пишу
текстовый промт в стиле Фримена → PNG → оборачивается в SVG-сет и попадает
в сцену как фон/слой (правок движка не нужно, resvg рендерит `<image>`).

| Файл | Что это |
|------|---------|
| `pereproshivka-intro-voice.mp3` | Дубль озвучки подводки (реплики по таймкодам) |
| `pereproshivka-intro-final.mp4` | Видео + голос, готовый ролик (без SFX) |

SFX (капля, лязг и т.п.) добавляются в редакторе по таблице из
`examples/lektorij/pereproshivka-intro-VO.md`.
