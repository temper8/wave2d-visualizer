"""Виджет дерева содержимого HDF5-файла (левая панель W2D Viewer).

Отделяет построение дерева от окна-оркестратора: виджет ничего не знает о
рендеринге и о том, как используется выбранный узел. Содержимое строится
через :meth:`H5Reader.walk`, о выборе сообщается колбэком ``on_select(path)``.

Импорт ``h5py`` не нужен: тип узла приходит из ``walk`` (``"group"``/
``"dataset"``), а форма и dtype берутся у самого объекта.
"""

from __future__ import annotations

from collections.abc import Callable

from tkinter import ttk

from src.common.h5reader import H5Reader


class H5TreeView(ttk.Frame):
    """Дерево групп и датасетов одного HDF5-файла.

    Корень файла не показывается: его единственный атрибут
    (``format_version``) вынесен в заголовок окна, поэтому группы верхнего
    уровня (``/manifest``, ``/input``, …) становятся корневыми узлами дерева.
    """

    def __init__(
        self,
        master,
        on_select: Callable[[str], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._reader: H5Reader | None = None

        self.tree = ttk.Treeview(self, show="tree", selectmode="browse")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._handle_select)

    def populate(self, reader: H5Reader) -> None:
        """Заполняет дерево содержимым ``reader`` (обход :meth:`H5Reader.walk`)."""
        self._reader = reader
        self.tree.delete(*self.tree.get_children())
        for full, kind, obj in reader.walk("/"):
            parent = full.rsplit("/", 1)[0]
            name = full.rsplit("/", 1)[1]
            if kind == "group":
                self.tree.insert(parent, "end", iid=full, text=name, open=False)
            else:
                label = f"{name}   {tuple(obj.shape)} {obj.dtype}"
                self.tree.insert(parent, "end", iid=full, text=label)

    def selection(self) -> str | None:
        """Путь выбранного узла или ``None``, если ничего не выбрано."""
        selected = self.tree.selection()
        return selected[0] if selected else None

    def _handle_select(self, event=None) -> None:
        path = self.selection()
        if path is not None and self._on_select is not None:
            self._on_select(path)
