"""Виджет области данных W2D Viewer (правая панель).

Показывает выбранный узел HDF5 одним из режимов:

- **2D** — изображение датасета: ``(R,Z)`` (если есть координаты) или
  ``(rho,theta)``, с выбором составляющей ``real``/``imag``/``abs`` и colorbar;
- **1D** — линия против оси ``index``/``rho``/``psi`` (``rho``/``psi`` —
  если переданы и совпадают по длине) с подписями из атрибута ``units``;
  комплексные данные — отдельным рендером-заглушкой (одна составляющая);
- **attrs** — текст атрибутов узла (когда рисовать нечего: выбрана группа);
- **message** — сообщение, если ничего не выбрано или размерность не
  поддерживается.

Виджет владеет переключателями ``(R,Z)/(rho,theta)``, ``real/imag/abs``,
холстом matplotlib и ``NavigationToolbar``. Окно-оркестратор лишь передаёт
готовый :class:`Selection`. Сама отрисовка датасетов — в
:mod:`src.wave2d.renderers` (без Tk).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

import matplotlib
matplotlib.use("TkAgg")  # до импорта pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import ttk

from src.wave2d.renderers import draw_1d, draw_1d_complex, draw_2d


def _units_text(units: Any) -> str:
    """Атрибут ``units`` как строка (bytes декодируются), иначе пусто."""
    if units is None:
        return ""
    if isinstance(units, bytes):
        return units.decode("utf-8", "replace").strip()
    return str(units).strip()


@dataclass
class Selection:
    """Данные выбранного узла, подготовленные оркестратором.

    Чистые данные — без Tk и ``h5py``. ``data`` — массив выбранного датасета
    (``None``, если у узла нет данных: группа или ошибка чтения), ``attrs`` —
    его атрибуты, ``kind`` — ``"group"``/``"dataset"``.
    """

    path: str | None = None
    kind: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)
    data: np.ndarray | None = None


class DatasetView(ttk.Frame):
    """Область данных: рендеринг выбранного узла в одном из режимов."""

    def __init__(
        self,
        master,
        coords: tuple[np.ndarray, np.ndarray] | None = None,
        rho: tuple[np.ndarray, Any] | None = None,
        psi: tuple[np.ndarray, Any] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.R: np.ndarray | None = None
        self.Z: np.ndarray | None = None
        self.set_coords(coords)
        self._axes: dict[str, tuple[np.ndarray, Any]] = {}
        self.set_axes(rho, psi)
        self._colorbar = None
        self._attr_expanded: bool | None = None
        self._selection: Selection | None = None
        self._build()

    # --- настройка -------------------------------------------------------

    def set_coords(
        self,
        coords: tuple[np.ndarray, np.ndarray] | None,
    ) -> None:
        """Задаёт координаты ``(R, Z)`` для физического вида.

        ``None`` — координат нет, доступен только вид ``(rho,theta)``.
        """
        if coords is None:
            self.R = self.Z = None
        else:
            self.R, self.Z = coords

    def set_axes(
        self,
        rho: tuple[np.ndarray, Any] | None = None,
        psi: tuple[np.ndarray, Any] | None = None,
    ) -> None:
        """Задаёт 1D-оси как пары ``(массив, units)`` для ``rho`` и/или ``psi``.

        ``None`` — оси нет (или её данные не прочитались): в переключателе
        осей она будет недоступна, отрисовка пойдёт против индекса.
        """
        self._axes = {}
        if rho is not None:
            self._axes["rho"] = rho
        if psi is not None:
            self._axes["psi"] = psi
        if hasattr(self, "_axis_buttons"):
            self._sync_axis_buttons()

    def _build(self) -> None:
        """Создаёт переключатели, холст, атрибуты и toolbar."""
        controls = self.controls = ttk.Frame(self)

        default_view = "rz" if self.R is not None else "rho"
        self.view_var = tk.StringVar(value=default_view)
        ttk.Radiobutton(
            controls, text="(R,Z)", variable=self.view_var, value="rz",
            command=self.redraw,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            controls, text="(rho,theta)", variable=self.view_var, value="rho",
            command=self.redraw,
        ).pack(side=tk.LEFT, padx=(0, 20))

        self.comp_var = tk.StringVar(value="abs")
        for comp in ("real", "imag", "abs"):
            ttk.Radiobutton(
                controls, text=comp, variable=self.comp_var, value=comp,
                command=self.redraw,
            ).pack(side=tk.LEFT)

        # Переключатель оси 1D: показывается только в 1D-режиме (см. _sync_axis_visibility).
        self.axis_var = tk.StringVar(value="index")
        self.axis_frame = ttk.Frame(controls)
        self._axis_buttons: dict[str, ttk.Radiobutton] = {}
        ttk.Label(self.axis_frame, text="ось:").pack(side=tk.LEFT)
        for name in ("index", "rho", "psi"):
            button = ttk.Radiobutton(
                self.axis_frame, text=name, variable=self.axis_var,
                value=name, command=self.redraw,
            )
            button.pack(side=tk.LEFT)
            self._axis_buttons[name] = button
        self._sync_axis_buttons()

        self.fig, self.ax = plt.subplots(figsize=(6.5, 5.5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()

        # Панель атрибутов показывается только в режиме attrs и занимает всю
        # область (см. _layout).
        attr_frame = self.attr_frame = ttk.Frame(self)
        self.attr_text = tk.Text(attr_frame, height=1, state="disabled", wrap="word")
        attr_sb = ttk.Scrollbar(
            attr_frame, orient="vertical", command=self.attr_text.yview
        )
        self.attr_text.configure(yscrollcommand=attr_sb.set)
        self.attr_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attr_sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        self.toolbar.update()

        self._layout(expanded=False)

    def _layout(self, expanded: bool) -> None:
        """Перекладывает область.

        ``expanded=True`` (режим attrs) — панель атрибутов занимает всё;
        ``False`` — показаны переключатели, холст и toolbar, атрибуты скрыты.
        """
        if self._attr_expanded == expanded:
            return
        self._attr_expanded = expanded
        for widget in (
            self.controls, self.canvas_widget, self.toolbar, self.attr_frame
        ):
            widget.pack_forget()
        if expanded:
            self.attr_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        else:
            self.controls.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
            self.canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self.toolbar.pack(side=tk.BOTTOM)

    # --- показ -----------------------------------------------------------

    def show(self, selection: Selection | None) -> None:
        """Показывает выбор (``None`` — узел не выбран)."""
        self._selection = selection
        self.redraw()

    def redraw(self) -> None:
        """Перерисовывает область по текущему выбору и режиму."""
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
            self._colorbar = None
        self.ax.clear()

        selection = self._selection
        data = selection.data if selection is not None else None
        path = selection.path if selection is not None else ""
        attrs = selection.attrs if selection is not None else {}

        mode, message = self._mode(selection, data, path)
        self._layout(expanded=(mode == "attrs"))
        self._sync_axis_visibility(mode)

        if mode == "attrs":
            self._set_attr_text(self._attrs_text(attrs))
        elif mode == "message":
            self.ax.text(
                0.5, 0.5, message,
                ha="center", va="center", transform=self.ax.transAxes,
            )
        elif mode == "1d":
            self._draw_1d(data, path, attrs)
        elif mode == "2d":
            self._colorbar = draw_2d(
                self.ax,
                self.fig,
                data,
                title=path,
                view=self.view_var.get(),
                R=self.R,
                Z=self.Z,
                comp=self.comp_var.get(),
            )

        self.canvas.draw_idle()

    @staticmethod
    def _mode(
        selection: Selection | None,
        data: np.ndarray | None,
        path: str,
    ) -> tuple[str, str]:
        """Определяет режим и (для message) текст сообщения."""
        if selection is None:
            return "message", "Выберите узел в дереве"
        if data is None:
            return "attrs", ""
        if data.ndim == 1:
            return "1d", ""
        if data.ndim == 2:
            return "2d", ""
        return "message", f"{path}\nshape={data.shape}"

    # --- 1D ---------------------------------------------------------------

    def _sync_axis_visibility(self, mode: str) -> None:
        """Показывает переключатель оси только в 1D-режиме."""
        managed = self.axis_frame.winfo_manager()
        if mode == "1d" and not managed:
            self.axis_frame.pack(side=tk.LEFT, padx=(12, 0))
        elif mode != "1d" and managed:
            self.axis_frame.pack_forget()

    def _sync_axis_buttons(self) -> None:
        """Доступные оси — активны (``index`` всегда), недоступные — disabled."""
        for name, button in self._axis_buttons.items():
            if name == "index" or name in self._axes:
                button.state(["!disabled"])
            else:
                button.state(["disabled"])
        if self.axis_var.get() != "index" and self.axis_var.get() not in self._axes:
            self.axis_var.set("index")

    def _draw_1d(self, data: np.ndarray, path: str, attrs: dict) -> None:
        """Рисует 1D: вещественный — линией, комплексный — заглушкой."""
        x, xlabel = self._active_axis(data)
        ylabel = self._ylabel(path, attrs)
        if np.iscomplexobj(data):
            draw_1d_complex(
                self.ax, data, title=path, x=x, xlabel=xlabel,
                ylabel=ylabel, comp=self.comp_var.get(),
            )
        else:
            draw_1d(
                self.ax, data, title=path, x=x, xlabel=xlabel, ylabel=ylabel
            )

    def _active_axis(
        self, data: np.ndarray
    ) -> tuple[np.ndarray | None, str]:
        """Выбранная ось ``(массив, подпись)`` или ``(None, "index")``.

        Ось берётся только если она есть и её длина совпадает с ``len(data)``;
        иначе рендер построит линию против индекса.
        """
        name = self.axis_var.get()
        entry = self._axes.get(name)
        if entry is None:
            return None, "index"
        values, units = entry
        if values is None or len(values) != len(data):
            return None, "index"
        text = _units_text(units)
        return values, (f"{name}, {text}" if text else name)

    @staticmethod
    def _ylabel(path: str, attrs: dict) -> str:
        """Подпись Y: имя датасета + ``units`` (если есть)."""
        name = path.rsplit("/", 1)[-1]
        units = _units_text(attrs.get("units"))
        return f"{name}, {units}" if units else name

    # --- атрибуты --------------------------------------------------------

    @staticmethod
    def _attrs_text(attrs: dict[str, Any]) -> str:
        lines = [f"{k} = {v}" for k, v in attrs.items()] or ["(атрибутов нет)"]
        return "\n".join(lines)

    def _set_attr_text(self, text: str) -> None:
        """Заменяет содержимое панели атрибутов (панель только для чтения)."""
        self.attr_text.configure(state="normal")
        self.attr_text.delete("1.0", tk.END)
        self.attr_text.insert("1.0", text)
        self.attr_text.configure(state="disabled")

    # --- служебное -------------------------------------------------------

    def close(self) -> None:
        """Освобождает matplotlib-ресурсы (при закрытии окна)."""
        try:
            self.canvas.get_tk_widget().destroy()
        except tk.TclError:
            pass
        plt.close(self.fig)
