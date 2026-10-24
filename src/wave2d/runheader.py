"""Шапка правой панели навигатора: имя и описание выбранного прогона.

Виджет не знает ни про HDF5, ни про навигатор: получает готовые строки
(:meth:`RunHeader.show`). Показывается над всеми «листами» прогона —
короткой текстовой сводкой, вкладками ``Summary``/``Tasks`` и сведениями
о файлах задач/производных артефактов, — поэтому ``Name``/``Description``
не дублируются в теле сводки (``format_run_info(header=False)``).

Длинное описание переносится по ширине панели: ``wraplength`` подписей
пересчитывается на ``<Configure>``.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

#: Отступ подписей по горизонтали (совпадает с ``_PANEL_PAD`` в ``app``).
_PAD_X = 4


class RunHeader(ttk.Frame):
    """Короткая шапка прогона: имя (полужирным) и описание с переносом."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        self._bold = bold  # держим ссылку, иначе именованный шрифт уберут

        self._title = ttk.Label(self, font=bold)
        self._title.grid(row=0, column=0, sticky="w", padx=_PAD_X, pady=(6, 0))
        self._subtitle = ttk.Label(self, justify="left", anchor="w")
        self._subtitle.grid(
            row=1, column=0, sticky="ew", padx=_PAD_X, pady=(2, 0)
        )
        self.columnconfigure(0, weight=1)
        self.bind("<Configure>", self._on_configure)

    def show(self, title: str | None, subtitle: str | None) -> None:
        """Показывает имя/описание прогона; пустые строки скрываются.

        Если обе строки пусты — скрывается вся шапка (``grid_remove``).
        """
        if title:
            self._title.configure(text=title)
            self._title.grid()
        else:
            self._title.grid_remove()
        if subtitle:
            self._subtitle.configure(text=subtitle)
            self._subtitle.grid()
        else:
            self._subtitle.grid_remove()
        if title or subtitle:
            self.grid()
        else:
            self.grid_remove()

    def clear(self) -> None:
        """Скрывает шапку и очищает подписи."""
        self._title.configure(text="")
        self._subtitle.configure(text="")
        self._title.grid_remove()
        self._subtitle.grid_remove()
        self.grid_remove()

    def _on_configure(self, event: tk.Event) -> None:
        """Подгоняет перенос описания под текущую ширину панели."""
        if event.widget is not self:
            return
        self._subtitle.configure(wraplength=max(event.width - 2 * _PAD_X, 120))
