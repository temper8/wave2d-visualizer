import tkinter as tk
from tkinter import ttk
import numpy as np
import h5py

import matplotlib
# Указываем Matplotlib использовать движок Tkinter
matplotlib.use('TkAgg')  
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

H5_FILE = 'z1.h5'

class FluctuationsVisualizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fluctuations")
        self.root.geometry("700x750")

        # --- ПЕРЕХВАТ ЗАКРЫТИЯ ОКНА ---
        # Связываем стандартный «крестик» окна с нашим методом очистки
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
                
        # 1. Загрузка легких метаданных
        try:
            with h5py.File(H5_FILE, 'r') as f:
                self.rho_1d = f['rho_mesh/rho'][:]
                self.time_values = f['time_values'][:]
                self.total_frames, _, self.max_tet_points = f['fluctuations'].shape
                
                # Задаем фиксированные границы шкалы по первому кадру
                base_frame = f['fluctuations'][0, :, :]
                self.vmin = float(np.nanmin(base_frame))
                self.vmax = float(np.nanmax(base_frame))
                
        except Exception as e:
            print(f"Ошибка чтения HDF5 файла: {e}")
            lbl = tk.Label(root, text=f"Ошибка загрузки {H5_FILE}.", fg="red")
            lbl.pack(pady=20)
            return

        # Подготовка полярной координатной сетки для pcolormesh
        theta_1d = np.linspace(0, 2 * np.pi, self.max_tet_points)
        self.T, self.R = np.meshgrid(theta_1d, self.rho_1d)

        # 2. Создание интерфейса Tkinter
        self.setup_ui()

        # 3. Отрисовка первого кадра
        self.update_plot(0)

    def setup_ui(self):
        # Верхняя панель для вывода времени
        self.time_label = tk.Label(self.root, text="Время: 0.0000e00 с", font=("Arial", 14, "bold"))
        self.time_label.pack(pady=10)

        # Создаем холст Matplotlib встроенный в Tkinter
        self.fig, self.ax = plt.subplots(figsize=(5.5, 5.5), subplot_kw={'projection': 'polar'})
        
        # Отключаем сетки и метки по вашему стандарту
        self.ax.grid(False)
        self.ax.set_yticklabels([])
        self.ax.set_xticklabels([])
        self.ax.spines['polar'].set_visible(False)
        
        # Создаем пустой объект pcolormesh для инициализации цветовой шкалы
        # Заполняем его нулями, чтобы построить colorbar
        initial_data = np.full_like(self.T, np.nan)
        self.quadmesh = self.ax.pcolormesh(
            self.T, self.R, initial_data, 
            cmap='coolwarm', shading='nearest', 
            vmin=self.vmin, vmax=self.vmax
        )
        self.cbar = self.fig.colorbar(self.quadmesh, ax=self.ax, pad=0.05)
        self.cbar.set_label('Плотность флуктуаций (rho_fluc)')

        # Помещаем холст Matplotlib в окно Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Нижняя панель управления (Слайдер)
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=20, pady=15)

        tk.Label(control_frame, text="Frame:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        # Ползунок (Scale)
        self.slider = ttk.Scale(
            control_frame, 
            from_=0, 
            to=self.total_frames - 1, 
            orient=tk.HORIZONTAL,
            command=self.on_slider_move
        )
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.frame_label = tk.Label(control_frame, text=f"0 / {self.total_frames - 1}", font=("Arial", 10))
        self.frame_label.pack(side=tk.LEFT, padx=5)

    def on_slider_move(self, value):
        # Функция вызывается при каждом движении ползунка
        frame_idx = int(float(value))
        self.frame_label.config(text=f"{frame_idx} / {self.total_frames - 1}")
        self.update_plot(frame_idx)

    def update_plot(self, frame_idx):
        # Ленивое чтение: берем только один кадр из HDF5
        with h5py.File(H5_FILE, 'r') as f:
            current_frame = f['fluctuations'][frame_idx, :, :]
        
        t_val = self.time_values[frame_idx]
        self.time_label.config(text=f"Время симуляции: {t_val:.4e} с")

        # КЛЮЧЕВОЙ МОМЕНТ ДЛЯ СКОРОСТИ: 
        # Вместо перерисовки всего холста, мы просто меняем массив цветов внутри quadmesh!
        # Метод set_array принимает плоский одномерный массив значений
        self.quadmesh.set_array(current_frame.flatten())
        
        # Обновляем только сам рисунок на холсте (происходит мгновенно)
        self.canvas.draw_idle()

    # --- МЕТОД ПРАВИЛЬНОЙ ОЧИСТКИ ПРИ ЗАКРЫТИИ ОКНА ---
    def on_closing(self):
        print("Закрытие приложения и освобождение ресурсов...")
        
        # 1. Удаляем виджет холста из памяти окна
        if hasattr(self, 'canvas_widget'):
            self.canvas_widget.destroy()
            
        # 2. Закрываем саму фигуру Matplotlib, чтобы разгрузить графический бэкенд
        if hasattr(self, 'fig'):
            plt.close(self.fig)
            
        # 3. Полностью уничтожаем главное окно и останавливаем root.mainloop()
        self.root.destroy()
        print("Приложение успешно закрыто.")

# Запуск приложения
if __name__ == "__main__":
    root = tk.Tk()
    app = FluctuationsVisualizerApp(root)
    root.mainloop()
