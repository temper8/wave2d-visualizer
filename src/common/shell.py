"""Открытие файлов и папок средствами ОС по умолчанию.

Не-HDF5 артефакты (MP4-ролики анимации) открываются проигрывателем/
ассоциацией ОС, а не viewer'ом; папки — системным файловым менеджером.
Windows — ``os.startfile``, macOS — ``open``, остальные — ``xdg-open``.
"""

from __future__ import annotations

from pathlib import Path

import os
import subprocess
import sys


def _open_path(path: Path) -> None:
    """Открывает путь (файл или папку) средством ОС по умолчанию."""
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def open_in_default_app(path: Path) -> None:
    """Открывает файл приложением, ассоциированным с его типом.

    Raises:
        OSError: если запустить ассоциацию не удалось.
    """
    _open_path(path)


def open_folder(path: Path) -> None:
    """Открывает папку в системном файловом менеджере.

    Raises:
        OSError: если запустить файловый менеджер не удалось.
    """
    _open_path(path)
