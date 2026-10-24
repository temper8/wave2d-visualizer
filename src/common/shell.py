"""Открытие файлов приложениями по умолчанию.

Не-HDF5 артефакты (MP4-ролики анимации) открываются проигрывателем/
ассоциацией ОС, а не viewer'ом. Windows — ``os.startfile``, macOS — ``open``,
остальные — ``xdg-open``.
"""

from __future__ import annotations

from pathlib import Path

import os
import subprocess
import sys


def open_in_default_app(path: Path) -> None:
    """Открывает файл приложением, ассоциированным с его типом.

    Raises:
        OSError: если запустить ассоциацию не удалось.
    """
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
