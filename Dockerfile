# Этап 1: Сборка Rust-приложения
FROM rust:1.85-slim AS builder

# Устанавливаем FFmpeg и инструменты для сборки
RUN apt-get update && apt-get install -y \
    ffmpeg \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Собираем проект в режиме release
RUN cargo build --release

# Этап 2: Финальный минимальный образ для запуска
FROM debian:bookworm-slim

# Устанавливаем FFmpeg (он нужен вашему приложению для рендеринга видео)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем скомпилированный бинарный файл из этапа сборки
COPY --from=builder /app/target/release/animdsl /app/animdsl

# Копируем папку с примерами, чтобы было что рендерить
COPY --from=builder /app/examples /app/examples

# При старте контейнера программа сразу рендерит видео с философом
CMD ["./animdsl", "render", "examples/philosopher.anim", "-o", "/app/output.mp4"]
