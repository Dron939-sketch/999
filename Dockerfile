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

# Создаём input.anim прямо внутри контейнера
RUN echo 'character "fred" { body-type: adult-male skin-color: light hair-style: slicked-back hair-color: dark clothing: overcoat clothing-color: dark-gray pants-color: dark-gray accessories: none } pose "thinking" { torso-bend: 5 head-nod: 10 arm-left-angle: -30 arm-right-angle: 30 elbow-left-bend: 0.6 elbow-right-bend: 0.6 mouth-smile: 0.1 } scene "intro" (duration: 5s, set: dark-room) { place fred at center facing front camera wide wait 2s text "Это тестовая анимация." at top wait 2s transition fade-black 1s }' > input.anim

CMD ["animdsl", "render", "input.anim", "-o", "/data/output.mp4"]
