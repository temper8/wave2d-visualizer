"""Точка входа: GUI-просмотрщик results.h5 (Wave2D).

Логика окна — в :class:`~src.wave2d.viewer.W2DViewer`.

Запуск::

    uv run w2d_viewer.py [<run_id>]      # по умолчанию — свежий прогон FT2
"""

import sys

import tkinter as tk

from src.common.paths import wave2d_results, wave2d_latest
from src.wave2d.viewer import W2DViewer


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    run_id = argv[0] if argv else wave2d_latest("FT2")
    file_path = str(wave2d_results(run_id))
    root = tk.Tk()
    W2DViewer(root, file_path)
    root.mainloop()


if __name__ == "__main__":
    main()