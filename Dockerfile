FROM rust:1.80-bookworm AS builder
WORKDIR /app

# Явно копируем файлы манифеста и исходный код
COPY Cargo.toml ./
COPY Cargo.lock ./
COPY src ./src

RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/animdsl /usr/local/bin/animdsl
RUN mkdir -p /data

# Порт должен совпадать с containerPort в настройках Amvera
EXPOSE 8080
CMD ["animdsl"]
