FROM rustlang/rust:nightly-bookworm AS builder

WORKDIR /app
COPY . .

# Диагностика: выводим список файлов в лог сборки
RUN ls -la /app

# Собираем проект в режиме release
RUN cargo build --release

# Финальный образ — лёгкий Debian
FROM debian:bookworm-slim

# Устанавливаем ffmpeg и ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Копируем собранный бинарник
COPY --from=builder /app/target/release/animdsl /usr/local/bin/animdsl

# Создаём директорию для постоянного хранения данных
RUN mkdir -p /data

# Устанавливаем рабочую директорию
WORKDIR /app

# Команда запуска: всегда рендерит input.anim
CMD ["sh", "-c", "animdsl render input.anim -o /data/output.mp4"]
