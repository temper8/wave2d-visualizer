import os
from matplotlib import pyplot as plt
import pandas as pd
from tqdm import tqdm


polar_mesh_file = 'Elmfire_WagD/polar_mesh_z1.dat'

polar_mesh = pd.read_csv(polar_mesh_file, sep=r'\s+')

# Вывод первых строк и структуры для проверки
print(polar_mesh.head())
print(polar_mesh.dtypes)
print(f"Размер данных: {polar_mesh.shape}")
print(f"Количество строк: {polar_mesh.shape[0]}")
print(f"Количество столбцов: {polar_mesh.shape[1]}")

df_times = pd.read_csv('Elmfire_WagD/time_z1.dat', sep=r'\s+', header=None, names=['time_index', 'time_value'])
df_times.set_index('time_index', inplace=True)

column_names = ['time_index', 'rho', 'theta', 'd_dens']

df_data = pd.read_csv('Elmfire_WagD/nep_z1.dat', sep=r'\s+', header=None, names=column_names, dtype={'time_index': int})

output_dir = 'plots_2d'
os.makedirs(output_dir, exist_ok=True)

grouped = df_data.groupby('time_index')
print("Отрисовка кадров...")
for t_index, group_df in tqdm(grouped, desc="Визуализация шагов по времени"):
    if t_index not in df_times.index:
        continue
    t_val = df_times.loc[t_index, 'time_value']
    
    # Создаем график с полярной проекцией
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={'projection': 'polar'})
    
    # Строим точки: угол (в радианах!) идет первым, радиус — вторым
    # Параметр c задает цвет (плотность флуктуаций), cmap — цветовую схему
    sc = ax.scatter(
        group_df['theta'], 
        group_df['rho'], 
        c=group_df['d_dens'], 
        cmap='coolwarm', 
        s=30,           # размер точек
        edgecolors='none'
    )
    # --- ОТКЛЮЧЕНИЕ СЕТКИ И МЕТОК ---
    ax.grid(False)           # Полностью выключает полярную сетку
    ax.set_yticklabels([])   # Убирает числовые метки радиуса (0.1, 0.2 и т.д.)
    ax.set_xticklabels([])   # Убирает метки углов (0, 45, 90 градусов), если они тоже не нужны
    ax.spines['polar'].set_visible(False) # Прячет внешнюю ограничивающую окружность
       
    # Добавляем цветовую шкалу справа
    cbar = plt.colorbar(sc, ax=ax, pad=0.1)
    cbar.set_label('Fluctuation density (d_dens)')
    
    ax.set_title(f"Time = {t_val:.2e} (Index: {t_index})", va='bottom')
    
    # Сохраняем кадр
    plt.savefig(f"{output_dir}/polar_time_{t_index:06d}.png", dpi=150, bbox_inches='tight')
    plt.close()

 