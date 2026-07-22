FROM rust:1.80-bookworm AS builder

WORKDIR /app

# Копируем все файлы из корня репозитория
COPY . .

# Диагностика: выводим список файлов в лог сборки (поможет понять, что попало в контейнер)
RUN ls -la /app

# Собираем проект в режиме release
RUN cargo build --release

# Финальный образ — лёгкий Debian
FROM debian:bookworm-slim

# Устанавливаем ffmpeg (нужен для рендера видео) и ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Копируем скомпилированный бинарник из builder-стадии
COPY --from=builder /app/target/release/animdsl /usr/local/bin/animdsl

# Создаём директорию для persistence
RUN mkdir -p /data

# Порт должен совпадать с containerPort в настройках Amvera
EXPOSE 8080

# Запускаем приложение
CMD ["animdsl"]
