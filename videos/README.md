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
