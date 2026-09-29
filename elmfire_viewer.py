"""Точка входа: GUI-просмотрщик флуктуаций ELMFIRE (``z1.h5``).

Логика окна — в :class:`~src.elmfire.viewer.ElmfireFluctuationsViewer`.

Запуск::

    uv run elmfire_viewer.py    # z1.h5 прогона WagD
"""

import tkinter as tk

from src.common.paths import elmfire_converted
from src.elmfire.viewer import ElmfireFluctuationsViewer
from src.plasma_fluctuations import PlasmaFluctuations

DEFAULT_RUN = "WagD"


def main() -> None:
    fluctuations = PlasmaFluctuations(str(elmfire_converted(DEFAULT_RUN)))
    root = tk.Tk()
    ElmfireFluctuationsViewer(root, fluctuations)
    root.mainloop()


if __name__ == "__main__":
    main()
