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

def view_complex_2d(R,Z, data_2d, title, filename=None):
    fig, ax = plt.subplots(2, 2, figsize=(12, 6))
    ax[0,0].pcolormesh(R, Z, data_2d[:,:].real, shading='gouraud')
    ax[0,0].set_aspect('equal')
    ax[0,0].set_title(f"{title}.real (R,Z)")
    #ax2.pcolormesh(R, Z, np.flip(density[:,:]), shading='gouraud')
    ax[0,1].imshow(data_2d[:,:].real, interpolation='none')
    ax[0,1].set_aspect('equal')
    ax[0,1].set_title(f"{title} (rho,theta)")

    ax[1,0].pcolormesh(R, Z, data_2d[:,:].imag, shading='gouraud')
    ax[1,0].set_aspect('equal')
    ax[1,0].set_title(f"{title}.imag (R,Z)")
    #ax2.pcolormesh(R, Z, np.flip(density[:,:]), shading='gouraud')
    ax[1,1].imshow(data_2d[:,:].imag, interpolation='none')
    ax[1,1].set_aspect('equal')
    ax[1,1].set_title(f"{title} (rho,theta)")

    if filename:
        fig.savefig(f"{filename}.png")  
    else:
         fig.savefig(f"{title}.png")  
    plt.show()    

def get_dataset_attributes(file_path: str, dataset_path: str) -> dict:
    """
    Читает и возвращает все атрибуты указанного датасета из HDF5 файла.
    
    :param file_path: Путь к файлу HDF5 (например, 'data.h5')
    :param dataset_path: Путь к датасету внутри файла (например, '/group/dataset')
    :return: Словарь со всеми атрибутами датасета
    """
    try:
        with h5py.File(file_path, 'r') as f:
            # Проверяем существование датасета в файле
            if dataset_path not in f:
                print(f"Ошибка: Датасет '{dataset_path}' не найден в файле.")
                return {}
            
            dset = f[dataset_path]
            # Превращаем интерфейс атрибутов в стандартный словарь Python
            return dict(dset.attrs.items())
            
    except FileNotFoundError:
        print(f"Ошибка: Файл '{file_path}' не найден.")
        return {}
    except Exception as e:
        print(f"Произошла ошибка при чтении файла: {e}")
        return {}
    
def get_attributes_recursive_from(file_path: str, start_path: str = '/') -> dict:
    """
    Рекурсивно собирает атрибуты, начиная с заданного пути (группы) в HDF5 файле.
    
    :param file_path: Путь к файлу HDF5
    :param start_path: Путь внутри HDF5, с которого начать обход (например, '/my_group')
    :return: Словарь вида { 'путь_к_объекту': { 'атрибут': значение } }
    """
    all_attributes = {}
    
    # Нормализуем начальный путь (убираем лишние слэши в конце)
    start_path = start_path.rstrip('/') or '/'

    def visitor(name, obj):
        if obj.attrs:
            # Формируем полный путь к объекту внутри файла
            #full_path = f"{start_path}/{name}".replace('//', '/')
            full_path = f"{name}".replace('//', '/')
            all_attributes[full_path] = dict(obj.attrs.items())

    try:
        with h5py.File(file_path, 'r') as f:
            if start_path not in f:
                print(f"Ошибка: Путь '{start_path}' не найден в файле.")
                return {}
                
            start_obj = f[start_path]
            
            # 1. Проверяем атрибуты самого стартового объекта
            if start_obj.attrs:
                all_attributes[start_path] = dict(start_obj.attrs.items())
            
            # 2. Если это группа, запускаем рекурсивный обход вложенных элементов
            if isinstance(start_obj, h5py.Group):
                start_obj.visititems(visitor)
                
    except FileNotFoundError:
        print(f"Ошибка: Файл '{file_path}' не найден.")
    except Exception as e:
        print(f"Произошла ошибка при чтении файла: {e}")
        
    return all_attributes

def print_dict(d:dict):
    # Вывод результатов
    for object_path, attrs in d.items():
        print(f"Объект: {object_path}")
        for attr_name, attr_value in attrs.items():
            print(f"  └─ {attr_name}: {attr_value}")



def plot_polar_2d(r, phi, Z, title="2D Полярный график", cmap="viridis"):
    """
    Рисует 2D массив значений в полярных координатах.
    
    Параметры:
    r (1D array): Вектор радиусов (длина N).
    phi (1D array): Вектор углов в радианах (длина M).
    Z (2D array): Матрица значений размера (N x M) или (M x N).
    title (str): Заголовок графика.
    cmap (str): Цветовая палитра.
    """
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    
    # Создаем 2D сетку координат для корректного отображения
    R, Phi = np.meshgrid(r, phi)
    
    # Если размерность Z не совпадает с сеткой (транспонирована), меняем ее
    if Z.shape != Phi.shape:
        Z = Z.T
        
    # Сетка углов в pcolormesh должна замыкаться, shading='auto' это учитывает
    mesh = ax.pcolormesh(Phi, R, Z, cmap=cmap, shading='auto')
    
    # Настройка внешнего вида
    fig.colorbar(mesh, ax=ax, label='Значение')
    ax.set_title(title, va='bottom', fontsize=14)
    
    plt.show()

import matplotlib.pyplot as plt
# Дальнейшая работа с data_array...
if __name__ == '__main__':
    # Укажите путь к вашему HDF5 файлу
    file_path = 'results.h5'

    run_info = get_attributes_recursive_from(file_path, start_path='/run_info')
    print_dict(run_info)
    run_params = get_attributes_recursive_from(file_path, start_path='/run_params')
    print_dict(run_params)

    dataset_name = '/coord/R'  # Имя 3D массива внутри файла
    R = dataset_reader(file_path, '/coord/X')
    Z = dataset_reader(file_path, '/coord/Y')
    data_2d = dataset_reader(file_path, '/nphi-122/field_2d/Ea')
    view2d(R, Z, data_2d, "Ea field")
    print("\nДанные успешно загружены в переменную 'data_array'")