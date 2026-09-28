"""Точка входа: GUI-просмотрщик results.h5 (Wave2D).

Логика окна — в :class:`~src.wave2d.viewer.W2DViewer`.

Запуск::

    uv run w2d_viewer.py [<run_id>]      # по умолчанию — свежий FT-2_LH_smoke_nphi
"""

import sys

import tkinter as tk
from tkinter import messagebox

from src.common.paths import wave2d_results, wave2d_latest
from src.wave2d.schema import UnsupportedFormatError, ensure_supported_path
from src.wave2d.viewer import W2DViewer

DEFAULT_CASE = "FT-2_LH_smoke_nphi"


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    run_id = argv[0] if argv else wave2d_latest(DEFAULT_CASE)
    file_path = str(wave2d_results(run_id))

    # Проверяем версию до создания окна, иначе при несовместимом формате
    # останется пустое окно.
    try:
        ensure_supported_path(file_path)
    except UnsupportedFormatError as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Формат не поддерживается", str(e), parent=root)
        root.destroy()
        return

    root = tk.Tk()
    W2DViewer(root, file_path)
    root.mainloop()


if __name__ == "__main__":
    main()