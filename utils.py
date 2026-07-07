import h5py
import numpy as np

def dataset_reader(file_path, dataset_name):
    try:
        # Открываем файл в режиме чтения
        with h5py.File(file_path, 'r') as f:
            # Проверяем существование набора данных
            if dataset_name not in f:
                raise ValueError(f"Набор данных '{dataset_name}' не найден в файле")
            
            dataset = f[dataset_name]
                      
            # Выводим информацию о массиве
            print(f"Успешно прочитан массив: {dataset_name}")
            print(f"Размерность: {dataset.shape}")
            print(f"Тип данных: {dataset.dtype}")
            
            # Читаем весь массив в память (осторожно с большими данными!)
            return np.array(dataset)
            
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        exit(1)

def view2d(R,Z, data_2d, title, filename=None):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    ax1.pcolormesh(R, Z, data_2d[:,:], shading='gouraud')
    ax1.set_aspect('equal')
    ax1.set_title(f"{title} (R,Z)")
    #ax2.pcolormesh(R, Z, np.flip(density[:,:]), shading='gouraud')
    ax2.imshow(data_2d[:,:], interpolation='none')
    ax2.set_aspect('equal')
    ax2.set_title(f"{title} (rho,theta)")
    if filename:
        fig.savefig(f"{filename}.png")  
    else:
         fig.savefig(f"{title}.png")  
    plt.show()

import matplotlib.pyplot as plt
# Дальнейшая работа с data_array...
if __name__ == '__main__':
    # Укажите путь к вашему HDF5 файлу
    file_path = 'results.h5'
    dataset_name = '/coord/R'  # Имя 3D массива внутри файла
    R = dataset_reader(file_path, '/nphi-122/grid_2d/X')
    Z = dataset_reader(file_path, '/nphi-122/grid_2d/Y')
    data_2d = dataset_reader(file_path, '/nphi-122/field_2d/Ea')
    view2d(R, Z, data_2d, "Ea field")
    print("\nДанные успешно загружены в переменную 'data_array'")