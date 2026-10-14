"""Виджет области данных W2D Viewer (правая панель).

Показывает выбранный узел HDF5 одним из режимов:

- **2D** — изображение датасета: ``(R,Z)`` (если есть координаты) или
  ``(rho,theta)``, с выбором составляющей ``real``/``imag``/``abs`` и colorbar;
- **1D** — одна линия (пока минимум);
- **attrs** — текст атрибутов узла (когда рисовать нечего: выбрана группа);
- **message** — сообщение, если ничего не выбрано или размерность не
  поддерживается.

Виджет владеет переключателями ``(R,Z)/(rho,theta)``, ``real/imag/abs``,
холстом matplotlib и ``NavigationToolbar``. Окно-оркестратор лишь передаёт
готовый :class:`Selection`.
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
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.R: np.ndarray | None = None
        self.Z: np.ndarray | None = None
        self.set_coords(coords)
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

        if mode == "attrs":
            self._set_attr_text(self._attrs_text(attrs))
        elif mode == "message":
            self.ax.text(
                0.5, 0.5, message,
                ha="center", va="center", transform=self.ax.transAxes,
            )
        elif mode == "1d":
            self.ax.plot(data)
            self.ax.set_title(path, fontsize=8)
        elif mode == "2d":
            self._draw_2d(path, data)

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

    def _draw_2d(self, title: str, data: np.ndarray) -> None:
        """Рисует 2D-датасет: ``(R,Z)`` при совпадении формы, иначе ``(rho,theta)``."""
        arr = self._component(data)
        use_rz = (
            self.view_var.get() == "rz"
            and self.R is not None
            and self.R.shape == data.shape
        )
        if use_rz:
            mesh = self.ax.pcolormesh(self.R, self.Z, arr, shading="gouraud")
            self.ax.set_aspect("equal")
            self.ax.set_title(f"{title} (R,Z)", fontsize=8)
        else:
            mesh = self.ax.imshow(
                arr, origin="lower", aspect="equal", interpolation="none"
            )
            self.ax.set_title(f"{title} (rho,theta)", fontsize=8)
        self._colorbar = self.fig.colorbar(mesh, ax=self.ax, pad=0.02)

    def _component(self, data: np.ndarray) -> np.ndarray:
        """Для комплексных данных — выбранная составляющая."""
        if np.iscomplexobj(data):
            comp = self.comp_var.get()
            if comp == "real":
                return data.real
            if comp == "imag":
                return data.imag
            return np.abs(data)
        return data

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
