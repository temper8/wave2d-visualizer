"""Точка входа: GUI-навигатор по каталогу Wave2D.

Логика окна — в :class:`~src.wave2d.app.W2DNavigatorApp`.

Запуск::

    uv run w2d_app.py [<data_root>]   # по умолчанию WAVE2D_DATA_DIR/<repo>/data
"""

import sys

import tkinter as tk

from src.wave2d.app import W2DNavigatorApp


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    root_dir = argv[0] if argv else None
    root = tk.Tk()
    W2DNavigatorApp(root, root_dir)
    root.mainloop()


if __name__ == "__main__":
    main()