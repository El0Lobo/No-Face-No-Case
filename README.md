# No Face No Case

No Face No Case is an offline desktop privacy planner for blurring, pixelating, or overlaying sensitive areas in images and videos.

This update moves the app further toward a planner-first workflow: review detections, choose face or person mode, add manual timeline boxes, remember people that should stay clear, then export a processed copy with the original audio preserved.

## Update Highlights

- Offline YOLO detection with bundled model assets.
- Face mode using the bundled YOLO26 face detector.
- Person mode using YOLO26 person detection.
- Person percentage slider: affect the full person or only the top part of the detected person box.
- Timeline editor for manual boxes.
- Each manual box has its own timeline row.
- Drag timeline handles to shorten or prolong a box.
- Drag the timeline bar to move the whole box in time.
- Manual boxes can ease between keyframed positions when moved later in the video.
- Double-click detections to remember faces or persons that should stay clear.
- Right-click detections to ignore false positives.
- Audio-preserving video export through local FFmpeg when available.
- Preview detection boxes stay preview-only and are not drawn into exported media.

## Modes

### Detection Area

- `Face area`: uses the face detector and affects detected face boxes.
- `Person`: switches to YOLO26 person detection and affects detected person boxes.

The `Person percentage` slider controls how much of the detected person box is affected:

- `100%`: full person.
- `33%`: roughly the top third.
- Lower values: smaller area from the top of the person box.

### Effect Target

- Blur or pixelate detected faces/persons.
- Keep remembered or protected areas clear while affecting the background.

## Planner Workflow

1. Choose an image or video.
2. Pick `Face area` or `Person`.
3. Adjust confidence, expansion, person percentage, blur, pixel size, and effect hold frames.
4. Review green detection boxes in the preview.
5. Right-click a detection to ignore it.
6. Double-click a detection to remember that face/person and keep it clear.
7. Drag manual boxes onto the preview for custom clear/effect regions.
8. Use the timeline to move, shorten, prolong, or keyframe manual boxes.
9. Export the processed media.

## Timeline Editing

Manual boxes appear as rows in the timeline.

- Drag the left or right handle to change duration.
- Drag the colored bar to move the box along the timeline.
- Move a box in the preview at a later frame to create a motion stop.
- The box eases between stops unless another stop is set.
- Use `Delete selected box` to remove the selected manual box.

## Export

Images are written directly.

Videos are processed frame by frame. The app writes a temporary processed video, then uses local FFmpeg to mux the original audio into the final output. If FFmpeg is not available, export still succeeds as a silent processed video.

Detection guide boxes are only part of the preview UI. They are not rendered into exported output.

## Run From Source

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py main.py
```

## One-Click Starters

- `start-macos.command` for macOS
- `start-linux.sh` for Linux
- `start-windows.bat` for Windows

Each launcher runs `main.py` from the repo root and prefers the local `.venv` interpreter if it exists.
If `ffmpeg` is missing, the launcher will try to install it with the platform package manager before the app starts.

## Build

For desktop bundles, use PyInstaller from a clean virtual environment.

Full build:

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean NoFaceNoCase.spec
```

Smaller build with face and person detection:

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean NoFaceNoCaseLite.spec
```

On Windows, you can also run:

```powershell
.\build-windows.bat
```

For the smaller face-and-person package:

```powershell
.\build-windows-lite.bat
```

If you prefer a manual command on Windows PowerShell:

```powershell
py -m pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean NoFaceNoCase.spec
```

To reset a bloated virtualenv, delete `.venv` and recreate it from `requirements.txt` for runtime only, or `requirements-dev.txt` if you also want tests and packaging tools.

The Windows build scripts install `requirements-dev.txt` before running PyInstaller, so the frozen app is built from the same dependency set as the source install.

The Windows GitHub Actions workflow now produces both:
- a one-file `.exe`
- a zipped folder bundle for users who prefer the unpacked PyInstaller layout

## GitHub Releases

Tag a commit like `v2.0.1` and GitHub Actions will build and publish:

- macOS `.dmg` plus `.zip`
- Windows one-file `.exe` plus zipped folder bundle
- Linux `.tar.gz`

The release workflow is in [`.github/workflows/release.yml`](/mnt/c/Users/Lobo/Documents/GitHub/demo%20tool%20final/.github/workflows/release.yml).

## Platform Notes

- Windows, macOS, and Linux are supported through Python, Tkinter, OpenCV, Pillow, and Ultralytics.
- The app runs locally and does not require API calls.
- Android is not supported by this Tkinter UI. The core processing code is separated so another UI layer could reuse it later.

## Project Layout

```text
main.py                         App entry point
no_face_no_case/app/            Tkinter GUI, splash, styling
no_face_no_case/core/           Detection, effects, identity, models, processor
no_face_no_case/infrastructure/ Media loading, inspection, FFmpeg audio muxing
no_face_no_case/assets/         Runtime styling/model assets
```
