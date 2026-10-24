"""Виджет правой панели навигатора: вкладки отчёта по прогону.

Показывается только для run-level файла (``report.h5``/``results.h5``):

- ``Summary`` — подробная сводка по прогону
  (:func:`~src.wave2d.run_info.format_run_info`);
- ``Tasks`` — таблица задач (:class:`ttk.Treeview`) с сортировкой по клику
  на заголовок.

Для папки прогона и листов задач используется обычная текстовая панель
(:mod:`src.wave2d.app`) — там вкладок нет.

Виджет не знает ни про HDF5, ни про навигатор: данные приходят готовыми
(:class:`~src.wave2d.run_info.RunInfo`), поэтому его можно переиспользовать
вне GUI-навигатора.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.wave2d.run_info import RunInfo, TaskInfo, format_run_info

_TASK_COLUMNS = ("task", "status", "node", "started", "time")
_TASK_HEADINGS = {
    "task": "Task",
    "status": "Status",
    "node": "Node",
    "started": "Started",
    "time": "Time, s",
}
_TASK_WIDTHS = {
    "task": 100,
    "status": 90,
    "node": 90,
    "started": 200,
    "time": 90,
}


class ReportTabs(ttk.Notebook):
    """Вкладки отчёта по прогону: ``Summary`` / ``Tasks``."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._summary_frame, self.summary = self._add_text_tab("Summary")
        self._tasks_frame, self.tasks = self._add_tasks_tab("Tasks")
        self._task_rows: list[TaskInfo] = []
        self._task_sort: tuple[str | None, bool] = (None, False)

    # --- публичный интерфейс -------------------------------------------

    def show_run(self, info: RunInfo) -> None:
        """Показывает подробную сводку и таблицу задач, выбирает ``Summary``."""
        _set_text(self.summary, format_run_info(info))
        self._fill_tasks(info.task_details)
        self.select(self._summary_frame)

    def clear(self) -> None:
        """Очищает вкладки (при перестройке дерева навигатора)."""
        _set_text(self.summary, "")
        self._fill_tasks([])

    # --- построение вкладок --------------------------------------------

    def _add_text_tab(self, title: str) -> tuple[ttk.Frame, tk.Text]:
        """Вкладка с прокручиваемым ``Text`` (read-only)."""
        frame = ttk.Frame(self)
        text = tk.Text(frame, wrap="none", state="disabled")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.add(frame, text=title)
        return frame, text

    def _add_tasks_tab(self, title: str) -> tuple[ttk.Frame, ttk.Treeview]:
        """Вкладка с таблицей задач (``ttk.Treeview``, сортировка по заголовку)."""
        frame = ttk.Frame(self)
        tree = ttk.Treeview(
            frame, columns=_TASK_COLUMNS, show="headings", selectmode="browse"
        )
        for column in _TASK_COLUMNS:
            tree.heading(
                column,
                text=_TASK_HEADINGS[column],
                command=lambda c=column: self._sort_tasks(c),
            )
            tree.column(column, width=_TASK_WIDTHS[column], anchor="w", stretch=True)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.add(frame, text=title)
        return frame, tree

    # --- таблица задач --------------------------------------------------

    def _fill_tasks(self, tasks: list[TaskInfo]) -> None:
        """Заменяет содержимое таблицы, сбрасывая сортировку."""
        self._task_rows = list(tasks)
        self._task_sort = (None, False)
        self._render_tasks()

    def _sort_tasks(self, column: str) -> None:
        """Сортирует таблицу по колонке; повторный клик меняет направление."""
        current, reverse = self._task_sort
        self._task_sort = (column, not reverse if current == column else False)
        self._render_tasks()

    def _render_tasks(self) -> None:
        self.tasks.delete(*self.tasks.get_children())
        rows = self._task_rows
        column, reverse = self._task_sort
        if column is not None:
            rows = sorted(rows, key=lambda t: _sort_key(t, column), reverse=reverse)
        for task in rows:
            self.tasks.insert(
                "",
                "end",
                values=(
                    task.name,
                    task.status or "",
                    task.node or "",
                    task.started or "",
                    "" if task.total_time_sec is None else f"{task.total_time_sec:.2f}",
                ),
            )


def _sort_key(task: TaskInfo, column: str) -> object:
    """Ключ сортировки строки таблицы (``time`` — числовой, остальное — текст)."""
    if column == "time":
        return -1.0 if task.total_time_sec is None else task.total_time_sec
    return _text(task, column).lower()


def _text(task: TaskInfo, column: str) -> str:
    """Строковое значение колонки для сортировки/отображения."""
    if column == "task":
        return task.name
    if column == "status":
        return task.status or ""
    if column == "node":
        return task.node or ""
    return task.started or ""


def _set_text(widget: tk.Text, text: str) -> None:
    """Записывает ``text`` в disabled-``Text`` (временно включая его)."""
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    widget.insert("1.0", text)
    widget.configure(state="disabled")