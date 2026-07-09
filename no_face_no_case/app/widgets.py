from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

from no_face_no_case.app.theme import ACCENT, BG, INK


def pixel_title(parent: tk.Widget, text: str, font_path: Path | None = None, size: int = 56) -> tk.Canvas:
    width, height = 760, 92
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(str(font_path), size) if font_path and font_path.exists() else ImageFont.truetype("arial.ttf", size)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (width - (bbox[2] - bbox[0])) // 2
    y = (height - (bbox[3] - bbox[1])) // 2 - 3
    draw.text((x + 3, y + 3), text, font=font, fill=INK)
    draw.text((x, y), text, font=font, fill=ACCENT)

    photo = ImageTk.PhotoImage(image)
    canvas = tk.Canvas(parent, width=width, height=height, bg=BG, highlightthickness=0)
    canvas.create_image(0, 0, anchor="nw", image=photo)
    canvas.image = photo
    return canvas
