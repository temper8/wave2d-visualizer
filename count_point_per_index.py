import sys

import pandas as pd

from src.common.paths import elmfire_raw, derived

run_id = sys.argv[1] if len(sys.argv) > 1 else "WagD"

print("Считывание индексов времени...")
# Читаем ТОЛЬКО столбец с индексами. Это экономит гигабайты ОЗУ, 
# так как остальные колонки нам для подсчёта количества точек не нужны.
df_indices = pd.read_csv(str(elmfire_raw(run_id) / 'nep_z1.dat'), sep=r'\s+', header=None, usecols=[0], names=['time_index'], dtype=int)

print("Подсчёт количества точек...")
# Группируем по индексам и считаем размер каждой группы
counts = df_indices.groupby('time_index').size().reset_index(name='points_count')

# Сохраняем результат в файл
output_file = derived(run_id, 'points_per_time_index.txt')
output_file.parent.mkdir(parents=True, exist_ok=True)
counts.to_csv(output_file, sep='\t', index=False)

print(f"Готово! Результаты сохранены в файл: {output_file}")
print("Первые несколько строк результата:")
print(counts.head())
