"""GUI-просмотрщик HDF5-файлов результатов Wave2D (``results.h5``/``report.h5``).

Тонкий оркестратор: владеет соединением :class:`H5Reader`, раскладывает две
панели и связывает их. Вся отрисовка — в
:class:`~src.wave2d.datasetview.DatasetView`, дерево содержимого — в
:class:`~src.wave2d.h5tree.H5TreeView`.

Точка входа — ``w2d_viewer.py`` в корне репозитория.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

import tkinter as tk
from tkinter import messagebox, ttk

from src.common.h5reader import H5Reader
from src.common.navigator import default_navigator
from src.wave2d.datasetview import DatasetView, Selection
from src.wave2d.h5tree import H5TreeView
from src.wave2d.multiview import AddResult, PlotItem, add_to_comparison
from src.wave2d.schema import (
    GRID_PSI,
    GRID_RHO,
    GRID_X,
    GRID_Y,
    format_version_of,
    open_results,
)


def _source_label(file_path: str) -> str:
    """Метка источника для MultiView: ``<case>/<stamp> [tasks/<task>]``.

    Best-effort: путь приводится к корню навигатора Wave2D; если не вышло —
    берётся имя родительской папки.
    """
    path = Path(file_path)
    try:
        root = default_navigator().wave2d.root
        parts = path.resolve().relative_to(root.resolve()).parts[:-1]
    except (ValueError, OSError):
        return path.parent.name or path.stem
    if not parts:
        return path.stem
    label = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
    if len(parts) >= 4 and parts[2] == "tasks":
        label += f" [tasks/{parts[3]}]"
    return label


class W2DViewer:
    """Окно просмотра одного HDF5-файла результатов Wave2D."""

    def __init__(self, root: tk.Tk, file_path: str):
        self.root = root
        self.file_path = file_path

        # Одно соединение на всё время работы, закрывается в on_closing.
        # open_results заодно проверяет версию схемы (>= 0.94).
        self.reader = open_results(file_path)

        # Версия схемы — единственный атрибут корня; выносим её в заголовок,
        # чтобы корневой узел в дереве был не нужен.
        version = format_version_of(self.reader)
        version_text = f"{version[0]}.{version[1]:02d}" if version else "?"
        self.root.title(f"W2D Viewer — {file_path} (формат {version_text})")
        self.root.geometry("1150x780")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.setup_ui()
        # Нет выбранного узла: область данных показывает сообщение.
        self.dataset_view.show(None)
        # Начальная ширина левой панели ~300 px (после первой раскладки окна).
        self._sash_done = False
        self.paned.bind("<Configure>", self._set_initial_sash, add="+")

    # --- интерфейс -------------------------------------------------------

    def setup_ui(self) -> None:
        paned = self.paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        self.tree_view = H5TreeView(paned, on_select=self.on_select)
        self.tree_view.populate(self.reader)

        self.dataset_view = DatasetView(
            paned,
            coords=self._load_coords(),
            rho=self._load_axis(GRID_RHO),
            psi=self._load_axis(GRID_PSI),
            on_add_to_comparison=self._add_to_comparison,
        )

        paned.add(self.tree_view, weight=1)
        paned.add(self.dataset_view, weight=3)

    def _load_coords(self) -> tuple[np.ndarray, np.ndarray] | None:
        """Координаты (R,Z) для физического вида, если есть в файле."""
        try:
            if self.reader.contains(GRID_X) and self.reader.contains(GRID_Y):
                return self.reader.array(GRID_X), self.reader.array(GRID_Y)
        except Exception:
            pass
        return None

    def _load_axis(self, path: str) -> tuple[np.ndarray, Any] | None:
        """1D-ось ``(массив, units)`` из файла или ``None`` (нет/ошибка)."""
        try:
            if self.reader.contains(path):
                return self.reader.array(path), self._attrs(path).get("units")
        except Exception:
            pass
        return None

    def _set_initial_sash(self, event=None) -> None:
        """Однократно задаёт начальную позицию разделителя: левая панель ~300 px."""
        if self._sash_done:
            return
        try:
            self.paned.sashpos(0, 300)
        except tk.TclError:
            return  # окно ещё не готово — попробуем на следующем <Configure>
        self._sash_done = True

    # --- обработчики -----------------------------------------------------

    def on_select(self, paths: list[str]) -> None:
        """Собирает :class:`Selection` по путям узлов и отдаёт их области данных.

        Список может быть пустым (снят выделение) или содержать несколько
        узлов (multi-select в дереве).
        """
        self.dataset_view.show([self._make_selection(path) for path in paths])

    def _make_selection(self, path: str) -> Selection:
        """Собирает :class:`Selection` по одному пути узла."""
        kind = self.reader.kind(path)
        return Selection(
            path=path,
            kind=kind,
            attrs=self._attrs(path),
            data=None if kind == "group" else self._array(path),
        )

    def _attrs(self, path: str) -> dict:
        """Атрибуты узла; ошибка чтения — пустой словарь (не роняем окно)."""
        try:
            return self.reader.attrs(path)
        except Exception:
            return {}

    def _array(self, path: str) -> np.ndarray | None:
        """Массив датасета; ошибка чтения — ``None`` (область покажет атрибуты)."""
        try:
            return self.reader.array(path)
        except Exception:
            return None

    def _add_to_comparison(self, selection: Selection) -> None:
        """Отправляет текущий датасет в общий набор MultiView."""
        if selection.data is None:
            return
        item = PlotItem(
            source=_source_label(self.file_path),
            file_path=self.file_path,
            node_path=selection.path or "",
            data=selection.data,
            attrs=dict(selection.attrs or {}),
            view=self.dataset_view.view_var.get(),
            comp=self.dataset_view.comp_var.get(),
        )
        if add_to_comparison(item) is AddResult.CONFLICT:
            messagebox.showwarning(
                "Сравнение",
                "В этой группе уже есть датасеты другой размерности "
                "(1D и 2D вместе не сравниваются).",
                parent=self.root,
            )

    def on_closing(self) -> None:
        """Освобождает ресурсы и закрывает окно."""
        self.dataset_view.close()
        self.reader.close()
        self.root.destroy()
