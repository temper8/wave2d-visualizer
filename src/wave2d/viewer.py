"""GUI-просмотрщик HDF5-файлов результатов Wave2D (``results.h5``/``report.h5``).

Тонкий оркестратор: владеет соединением :class:`H5Reader`, раскладывает две
панели и связывает их. Вся отрисовка — в
:class:`~src.wave2d.datasetview.DatasetView`, дерево содержимого — в
:class:`~src.wave2d.h5tree.H5TreeView`.

У датасета с осью стека (моды ``nphi`` у merged или угол ``phi`` у
``total_fields.hdf5``) панель ``DatasetView`` даёт кнопку **Animate**: она
перебирает кадры по оси стека и пишет ``MP4`` рядом с исходным файлом (см.
:meth:`W2DViewer._animate`).

Точка входа — ``w2d_viewer.py`` в корне репозитория.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

import imageio

import tkinter as tk
from tkinter import messagebox, ttk

from src.common.h5reader import H5Reader
from src.common.navigator import default_navigator
from src.wave2d.datasetview import DatasetView, Selection
from src.wave2d.h5tree import H5TreeView
from src.wave2d.multiview import AddResult, PlotItem, add_to_comparison
from src.wave2d.schema import (
    GEOMETRY_R,
    GRID_PSI,
    GRID_RHO,
    GRID_X,
    GRID_Y,
    MERGED_GROUPS,
    MERGED_LAYOUT,
    MERGED_LAYOUT_NPHI_AXIS,
    NPHI,
    SPECTRUM_AN,
    SPECTRUM_N,
    STACK_COORD,
    STACK_NAME,
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


class _AnimationProgress:
    """Окно прогресса сборки анимации (без кнопки отмены).

    Прогресс идёт по кадрам: заполнение ``ttk.Progressbar`` и подпись
    ``Frame i/N``. Закрытие окна по крестику заблокировано — иначе writer
    остался бы незакрытым.
    """

    def __init__(self, root: tk.Misc, title: str, total: int) -> None:
        self._win = tk.Toplevel(root)
        self._win.title(title)
        self._win.transient(root)
        self._win.resizable(False, False)
        self._win.protocol("WM_DELETE_WINDOW", lambda: None)
        self._label = ttk.Label(self._win, text="Rendering…", width=44, anchor="w")
        self._label.pack(fill=tk.X, padx=12, pady=(12, 6))
        self._bar = ttk.Progressbar(
            self._win, mode="determinate", maximum=max(1, total), length=320,
        )
        self._bar.pack(fill=tk.X, padx=12, pady=(0, 12))
        self._win.update_idletasks()
        self._center(root)

    def _center(self, root: tk.Misc) -> None:
        x = root.winfo_rootx() + (root.winfo_width() - self._win.winfo_width()) // 2
        y = root.winfo_rooty() + (root.winfo_height() - self._win.winfo_height()) // 2
        self._win.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def update(self, value: int, text: str) -> None:
        """Обновляет заполнение и подпись (без ожидания событий)."""
        self._bar["value"] = value
        self._label.configure(text=text)
        self._win.update_idletasks()

    def close(self) -> None:
        """Закрывает окно прогресса."""
        self._win.destroy()


class W2DViewer:
    """Окно просмотра одного HDF5-файла результатов Wave2D."""

    def __init__(self, root: tk.Tk, file_path: str):
        self.root = root
        self.file_path = file_path
        #: Идёт ли сейчас сборка MP4 (защита от повторного запуска).
        self._animating = False

        # Одно соединение на всё время работы, закрывается в on_closing.
        # open_results заодно проверяет версию схемы (>= 0.94).
        self.reader = open_results(file_path)

        # Версия схемы — единственный атрибут корня; выносим её в заголовок,
        # чтобы корневой узел в дереве был не нужен.
        version = format_version_of(self.reader)
        version_text = f"{version[0]}.{version[1]:02d}" if version else "?"
        self.root.title(f"W2D Viewer — {file_path} (format {version_text})")
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
            major_radius=self._load_major_radius(),
            spectrum_an=self._load_spectrum_an(),
            rho=self._load_axis(GRID_RHO),
            psi=self._load_axis(GRID_PSI),
            on_add_to_comparison=self._add_to_comparison,
            on_animate=self._animate,
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

    def _load_major_radius(self) -> np.ndarray | None:
        """Большой радиус ``R(rho,theta)`` (см) для топ-вида экватора или ``None``."""
        return self._array(GEOMETRY_R)

    def _load_spectrum_an(self) -> dict[int, complex]:
        """Веса ``An(n)`` спектра антенны для реконструкции одной моды ``nphi``.

        ``{}``, если ``/spectrum`` в файле нет (тогда вес считается равным 1).
        """
        try:
            if self.reader.contains(SPECTRUM_N) and self.reader.contains(SPECTRUM_AN):
                n = self.reader.array(SPECTRUM_N)
                an = self.reader.array(SPECTRUM_AN)
                return {int(k): complex(v) for k, v in zip(n, an)}
        except Exception:
            pass
        return {}

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
        """Собирает :class:`Selection` по одному пути узла.

        Для объединённого файла (раскладка ``nphi-axis``) в датасетах групп
        ``/fields``, ``/power_balance``, ``/spectrum`` последняя ось — ``nphi``;
        координата берётся из ``/nphi``, чтобы область данных дала слайдер моды.
        """
        kind = self.reader.kind(path)
        data = None if kind == "group" else self._array(path)
        mode_axis, mode_values, mode_name = self._mode_axis(path, data)
        return Selection(
            path=path,
            kind=kind,
            attrs=self._attrs(path),
            data=data,
            mode_axis=mode_axis,
            mode_values=mode_values,
            mode_name=mode_name,
        )

    def _mode_axis(
        self, path: str, data: np.ndarray | None
    ) -> tuple[int | None, np.ndarray | None, str | None]:
        """Ось стека ``(номер, координата, имя)`` для датасета с 3-й осью.

        Ось — последняя. Координата берётся из корневого ``stack_coord``
        (напр. ``/phi`` у ``total_fields.hdf5``). Для merged-файла без этого
        атрибута — обратная совместимость: ``/nphi``, если раскладка
        ``nphi-axis`` и датасет лежит в стековой группе. Иначе —
        ``(None, None, None)``.
        """
        if data is None or data.ndim < 2:
            return None, None, None
        root = self.reader.attrs("/")
        coord = root.get(STACK_COORD)
        name = root.get(STACK_NAME)
        if coord is None:
            if root.get(MERGED_LAYOUT) != MERGED_LAYOUT_NPHI_AXIS:
                return None, None, None
            group = "/" + path.strip("/").split("/", 1)[0]
            if group not in MERGED_GROUPS:
                return None, None, None
            coord, name = NPHI, "nphi"
        if isinstance(coord, bytes):
            coord = coord.decode("utf-8", "replace")
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        values = self._array(coord)
        if values is None or data.shape[-1] != len(values):
            return None, None, None
        return data.ndim - 1, values, (None if name is None else str(name))

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
                "Comparison",
                "This group already has datasets of a different dimension "
                "(1D and 2D cannot be compared together).",
                parent=self.root,
            )

    def on_closing(self) -> None:
        """Освобождает ресурсы и закрывает окно."""
        self.dataset_view.close()
        self.reader.close()
        self.root.destroy()

    # --- анимация ---------------------------------------------------------

    def _ask_animation_options(self) -> tuple[int, bool] | None:
        """Диалог параметров анимации: ``fps`` и выравнивание шкалы цвета.

        Возвращает ``(fps, align)`` или ``None`` при отмене. ``align=True`` —
        фиксировать ``vmin/vmax`` по всему стеку (кадры не «мигают»),
        ``align=False`` — автоподбор шкалы на каждом кадре.
        """
        result: dict[str, object] = {}
        dlg = tk.Toplevel(self.root)
        dlg.title("Animate")
        dlg.transient(self.root)
        dlg.resizable(False, False)

        fps_var = tk.IntVar(value=10)
        align_var = tk.BooleanVar(value=True)

        body = ttk.Frame(dlg)
        body.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(body, text="Frames per second:").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Spinbox(
            body, from_=1, to=60, textvariable=fps_var, width=6,
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Checkbutton(
            body,
            text="Align color scale (fixed vmin/vmax) across frames",
            variable=align_var,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        def accept() -> None:
            try:
                fps = int(fps_var.get())
            except (tk.TclError, ValueError):
                return
            result["fps"] = min(max(fps, 1), 60)
            result["align"] = bool(align_var.get())
            dlg.destroy()

        buttons = ttk.Frame(dlg)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(buttons, text="Animate", command=accept).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT)

        dlg.bind("<Return>", lambda _e: accept())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        dlg.grab_set()
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (
            self.root.winfo_width() - dlg.winfo_width()
        ) // 2
        y = self.root.winfo_rooty() + (
            self.root.winfo_height() - dlg.winfo_height()
        ) // 2
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.root.wait_window(dlg)
        if "fps" not in result:
            return None
        return int(result["fps"]), bool(result["align"])

    def _animate(self) -> None:
        """Собирает MP4, перебирая кадры по оси стека текущего среза.

        Анимируется ровно то, что видно: выбранный вид ``(R,Z)/(rho,theta)`` и
        составляющая ``real/imag/abs``, а также экватор ``Z=0`` (Ring/Flat),
        если он включён. Параметры (``fps`` и выравнивание шкалы цвета
        ``vmin/vmax`` по всему стеку либо автоподбор на каждом кадре)
        спрашиваются в диалоге :meth:`_ask_animation_options`. Свип идёт по
        всей оси: моды ``nphi`` у merged или угол ``phi`` у
        ``total_fields.hdf5``. Процесс идёт в главном потоке (matplotlib не
        потокобезопасен), по кадру на ``after``: окно остаётся отзывчивым,
        холст служит превью, а ход сборки показывает окно
        :class:`_AnimationProgress`. Результат — ``MP4`` рядом с исходным
        файлом, в подпапке ``animations/``.
        """
        view = self.dataset_view
        if self._animating:
            return
        selection = view.stacked_selection()
        if selection is None:
            messagebox.showinfo(
                "Animate",
                "Select a dataset with a mode/angle axis (merged or total field).",
                parent=self.root,
            )
            return
        length = view.stack_length()
        if length < 2:
            messagebox.showinfo(
                "Animate",
                "Need at least 2 frames along the stack axis.",
                parent=self.root,
            )
            return
        options = self._ask_animation_options()
        if options is None:
            return
        fps, align = options

        source = Path(self.file_path)
        axis = selection.mode_name or "axis"
        out = source.parent / "animations" / f"{source.stem}__{axis}.mp4"
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            writer = imageio.get_writer(
                str(out), fps=fps, codec="libx264", quality=8,
                macro_block_size=2,
            )
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(
                "Animate", f"Could not start video writer:\n{e}",
                parent=self.root,
            )
            return

        self._animating = True
        original_index = int(view.mode_var.get())
        progress = _AnimationProgress(self.root, "Animate", length)
        # Выравнивание шкалы цвета по всему стеку — иначе кадры «мигают».
        if align:
            view.set_color_limits(*view.animation_color_limits())
        else:
            view.set_color_limits(None, None)

        def finish(error: str | None = None) -> None:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass
            self._animating = False
            view.set_color_limits(None, None)  # вернуть автоподбор шкалы
            view.mode_var.set(original_index)
            view.redraw()
            progress.close()
            if error is None:
                messagebox.showinfo(
                    "Animate", f"Saved:\n{out}", parent=self.root
                )
            else:
                messagebox.showerror("Animate", error, parent=self.root)

        def step(index: int) -> None:
            if index >= length:
                finish()
                return
            try:
                writer.append_data(view.render_frame(index))
            except Exception as e:  # noqa: BLE001
                finish(str(e))
                return
            progress.update(index + 1, f"Frame {index + 1}/{length}")
            self.root.after(1, lambda: step(index + 1))

        self.root.after(1, lambda: step(0))
