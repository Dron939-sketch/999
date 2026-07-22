# Этап 1: Сборка Rust-приложения
FROM rust:1.85-slim AS builder

RUN apt-get update && apt-get install -y \
    ffmpeg \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN cargo build --release

# Этап 2: Финальный образ для запуска
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем исполняемый файл
COPY --from=builder /app/target/release/animdsl /app/animdsl

# Копируем примеры И РЕСУРСЫ (это исправляет черный экран!)
COPY --from=builder /app/examples /app/examples
COPY --from=builder /app/assets /app/assets

# Создаем папку для результата
RUN mkdir -p /app/output

# Запускаем рендеринг нашего ролика
CMD ["./animdsl", "render", "examples/freeman-30s.anim", "-o", "/app/output/result.mp4"]
