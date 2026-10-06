"""GUI-просмотрщик results.h5 (Wave2D).

Слева — дерево содержимого файла (группы/датасеты) и панель атрибутов,
в центре — изображение выбранного датасета. Матрицы читаются лениво,
только по выбору пользователя. Одно соединение HDF5 на всё время работы.

Точка входа — ``w2d_viewer.py`` в корне репозитория.
"""

import numpy as np
import h5py

import matplotlib
matplotlib.use("TkAgg")  # до импорта pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import ttk

from src.wave2d.schema import GRID_X, GRID_Y, format_version_of, open_results


class W2DViewer:
    """Окно просмотра одного HDF5-файла результатов Wave2D."""

    def __init__(self, root: tk.Tk, file_path: str):
        self.root = root
        self.file_path = file_path

        # Одно соединение на всё время работы, закрывается в on_closing.
        # open_results заодно проверяет версию схемы (>= 0.94).
        self.reader = open_results(file_path)

        self.R = None
        self.Z = None
        self._load_coords()

        self.current_path: str | None = None
        self.current_data: np.ndarray | None = None
        self._colorbar = None

        # Версия схемы — единственный атрибут корня; выносим её в заголовок,
        # чтобы корневой узел в дереве был не нужен.
        version = format_version_of(self.reader)
        version_text = f"{version[0]}.{version[1]:02d}" if version else "?"
        self.root.title(f"W2D Viewer — {file_path} (формат {version_text})")
        self.root.geometry("1150x780")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.setup_ui()
        self.populate_tree()
        # Нет выбранного датасета: атрибуты сразу занимают основную область.
        self.redraw()
        # Начальная ширина левой панели ~300 px (после первой раскладки окна).
        self._sash_done = False
        self.paned.bind("<Configure>", self._set_initial_sash, add="+")

    # --- данные ----------------------------------------------------------

    def _load_coords(self) -> None:
        """Координаты (R,Z) для физического вида, если есть в файле."""
        try:
            if self.reader.contains(GRID_X) and self.reader.contains(GRID_Y):
                self.R = self.reader.array(GRID_X)
                self.Z = self.reader.array(GRID_Y)
        except Exception:
            self.R = self.Z = None

    # --- интерфейс -------------------------------------------------------

    def setup_ui(self) -> None:
        paned = self.paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # --- левая часть: дерево ---
        left = ttk.Frame(paned)
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        tree_sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_sb.grid(row=0, column=1, sticky="ns")

        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # --- центр: переключатели + холст + атрибуты ---
        right = ttk.Frame(paned)
        controls = self.controls = ttk.Frame(right)
        controls.pack(fill=tk.X, padx=4, pady=4)

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
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Панель атрибутов показывается только когда нет датасета для
        # визуализации и занимает всю основную область (см. _layout_right).
        attr_frame = self.attr_frame = ttk.Frame(right)
        attr_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.attr_text = tk.Text(attr_frame, height=1, state="disabled", wrap="word")
        attr_sb = ttk.Scrollbar(
            attr_frame, orient="vertical", command=self.attr_text.yview
        )
        self.attr_text.configure(yscrollcommand=attr_sb.set)
        self.attr_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        attr_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._set_attr_text("(выберите узел в дереве)")

        self.toolbar = NavigationToolbar2Tk(self.canvas, right)
        self.toolbar.update()

        paned.add(left, weight=1)
        paned.add(right, weight=3)

    def _set_initial_sash(self, event=None) -> None:
        """Однократно задаёт начальную позицию разделителя: левая панель ~300 px."""
        if self._sash_done:
            return
        try:
            self.paned.sashpos(0, 300)
        except tk.TclError:
            return  # окно ещё не готово — попробуем на следующем <Configure>
        self._sash_done = True

    def _layout_right(self, expanded: bool) -> None:
        """Перекладывает правую панель.

        ``expanded=True`` — нет датасета для визуализации: панель атрибутов
        занимает всю основную область. ``False`` — есть изображение: атрибуты
        скрыты, а холст и toolbar занимают всю область.
        """
        if getattr(self, "_attr_expanded", None) == expanded:
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

    def populate_tree(self) -> None:
        """Строит дерево содержимого файла через :meth:`H5Reader.walk`.

        Корень файла не показывается: его единственный атрибут —
        ``format_version`` (вынесен в заголовок окна), а группы верхнего
        уровня (``/manifest``, ``/input``, …) становятся корневыми узлами
        дерева.
        """
        for full, kind, obj in self.reader.walk("/"):
            parent = full.rsplit("/", 1)[0]
            name = full.rsplit("/", 1)[1]
            if kind == "group":
                self.tree.insert(parent, "end", iid=full, text=name, open=False)
            else:
                label = f"{name}   {tuple(obj.shape)} {obj.dtype}"
                self.tree.insert(parent, "end", iid=full, text=label)

    # --- обработчики -----------------------------------------------------

    def on_select(self, event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        path = selection[0]
        self._show_attributes(path)

        obj = self.reader.file[path] if self.reader.contains(path) else None
        if isinstance(obj, h5py.Group):
            self.current_path = None
            self.current_data = None
        else:
            self.current_path = path
            self.current_data = self.reader.array(path)
        self.redraw()

    def _set_attr_text(self, text: str) -> None:
        """Заменяет содержимое панели атрибутов (панель только для чтения)."""
        self.attr_text.configure(state="normal")
        self.attr_text.delete("1.0", tk.END)
        self.attr_text.insert("1.0", text)
        self.attr_text.configure(state="disabled")

    def _show_attributes(self, path: str) -> None:
        try:
            attrs = self.reader.attrs(path) if self.reader.contains(path) else {}
        except Exception:
            attrs = {}
        lines = [f"{k} = {v}" for k, v in attrs.items()] or ["(атрибутов нет)"]
        self._set_attr_text("\n".join(lines))

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

    def redraw(self) -> None:
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
            self._colorbar = None
        self.ax.clear()

        data = self.current_data
        self._layout_right(data is None)
        title = self.current_path or ""

        if data is None:
            self.ax.text(
                0.5, 0.5, "Выберите датасет",
                ha="center", va="center", transform=self.ax.transAxes,
            )
        elif data.ndim == 1:
            self.ax.plot(data)
            self.ax.set_title(title, fontsize=8)
        elif data.ndim == 2:
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
        else:
            self.ax.text(
                0.5, 0.5, f"{title}\nshape={data.shape}",
                ha="center", va="center", transform=self.ax.transAxes,
            )

        self.canvas.draw_idle()

    def on_closing(self) -> None:
        """Освобождает ресурсы и закрывает окно."""
        if hasattr(self, "canvas"):
            self.canvas.get_tk_widget().destroy()
        if hasattr(self, "fig"):
            plt.close(self.fig)
        self.reader.close()
        self.root.destroy()