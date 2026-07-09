from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Return the runtime root for source and PyInstaller builds."""
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def asset_path(name: str) -> Path:
    return app_root() / "assets" / name


def bundled_or_old_asset(name: str) -> Path:
    """Resolve a bundled asset, falling back to the archived app during migration."""
    bundled = asset_path(name)
    if bundled.exists():
        return bundled

    old_name = {
        "acme.png": "Ⓐ.png",
        "default_overlay.png": "default.png",
    }.get(name, name)
    old_path = app_root().parent / "old" / old_name
    return old_path if old_path.exists() else bundled
