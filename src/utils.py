import numpy as np

from src.common.h5reader import H5Reader


def dataset_reader(file_path, dataset_name):
    """Читает массив из HDF5 (обёртка над :meth:`H5Reader.array`)."""
    with H5Reader(file_path) as reader:
        return reader.array(dataset_name)

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
    """Атрибуты объекта HDF5 (обёртка над :meth:`H5Reader.attrs`)."""
    with H5Reader(file_path) as reader:
        return reader.attrs(dataset_path)
    
def get_attributes_recursive_from(file_path: str, start_path: str = '/') -> dict:
    """Рекурсивные атрибуты (обёртка над :meth:`H5Reader.attrs_recursive`)."""
    with H5Reader(file_path) as reader:
        return reader.attrs_recursive(start_path)

def print_dict(d:dict):
    # Вывод результатов
    for object_path, attrs in d.items():
        print(f"Объект: {object_path}")
        for attr_name, attr_value in attrs.items():
            print(f"  - {attr_name}: {attr_value}")



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
    from src.common.paths import wave2d_results
    # Укажите путь к вашему HDF5 файлу
    file_path = str(wave2d_results("FT2"))

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