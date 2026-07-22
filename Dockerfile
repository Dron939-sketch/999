FROM rustlang/rust:nightly-bookworm AS builder

WORKDIR /app
COPY . .

RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/animdsl /usr/local/bin/animdsl

RUN mkdir -p /data

WORKDIR /app

# === Создаём input.anim с правильными переносами строк ===
RUN printf 'scene "test" {\n    duration: 3\n    background: #000000\n}\n' > input.anim

# Диагностика: показываем содержимое файла в логе сборки
RUN cat input.anim && echo "---" && wc -l input.anim

CMD ["animdsl", "render", "input.anim", "-o", "/data/output.mp4"]
