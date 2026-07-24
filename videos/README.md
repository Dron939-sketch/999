# Готовые видео

Сюда CI автоматически складывает отрендеренные ролики (MP4, 1280×720, немые —
озвучка накладывается отдельно по сценариям из `examples/lektorij/*-VO.md`).

**Скачать:** открой файл на GitHub → кнопка **Download raw file** (справа сверху).

## Как это работает

Workflow `.github/workflows/render.yml`:
- запускается на каждый push в `main` (и вручную: вкладка **Actions → Render
  Videos → Run workflow** — можно запустить на любой ветке);
- собирает движок, рендерит список роликов ниже и коммитит MP4 в эту папку.

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

**Настройка (один раз):** Settings → Secrets and variables → Actions →
- `FISH_AUDIO_API_KEY` — ключ API Fish Audio (обязателен);
- `FISH_AUDIO_VOICE_ID` — reference_id голоса Фреди (желателен, иначе
  голос по умолчанию).

| Файл | Что это |
|------|---------|
| `pereproshivka-intro-voice.mp3` | Дубль озвучки подводки (реплики по таймкодам) |
| `pereproshivka-intro-final.mp4` | Видео + голос, готовый ролик (без SFX) |

SFX (капля, лязг и т.п.) добавляются в редакторе по таблице из
`examples/lektorij/pereproshivka-intro-VO.md`.
