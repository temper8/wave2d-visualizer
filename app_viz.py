import streamlit as st
import numpy as np
import h5py
import matplotlib.pyplot as plt

# 1. Настройка страницы
st.set_page_config(page_title="Plasma Wave 2D", layout="centered")
st.title("🌊 Интерактивный анализ адаптивной 3D-сетки")

# Функция для безопасного подключения к HDF5 и чтения легких метаданных
@st.cache_resource
def open_h5_file(filepath):
    # Файл открывается один раз и кэшируется Streamlit как постоянный ресурс
    return h5py.File(filepath, 'r')

try:
    f = open_h5_file('z1.h5')
    
    # Считываем одномерные метаданные (они легкие)
    rho_1d = f['rho_mesh/rho'][:]
    time_values = f['time_values'][:]
    ntheta_1d = f['/rho_mesh/N_theta'][:]
    
    # Определяем размеры нашей 3D матрицы флуктуаций
    # Срез имеет форму (N_rho, Max_tet), например (17, 105)
    total_frames = f['fluctuations'].shape[0]
    max_tet_points = f['fluctuations'].shape[2]
    
except Exception as e:
    st.error(f"Не удалось открыть файл данных HDF5. Убедитесь, что запустили конвертер. Ошибка: {e}")
    st.stop()


# --- 2. БОКОВАЯ ПАНЕЛЬ УПРАВЛЕНИЯ ---
st.sidebar.header("⚙️ Панель управления")
#total_frames = 945
# Слайдер выбора временного шага (кадра)
frame_idx = st.sidebar.slider(
    "Временной шаг (Индекс кадра):",
    min_value=0,
    max_value=total_frames - 1,
    value=0
)

# Выбор палитры
cmap_choice = st.sidebar.selectbox(
    "Цветовая схема:",
    options=['coolwarm', 'viridis', 'magma', 'inferno'],
    index=0
)

# Чекбокс для фиксации масштаба цвета
fix_scale = st.sidebar.checkbox("Зафиксировать шкалу цвета (абсолютные значения)", value=True)

# --- 3. ЧТЕНИЕ ДАННЫХ И ОТРИСОВКА ---
# Ленивое чтение: достаем с диска ТОЛЬКО одну матрицу для выбранного кадра
current_frame = f['fluctuations'][frame_idx, :, :]
t_val = time_values[frame_idx]

# Отображаем метку времени в интерфейсе
st.metric(label="Физическое время симуляции", value=f"{t_val:.4e} с")

# Генерируем сетку углов тета для прямоугольного отображения в matplotlib
theta_1d = np.linspace(0, 2 * np.pi, max_tet_points)
T, R = np.meshgrid(theta_1d, rho_1d)

# Создаем полярный график
fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={'projection': 'polar'})

# Настройка границ цветовой шкалы
if fix_scale:
    # Игнорируем NaN при поиске глобального минимума и максимума в текущем кадре или задаем вручную.
    # Для идеальной фиксации лучше посчитать один раз при конвертации, 
    # но для скорости возьмем min/max по всему открытому срезу, если не заданы жесткие границы.
    vmin = float(np.nanmin(f['fluctuations'][0, :, :]))
    vmax = float(np.nanmax(f['fluctuations'][0, :, :]))
    color_limits = {'vmin': vmin, 'vmax': vmax}
else:
    color_limits = {}

# Отрисовка. pcolormesh автоматически не рисует ячейки, где лежит np.nan
tc = ax.pcolormesh(
    T, R, current_frame, 
    cmap=cmap_choice, 
    shading='nearest', 
    **color_limits
)

# Полностью убираем координатную сетку, радиальные и угловые метки по вашему требованию
ax.grid(False)
ax.set_yticklabels([])
ax.set_xticklabels([])
ax.spines['polar'].set_visible(False)

# Добавляем цветовую шкалу
cbar = plt.colorbar(tc, ax=ax, pad=0.05)
cbar.set_label('Плотность флуктуаций (rho_fluc)')

# Выводим график в Streamlit
st.pyplot(fig)

# --- 4. ДОПОЛНИТЕЛЬНАЯ СТАТИСТИКА (По желанию) ---
with st.expander("📊 Посмотреть статистику кадра"):
    valid_points = np.count_nonzero(~np.isnan(current_frame))
    st.write(f"**Всего ячеек в матрице:** {current_frame.size} (из них заполнены: {valid_points}, пусты с маской NaN: {current_frame.size - valid_points})")
    st.write(f"**Максимальный уровень флуктуаций:** {np.nanmax(current_frame):.4f}")
    st.write(f"**Минимальный уровень флуктуаций:** {np.nanmin(current_frame):.4f}")
