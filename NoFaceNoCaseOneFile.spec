# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

# PyInstaller executes spec files without defining __file__, so anchor paths to the build cwd.
project_root = Path.cwd()
asset_dir = project_root / "no_face_no_case" / "assets"

datas = []
for path in sorted(asset_dir.iterdir()):
    if path.is_file():
        datas.append((str(path), "assets"))

binaries = []
hiddenimports = []

for package in ("PIL", "tkcalendar", "ultralytics"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

# OpenCV needs its native extension and support DLLs bundled explicitly.
binaries += collect_dynamic_libs("cv2")
hiddenimports.append("cv2")
hiddenimports.append("onnxruntime")
hiddenimports.append("onnxruntime.capi._pybind_state")

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="No Face No Case",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(asset_dir / "icon.ico"),
)
