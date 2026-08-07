from scipy.interpolate import RegularGridInterpolator
import numpy as np

def get_periodic_interpolator(rho_1d, max_theta, matrix_data):
    """
    Создает интерполятор, принудительно замыкая азимутальный угол theta в кольцо.
    """
    # 1. Добавляем физическую точку 2*pi в конец исходной оси углов
    theta_periodic = np.linspace(0, 2 * np.pi, max_theta + 1)

    # 2. Дублируем самый первый столбец данных (угол 0) в самый конец матрицы
    # Теперь переход между 359 градусами и 0 градусов станет непрерывным
    matrix_periodic = np.hstack([matrix_data, matrix_data[:, [0]]])
    
    # 3. Строим интерполятор на расширенных данных
    return RegularGridInterpolator(
        (rho_1d, theta_periodic), 
        matrix_periodic, 
        method='linear', 
        bounds_error=False, 
        fill_value=0.0
    )

def get_interpolator(rho_1d, max_theta, matrix_data):
    """
    Создает интерполятор, без замыкания theta в кольцо.
    """
    # 1. Добавляем физическую точку 2*pi в конец исходной оси углов
    theta_1d = np.linspace(0, 2 * np.pi, max_theta)

    # 3. Строим интерполятор на расширенных данных
    return RegularGridInterpolator(
        (rho_1d, theta_1d), 
        matrix_data, 
        method='linear', 
        bounds_error=False, 
        fill_value=0.0
    )
