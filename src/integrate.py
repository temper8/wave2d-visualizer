import numpy as np
from scipy.integrate import trapezoid

def integrate_on_custom_grid(interp_fluc, interp_field, rho_min, rho_max, N_rho, N_theta):
    """
    Вычисляет интеграл произведения флуктуаций и поля на новой регулярной полярной сетке,
    принимая на вход готовые объекты интерполяторов.

    :param interp_fluc:  RegularGridInterpolator для флуктуаций текущего кадра
    :param interp_field: RegularGridInterpolator для функции поля
    :param rho_min:      Минимальный радиус области интегрирования
    :param rho_max:      Максимальный радиус области интегрирования
    :param N_rho:        Количество узлов новой регулярной сетки по радиусу
    :param N_theta:      Количество узлов новой регулярной сетки по углу
    :return:             float, значение двумерного интеграла
    """
    # 1. Автоматически генерируем новые регулярные координатные оси
    custom_rho = np.linspace(rho_min, rho_max, N_rho, dtype=np.float32)
    custom_theta = np.linspace(0, 2 * np.pi, N_theta, dtype=np.float32)

    # 2. Строим 2D сетку и разворачиваем её в список точек для запроса (N_points, 2)
    T_custom, R_custom = np.meshgrid(custom_theta, custom_rho)
    query_points = np.vstack([R_custom.flatten(), T_custom.flatten()]).T

    # 3. Мгновенно аппроксимируем обе функции на узлы новой регулярной сетки
    fluc_values = interp_fluc(query_points).reshape(R_custom.shape)
    field_values = interp_field(query_points).reshape(R_custom.shape)

    # 4. Перемножаем значения и добавляем полярный ЯКОБИАН (умножение на радиус R_custom)
    integrand = fluc_values * field_values * R_custom

    # 5. Двумерный интеграл методом трапеций по осям новой регулярной сетки
    integral_theta = trapezoid(integrand, x=custom_theta, axis=1)
    total_integral = trapezoid(integral_theta, x=custom_rho, axis=0)

    return float(total_integral)


