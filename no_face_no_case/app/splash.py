from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

from no_face_no_case.app.theme import ACCENT, BG, INK, TEXT
from no_face_no_case.paths import bundled_or_old_asset


class SplashScreen:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.overrideredirect(True)
        self.root.geometry(self._center_geometry(600, 600))
        self.root.configure(bg=BG)
        self.running = True
        self.close_after_id: str | None = None
        self.tick_after_id: str | None = None
        self.message_index = 0
        self.messages = [
            "Preparing the planner...",
            "Lowering preview resolution...",
            "Keeping chosen areas clear...",
            "Loading face privacy tools...",
            "Opening No Face No Case...",
        ]

        self.canvas = tk.Canvas(root, width=600, height=600, highlightthickness=0, bg=BG)
        self.canvas.pack(fill="both", expand=True)
        self.splash_image = self._load_splash()
        self.font = self._load_font(20)
        self._draw()

    def show(self, duration_ms: int = 1800) -> None:
        self.close_after_id = self.root.after(duration_ms, self.close)
        self.tick_after_id = self.root.after(250, self._tick)

    def close(self) -> None:
        self.running = False
        for after_id in (self.close_after_id, self.tick_after_id):
            if after_id is None:
                continue
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        self.close_after_id = None
        self.tick_after_id = None
        self.root.destroy()

    def _tick(self) -> None:
        self.tick_after_id = None
        if not self.running:
            return
        self.message_index = min(self.message_index + 1, len(self.messages) - 1)
        self._draw()
        if self.running:
            self.tick_after_id = self.root.after(350, self._tick)

    def _draw(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_image(300, 300, image=self.splash_image)
        message = self.messages[self.message_index]
        self.canvas.create_rectangle(0, 548, 600, 600, fill=INK, outline=INK, width=0)
        self.canvas.create_text(302, 581, text=message.upper(), fill="#000000", font=("Courier New", 15, "bold"))
        self.canvas.create_text(300, 579, text=message.upper(), fill=TEXT, font=("Courier New", 15, "bold"))

    def _load_splash(self) -> ImageTk.PhotoImage:
        path = bundled_or_old_asset("splash.png")
        if path.exists():
            image = Image.open(path).resize((600, 600), Image.Resampling.LANCZOS).convert("RGB")
        else:
            image = Image.new("RGB", (600, 600), BG)
        return ImageTk.PhotoImage(image)

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        path: Path = bundled_or_old_asset("PixelifySans-Regular.ttf")
        if path.exists():
            return ImageFont.truetype(str(path), size)
        return ImageFont.load_default()

    def _center_geometry(self, width: int, height: int) -> str:
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        return f"{width}x{height}+{x}+{y}"
