"""Виджет области данных W2D Viewer (правая панель).

Показывает выбранный узел HDF5 одним из режимов:

- **2D** — изображение датасета: ``(R,Z)`` (если есть координаты) или
  ``(rho,theta)``, с выбором составляющей ``real``/``imag``/``abs`` и colorbar;
- **3D-стек** — срез файла с осью стека последней (моды ``nphi`` у merged или
  угол ``phi`` у ``total_fields.hdf5``): слайдер оси + та же отрисовка, что для
  2D (поле) или 1D (профиль); экватор ``Z=0`` (топ-вид тора) для оси ``phi``
  включается чекбоксом **Equator (Z=0)** (по умолчанию **включён**; при
  наличии ``/geometry/R`` — сечение, иначе схема-компас со стрелкой на текущем
  ``phi``); для одной моды ``nphi`` — тем же чекбоксом (по умолчанию
  **выключен**), при этом поле реконструируется как ``An(n)·e^{i·n·phi}·E_n``,
  добавляется **второй слайдер** угла ``phi`` и переключатель **Ring / Flat
  (R,phi)** (полярный топ-вид или плоская развёртка ``R``×``phi``); у 2D-среза
  стека есть кнопка **Animate** (перебор кадров по оси стека, ``MP4`` — см.
  :meth:`W2DViewer._animate`);
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

import textwrap

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
    draw_equatorial_map,
    draw_equatorial_view,
    draw_toroidal_view,
)

#: Число точек тороидального угла при реконструкции одной моды ``nphi`` (1°).
PHI_SAMPLES = 360


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

    #: Ширина переноса подписи прогона (символов) — держим в несколько строк.
    _FOOTER_WRAP = 110
    #: Максимум строк подписи; длиннее — обрезаем и ставим «…» в конце.
    _FOOTER_MAX_LINES = 2

    def __init__(
        self,
        master,
        coords: tuple[np.ndarray, np.ndarray] | None = None,
        rho: tuple[np.ndarray, Any] | None = None,
        psi: tuple[np.ndarray, Any] | None = None,
        major_radius: np.ndarray | None = None,
        spectrum_an: dict[int, complex] | None = None,
        on_add_to_comparison: Callable[[Selection], None] | None = None,
        on_animate: Callable[[], None] | None = None,
        run_footer: tuple[str | None, str | None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.R: np.ndarray | None = None
        self._on_add_to_comparison = on_add_to_comparison
        self._on_animate = on_animate
        #: Имя/описание прогона, рисуемые под фигурой (``supxlabel``).
        self._run_footer: tuple[str | None, str | None] = run_footer or (None, None)
        self.Z: np.ndarray | None = None
        self.set_coords(coords)
        self.major_radius: np.ndarray | None = None
        self.spectrum_an: dict[int, complex] = {}
        self._toroidal_colorbar = None
        self.set_major_radius(major_radius)
        self.set_spectrum_an(spectrum_an)
        self._axes: dict[str, tuple[np.ndarray, Any]] = {}
        self.set_axes(rho, psi)
        self._colorbar = None
        #: Фиксированные пределы шкалы цвета (``(vmin, vmax)``) на время анимации.
        self._clim: tuple[float, float] | None = None
        #: То же для панели экватора (реконструкция моды ``nphi`` может отличаться).
        self._equator_clim: tuple[float, float] | None = None
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

    def set_spectrum_an(
        self, spectrum_an: dict[int, complex] | None
    ) -> None:
        """Задаёт веса ``An(n)`` спектра антенны для реконструкции моды ``nphi``.

        ``None``/пусто — реконструкция одной моды считает вес равным ``1``.
        """
        self.spectrum_an = {
            int(k): complex(v) for k, v in (spectrum_an or {}).items()
        }

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

    def set_run_footer(
        self, name: str | None, description: str | None = None
    ) -> None:
        """Задаёт имя/описание прогона для подписи под фигурой (``None`` — убрать)."""
        self._run_footer = (name, description)
        if hasattr(self, "footer_var"):
            self.redraw()

    def _build(self) -> None:
        """Создаёт панель управления, холст, атрибуты и toolbar.

        Радиокнопки заранее не создаются: их набор зависит от выбранного
        датасета и собирается в :meth:`_rebuild_controls`.
        """
        self.controls = ttk.Frame(self)
        #: Вторая строка переключателей (угол + экватор) — не влезает в одну.
        self.controls_row2 = ttk.Frame(self)
        # Выборы переживают смену датасета: переключатели пересобираются, а
        # значения (2D-вид, составляющая, ось) сохраняются.
        self.view_var = tk.StringVar(value="rz" if self.R is not None else "rho")
        self.comp_var = tk.StringVar(value="abs")
        self.axis_var = tk.StringVar(value="index")
        #: Чекбокс «Footer»: показывать имя/описание прогона на картинке.
        self.footer_var = tk.BooleanVar(value=True)
        self.mode_var = tk.IntVar(value=0)
        #: Слайдер тороидального угла (реконструкция одной моды ``nphi``).
        self.phi_var = tk.IntVar(value=0)
        #: Чекбокс «Equator (Z=0)» для моды ``nphi`` (по умолчанию выключен).
        self.toroidal_var = tk.BooleanVar(value=False)
        #: Чекбокс экватора для оси ``phi`` (``total_fields.hdf5``) — включён.
        self.phi_toroidal_var = tk.BooleanVar(value=True)
        #: Чекбокс «Fill» (экватор через ``pcolormesh`` вместо маркеров).
        self.fill_var = tk.BooleanVar(value=False)
        #: Переключатель вида экватора: ``ring`` (полярный) или ``flat`` (R,phi).
        self.equator_view_var = tk.StringVar(value="ring")
        self._mode_label: ttk.Label | None = None
        self._phi_label: ttk.Label | None = None

        # Две панели: полоидальная карта (широкая) и топ-вид тора (узкая).
        # Топ-вид скрыт, пока не запрошен чекбоксом; пока он скрыт, карта
        # занимает обе колонки (см. :meth:`_set_toroidal`).
        self.fig = plt.figure(figsize=(6.5, 5.5), layout="constrained")
        self._grid = self.fig.add_gridspec(1, 2, width_ratios=(3, 1))
        # По умолчанию карта занимает обе колонки: пока топ-вид скрыт,
        # constrained layout иначе оставлял бы справа пустую четверть.
        self.ax = self.fig.add_subplot(self._grid[0, :])
        self.ax_tor = self.fig.add_subplot(self._grid[0, 1])
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
            self.controls, self.controls_row2, self.canvas_widget,
            self.toolbar, self.attr_frame,
        ):
            widget.pack_forget()
        if expanded:
            self.attr_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        else:
            self.controls.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(4, 0))
            self.controls_row2.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 4))
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

        self._apply_run_footer()
        self.canvas.draw_idle()

    def _apply_run_footer(self) -> None:
        """Рисует подпись ``<name>: <description>`` под фигурой (``supxlabel``).

        Текст figure-level: имя и описание объединяются в одну строку
        ``<name>: <description>``, затем переносятся по ширине
        (:attr:`_FOOTER_WRAP`). Всего не больше :attr:`_FOOTER_MAX_LINES`
        строк: если длиннее — хвост обрезается и ставится «…». Текст попадает
        и на экран, и в сохранённый PNG, и в кадры анимации. При выключенном
        чекбоксе «Footer» или пустых строках подпись снимается.
        """
        name, description = self._run_footer
        if not self.footer_var.get() or not (name or description):
            self.fig.supxlabel("")
            return
        parts = [str(part) for part in (name, description) if part]
        text = ": ".join(parts)
        lines = textwrap.wrap(text, width=self._FOOTER_WRAP) or [text]
        if len(lines) > self._FOOTER_MAX_LINES:
            lines = lines[: self._FOOTER_MAX_LINES]
            lines[-1] = lines[-1][: self._FOOTER_WRAP - 1].rstrip() + "…"
        self.fig.supxlabel("\n".join(lines), fontsize=9)

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
            return "message", "Select a node in the tree"
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
        for parent in (self.controls, self.controls_row2):
            for child in parent.winfo_children():
                child.destroy()
        self._mode_label = None
        self._phi_label = None

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
        if mode in ("1d", "2d", "3d") and any(self._run_footer):
            self._add_footer_toggle()

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
        ttk.Label(frame, text="axis:").pack(side=tk.LEFT)
        for name in names:
            ttk.Radiobutton(
                frame, text=name, variable=self.axis_var, value=name,
                command=self.redraw,
            ).pack(side=tk.LEFT)

    def _add_animate_button(self) -> None:
        """Кнопка «Animate» — справа в строке переключателей стека.

        Появляется только у 2D-срезов с осью стека (моды ``nphi`` у merged или
        угол ``phi`` у ``total_fields.hdf5``) и только если оркестратор задал
        обработчик ``on_animate``. Сам процесс — во viewer.
        """
        if self._on_animate is None:
            return
        ttk.Button(
            self.controls, text="Animate", command=self._on_animate,
        ).pack(side=tk.RIGHT)

    def _add_compare_button(self) -> None:
        """Кнопка «В сравнение» — справа в строке переключателей."""
        if self._on_add_to_comparison is None:
            return
        ttk.Button(
            self.controls,
            text="Add to comparison",
            command=self._emit_add_to_comparison,
        ).pack(side=tk.RIGHT)

    def _emit_add_to_comparison(self) -> None:
        """Отдаёт колбэку все показанные датасеты (multi-select — каждый)."""
        if self._on_add_to_comparison is None:
            return
        for selection in self._selections:
            if selection.data is not None:
                self._on_add_to_comparison(selection)

    def _add_footer_toggle(self) -> None:
        """Чекбокс «Footer»: показывать имя/описание прогона на картинке."""
        ttk.Checkbutton(
            self.controls,
            text="Footer",
            variable=self.footer_var,
            command=self.redraw,
        ).pack(side=tk.RIGHT)

    # --- стек по модам (3D) ----------------------------------------------

    def _add_stacked_controls(self) -> None:
        """Переключатели стека: слайдер моды/угла, затем вид/ось/составляющая.

        Для одной моды ``nphi`` с геометрией экватор ``Z=0`` включается
        чекбоксом (по умолчанию выключен); при включении добавляются слайдер
        тороидального угла и переключатели Ring / Flat (R,phi). Для оси ``phi``
        экватор включён всегда.
        """
        first = self._selections[0]
        self._add_mode_scale(first)
        if first.data is None:
            return
        if first.data.ndim - 1 == 2:
            if first.mode_name == "phi" or self._equatorial_ready(first):
                self._add_equator_controls(first)
            self._add_view_buttons()
            self._add_comp_buttons()
            self._add_animate_button()
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
        ttk.Label(
            frame,
            text="angle:" if selection.mode_name == "phi" else "mode:",
        ).pack(side=tk.LEFT)
        tk.Scale(
            frame, from_=0, to=count - 1, orient=tk.HORIZONTAL, showvalue=False,
            variable=self.mode_var, length=150,
            command=lambda _value: self.redraw(),
        ).pack(side=tk.LEFT)
        self._mode_label = ttk.Label(frame, text=self._mode_value(selection))
        self._mode_label.pack(side=tk.LEFT, padx=(6, 0))

    def _add_angle_scale(self) -> None:
        """Второй слайдер: тороидальный угол для реконструкции одной моды ``nphi``.

        Слайдер идёт по равномерной сетке :data:`PHI_SAMPLES` на ``[0, 2π)``;
        один его шаг — ``1°``.
        """
        if not 0 <= self.phi_var.get() < PHI_SAMPLES:
            self.phi_var.set(0)
        frame = ttk.Frame(self.controls_row2)
        frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(frame, text="angle:").pack(side=tk.LEFT)
        tk.Scale(
            frame, from_=0, to=PHI_SAMPLES - 1, orient=tk.HORIZONTAL,
            showvalue=False, variable=self.phi_var, length=150,
            command=lambda _value: self.redraw(),
        ).pack(side=tk.LEFT)
        self._phi_label = ttk.Label(frame, text=f"phi={self.phi_var.get()}°")
        self._phi_label.pack(side=tk.LEFT, padx=(6, 0))

    def _equator_var(self, selection: Selection) -> tk.BooleanVar:
        """Чекбокс экватора для выбора: у оси ``phi`` он свой (включён)."""
        if selection.mode_name == "phi":
            return self.phi_toroidal_var
        return self.toroidal_var

    def _add_equator_controls(self, selection: Selection) -> None:
        """Экватор ``Z=0``: переключатель опции и зависимые контролы.

        Управляется чекбоксом ``Equator (Z=0)``: для оси ``phi``
        (``total_fields.hdf5``) он по умолчанию **включён**, для одной моды
        ``nphi`` (merged-файл) — **выключен**. При включении для моды ``nphi``
        добавляется слайдер тороидального угла :meth:`_add_angle_scale`; при
        выключении экватор не рисуется и не считается. «Ring» — полярный
        топ-вид (кольцо), «Flat (R,phi)» — плоская развёртка ``R``×``phi``;
        «Fill» включает ``pcolormesh`` вместо ``scatter``.
        """
        var = self._equator_var(selection)
        ttk.Checkbutton(
            self.controls_row2,
            text="Equator (Z=0)",
            variable=var,
            command=self._equator_toggled,
        ).pack(side=tk.LEFT, padx=(0, 20))
        if not var.get():
            return
        if selection.mode_name != "phi":
            self._add_angle_scale()
        frame = ttk.Frame(self.controls_row2)
        frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(
            frame, text="Ring", variable=self.equator_view_var,
            value="ring", command=self.redraw,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            frame, text="Flat (R,phi)", variable=self.equator_view_var,
            value="flat", command=self.redraw,
        ).pack(side=tk.LEFT)
        ttk.Checkbutton(
            self.controls_row2,
            text="Fill",
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

    # --- анимация (оркестратор — viewer) ---------------------------------

    def stacked_selection(self) -> Selection | None:
        """Первый выбранный датасет с осью стека (режим 3D) или ``None``."""
        for selection in self._selections:
            if selection.data is not None and selection.mode_axis is not None:
                return selection
        return None

    def stack_length(self) -> int:
        """Число кадров по оси стека (``0``, если датасета с осью нет)."""
        selection = self.stacked_selection()
        if selection is None or selection.mode_axis is None:
            return 0
        return int(selection.data.shape[selection.mode_axis])

    def set_color_limits(
        self,
        clim: tuple[float, float] | None,
        equator_clim: tuple[float, float] | None = None,
    ) -> None:
        """Фиксирует (``clim``) или отпускает (``None``) шкалы цвета и перерисовывает.

        Первая пара — основная карта, вторая — панель экватора ``Z=0``.
        """
        self._clim = clim
        self._equator_clim = equator_clim
        self.redraw()

    def global_color_limits(self) -> tuple[float, float] | None:
        """Диапазон выбранной составляющей по всему стеку (для фиксации шкалы).

        Считается по всей оси стека (не только по текущему срезу), чтобы
        шкала цвета не плавала от кадра к кадру. Нечисловые (``NaN``/``inf``)
        точки игнорируются.
        """
        selection = self.stacked_selection()
        if selection is None:
            return None
        values = np.asarray(component(selection.data, self.comp_var.get()))
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return None
        return float(finite.min()), float(finite.max())

    def animation_color_limits(
        self,
    ) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        """Пределы шкал ``(карта, экватор)`` на всю анимацию.

        Карта — диапазон составляющей по всему стеку. Экватор для оси ``phi``
        берётся из тех же данных (подмножество), для оси ``nphi`` — из
        реконструкции ``An(n)·e^{i·n·phi}·E_n`` (диапазон по всем модам).
        ``None`` — экватор не включён или геометрии нет.
        """
        main = self.global_color_limits()
        selection = self.stacked_selection()
        if selection is None:
            return main, None
        if selection.mode_name == "phi":
            return main, main
        if selection.mode_name == "nphi" and self._equatorial_ready(selection):
            return main, self._nphi_equator_limits(selection)
        return main, None

    def _nphi_equator_limits(
        self, selection: Selection
    ) -> tuple[float, float] | None:
        """Диапазон значений экватора-реконструкции по всем модам.

        Для ``abs`` — ``[0, max|An·E|]``; для ``real``/``imag`` — ``[-b, b]``,
        где ``b = max|An·E|`` (фаза ``e^{i·n·phi}`` не меняет модуль).
        """
        modes = selection.mode_values
        data = selection.data
        major = self.major_radius
        if modes is None or data is None or major is None or len(modes) == 0:
            return None
        indices = self._midplane_indices(major)
        if indices is None:
            return None
        i_out, i_in = indices
        peak = 0.0
        for imode in range(len(modes)):
            weight = abs(self.spectrum_an.get(int(modes[imode]), 1.0 + 0.0j))
            for column in (i_out, i_in):
                block = np.abs(data[:, column, imode])
                if block.size:
                    peak = max(peak, float(np.nanmax(block)) * weight)
        if peak <= 0:
            return None
        if self.comp_var.get() == "abs":
            return 0.0, peak
        return -peak, peak

    def render_frame(self, index: int) -> np.ndarray:
        """Ставит срез по индексу оси стека, рисует холст и возвращает ``RGB``-кадр."""
        self.mode_var.set(int(index))
        self.redraw()
        self.canvas.draw()
        rgba = np.asarray(self.canvas.buffer_rgba())
        return np.ascontiguousarray(rgba[..., :3])

    def _stack_span_token(self, selection: Selection) -> str | None:
        """Токен размаха оси стека по модам: ``-122..+122``.

        Только для оси ``nphi`` (merged), берётся фактический min..max по
        :attr:`Selection.mode_values`. Угол ``phi`` (total_fields) всегда
        покрывает полный оборот, поэтому его диапазон в имени не пишется —
        важнее число шагов (:meth:`_phi_samples_token`). ``None`` — данных нет.
        """
        if selection.mode_name != "nphi":
            return None
        values = selection.mode_values
        if values is None or len(values) == 0:
            return None
        array = np.asarray(values)
        return f"{int(array.min()):+d}..{int(array.max()):+d}"

    def _phi_samples_token(self, selection: Selection) -> str | None:
        """Токен числа шагов по phi: ``phi_samples=180``.

        Только для оси ``phi`` (total_fields): диапазон всегда полный оборот,
        а разбиение может быть разным — в имени важно именно число шагов
        (длина оси ``/phi``). ``None`` — другая ось или данных нет.
        """
        if selection.mode_name != "phi":
            return None
        values = selection.mode_values
        if values is None or len(values) == 0:
            return None
        return f"phi_samples={len(values)}"

    def animation_tokens(self) -> list[str]:
        """Токены имени файла анимации: поле, ось, размах и шаги по phi.

        Имя поля берётся как в файле (``Ex``, ``Ea``, …). Далее — ось стека,
        затем размах мод (``-122..+122`` у ``nphi``) либо число шагов по phi
        (``phi_samples=180`` у ``phi``). Умолчательные состояния не пишутся:
        вид ``rho`` и выключенный экватор опускаются, составляющая — только для
        комплексных полей. Токен ``scale_*`` добавляет viewer (он знает выбор
        в диалоге Animate).
        """
        selection = self.stacked_selection()
        if selection is None:
            return []
        field = (selection.path or "").rsplit("/", 1)[-1] or "field"
        tokens = [field, selection.mode_name or "axis"]
        for token in (
            self._stack_span_token(selection),
            self._phi_samples_token(selection),
        ):
            if token:
                tokens.append(token)
        if np.iscomplexobj(selection.data):
            tokens.append(self.comp_var.get())
        if self.view_var.get() == "rz":
            tokens.append("rz")
        if self._equator_active(selection):
            tokens.append(f"eq-{self.equator_view_var.get()}")
            if self.fill_var.get():
                tokens.append("fill")
        return tokens

    def _equator_active(self, selection: Selection) -> bool:
        """Включён ли экватор и есть ли для него данные (иначе не рисуется)."""
        return self._equator_var(selection).get() and self._equatorial_ready(
            selection
        )

    def _draw_stacked(self) -> None:
        """Рисует срез стека по моде: 2D-карту поля или 1D-профиль."""
        selection = self._selections[0]
        if selection.data is None or selection.mode_axis is None:
            return
        sliced = self._slice(selection)
        if self._mode_label is not None:
            self._mode_label.configure(text=self._mode_value(selection))
        if self._phi_label is not None:
            self._phi_label.configure(text=f"phi={int(self.phi_var.get())}°")
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
            # Топ-вид — до карты: он меняет раскладку осей, а цветовая шкала
            # карты должна создаваться уже для суженной оси.
            self._draw_toroidal(selection)
            self._colorbar = draw_2d(
                self.ax, self.fig, sliced, title=title,
                view=self.view_var.get(), R=self.R, Z=self.Z,
                comp=self.comp_var.get(),
                vmin=None if self._clim is None else self._clim[0],
                vmax=None if self._clim is None else self._clim[1],
            )

    def _equator_toggled(self) -> None:
        """Пересобирает контролы после включения/выключения экватора.

        Делается отложенно (``after_idle``): чекбокс, вызвавший команду, будет
        уничтожен при перестроении панели — нельзя делать это внутри его
        обработчика.
        """
        selection = self._selection
        self.after_idle(lambda: self.show(selection))

    def _equator_enabled(self, selection: Selection) -> bool:
        """Включён ли экватор: по чекбоксу (у оси ``phi`` — свой)."""
        return bool(self._equator_var(selection).get())

    def _draw_toroidal(self, selection: Selection) -> None:
        """Топ-вид экватора рядом с картой, если включён.

        Для оси ``phi`` — экваториальное сечение из данных (или схема-компас
        без ``/geometry/R``). Для оси ``nphi`` — реконструкция одной моды
        ``An(n)·e^{i·n·phi}·E_n``; без геометрии топ-вид не рисуется. При
        выключенном экваторе реконструкция не считается вовсе.
        """
        if not self._equator_enabled(selection) or selection.data is None:
            return
        ready = selection.mode_name == "phi" or (
            selection.mode_name == "nphi" and self._equatorial_ready(selection)
        )
        if not ready:
            return
        self._set_toroidal(True)
        self.ax_tor.clear()
        if self._draw_equatorial(selection):
            return
        # Фолбэк: схема-компас без данных (только для оси phi).
        values = selection.mode_values
        if selection.mode_name != "phi" or values is None or len(values) == 0:
            self._set_toroidal(False)
            return
        index = min(max(int(self.mode_var.get()), 0), len(values) - 1)
        draw_toroidal_view(
            self.ax_tor, float(values[index]), title=selection.path or ""
        )

    def _equatorial_ready(self, selection: Selection) -> bool:
        """Есть ли геометрия и мидплейн для экваториального сечения ``Z=0``."""
        major = self.major_radius
        data = selection.data
        if major is None or data is None or data.ndim != 3:
            return False
        if selection.mode_name not in ("phi", "nphi"):
            return False
        if major.shape != data.shape[:2]:
            return False
        return self._midplane_indices(major) is not None

    def _draw_equatorial(self, selection: Selection) -> bool:
        """Рисует экваториальное сечение ``Z=0`` (Ring или Flat).

        Возвращает ``False``, если нет ``/geometry/R`` или мидплейна. Для оси
        ``phi`` берутся данные по углам; для оси ``nphi`` — реконструкция
        одной моды на сетке углов :data:`PHI_SAMPLES`.
        """
        major = self.major_radius
        data = selection.data
        if major is None or data is None or data.ndim != 3:
            return False
        if major.shape != data.shape[:2]:
            return False
        indices = self._midplane_indices(major)
        if indices is None:
            return False
        i_out, i_in = indices
        if selection.mode_name == "phi":
            built = self._equatorial_from_phi(selection, i_out, i_in)
        elif selection.mode_name == "nphi":
            built = self._equatorial_single_mode(selection, i_out, i_in)
        else:
            return False
        if built is None:
            return False
        phi_rad, r_out, r_in, values_out, values_in, current = built
        keep_out = np.isfinite(r_out) & (r_out > 0)
        keep_in = np.isfinite(r_in) & (r_in > 0)
        if not keep_out.any() or not keep_in.any():
            return False
        kwargs = dict(
            phi_rad=phi_rad,
            radius_out=r_out[keep_out],
            radius_in=r_in[keep_in],
            values_out=values_out[keep_out],
            values_in=values_in[keep_in],
            current=current,
            title=selection.path or "",
            fill=self.fill_var.get(),
            vmin=None if self._equator_clim is None else self._equator_clim[0],
            vmax=None if self._equator_clim is None else self._equator_clim[1],
        )
        if self.equator_view_var.get() == "flat":
            self._toroidal_colorbar = draw_equatorial_map(
                self.ax_tor, self.fig, **kwargs
            )
        else:
            self._toroidal_colorbar = draw_equatorial_view(
                self.ax_tor, self.fig, **kwargs
            )
        return True

    def _equatorial_from_phi(
        self, selection: Selection, i_out: int, i_in: int
    ) -> tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int
    ] | None:
        """Экватор для оси ``phi``: ``(phi, R_out, R_in, V_out, V_in, cur)``."""
        phi = selection.mode_values
        data = selection.data
        major = self.major_radius
        if phi is None or data is None or major is None or len(phi) == 0:
            return None
        index = min(max(int(self.mode_var.get()), 0), len(phi) - 1)
        values = component(data, self.comp_var.get())
        return (
            np.asarray(phi, dtype=float),
            major[:, i_out], major[:, i_in],
            values[:, i_out, :], values[:, i_in, :],
            index,
        )

    def _equatorial_single_mode(
        self, selection: Selection, i_out: int, i_in: int
    ) -> tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int
    ] | None:
        """Реконструкция экватора одной моды ``nphi``: ``An(n)·e^{i·n·phi}·E_n``.

        Угол — равномерная сетка :data:`PHI_SAMPLES` на ``[0, 2π)``; вес
        ``An(n)`` берётся из спектра (``1``, если его нет). Возвращает
        ``(phi_rad, R_out, R_in, V_out, V_in, current)``.
        """
        modes = selection.mode_values
        data = selection.data
        major = self.major_radius
        if modes is None or data is None or major is None or len(modes) == 0:
            return None
        imode = min(max(int(self.mode_var.get()), 0), len(modes) - 1)
        n = int(modes[imode])
        weight = self.spectrum_an.get(n, 1.0 + 0.0j)
        phi = np.arange(PHI_SAMPLES, dtype=float) * (2.0 * np.pi / PHI_SAMPLES)
        wave = weight * np.exp(1.0j * n * phi)
        comp = self.comp_var.get()
        e_out = data[:, i_out, imode]
        e_in = data[:, i_in, imode]
        values_out = component(e_out[:, None] * wave[None, :], comp)
        values_in = component(e_in[:, None] * wave[None, :], comp)
        current = min(max(int(self.phi_var.get()), 0), PHI_SAMPLES - 1)
        return (
            phi,
            major[:, i_out], major[:, i_in],
            values_out, values_in,
            current,
        )

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
        self._set_toroidal(False)

    def _set_toroidal(self, visible: bool) -> None:
        """Раскладка: одна карта на всю ширину или карта + топ-вид экватора.

        Пока топ-вид скрыт, основная ось занимает обе колонки ``gridspec`` —
        иначе ``constrained`` layout отдавал бы ей только 3/4 ширины и график
        был бы смещён влево.
        """
        spec = self._grid[0, 0] if visible else self._grid[0, :]
        self.ax.set_subplotspec(spec)
        self.ax_tor.set_visible(visible)

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
        lines = [f"{k} = {v}" for k, v in attrs.items()] or ["(no attributes)"]
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
