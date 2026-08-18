# Готовые видео

Ролики (MP4, 1280×720) и озвучка (MP3) **НЕ хранятся в git** — они заливаются в
**GitHub Releases** (иначе `videos/` и история репозитория пухли бы линейно по
числу прогонов CI). В репозитории — только исходники и манифест.

**Где скачать:** вкладка **Releases** репозитория → релиз с тегом
`renders-<ветка>` (напр. `renders-claude-…`). Каждый прогон CI обновляет этот
rolling-релиз свежими файлами (`*.mp4`, `*.mp3`, `*-final.mp4` со звуком).
Локально: `python3 tools/studio.py` кладёт результат в эту папку (git её игнорит).

## Как это работает — «завод»

Один оркестратор `tools/studio.py` по манифесту `tools/productions.json`
для каждого ролика делает всё сам: **картинки → рендер → озвучка → сведение**
и кладёт готовый MP4 со звуком сюда.

Workflow `.github/workflows/render.yml`:
- запускается на push в `main`/`master` **и в рабочие ветки `claude/**`**
  (и вручную: **Actions → Render Videos → Run workflow**);
- ставит ffmpeg, собирает движок, вызывает `python3 tools/studio.py --strict`
  и заливает результат (`*.mp4`, `*.mp3`) в GitHub Release `renders-<ветка>`.

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
| `osoznannost-intro.mp4` | `examples/lektorij/osoznannost-intro.anim` | Подводка к курсу «Осознанность»: телевизор, который никто не смотрит |
| `lazejka-intro.mp4` | `examples/lektorij/lazejka-intro.anim` | Подводка к курсу «Лазейка»: забор цел, а щель есть |
| `lazejka-chuzhoe-intro.mp4` | `examples/lektorij/lazejka-chuzhoe-intro.anim` | «Лазейка», угол читателя: шлагбаум, а ты пешком |
| `fredi-hudshij-sobesednik-1.mp4` | `examples/fredi/fredi-hudshij-sobesednik-1.anim` | Фреди, часть 1 — диагноз: худший собеседник это ты сам. Шесть локаций: спальня → переговорка → спальня → прихожая → офис → кухня |
| `fredi-hudshij-sobesednik-2.mp4` | `examples/fredi/fredi-hudshij-sobesednik-2.anim` | Фреди, часть 2 — что делать. Четыре локации: кухня (шов с частью 1) → спальня → поликлиника → спальня. Склеивается с частью 1 (`ffmpeg concat`), готовый файл 2:58 |
| `perehod-1.mp4` | `examples/perehod/perehod-1.anim` | «Переход», часть 1 — заход и механизм: гербарий, образцы под булавками. 1:15.1 |
| `perehod-2.mp4` | `examples/perehod/perehod-2.anim` | «Переход», часть 2 — выгорающий календарь, посадка на бите усталости, решётка из знаков вопроса. 1:15.3 |
| `perehod-3.mp4` | `examples/perehod/perehod-3.anim` | «Переход», часть 3 — интерфейс игры, «нужно 35, у вас 23», карта месяца, титр. 1:34.0. Склейка трёх частей — 4:04 |

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
