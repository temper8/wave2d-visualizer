"""Виджет области данных W2D Viewer (правая панель).

Показывает выбранный узел HDF5 одним из режимов:

- **2D** — изображение датасета: ``(R,Z)`` (если есть координаты) или
  ``(rho,theta)``, с выбором составляющей ``real``/``imag``/``abs`` и colorbar;
- **3D-стек** — срез файла с осью стека последней (моды ``nphi`` у merged или
  угол ``phi`` у ``total_fields.hdf5``): слайдер оси + та же отрисовка, что для
  2D (поле) или 1D (профиль); для оси ``phi`` — чекбокс «Тороидальный вид»
  (топ-вид тора: экваториальное сечение ``Z=0`` при наличии ``/geometry/R``
  либо схема-компас со стрелкой на текущем ``phi``);
- **1D** — одна или **несколько** линий против общей оси
  ``index``/``rho``/``psi`` (``rho``/``psi`` — если переданы и совпадают по
  длине у всех рядов) с подписями из атрибута ``units`` и легендой;
  комплексные данные — по выбранной составляющей ``real``/``imag``/``abs``;
- **attrs** — текст атрибутов узла (когда рисовать нечего: выбрана группа);
- **message** — сообщение, если ничего не выбрано или размерность не
  поддерживается.

Виджет владеет холстом matplotlib и ``NavigationToolbar``; набор
переключателей собирается под выбранный датасет: 2D — ``(R,Z)/(rho,theta)``
и ``real/imag/abs``, 1D — ``index/rho/psi`` (и ``real/imag/abs`` для
комплексных данных). Окно-оркестратор передаёт один узел или их список
(multi-select) как :class:`Selection`.
Сама отрисовка датасетов — в :mod:`src.wave2d.renderers` (без Tk).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

import matplotlib
matplotlib.use("TkAgg")  # до импорта pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import ttk

from src.wave2d.renderers import (
    component,
    draw_2d,
    draw_curves,
    draw_equatorial_view,
    draw_toroidal_view,
)


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
    #: Номер оси стека (последняя ось) в объединённом/производном файле.
    mode_axis: int | None = None
    #: Координаты оси стека (``/nphi``/``/phi``) для подписи слайдера.
    mode_values: np.ndarray | None = None
    #: Имя оси стека (``"nphi"``/``"phi"``) для подписи слайдера.
    mode_name: str | None = None


class DatasetView(ttk.Frame):
    """Область данных: рендеринг выбранного узла в одном из режимов."""

    def __init__(
        self,
        master,
        coords: tuple[np.ndarray, np.ndarray] | None = None,
        rho: tuple[np.ndarray, Any] | None = None,
        psi: tuple[np.ndarray, Any] | None = None,
        major_radius: np.ndarray | None = None,
        on_add_to_comparison: Callable[[Selection], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.R: np.ndarray | None = None
        self._on_add_to_comparison = on_add_to_comparison
        self.Z: np.ndarray | None = None
        self.set_coords(coords)
        self.major_radius: np.ndarray | None = None
        self._toroidal_colorbar = None
        self.set_major_radius(major_radius)
        self._axes: dict[str, tuple[np.ndarray, Any]] = {}
        self.set_axes(rho, psi)
        self._colorbar = None
        self._attr_expanded: bool | None = None
        self._selection: Selection | list[Selection] | None = None
        self._selections: list[Selection] = []
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

    def set_major_radius(self, major_radius: np.ndarray | None) -> None:
        """Задаёт большой радиус ``R(rho,theta)`` (см) для топ-вида экватора.

        ``None`` — геометрии нет: топ-вид останется схемой-компасом.
        """
        self.major_radius = (
            None if major_radius is None else np.asarray(major_radius)
        )

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
        if hasattr(self, "controls"):
            # Вызвано после сборки — пересобираем переключатели под выбор.
            self.show(self._selection)

    def _build(self) -> None:
        """Создаёт панель управления, холст, атрибуты и toolbar.

        Радиокнопки заранее не создаются: их набор зависит от выбранного
        датасета и собирается в :meth:`_rebuild_controls`.
        """
        self.controls = ttk.Frame(self)
        # Выборы переживают смену датасета: переключатели пересобираются, а
        # значения (2D-вид, составляющая, ось) сохраняются.
        self.view_var = tk.StringVar(value="rz" if self.R is not None else "rho")
        self.comp_var = tk.StringVar(value="abs")
        self.axis_var = tk.StringVar(value="index")
        self.mode_var = tk.IntVar(value=0)
        #: Чекбокс «Тороидальный вид» (топ-вид тора рядом с полоидальной картой).
        self.toroidal_var = tk.BooleanVar(value=True)
        #: Чекбокс «Заливка» (топ-вид экватора через ``pcolormesh`` вместо маркеров).
        self.fill_var = tk.BooleanVar(value=False)
        self._mode_label: ttk.Label | None = None

        # Две панели: полоидальная карта (широкая) и топ-вид тора (узкая).
        # Топ-вид скрыт, пока не запрошен чекбоксом; ``constrained`` layout
        # игнорирует невидимые оси и отдаёт всю ширину карте.
        self.fig = plt.figure(figsize=(6.5, 5.5), layout="constrained")
        grid = self.fig.add_gridspec(1, 2, width_ratios=(3, 1))
        self.ax = self.fig.add_subplot(grid[0, 0])
        self.ax_tor = self.fig.add_subplot(grid[0, 1])
        self.ax_tor.set_visible(False)
        # Больше воздуха по краям фигуры (w_pad/h_pad — в дюймах).
        self.fig.get_layout_engine().set(w_pad=0.12, h_pad=0.12)
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

    def show(
        self, selection: Selection | list[Selection] | None
    ) -> None:
        """Показывает выбор.

        ``None`` — узел не выбран; одиночный :class:`Selection` — один узел;
        список — несколько (multi-select в дереве). Сначала пересобирает
        переключатели под режим выбора, затем перерисовывает область.
        """
        self._selection = selection
        self._selections = self._as_list(selection)
        mode, _ = self._mode()
        self._rebuild_controls(mode)
        self.redraw()

    @staticmethod
    def _as_list(
        selection: Selection | list[Selection] | None,
    ) -> list[Selection]:
        """Нормализует выбор к списку (одиночный узел — список из одного)."""
        if selection is None:
            return []
        if isinstance(selection, Selection):
            return [selection]
        return list(selection)

    def redraw(self) -> None:
        """Перерисовывает область по текущему выбору и режиму."""
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
            self._colorbar = None
        self.ax.clear()
        self._hide_toroidal()

        mode, message = self._mode()
        self._layout(expanded=(mode == "attrs"))

        if mode == "attrs":
            self._set_attr_text(self._attrs_text(self._selections[0].attrs))
        elif mode == "message":
            self.ax.text(
                0.5, 0.5, message,
                ha="center", va="center", transform=self.ax.transAxes,
            )
        elif mode == "3d":
            self._draw_stacked()
        elif mode == "1d":
            self._draw_1d()
        elif mode == "2d":
            selection = self._selections[0]
            self._colorbar = draw_2d(
                self.ax,
                self.fig,
                selection.data,
                title=selection.path or "",
                view=self.view_var.get(),
                R=self.R,
                Z=self.Z,
                comp=self.comp_var.get(),
            )

        self.canvas.draw_idle()

    def _line_selections(self) -> list[Selection]:
        """Выбранные 1D-датасеты (для наложения нескольких кривых)."""
        return [
            s for s in self._selections
            if s.data is not None and s.data.ndim == 1
        ]

    def _mode(self) -> tuple[str, str]:
        """Режим и (для message) текст сообщения по текущему выбору.

        Все выбранные 1D-датасеты показываются вместе (наложение); при
        2D/группе/смешанном выборе поведение — по первому узлу (multi-select
        для 2D — отдельная задача ``p2-multiview-2d-grid-rendering``).
        """
        selections = self._selections
        if not selections:
            return "message", "Выберите узел в дереве"
        if all(s.data is not None and s.data.ndim == 1 for s in selections):
            return "1d", ""
        first = selections[0]
        if first.data is None:
            return "attrs", ""
        if first.mode_axis is not None:
            return "3d", ""
        if first.data.ndim == 1:
            return "1d", ""
        if first.data.ndim == 2:
            return "2d", ""
        return "message", f"{first.path}\nshape={first.data.shape}"

    # --- переключатели ----------------------------------------------------

    def _rebuild_controls(self, mode: str) -> None:
        """Собирает панель переключателей под текущий режим.

        Создаются только применимые к выбору кнопки: 2D — вид и
        составляющая, 1D — ось (и составляющая для комплексных данных),
        ``attrs``/``message`` — панель пуста.
        """
        for child in self.controls.winfo_children():
            child.destroy()
        self._mode_label = None

        if mode == "2d":
            self._add_view_buttons()
            self._add_comp_buttons()
        elif mode == "3d":
            self._add_stacked_controls()
        elif mode == "1d":
            lines = self._line_selections()
            self._add_axis_buttons(lines)
            if any(np.iscomplexobj(s.data) for s in lines):
                self._add_comp_buttons()
        if mode in ("1d", "2d"):
            self._add_compare_button()
    def _add_view_buttons(self) -> None:
        """2D-вид ``(R,Z)/(rho,theta)``; ``(R,Z)`` — только если есть координаты."""
        options = [("rho", "(rho,theta)")]
        if self.R is not None:
            options.insert(0, ("rz", "(R,Z)"))
        if self.view_var.get() not in [value for value, _ in options]:
            self.view_var.set("rho")
        frame = ttk.Frame(self.controls)
        frame.pack(side=tk.LEFT, padx=(0, 20))
        for value, text in options:
            ttk.Radiobutton(
                frame, text=text, variable=self.view_var, value=value,
                command=self.redraw,
            ).pack(side=tk.LEFT)

    def _add_comp_buttons(self) -> None:
        """Составляющая ``real/imag/abs`` (2D и комплексный 1D)."""
        if self.comp_var.get() not in ("real", "imag", "abs"):
            self.comp_var.set("abs")
        frame = ttk.Frame(self.controls)
        frame.pack(side=tk.LEFT, padx=(0, 20))
        for comp in ("real", "imag", "abs"):
            ttk.Radiobutton(
                frame, text=comp, variable=self.comp_var, value=comp,
                command=self.redraw,
            ).pack(side=tk.LEFT)

    def _add_axis_buttons(self, lines: list[Selection]) -> None:
        """Ось 1D: ``index`` всегда, ``rho``/``psi`` — если совпали по длине.

        При наложении нескольких рядов ось доступна, только если её длина
        совпадает с каждым рядом (иначе ряды были бы на разных x).
        """
        lengths = {len(s.data) for s in lines}
        names = ["index"] + [
            name for name, (values, _units) in self._axes.items()
            if values is not None
            and lengths
            and all(len(values) == length for length in lengths)
        ]
        if self.axis_var.get() not in names:
            self.axis_var.set("index")
        frame = ttk.Frame(self.controls)
        frame.pack(side=tk.LEFT)
        ttk.Label(frame, text="ось:").pack(side=tk.LEFT)
        for name in names:
            ttk.Radiobutton(
                frame, text=name, variable=self.axis_var, value=name,
                command=self.redraw,
            ).pack(side=tk.LEFT)

    def _add_compare_button(self) -> None:
        """Кнопка «В сравнение» — справа в строке переключателей."""
        if self._on_add_to_comparison is None:
            return
        ttk.Button(
            self.controls,
            text="В сравнение",
            command=self._emit_add_to_comparison,
        ).pack(side=tk.RIGHT)

    def _emit_add_to_comparison(self) -> None:
        """Отдаёт колбэку все показанные датасеты (multi-select — каждый)."""
        if self._on_add_to_comparison is None:
            return
        for selection in self._selections:
            if selection.data is not None:
                self._on_add_to_comparison(selection)

    # --- стек по модам (3D) ----------------------------------------------

    def _add_stacked_controls(self) -> None:
        """Переключатели стека: слайдер моды, затем вид/ось/составляющая."""
        first = self._selections[0]
        self._add_mode_scale(first)
        if first.data is None:
            return
        if first.data.ndim - 1 == 2:
            if first.mode_name == "phi":
                self._add_toroidal_toggle()
            self._add_view_buttons()
            self._add_comp_buttons()
        else:
            self._add_axis_buttons([replace(first, data=self._slice(first))])
            if np.iscomplexobj(first.data):
                self._add_comp_buttons()

    def _add_mode_scale(self, selection: Selection) -> None:
        """Горизонтальный слайдер индекса среза по оси стека (последняя ось)."""
        axis = selection.mode_axis
        count = 0 if selection.data is None or axis is None else int(selection.data.shape[axis])
        if count <= 0:
            return
        if not 0 <= self.mode_var.get() < count:
            self.mode_var.set(0)
        frame = ttk.Frame(self.controls)
        frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(frame, text="мода:").pack(side=tk.LEFT)
        tk.Scale(
            frame, from_=0, to=count - 1, orient=tk.HORIZONTAL, showvalue=False,
            variable=self.mode_var, length=150,
            command=lambda _value: self.redraw(),
        ).pack(side=tk.LEFT)
        self._mode_label = ttk.Label(frame, text=self._mode_value(selection))
        self._mode_label.pack(side=tk.LEFT, padx=(6, 0))

    def _add_toroidal_toggle(self) -> None:
        """Чекбоксы топ-вида: «Тороидальный вид» и «Заливка» экватора.

        Доступны только датасетам с осью ``phi`` (``total_fields.hdf5``) —
        то есть выставляются для каждой компоненты (``Ex``/``Ey``/``Ez``/``Ea``).
        «Заливка» включает ``pcolormesh`` вместо ``scatter`` (интерполяция
        между ``phi``); при одном угле она игнорируется.
        """
        ttk.Checkbutton(
            self.controls,
            text="Тороидальный вид",
            variable=self.toroidal_var,
            command=self.redraw,
        ).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Checkbutton(
            self.controls,
            text="Заливка",
            variable=self.fill_var,
            command=self.redraw,
        ).pack(side=tk.LEFT, padx=(0, 20))

    def _slice(self, selection: Selection) -> np.ndarray:
        """Срез по текущему индексу моды (уменьшает размерность на 1)."""
        data = selection.data
        axis = selection.mode_axis
        if data is None or axis is None:
            return np.asarray([])
        count = data.shape[axis]
        index = min(max(int(self.mode_var.get()), 0), count - 1)
        return data.take(index, axis=axis)

    def _mode_value(self, selection: Selection) -> str:
        """Подпись среза: ``nphi=<значение>``, ``phi=<град>°`` или ``#<индекс>``."""
        index = int(self.mode_var.get())
        values = selection.mode_values
        if values is None:
            return f"#{index}"
        if not 0 <= index < len(values):
            return ""
        name = selection.mode_name or "nphi"
        if name == "phi":
            return f"phi={np.rad2deg(float(values[index])):.1f}°"
        return f"{name}={int(values[index])}"

    def _draw_stacked(self) -> None:
        """Рисует срез стека по моде: 2D-карту поля или 1D-профиль."""
        selection = self._selections[0]
        if selection.data is None or selection.mode_axis is None:
            return
        sliced = self._slice(selection)
        if self._mode_label is not None:
            self._mode_label.configure(text=self._mode_value(selection))
        title = selection.path or ""
        value = self._mode_value(selection)
        if value:
            title = f"{title}  [{value}]"
        if sliced.ndim == 1:
            comp = self.comp_var.get()
            ylabel = self._ylabel(selection.path or "", selection.attrs)
            x, xlabel = self._active_axis([replace(selection, data=sliced)])
            draw_curves(
                self.ax,
                [(x, component(sliced, comp), ylabel, None)],
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
            )
        else:
            self._colorbar = draw_2d(
                self.ax, self.fig, sliced, title=title,
                view=self.view_var.get(), R=self.R, Z=self.Z,
                comp=self.comp_var.get(),
            )
            self._draw_toroidal(selection)

    def _draw_toroidal(self, selection: Selection) -> None:
        """Топ-вид тора рядом с картой, если включён и есть ось ``phi``.

        При наличии ``/geometry/R`` рисуется экваториальное сечение ``Z=0``
        (данные поля); иначе — схема-компас со стрелкой на текущем ``phi``.
        """
        if selection.mode_name != "phi" or not self.toroidal_var.get():
            return
        values = selection.mode_values
        if values is None or len(values) == 0:
            return
        index = min(max(int(self.mode_var.get()), 0), len(values) - 1)
        self.ax_tor.set_visible(True)
        self.ax_tor.clear()
        if self._draw_equatorial(selection, index):
            return
        draw_toroidal_view(
            self.ax_tor, float(values[index]), title=selection.path or ""
        )

    def _draw_equatorial(self, selection: Selection, index: int) -> bool:
        """Рисует экваториальное сечение ``Z=0`` вместо схемы-компаса.

        Возвращает ``False``, если нет ``/geometry/R`` или не найден мидплейн
        (тогда вызывающий рисует схему). Точки ``theta=0`` (наружу) и
        ``theta=180`` (внутрь) кладутся в полярные координаты по большому
        радиусу; нефизичные сентинелы ``R <= 0`` отбрасываются.
        """
        major = self.major_radius
        data = selection.data
        phi = selection.mode_values
        if major is None or data is None or phi is None:
            return False
        if data.ndim != 3 or major.shape != data.shape[:2]:
            return False
        indices = self._midplane_indices(major)
        if indices is None:
            return False
        i_out, i_in = indices
        values = component(data, self.comp_var.get())
        r_out, r_in = major[:, i_out], major[:, i_in]
        keep_out = np.isfinite(r_out) & (r_out > 0)
        keep_in = np.isfinite(r_in) & (r_in > 0)
        if not keep_out.any() or not keep_in.any():
            return False
        self._toroidal_colorbar = draw_equatorial_view(
            self.ax_tor,
            self.fig,
            phi_rad=np.asarray(phi, dtype=float),
            radius_out=r_out[keep_out],
            radius_in=r_in[keep_in],
            values_out=values[keep_out, i_out, :],
            values_in=values[keep_in, i_in, :],
            current=index,
            title=selection.path or "",
            fill=self.fill_var.get(),
        )
        return True

    def _midplane_indices(
        self, major: np.ndarray
    ) -> tuple[int, int] | None:
        """Индексы ``theta=0`` (наружу) и ``theta=180`` (внутрь) на ``Z=0``.

        При наличии ``(R,Z)`` кандидаты — столбцы с минимальным ``|Z|``;
        иначе мидплейн берётся по краям большого радиуса. ``None``, если
        мидплейна в сетке нет.
        """
        if self.Z is not None and self.Z.shape == major.shape:
            zmax = np.abs(self.Z).max(axis=0)
            span = float(zmax.max())
            if span <= 0:
                return None
            candidates = np.where(zmax <= 1e-6 * span)[0]
            if len(candidates) < 2:
                return None
            column = np.median(major[:, candidates], axis=0)
            return (
                int(candidates[int(np.argmax(column))]),
                int(candidates[int(np.argmin(column))]),
            )
        column = np.median(major, axis=0)
        return int(np.argmax(column)), int(np.argmin(column))

    def _hide_toroidal(self) -> None:
        """Прячет и очищает топ-вид (его показывает только :meth:`_draw_stacked`)."""
        if self._toroidal_colorbar is not None:
            try:
                self._toroidal_colorbar.remove()
            except Exception:
                pass
            self._toroidal_colorbar = None
        self.ax_tor.clear()
        self.ax_tor.set_visible(False)

    # --- 1D ---------------------------------------------------------------

    def _draw_1d(self) -> None:
        """Рисует 1D: один ряд или наложение нескольких с легендой."""
        lines = self._line_selections()
        if not lines:
            return
        x, xlabel = self._active_axis(lines)
        comp = self.comp_var.get()
        series = [
            (
                x,
                component(selection.data, comp),
                self._ylabel(selection.path or "", selection.attrs),
                None,
            )
            for selection in lines
        ]
        single = len(lines) == 1
        first = lines[0]
        draw_curves(
            self.ax,
            series,
            title=(first.path or "") if single else "",
            xlabel=xlabel,
            ylabel=self._ylabel(first.path or "", first.attrs) if single else "",
        )

    def _active_axis(
        self, lines: list[Selection]
    ) -> tuple[np.ndarray | None, str]:
        """Выбранная ось ``(массив, подпись)`` или ``(None, "index")``.

        Ось берётся, только если она есть и её длина совпадает с **каждым**
        рядом; иначе рендер построит линии против индекса.
        """
        name = self.axis_var.get()
        entry = self._axes.get(name)
        if entry is None:
            return None, "index"
        values, units = entry
        if values is None or not lines:
            return None, "index"
        if any(len(values) != len(s.data) for s in lines):
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
