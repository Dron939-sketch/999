#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_gen.py — генерация иллюстраций по текстовому промту (Nano Banana / API).

Пишет PNG и, по желанию, оборачивает его в SVG-сет для движка animdsl
(resvg рендерит <image> с data-URI, так что сгенерённая картинка становится
обычным фоном/слоем сцены — правки движка не нужны).

Провайдер и ключ берутся ТОЛЬКО из окружения (в CI — из секретов):
  * IMAGE_API_KEY       — ключ (обязателен);
  * IMAGE_API_PROVIDER  — gemini (Nano Banana) | openai | fal (Flux).

Промт лучше писать в стиле Фримена, чтобы картинка легла в ряд:
  "hand-drawn 2D cartoon, thick wobbly black ink outline, flat light-gray
   background, high contrast black and white, Mr. Freeman style, ..."

Использование:
    python3 tools/image_gen.py -o videos/pic.png --prompt "..."
    python3 tools/image_gen.py -o assets/sets/x.png --prompt "..." \
        --wrap-svg examples/assets/sets/x.svg --size 1280x720
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vectorize

FREEMAN_STYLE = (
    "hand-drawn 2D cartoon in the style of Mr. Freeman, thick wobbly "
    "hand-inked black outlines, flat light-gray paper background, stark "
    "high-contrast black and white, subtle film grain, minimal, graphic, "
    "expressive. "
)


def gen_gemini(prompt, api_key, size):
    """Nano Banana (Gemini image) → PNG-байты."""
    model = os.environ.get("IMAGE_MODEL", "gemini-2.5-flash-image")
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    body = {"contents": [{"parts": [{"text": FREEMAN_STYLE + prompt}]}]}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini не вернул картинку: " + json.dumps(data)[:300])


def gen_fal(prompt, api_key, size):
    """fal.ai (по умолчанию Flux dev) → PNG-байты."""
    model = os.environ.get("IMAGE_MODEL", "fal-ai/flux/dev")
    w, h = (size or "1280x720").split("x")
    body = {
        "prompt": FREEMAN_STYLE + prompt,
        "image_size": {"width": int(w), "height": int(h)},
        "num_images": 1,
        "sync_mode": True,  # вернуть картинку в ответе, без отдельного опроса
    }
    req = urllib.request.Request(
        f"https://fal.run/{model}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Key {api_key}"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    images = data.get("images") or []
    if not images:
        raise RuntimeError("fal не вернул картинку: " + json.dumps(data)[:300])
    url = images[0].get("url", "")
    if url.startswith("data:"):  # data-URI (sync_mode)
        return base64.b64decode(url.split(",", 1)[1])
    with urllib.request.urlopen(url, timeout=120) as r2:  # либо ссылка на fal.media
        return r2.read()


def gen_openai(prompt, api_key, size):
    """OpenAI images → PNG-байты (запасной провайдер)."""
    url = "https://api.openai.com/v1/images/generations"
    body = {"model": os.environ.get("IMAGE_MODEL", "gpt-image-1"),
            "prompt": FREEMAN_STYLE + prompt, "size": size or "1280x720", "n": 1}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    b64 = data["data"][0]["b64_json"]
    return base64.b64decode(b64)


PROVIDERS = {"gemini": gen_gemini, "openai": gen_openai, "fal": gen_fal}


def wrap_in_svg(png_path, svg_path, size, mode="auto"):
    """Делает из картинки SVG-сет для движка — обводкой или вставкой.

    Раньше здесь стояла своя копия вставки растром: сгенерённая картинка ВСЕГДА
    попадала в кадр растром и мылилась на сверхкрупе, а mime был захардкожен
    как png, хотя провайдер мог вернуть jpeg. Теперь этим занимается художник
    (`tools/vectorize.py`): рисунок обводится в настоящие пути, фото
    вставляется, формат берётся по сигнатуре файла. Режим — по замеру, если не
    задан явно.
    """
    w, h = (size or "1280x720").lower().split("x")
    return vectorize.convert(png_path, svg_path, mode=mode, size=(int(w), int(h)))


def main(argv):
    ap = argparse.ArgumentParser(description="Генерация картинки (Nano Banana)")
    ap.add_argument("-o", "--output", required=True, help="куда писать PNG")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--wrap-svg", help="также сделать из PNG SVG-сет по этому пути")
    ap.add_argument("--wrap-mode", choices=("auto", "trace", "embed"), default="auto",
                    help="обводить в вектор, вставить растром или решить замером")
    args = ap.parse_args(argv)

    api_key = os.environ.get("IMAGE_API_KEY")
    if not api_key:
        sys.exit("IMAGE_API_KEY не задан — генерация картинок пропущена.")
    provider = os.environ.get("IMAGE_API_PROVIDER", "gemini").lower()
    gen = PROVIDERS.get(provider)
    if not gen:
        sys.exit(f"неизвестный IMAGE_API_PROVIDER={provider} "
                 f"(есть: {', '.join(PROVIDERS)})")

    print(f"[image_gen] {provider}: {args.prompt[:70]}...")
    png = gen(args.prompt, api_key, args.size)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "wb") as f:
        f.write(png)
    print(f"OK: {args.output} ({len(png)} байт)")
    if args.wrap_svg:
        used = wrap_in_svg(args.output, args.wrap_svg, args.size, args.wrap_mode)
        print(f"OK: сет {args.wrap_svg} ({used})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
