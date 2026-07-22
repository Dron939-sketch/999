FROM rustlang/rust:nightly-bookworm AS builder

WORKDIR /app
COPY . .

RUN echo "=== Файлы в /app ===" && ls -la /app

RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/animdsl /usr/local/bin/animdsl

RUN mkdir -p /data

WORKDIR /app

# ПРАВИЛЬНАЯ КОМАНДА: сначала render, потом файл
CMD ["animdsl", "render", "input.anim", "-o", "/data/output.mp4"]
