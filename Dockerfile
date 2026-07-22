FROM rustlang/rust:nightly-bookworm AS builder

# Разрешаем предупреждения (линтер)
ENV RUSTFLAGS="-A warnings"

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

CMD ["animdsl", "render", "input.anim", "-o", "/data/output.mp4"]
