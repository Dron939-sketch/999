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

# ── МАСТЕРИНГ ЗВУКА ─────────────────────────────────────────────────────────
# Замер оригинала (_9 октября 2024.mp4) против нашего первого сведения:
#
#     величина              оригинал   было у нас
#     Integrated loudness   -12.6 LUFS   -29.5 LUFS
#     Loudness range (LRA)    6.6 LU      26.4 LU
#     True peak              +0.1 dBFS    -7.9 dBFS
#
# Мы отдавали ролик на 17 дБ тише оригинала: зритель выкручивает громкость,
# и вместе с речью поднимается наш же шумовой пол. И разброс громкости у нас
# был вчетверо шире — часть реплик тонула, часть била. Оригинал сведён плотно.
#
# Лечим системно, а не покадрово: двухпроходный loudnorm к целевой громкости.
# Первый проход МЕРЯЕТ, второй применяет замеренное — одного прохода мало,
# он работает вслепую и промахивается на несколько дБ.
TARGET_I="${TARGET_LUFS:--14}"     # оригинал -12.6; -14 держит запас под кодек
TARGET_LRA="${TARGET_LRA:-7}"      # у оригинала 6.6 LU
TARGET_TP="${TARGET_TP:--1.5}"     # AAC добавляет ~1.3 дБ перелёта (замерено)

# Компрессор ПЕРЕД нормализацией. Без него loudnorm упирался в -17.5 LUFS и
# 13 LU: у нашей дорожки шумовой пол на -50, а речь далеко от полной шкалы,
# и нормализатор не может поднять уровень, не выбив пик. Замер трёх настроек:
#   thr .02  ratio 6 → I -14.9  LRA 6.2   (оригинал: -12.6 / 6.6)
#   thr .012 ratio 8 → I -14.5  LRA 4.8   пережато
#   thr .008 ratio 9 → I -13.9  LRA 3.4   пережато
# Берём первую: разброс важнее последних двух децибел громкости.
COMPRESS="acompressor=threshold=0.02:ratio=6:attack=5:release=180:makeup=4"

echo "мастеринг: замер..." >&2
MEAS="$(ffmpeg -hide_banner -nostats -i "$AUDIO" \
    -af "loudnorm=I=${TARGET_I}:LRA=${TARGET_LRA}:TP=${TARGET_TP}:print_format=json" \
    -f null - 2>&1 | sed -n '/^{/,/^}/p')"

get() { printf '%s' "$MEAS" | sed -n "s/.*\"$1\"[^\"]*\"\([^\"]*\)\".*/\1/p" | head -1; }
M_I="$(get input_i)"; M_TP="$(get input_tp)"; M_LRA="$(get input_lra)"; M_TH="$(get input_thresh)"

if [[ -n "$M_I" && "$M_I" != "-inf" ]]; then
    echo "мастеринг: было I=${M_I} LUFS, LRA=${M_LRA} LU, TP=${M_TP} dBFS" \
         "→ цель I=${TARGET_I}, LRA=${TARGET_LRA}, TP=${TARGET_TP}" >&2
    AF="${COMPRESS},loudnorm=I=${TARGET_I}:LRA=${TARGET_LRA}:TP=${TARGET_TP}"
    AF="${AF}:measured_I=${M_I}:measured_LRA=${M_LRA}:measured_TP=${M_TP}"
    # ДИНАМИЧЕСКИЙ режим, не linear: линейный режим тянет только общий
    # уровень и упирается в потолок пика — на первом прогоне он дотянул лишь
    # до -17.5 LUFS вместо -13 и не сжал разброс (13 LU вместо 7).
    AF="${AF}:measured_thresh=${M_TH}:linear=false:print_format=summary"
    # Потолок пика подтверждаем лимитером ПОСЛЕ нормализации: loudnorm считает
    # истинный пик ДО кодека, а AAC добавляет свой перелёт (замерено: +0.3 dBFS
    # на выходе при заявленном -1.0).
    AF="${AF},alimiter=limit=0.841:level=false"
    # ЧАСТОТА ОБРАТНО В 48 кГц. loudnorm внутри работает на 192 кГц и без
    # явного указания тянет высокую частоту в выход: получался AAC 96 кГц.
    # ffmpeg такой файл читает, а большинство плееров и браузеров — нет, и
    # ролик выглядит НЕМЫМ при формально исправной дорожке. Ровно это и
    # случилось со всеми четырьмя интро.
    AF="${AF},aresample=48000"
else
    echo "предупреждение: замер громкости не удался — мастеринг пропущен." >&2
    AF="anull"
fi

ffmpeg -y \
    -i "$VIDEO" \
    -i "$AUDIO" \
    -filter_complex "[0:v]${VF},format=yuv420p[v];[1:a]${AF}[a]" \
    -map "[v]" -map "[a]" \
    -c:v libx264 -preset medium -crf 20 \
    -c:a aac -b:a 160k -ar 48000 -ac 2 \
    -t "$AUDIO_DUR" \
    -movflags +faststart \
    "$OUT"

echo "Готово: $OUT (длительность ${AUDIO_DUR}s)"
