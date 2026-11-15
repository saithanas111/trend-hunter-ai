import csv
import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

QUEUE = Path("content_queue.json")
ASSET_DIR = Path("assets")
VIDEO_DIR = ASSET_DIR / "videos"
REPO_RAW = "https://raw.githubusercontent.com/saithanas111/trend-hunter-ai/main"


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_width):
    words, lines, current = text.split(), [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build_poster(item, image_path, poster_path):
    product = Image.open(image_path).convert("RGB")
    canvas_size = (1080, 1920)
    background = ImageOps.fit(product, canvas_size).filter(ImageFilter.GaussianBlur(28))
    background = ImageEnhance.Brightness(background).enhance(0.38)
    canvas = background.convert("RGBA")
    overlay = Image.new("RGBA", canvas_size, (8, 14, 28, 105))
    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    title = item.get("product", "Trending product")
    headline = "90° ELBOW USB-C CABLE" if "90" in title or "Degree" in title else title[:42].upper()
    draw.rounded_rectangle((70, 100, 1010, 360), radius=42, fill=(12, 24, 44, 225))
    fnt = font(62, True)
    lines = wrap(draw, headline, fnt, 820)
    y = 155
    for line in lines[:2]:
        draw.text((125, y), line, font=fnt, fill=(255, 255, 255, 255), stroke_width=1)
        y += 82

    product.thumbnail((860, 860), Image.Resampling.LANCZOS)
    panel = Image.new("RGBA", (940, 940), (255, 255, 255, 255))
    px = (940 - product.width) // 2
    py = (940 - product.height) // 2
    panel.paste(product, (px, py))
    mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 939, 939), radius=42, fill=255)
    canvas.paste(panel, (70, 470), mask)

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((70, 1480, 1010, 1790), radius=42, fill=(12, 24, 44, 230))
    sub = "Choose the compatible cable option for your Xiaomi device."
    for i, line in enumerate(wrap(draw, sub, font(38), 820)[:2]):
        draw.text((125, 1540 + i * 54), line, font=font(38), fill=(255, 255, 255, 255))
    draw.text((125, 1695), "CHECK DETAILS & COMPATIBILITY", font=font(34, True), fill=(255, 210, 90, 255))
    draw.text((125, 1840), "Product link in caption", font=font(30, True), fill=(255, 255, 255, 255))
    canvas.convert("RGB").save(poster_path, "JPEG", quality=92, optimize=True)


def main():
    print(
        "SKIPPED: this legacy renderer turns a still product image into a 2.5D zoom. "
        "Trend Hunter requires a genuine multi-angle 3D CGI render. "
        "No approved 3D renderer is configured, so no substitute video was generated."
    )
    return 0

if __name__ == "__main__":
    main()
