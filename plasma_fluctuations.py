import numpy as np
import h5py


# =====================================================================
# КЛАСС ДЛЯ РАБОТЫ С ДАННЫМИ ФЛУКТУАЦИЙ
# =====================================================================
class PlasmaFluctuations:
    """Класс отвечает за загрузку, кэширование метаданных и чтение кадров флуктуаций."""
    def __init__(self, filepath):
        self.filepath = filepath
        self.rho_1d = None
        self.time_values = None
        self.total_frames = 0
        self.max_tet_points = 0
        self.vmin = 0.0
        self.vmax = 0.0
        
        # Автоматически загружаем легкие метаданные при инициализации
        self._load_metadata()

    def _load_metadata(self):
        """Внутренний метод для чтения структуры сетки и границ шкалы флуктуаций."""
        with h5py.File(self.filepath, 'r') as f:
            self.rho_1d = f['rho_mesh/rho'][:]
            self.time_values = f['time_values'][:]
            self.total_frames, _, self.max_tet_points = f['fluctuations'].shape
            
            # Задаем базовые границы шкалы по первому кадру
            base_frame = f['fluctuations'][0, :, :]
            self.vmin = float(np.nanmin(base_frame))
            self.vmax = float(np.nanmax(base_frame))

    def get_frame(self, frame_idx):
        """Ленивое чтение конкретного 2D-кадра флуктуаций по индексу времени."""
        with h5py.File(self.filepath, 'r') as f:
            return f['fluctuations'][frame_idx, :, :]

    def get_time_at(self, frame_idx):
        """Возвращает физическое время симуляции для указанного кадра."""
        return self.time_values[frame_idx]

    def generate_mesh(self):
        """Генерирует 2D координатную сетку для pcolormesh."""
        theta_1d = np.linspace(0, 2 * np.pi, self.max_tet_points)
        return np.meshgrid(theta_1d, self.rho_1d)
