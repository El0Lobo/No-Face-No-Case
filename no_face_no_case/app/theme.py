from __future__ import annotations

import tkinter as tk
from tkinter import ttk


BG = "#24231f"
PANEL = "#302f2a"
SURFACE = "#3b3932"
TEXT = "#f4eee0"
MUTED = "#bdb5a4"
INK = "#0d0c0a"
ACCENT = "#f5a623"
ACCENT_DARK = "#bd7a06"
GREEN = "#00f58d"
BLUE = "#28a0ff"
DANGER = "#ff3b36"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
SECTION_FONT = ("Segoe UI", 13, "bold")


def apply_theme(root: tk.Tk) -> None:
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        ".",
        background=BG,
        foreground=TEXT,
        fieldbackground="#191816",
        bordercolor=INK,
        darkcolor=INK,
        lightcolor=SURFACE,
        troughcolor=INK,
        font=FONT,
    )
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("ToolPanel.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("Section.TLabel", background=BG, foreground=ACCENT, font=SECTION_FONT)
    style.configure("TButton", background=PANEL, foreground=TEXT, padding=(10, 6), borderwidth=2, relief="solid", font=FONT_BOLD)
    style.map(
        "TButton",
        background=[("active", SURFACE), ("pressed", INK)],
        foreground=[("active", ACCENT), ("pressed", ACCENT)],
        relief=[("pressed", "sunken"), ("!pressed", "raised")],
    )
    style.configure("Accent.TButton", background=ACCENT, foreground=INK, font=("Segoe UI", 12, "bold"), padding=(18, 8), borderwidth=2)
    style.map("Accent.TButton", background=[("active", "#ffd166"), ("pressed", ACCENT_DARK)], foreground=[("active", INK)])
    style.configure("TCheckbutton", background=BG, foreground=TEXT)
    style.configure("TRadiobutton", background=BG, foreground=TEXT)
    style.map(
        "TCheckbutton",
        background=[("active", BG)],
        foreground=[("active", ACCENT), ("selected", TEXT)],
        indicatorcolor=[("selected", ACCENT), ("!selected", TEXT)],
    )
    style.map(
        "TRadiobutton",
        background=[("active", BG)],
        foreground=[("active", ACCENT), ("selected", ACCENT)],
        indicatorcolor=[("selected", ACCENT), ("!selected", TEXT)],
    )
    style.configure("TEntry", fieldbackground="#191816", foreground=TEXT, insertcolor=ACCENT, borderwidth=2, padding=(5, 4))
    style.configure("Horizontal.TScale", background=BG)
    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#191816", borderwidth=1)
    style.configure("Vertical.TScrollbar", background=ACCENT, troughcolor="#191816", borderwidth=1, arrowcolor=TEXT)
    style.map("Vertical.TScrollbar", background=[("active", "#ffd166")])
    style.configure("Horizontal.TScrollbar", background=ACCENT, troughcolor="#191816", borderwidth=1, arrowcolor=TEXT)
    style.configure("TSeparator", background=INK)
