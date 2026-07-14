import os
import h5py
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm

files ={
    "polar_mesh" : 'Elmfire_WagD/polar_mesh_z1.dat',
    'rho_mesh' : 'Elmfire_WagD/rho_mesh_z1.dat',
    'time' : 'Elmfire_WagD/time_z1.dat',
    'data' : 'Elmfire_WagD/nep_z1.dat',
}

polar_mesh = pd.read_csv(files['polar_mesh'], sep=r'\s+')

# Вывод первых строк и структуры для проверки
print(polar_mesh.head())
print(polar_mesh.dtypes)
print(f"Размер данных: {polar_mesh.shape}")
print(f"Количество строк: {polar_mesh.shape[0]}")
print(f"Количество столбцов: {polar_mesh.shape[1]}")

rho_mesh = pd.read_csv(files['rho_mesh'], sep=r'\s+')
rho_1d = np.array(rho_mesh['rho(cm)'], dtype=np.float32)
N_theta_1d = np.array(rho_mesh['Ntet'], dtype=np.int32)
print(rho_mesh.head())
print(rho_mesh.dtypes)

df_times = pd.read_csv(files['time'], sep=r'\s+', header=None, names=['time_index', 'time_value'],
                       dtype={'time_index': np.int32, 'rho_fluc': np.float32})
df_times.set_index('time_index', inplace=True)
print(df_times.head())
print(df_times.dtypes)
time_indices = np.array(df_times.index, dtype=np.int32)
N_time = len(time_indices)
N_rho= len(rho_1d)
N_theta = N_theta_1d[-1]

print(f'data size = {N_time} x {N_rho} x {N_theta}')
time_values = df_times.loc[time_indices, 'time_value'].values.astype(np.float32)





column_names = ['time_index', 'rho', 'theta', 'd_dens']
df_dens = pd.read_csv(files['data'], sep=r'\s+', header=None, names=column_names, dtype={'time_index': int})

output_h5 = 'z1.h5'
with h5py.File(output_h5, 'w') as f:
    # Создаем простые одномерные датасеты
    f.create_dataset('rho_mesh/rho', data=rho_1d)
    f.create_dataset('rho_mesh/N_theta', data=N_theta_1d)
    f.create_dataset('time_indices', data=time_indices)
    f.create_dataset('time_values', data=time_values)

    ds_fluct = f.create_dataset('fluctuations', shape=(N_time, N_rho, N_theta), 
                                    dtype='float32', compression='gzip', chunks=(1, N_rho, N_theta))
    

        
    # Заполняем куб пошагово, чтобы не держать в памяти гигантские массивы
    for t_idx, time_val in enumerate(time_indices):
        step_data = df_dens[df_dens['time_index'] == time_val]['rho'].values
        ds_fluct[t_idx] = step_data.reshape(N_rho, N_theta)    