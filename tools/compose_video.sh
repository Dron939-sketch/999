#!/usr/bin/env bash
# =============================================================================
#  compose_video.sh — собирает финальный ролик лекции Лектория.
#
#  Движок animdsl рендерит НЕМОЕ чёрно-белое видео с Фреди. Этот скрипт
#  подмешивает закадровый голос (mp3 из серверного TTS Frederick) и, по желанию,
#  накладывает титр с названием лекции (drawtext умеет кириллицу при шрифте
#  с кириллическими глифами — по умолчанию DejaVuSans).
#
#  Использование:
#    tools/compose_video.sh <video.mp4> <audio.mp3> <out.mp4> ["Титр лекции"]
#
#  Пример:
#    cargo run --release -- render examples/lektorij/lekciya-2-frejd-psihodinamika.anim -o fredi.mp4
#    tools/compose_video.sh fredi.mp4 lekciya-2.mp3 lekciya-2-final.mp4 "Лекция 2. Фрейд"
#
#  Длительность результата = длительность озвучки (видео при необходимости
#  дотягивается удержанием последнего кадра через tpad). Требуется ffmpeg.
# =============================================================================
set -euo pipefail

VIDEO="${1:-}"
AUDIO="${2:-}"
OUT="${3:-}"
TITLE="${4:-}"
FONT="${FONT_FILE:-/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf}"

if [[ -z "$VIDEO" || -z "$AUDIO" || -z "$OUT" ]]; then
    echo "usage: $0 <video.mp4> <audio.mp3> <out.mp4> [\"Титр\"]" >&2
    exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg не найден в PATH." >&2
    exit 1
fi
for f in "$VIDEO" "$AUDIO"; do
    [[ -f "$f" ]] || { echo "нет файла: $f" >&2; exit 1; }
done

# Длительность озвучки — под неё тянем видео (удержание последнего кадра).
AUDIO_DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$AUDIO")"

# Видеофильтр: дотянуть видео до длины аудио, при титре — наложить его на первые 4с.
VF="tpad=stop_mode=clone:stop_duration=${AUDIO_DUR}"
if [[ -n "$TITLE" ]]; then
    if [[ -f "$FONT" ]]; then
        # Экранируем спецсимволы drawtext.
        ESC_TITLE="${TITLE//\\/\\\\}"; ESC_TITLE="${ESC_TITLE//:/\\:}"; ESC_TITLE="${ESC_TITLE//\'/\\\'}"
        VF="${VF},drawtext=fontfile='${FONT}':text='${ESC_TITLE}':fontcolor=black:fontsize=48:x=(w-text_w)/2:y=h*0.86:enable='lt(t,4)'"
    else
        echo "предупреждение: шрифт $FONT не найден — титр пропущен." >&2
    fi
fi

ffmpeg -y \
    -i "$VIDEO" \
    -i "$AUDIO" \
    -filter_complex "[0:v]${VF},format=yuv420p[v]" \
    -map "[v]" -map 1:a \
    -c:v libx264 -preset medium -crf 20 \
    -c:a aac -b:a 160k \
    -t "$AUDIO_DUR" \
    -movflags +faststart \
    "$OUT"

echo "Готово: $OUT (длительность ${AUDIO_DUR}s)"
