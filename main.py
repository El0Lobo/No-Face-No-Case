from __future__ import annotations

import os
import sys
from pathlib import Path
import tkinter as tk

from no_face_no_case.app.gui import PlannerApp
from no_face_no_case.app.splash import SplashScreen
from no_face_no_case.infrastructure.ffmpeg_bootstrap import ensure_ffmpeg


def main() -> None:
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")
    ensure_ffmpeg()
    launch_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else None
    if launch_path is not None and not launch_path.exists():
        launch_path = None

    splash_root = tk.Tk()
    splash = SplashScreen(splash_root)
    splash.show()
    splash_root.mainloop()

    root = tk.Tk()
    app = PlannerApp(root)
    if launch_path is not None and launch_path.is_file():
        app.load_media_file(launch_path)
    root.mainloop()


if __name__ == "__main__":
    main()
