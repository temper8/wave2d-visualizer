"""GUI-просмотрщик z1.h5 (ELMFIRE): эволюция флуктуаций плотности.

Полярная карта одного кадра + ползунок по времени. Кадры читаются лениво
(по одному) через :class:`~src.plasma_fluctuations.PlasmaFluctuations`.

Точка входа — ``elmfire_viewer.py`` в корне репозитория.
"""

import tkinter as tk
from tkinter import ttk

import numpy as np

import matplotlib
matplotlib.use("TkAgg")  # до импорта pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from src.plasma_fluctuations import PlasmaFluctuations


class ElmfireFluctuationsViewer:
    """Окно просмотра временного ряда флуктуаций из ``z1.h5``."""

    def __init__(self, root: tk.Tk, fluctuations: PlasmaFluctuations):
        self.root = root
        self.data = fluctuations

        self.root.title("ELMFIRE Fluctuations")
        self.root.geometry("700x750")

        # Перехват «крестика» окна: освобождаем ресурсы Matplotlib.
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Полярная сетка для pcolormesh.
        self.T, self.R = self.data.generate_mesh()

        self.setup_ui()
        self.update_plot(0)

    def setup_ui(self) -> None:
        """Строит холст Matplotlib и панель со слайдером."""
        self.time_label = tk.Label(
            self.root, text="Время: 0.00000 с", font=("Arial", 14, "bold")
        )
        self.time_label.pack(pady=10)

        self.fig, self.ax = plt.subplots(
            figsize=(5.5, 5.5), subplot_kw={"projection": "polar"}
        )

        # Сетки и метки скрыты — по стандарту оформления проекта.
        self.ax.grid(False)
        self.ax.set_yticklabels([])
        self.ax.set_xticklabels([])
        self.ax.spines["polar"].set_visible(False)

        # Пустой pcolormesh нужен, чтобы сразу построить цветовую шкалу.
        initial_data = np.full_like(self.T, np.nan)
        self.quadmesh = self.ax.pcolormesh(
            self.T,
            self.R,
            initial_data,
            cmap="coolwarm",
            shading="nearest",
            vmin=self.data.vmin,
            vmax=self.data.vmax,
        )
        self.cbar = self.fig.colorbar(self.quadmesh, ax=self.ax, pad=0.05)
        self.cbar.set_label("Плотность флуктуаций (rho_fluc)")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        control_frame = tk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=20, pady=15)

        tk.Label(control_frame, text="Frame:", font=("Arial", 10)).pack(
            side=tk.LEFT, padx=5
        )

        self.slider = ttk.Scale(
            control_frame,
            from_=0,
            to=self.data.total_frames - 1,
            orient=tk.HORIZONTAL,
            command=self.on_slider_move,
        )
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.frame_label = tk.Label(
            control_frame,
            text=f"0 / {self.data.total_frames - 1}",
            font=("Arial", 10),
        )
        self.frame_label.pack(side=tk.LEFT, padx=5)

    def on_slider_move(self, value: str) -> None:
        """Обработчик движения ползунка."""
        frame_idx = int(float(value))
        self.frame_label.config(text=f"{frame_idx} / {self.data.total_frames - 1}")
        self.update_plot(frame_idx)

    def update_plot(self, frame_idx: int) -> None:
        """Перерисовывает карту для кадра ``frame_idx``."""
        current_frame = self.data.get_frame(frame_idx)
        t_val = self.data.get_time_at(frame_idx)

        self.time_label.config(text=f"Время симуляции: {t_val:.8f} с")
        self.quadmesh.set_array(current_frame.flatten())
        # Обновляем только рисунок на холсте (мгновенно).
        self.canvas.draw_idle()

    def on_closing(self) -> None:
        """Освобождает ресурсы Matplotlib при закрытии окна."""
        if hasattr(self, "canvas_widget"):
            self.canvas_widget.destroy()

        if hasattr(self, "fig"):
            plt.close(self.fig)

        self.root.destroy()
