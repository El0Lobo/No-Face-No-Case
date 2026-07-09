@echo off
setlocal
cd /d "%~dp0"

where ffmpeg >nul 2>nul
if errorlevel 1 (
    where winget >nul 2>nul
    if not errorlevel 1 (
        winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
        if errorlevel 1 exit /b 1
    ) else (
        where choco >nul 2>nul
        if not errorlevel 1 (
            choco install ffmpeg -y
            if errorlevel 1 exit /b 1
        ) else (
            where scoop >nul 2>nul
            if not errorlevel 1 (
                scoop install ffmpeg
                if errorlevel 1 exit /b 1
            ) else (
                echo ffmpeg is not installed and no supported installer was found.
                exit /b 1
            )
        )
    )
)

set "PYTHON="
if exist ".venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON (
    py -3 -V >nul 2>nul && set "PYTHON=py -3"
)
if not defined PYTHON (
    python --version >nul 2>nul && set "PYTHON=python"
)

if not defined PYTHON (
    echo Python is not available. Install Python 3 or create .venv first.
    exit /b 1
)

%PYTHON% main.py
