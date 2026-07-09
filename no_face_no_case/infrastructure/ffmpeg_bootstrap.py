from __future__ import annotations

import platform
import shutil
import subprocess

from no_face_no_case.infrastructure.media_io import find_ffmpeg


def ensure_ffmpeg() -> bool:
    if find_ffmpeg() is not None:
        return True

    for command_group in _install_commands():
        if _run_install_group(command_group):
            if find_ffmpeg() is not None:
                return True
    return False


def _install_commands() -> list[list[list[str]]]:
    system = platform.system().lower()
    if system == "windows":
        return [
            [["winget", "install", "-e", "--id", "Gyan.FFmpeg", "--accept-package-agreements", "--accept-source-agreements"]],
            [["choco", "install", "ffmpeg", "-y"]],
            [["scoop", "install", "ffmpeg"]],
        ]
    if system == "darwin":
        return [[["brew", "install", "ffmpeg"]]]
    return [
        [["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "-y", "ffmpeg"]],
        [["sudo", "dnf", "install", "-y", "ffmpeg"]],
        [["sudo", "pacman", "-Sy", "--noconfirm", "ffmpeg"]],
        [["sudo", "zypper", "install", "-y", "ffmpeg"]],
        [["brew", "install", "ffmpeg"]],
    ]


def _run_install_group(commands: list[list[str]]) -> bool:
    for command in commands:
        if shutil.which(command[0]) is None and command[0] != "sudo":
            continue
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return False
    return True
