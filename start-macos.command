#!/bin/sh
set -eu

cd "$(dirname "$0")"

if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    echo "ffmpeg is not installed and Homebrew is not available."
    exit 1
  fi
fi

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
