@echo off
setlocal
cd /d "%~dp0"

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

if "%PYTHON%"=="py -3" (
    py -3 -m pip install -r requirements-dev.txt
) else if "%PYTHON%"=="python" (
    python -m pip install -r requirements-dev.txt
) else (
    "%PYTHON%" -m pip install -r requirements-dev.txt
)

if "%PYTHON%"=="py -3" (
    py -3 -m PyInstaller --noconfirm --clean NoFaceNoCase.spec
) else if "%PYTHON%"=="python" (
    python -m PyInstaller --noconfirm --clean NoFaceNoCase.spec
) else (
    "%PYTHON%" -m PyInstaller --noconfirm --clean NoFaceNoCase.spec
)

if "%PYTHON%"=="py -3" (
    py -3 -m PyInstaller --noconfirm --clean NoFaceNoCaseOneFile.spec
) else if "%PYTHON%"=="python" (
    python -m PyInstaller --noconfirm --clean NoFaceNoCaseOneFile.spec
) else (
    "%PYTHON%" -m PyInstaller --noconfirm --clean NoFaceNoCaseOneFile.spec
)
