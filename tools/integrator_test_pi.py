import h5py
from scipy.interpolate import RegularGridInterpolator
import numpy as np

from src.common.paths import elmfire_converted, wave2d_latest, wave2d_results
from src.integrate import integrate_on_custom_grid
from src.interpolator import get_interpolator, get_periodic_interpolator
from src.utils import dataset_reader, get_attributes_recursive_from
from src.wave2d.schema import (
    GRID_RHO,
    INPUT_W2GRID,
    ensure_supported_path,
    field_dataset,
)



# Считываем данные флуктуаций (например, кадр 42)
with h5py.File(str(elmfire_converted("WagD")), 'r') as f:
    f_mat = f['fluctuations'][42, :, :]
    f_rho = f['rho_mesh/rho'][:]
    # Восстанавливаем исходную равномерную ось theta для флуктуаций
    f_max_tet = f_mat.shape[1]
    f_theta = np.linspace(0, 2 * np.pi, f_max_tet+1)

# Считываем данные функции поля со своей независимой геометрией

run_id = wave2d_latest("FT-2_LH_smoke_nphi")
file_path = str(wave2d_results(run_id))

# Только новый формат: старая схема будет отклонена с сообщением.
ensure_supported_path(file_path)

run_params = get_attributes_recursive_from(file_path, start_path=INPUT_W2GRID)
#print_dict(run_params)    
nphi = int(run_params[INPUT_W2GRID]['nphi1'])
print(nphi)
Ea_field = dataset_reader(file_path, field_dataset(nphi, "Ea"))
field_max_rho, field_max_theta = Ea_field.shape
print(field_max_rho, field_max_theta)
field_rho = dataset_reader(file_path, GRID_RHO)
field_rho = field_rho[0:field_max_rho]

# инициализация массивов 1 для проверки интегрирования
f_mat[:,:] = 1.0
Ea_field[:,:] = 1.0

#interp_fluc = get_periodic_interpolator(f_rho, f_max_tet, f_mat)
#interp_field = get_periodic_interpolator(field_rho, field_max_theta, Ea_field)
interp_fluc = get_interpolator(f_rho, f_max_tet, f_mat)
interp_field = get_interpolator(field_rho, field_max_theta, Ea_field)

# --- Этап 2: Вызов нашей сверх-лаконичной функции ---
print(f"fluct_rho_max = {f_rho[-1]}")
print(f"field_rho_max = {field_rho[-1]}")
result = integrate_on_custom_grid(
    interp_fluc=interp_fluc,
    interp_field=interp_field,
    rho_min=float(field_rho[0]),
    rho_max=float(field_rho[-1]),
    N_rho=1000,
    N_theta=1000
)/field_rho[-1]/field_rho[-1]
print(f"Интеграл: {result:.6f}")
