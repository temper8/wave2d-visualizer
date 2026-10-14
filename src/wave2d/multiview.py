"""Сравнение графиков (MultiView): реестр и окно.

Окно просмотра показывает один датасет за раз; чтобы сравнить одноимённые
датасеты из **разных** расчётов, их складывают в общий набор
:class:`ComparisonSet`. Элементы группируются по **имени** датасета (лист
пути): одна группа — одна вкладка MultiView.

Вкладки рисуются по размерности группы: 1D — наложение рядов с легендой
(:func:`~src.wave2d.renderers.draw_curves`), 2D и прочее — текстовый список
(сетка 2D — отдельная задача ``p2-multiview-2d-grid-rendering``).

Модель данных (:class:`PlotItem`, :class:`ComparisonSet`) не зависит от Tk;
GUI-окно — ниже в этом же модуле.

См. ``TODO/p2-multiview-compare-runs.md``.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from tkinter import ttk
from typing import Any

import numpy as np

import matplotlib
matplotlib.use("TkAgg")  # до импорта pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

from src.wave2d.renderers import component, draw_curves


@dataclass
class PlotItem:
    """Один график, добавленный в сравнение.

    ``data``/``attrs`` — **снимок** значений на момент добавления (не ссылка
    на файл): элемент самодостаточен и не зависит от жизни :class:`H5Reader`
    или доступности сетевой шары. ``view``/``comp`` фиксируют, как датасет
    был показан в исходном окне (вид ``(R,Z)/(rho,theta)`` и составляющая
    ``real/imag/abs``).
    """

    source: str
    """Человекочитаемая метка источника (прогон/задача), напр. ``FT2/<stamp>``."""

    file_path: str
    """Путь к ``results.h5``, откуда взят датасет."""

    node_path: str
    """Путь узла внутри файла, напр. ``/fields/nphi+122/Ea``."""

    data: np.ndarray | None = None
    attrs: dict[str, Any] = field(default_factory=dict)
    view: str = "rho"
    comp: str = "abs"
    color: str | None = None

    @property
    def name(self) -> str:
        """Имя датасета (лист ``node_path``) — ключ группы."""
        return self.node_path.rsplit("/", 1)[-1]

    @property
    def key(self) -> tuple[str, str]:
        """Идентичность элемента: ``(файл, узел)``.

        Два разных элемента с одинаковым именем (коллизия веток) различимы по
        ``node_path``; повторное добавление того же узла заменяет элемент.
        """
        return (self.file_path, self.node_path)

    @property
    def ndim(self) -> int:
        """Размерность данных (``0``, если данных нет) — для проверки типа."""
        return self.data.ndim if self.data is not None else 0


class AddResult(Enum):
    """Итог :meth:`ComparisonSet.add`."""

    CREATED = "created"
    """Создана новая группа (имени ещё не было)."""

    ADDED = "added"
    """Элемент добавлен в существующую группу."""

    REPLACED = "replaced"
    """Тот же узел уже был — элемент заменён на месте."""

    CONFLICT = "conflict"
    """Конфликт типов: в группе 1D, а добавляется 2D (или наоборот)."""


class ComparisonSet:
    """Набор сравниваемых графиков, сгруппированных по имени датасета.

    Группы хранятся в порядке первого появления имени; слушатели
    (:meth:`subscribe`) уведомляются при любом изменении, чтобы окно MultiView
    могло перерисоваться.
    """

    def __init__(self) -> None:
        self._groups: dict[str, list[PlotItem]] = {}
        self._listeners: list[Callable[[], None]] = []

    # --- чтение ----------------------------------------------------------

    def groups(self) -> list[str]:
        """Имена групп в порядке первого появления."""
        return list(self._groups)

    def items(self, name: str) -> list[PlotItem]:
        """Копия списка элементов группы (пустая, если группы нет)."""
        return list(self._groups.get(name, ()))

    def __len__(self) -> int:
        """Общее число элементов во всех группах."""
        return sum(len(items) for items in self._groups.values())

    def is_empty(self) -> bool:
        """``True``, если набор пуст."""
        return not self._groups

    # --- изменение -------------------------------------------------------

    def add(self, item: PlotItem) -> AddResult:
        """Добавляет элемент в группу по имени (при необходимости создаёт её).

        Повторное добавление того же узла (по :attr:`PlotItem.key`) заменяет
        элемент. Элемент другой размерности, чем уже накопленные в группе,
        не добавляется — возвращается :attr:`AddResult.CONFLICT`.
        """
        items = self._groups.get(item.name)
        if items is None:
            self._groups[item.name] = [item]
            self._notify()
            return AddResult.CREATED

        for i, existing in enumerate(items):
            if existing.key == item.key:
                items[i] = item
                self._notify()
                return AddResult.REPLACED

        if items and items[0].ndim != item.ndim:
            return AddResult.CONFLICT

        items.append(item)
        self._notify()
        return AddResult.ADDED

    def remove(self, item: PlotItem) -> bool:
        """Удаляет элемент по :attr:`PlotItem.key`; пустую группу убирает.

        Возвращает ``True``, если элемент был найден и удалён.
        """
        items = self._groups.get(item.name)
        if not items:
            return False
        for i, existing in enumerate(items):
            if existing.key == item.key:
                del items[i]
                if not items:
                    del self._groups[item.name]
                self._notify()
                return True
        return False

    def clear(self) -> None:
        """Убирает все группы и элементы."""
        if not self._groups:
            return
        self._groups.clear()
        self._notify()

    # --- слушатели -------------------------------------------------------

    def subscribe(self, listener: Callable[[], None]) -> None:
        """Регистрирует колбэк, вызываемый при изменении набора."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[], None]) -> None:
        """Снимает колбэк (отсутствующий игнорируется)."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()


_default_comparison: ComparisonSet | None = None


def default_comparison() -> ComparisonSet:
    """Единый набор сравнения на приложение (создаётся при первом обращении)."""
    global _default_comparison
    if _default_comparison is None:
        _default_comparison = ComparisonSet()
    return _default_comparison


# --- окно (GUI) ----------------------------------------------------------


class MultiViewWindow(tk.Toplevel):
    """Окно сравнения: вкладка на группу.

    1D-группа рисуется наложением рядов с легендой, 2D/прочее — текстовым
    списком (реальный рендер 2D — отдельная задача). Окно подписывается на
    :class:`ComparisonSet` и перестраивается при изменениях.
    """

    def __init__(self, comparison: ComparisonSet) -> None:
        super().__init__()
        self.comparison = comparison
        self.title("MultiView — сравнение графиков")
        self.geometry("720x650")
        self.minsize(420, 300)
        # Закрытие прячет окно (набор сохраняется), а не уничтожает его.
        self.protocol("WM_DELETE_WINDOW", self.hide)

        self._figures: list = []
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._selected_name: str | None = None
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        comparison.subscribe(self.refresh)
        self.refresh()

    # --- показ/скрытие ---------------------------------------------------

    def show(self) -> None:
        """Показывает окно (после закрытия — снова)."""
        self.deiconify()
        self.lift()

    def hide(self) -> None:
        """Прячет окно; набор сравнения при этом сохраняется."""
        self.withdraw()

    # --- вкладки ---------------------------------------------------------

    def refresh(self) -> None:
        """Перестраивает вкладки под текущее состояние набора."""
        for fig in self._figures:
            plt.close(fig)
        self._figures.clear()
        for tab_id in self._notebook.tabs():
            self._notebook.forget(tab_id)
        for child in list(self._notebook.winfo_children()):
            child.destroy()

        groups = self.comparison.groups()
        if not groups:
            frame = ttk.Frame(self._notebook)
            ttk.Label(
                frame,
                justify="center",
                text=(
                    "Нет добавленных графиков.\n\n"
                    "Нажмите «В сравнение» в окне просмотра."
                ),
            ).pack(expand=True)
            self._notebook.add(frame, text="(пусто)")
            return

        for name in groups:
            count = len(self.comparison.items(name))
            self._notebook.add(self._build_tab(name), text=f"{name} ({count})")

        target = self._selected_name if self._selected_name in groups else groups[0]
        self.select_group(target)

    def select_group(self, name: str) -> None:
        """Выбирает вкладку группы ``name`` (если она есть)."""
        groups = self.comparison.groups()
        if name not in groups:
            return
        tabs = self._notebook.tabs()
        index = groups.index(name)
        if index < len(tabs):
            self._notebook.select(tabs[index])
            self._selected_name = name

    def _build_tab(self, name: str) -> ttk.Frame:
        """Вкладка группы: 1D — график-наложение, иначе — текстовый список."""
        items = self.comparison.items(name)
        if items and all(item.ndim == 1 for item in items):
            return self._build_plot_tab(name, items)
        return self._build_list_tab(name, items)

    def _build_plot_tab(
        self, name: str, items: list[PlotItem]
    ) -> ttk.Frame:
        """Вкладка 1D-группы: наложение рядов с легендой + удаление."""
        frame = ttk.Frame(self._notebook)
        fig, ax = plt.subplots(figsize=(6.4, 4.2), layout="constrained")
        fig.get_layout_engine().set(w_pad=0.12, h_pad=0.12)
        self._figures.append(fig)
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        bottom = ttk.Frame(frame)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        toolbar = NavigationToolbar2Tk(canvas, bottom)
        toolbar.update()
        toolbar.pack(side=tk.TOP, fill=tk.X)

        series = [
            (
                None,
                component(item.data, item.comp),
                self._item_label(item),
                item.color,
            )
            for item in items
        ]
        draw_curves(
            ax, series, title=f"{name} — сравнение", xlabel="index", ylabel=name
        )
        canvas.draw()

        self._add_remove_row(bottom, items)
        return frame

    def _build_list_tab(
        self, name: str, items: list[PlotItem]
    ) -> ttk.Frame:
        """Вкладка прочих групп: заголовок, список элементов, удаление."""
        frame = ttk.Frame(self._notebook)
        ttk.Label(
            frame, text=f"Датасет: {name}   (элементов: {len(items)})"
        ).pack(anchor="w", padx=6, pady=(6, 2))

        body = ttk.Frame(frame)
        body.pack(fill=tk.BOTH, expand=True, padx=6)
        listbox = tk.Listbox(body, activestyle="none")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        for item in items:
            shape = tuple(item.data.shape) if item.data is not None else ()
            listbox.insert(tk.END, f"{item.source}   {item.node_path}   {shape}")

        self._add_remove_row(frame, items, listbox)
        return frame

    def _add_remove_row(
        self,
        parent,
        items: list[PlotItem],
        listbox: tk.Listbox | None = None,
    ) -> None:
        """Строка удаления: список элементов (если не задан) и кнопка."""
        row = ttk.Frame(parent)
        row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)
        if listbox is None:
            listbox = tk.Listbox(row, height=4, activestyle="none")
            listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
            for item in items:
                listbox.insert(tk.END, self._item_label(item))
        actions = ttk.Frame(row)
        actions.pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(
            actions,
            text="Удалить выбранное",
            command=lambda: self._remove_selected(listbox, items),
        ).pack(fill=tk.X)
        ttk.Button(
            actions,
            text="Очистить все",
            command=self.comparison.clear,
        ).pack(fill=tk.X, pady=(4, 0))

    @staticmethod
    def _item_label(item: PlotItem) -> str:
        """Подпись элемента для легенды/списка: источник и путь узла."""
        return f"{item.source} · {item.node_path}"

    def _remove_selected(
        self, listbox: tk.Listbox, items: list[PlotItem]
    ) -> None:
        """Удаляет выбранный в списке элемент из набора."""
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index < len(items):
            self.comparison.remove(items[index])

    def _on_tab_changed(self, event=None) -> None:
        """Запоминает выбранную вкладку, чтобы сохранить её при перестройке."""
        try:
            index = self._notebook.index(self._notebook.select())
        except tk.TclError:
            return
        groups = self.comparison.groups()
        if 0 <= index < len(groups):
            self._selected_name = groups[index]


_window: MultiViewWindow | None = None


def open_multiview(comparison: ComparisonSet | None = None) -> MultiViewWindow:
    """Открывает (или показывает уже открытое) окно MultiView.

    Окно создаётся дочерним для корня Tk по умолчанию, поэтому не закрывается
    вместе с окном просмотра, из которого был добавлен график.
    """
    global _window
    comparison = comparison or default_comparison()
    if _window is None or not _window.winfo_exists():
        _window = MultiViewWindow(comparison)
    _window.show()
    return _window


def add_to_comparison(
    item: PlotItem, comparison: ComparisonSet | None = None
) -> AddResult:
    """Добавляет элемент в набор, открывает окно и выбирает вкладку группы."""
    comparison = comparison or default_comparison()
    result = comparison.add(item)
    window = open_multiview(comparison)
    if result is not AddResult.CONFLICT:
        window.select_group(item.name)
    return result
