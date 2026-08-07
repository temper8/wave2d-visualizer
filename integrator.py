import h5py
from scipy.interpolate import RegularGridInterpolator
import numpy as np

from src.integrate import integrate_on_custom_grid
from src.interpolator import get_periodic_interpolator
from utils import dataset_reader, get_attributes_recursive_from

# Считываем данные флуктуаций (например, кадр 42)
with h5py.File('z1.h5', 'r') as f:
    f_mat = f['fluctuations'][42, :, :]
    f_rho = f['rho_mesh/rho'][:]
    # Восстанавливаем исходную равномерную ось theta для флуктуаций
    f_max_tet = f_mat.shape[1]

# Считываем данные функции поля со своей независимой геометрией

file_path = 'results.h5'

run_params = get_attributes_recursive_from(file_path, start_path='/run_params')
#print_dict(run_params)    
nphi = run_params['w2grid']['nphi1']
nphi = f"nphi-{abs(nphi):03d}" if nphi < 0 else f"nphi{nphi:03d}"
print(nphi)
Ea_field = dataset_reader(file_path, f'/{nphi}/field_2d/Ea')
field_max_rho, field_max_theta = Ea_field.shape
print(field_max_rho, field_max_theta)
field_rho = dataset_reader(file_path, '/coord/rho')
field_rho= field_rho[0:field_max_rho]

# --- Этап 1: Создание интерполяторов где-то в коде (например, в классах) ---
# (Данные очищены от NaN через np.nan_to_num)
interp_fluc = get_periodic_interpolator(f_rho, f_max_tet, f_mat)
interp_field = get_periodic_interpolator(field_rho, field_max_theta, Ea_field)

# --- Этап 2: Вызов нашей сверх-лаконичной функции ---
result = integrate_on_custom_grid(
    interp_fluc=interp_fluc,
    interp_field=interp_field,
    rho_min=float(f_rho[0]),
    rho_max=float(f_rho[-1]),
    N_rho=3000,
    N_theta=6000
)

print(f"Интеграл: {result:.6f}")
