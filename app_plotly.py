import streamlit as st
import numpy as np
import h5py
import plotly.graph_objects as go

st.set_page_config(page_title="Plasma Wave 2D (Plotly)", layout="centered")
st.title("🌊 Сверхбыстрый анализ плазмы с Plotly")

H5_FILE = 'z1.h5'

# --- 1. КЭШИРОВАНИЕ МЕТАДАННЫХ ---
@st.cache_data
def load_metadata():
    with h5py.File(H5_FILE, 'r') as f:
        rho_1d = f['rho_mesh/rho'][:]
        time_values = f['time_values'][:]
        total_frames, _, max_tet_points = f['fluctuations'].shape
    return rho_1d, time_values, total_frames, max_tet_points

try:
    rho_1d, time_values, total_frames, max_tet_points = load_metadata()
except Exception as e:
    st.error(f"Не удалось прочитать HDF5 файл. Ошибка: {e}")
    st.stop()

# --- 2. ЛЕНИВОЕ ЧТЕНИЕ КАДРА ---
def read_single_frame(frame_idx):
    with h5py.File(H5_FILE, 'r') as f:
        current_frame = f['fluctuations'][frame_idx, :, :]
        # Берём первый кадр за эталон для фиксации шкалы
        base_frame = f['fluctuations'][0, :, :]
        vmin = float(np.nanmin(base_frame))
        vmax = float(np.nanmax(base_frame))
    return current_frame, vmin, vmax

# --- 3. ИНТЕРФЕЙС УПРАВЛЕНИЯ ---
st.sidebar.header("⚙️ Панель управления")

frame_idx = st.sidebar.slider(
    "Временной шаг (Индекс кадра):",
    min_value=0,
    max_value=total_frames - 1,
    value=0
)

# Палитры Plotly (названия немного отличаются от matplotlib)
cmap_choice = st.sidebar.selectbox(
    "Цветовая схема:",
    options=['Coolwarm', 'Viridis', 'Plasma', 'Inferno', 'Jet'],
    index=0
)

fix_scale = st.sidebar.checkbox("Зафиксировать шкалу цвета", value=True)

# Чтение текущих данных
current_frame, vmin, vmax = read_single_frame(frame_idx)
t_val = time_values[frame_idx]

st.metric(label="Физическое время симуляции", value=f"{t_val:.4e} с")

print(f"max_tet_points= {max_tet_points}")
# --- 4. ПЕРЕВОД В ДЕКАРТОВЫ КООРДИНАТЫ ДЛЯ ПРАВИЛЬНОЙ ОТРИСОВКИ ---
theta_1d = np.linspace(0, 2 * np.pi, max_tet_points)
T, R = np.meshgrid(theta_1d, rho_1d)

# Переводим сетку в X и Y, чтобы Plotly построил честную 2D-карту
X = R * np.cos(T)
Y = R * np.sin(T)

# --- 5. ПОСТРОЕНИЕ ИНТЕРАКТИВНОГО ГРАФИКА PLOTLY ---
fig = go.Figure()

# Задаем параметры цветовой шкалы
color_axis_args = {'zmin': vmin, 'zmax': vmax} if fix_scale else {}

x_coords = X[0, :] # строка углов, пересчитанная в X
y_coords = Y[:, 0] # столбец радиусов, пересчитанный в Y

fig.add_trace(go.Heatmap(
    x=X[0, :],         # Используем одномерные срезы сетки
    y=Y[:, 0],
    z=current_frame,   # Сама матрица 17x105 с NaN-масками
    colorscale='plasma', #cmap_choice,
    hoverinfo='x+y+z',
    showscale=True,
    colorbar=dict(title='Плотность флуктуаций'),
    **color_axis_args
))

# Настраиваем внешний вид: убираем оси, делаем график квадратным
fig.update_layout(
    xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
    yaxis=dict(visible=False),
    margin=dict(l=20, r=20, t=40, b=20),
    width=600,
    height=600,
    showlegend=False,
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)'
)
# Выводим в Streamlit (используем True для адаптивности под размер экрана)
st.plotly_chart(fig,  width='stretch')
