import os
from matplotlib import pyplot as plt
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
print(rho_mesh.head())
print(rho_mesh.dtypes)

df_times = pd.read_csv(files['time'], sep=r'\s+', header=None, names=['time_index', 'time_value'])
df_times.set_index('time_index', inplace=True)

print(df_times.head())
print(df_times.dtypes)