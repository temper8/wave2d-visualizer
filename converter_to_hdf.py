import os
import h5py
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm

files ={
    "polar_mesh" : 'Elmfire_WagD/polar_mesh_z1.dat',
    'rho_mesh' : 'Elmfire_WagD/rho_mesh_z1.dat',
    'time' : 'Elmfire_WagD/time_z1.dat'
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

time_values = df_times.loc[time_indices, 'time_value'].values.astype(np.float32)





output_h5 = 'z1.h5'
with h5py.File(output_h5, 'w') as f:
    # Создаем простые одномерные датасеты
    f.create_dataset('rho_mesh/rho', data=rho_1d)
    f.create_dataset('rho_mesh/N_theta', data=N_theta_1d)
    f.create_dataset('time_indices', data=time_indices)
    f.create_dataset('time_values', data=time_values)