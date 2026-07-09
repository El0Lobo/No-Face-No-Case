#!/bin/sh
set -eu

cd "$(dirname "$0")"

ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    return 0
  fi

  if command -v apt-get >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1; then
      sudo apt-get update
      sudo apt-get install -y ffmpeg
    else
      apt-get update
      apt-get install -y ffmpeg
    fi
  elif command -v dnf >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1; then
      sudo dnf install -y ffmpeg
    else
      dnf install -y ffmpeg
    fi
  elif command -v pacman >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1; then
      sudo pacman -Sy --noconfirm ffmpeg
    else
      pacman -Sy --noconfirm ffmpeg
    fi
  elif command -v zypper >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1; then
      sudo zypper install -y ffmpeg
    else
      zypper install -y ffmpeg
    fi
  elif command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    echo "ffmpeg is not installed and no supported package manager was found."
    exit 1
  fi
}

ensure_ffmpeg

if [ -x ".venv/bin/python3" ]; then
  PYTHON=".venv/bin/python3"
elif [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON="$(command -v python)"
else
  echo "Python is not available. Install Python 3 or create .venv first."
  exit 1
fi

exec "$PYTHON" main.py
