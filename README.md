# 🌊 Wave2D Visualizer & Integrator

Программный комплекс на Python для конвертации, анализа, 2D-визуализации и численного
интегрирования результатов моделирования плазмы (данные ELMFIRE).

Проект умеет:

- конвертировать сырые `.dat`-файлы ELMFIRE в сжатый HDF5;
- строить 2D-карты физических полей в координатах `(R, Z)` и `(rho, theta)`;
- интерактивно просматривать эволюцию флуктуаций плотности с ползунком по времени;
- собирать PNG-кадры в видеоролик;
- численно интегрировать произведение флуктуаций и поля на произвольной полярной сетке.

## 📋 Требования

- Python ≥ 3.14
- [uv](https://docs.astral.sh/uv/) — менеджер пакетов и виртуальных окружений
- Tkinter (для GUI-приложений) — обычно входит в стандартную поставку Python

Основные зависимости (см. `pyproject.toml`): `numpy`, `scipy`, `pandas`, `h5py`,
`matplotlib`, `imageio`, `imageio-ffmpeg`, `tqdm`.

## 🛠️ Установка

1. Клонируйте репозиторий и перейдите в папку проекта:

   ```bash
   git clone https://github.com/temper8/wave2d-visualizer.git
   cd wave2d-visualizer
   ```

2. Установите зависимости (uv сам создаст виртуальное окружение `.venv`):

   ```bash
   uv sync
   ```

Все команды ниже запускаются через `uv run <скрипт>` — uv автоматически
использует окружение проекта.

## 📁 Структура проекта

```
wave2d-visualizer/
├── src/
│   ├── utils.py                 # чтение HDF5, 2D-визуализация полей, вывод атрибутов
│   ├── integrate.py             # интеграл произведения флуктуаций и поля
│   ├── interpolator.py          # построение интерполяторов (с замыканием theta и без)
│   └── plasma_fluctuations.py   # класс PlasmaFluctuations: ленивое чтение кадров
├── Elmfire_WagD/                # исходные данные ELMFIRE (.dat)
├── plots_2d/                    # сохранённые PNG-кадры
├── Globus/, FT2/                # готовые графики полей для двух конфигураций
├── converter_to_hdf.py          # ELMFIRE .dat -> HDF5 (z1.h5)
├── Elmfire_reader.py            # просмотр структуры .dat-файлов
├── count_point_per_index.py     # число точек на каждый временной индекс
├── main.py                      # 2D-визуализация полей из results.h5
├── app_tk.py                    # GUI: просмотр флуктуаций (Tkinter + Matplotlib)
├── app_vis_fluct_tk.py          # GUI-дубликат app_tk.py
├── integrator.py                # пример интегрирования по кадру флуктуаций
├── integrator_test_pi.py        # тест интегрирования на единичных полях
├── make_video.py                # сборка PNG -> fluctuations_evolution.mp4
├── pyproject.toml
└── uv.lock
```

## 🗂️ Данные

| Файл | Описание |
|------|----------|
| `Elmfire_WagD/polar_mesh_z1.dat` | полярная сетка (R, Z) |
| `Elmfire_WagD/rho_mesh_z1.dat` | радиальная сетка `rho` и число точек по углу `Ntet` |
| `Elmfire_WagD/time_z1.dat` | временные индексы и физическое время |
| `Elmfire_WagD/nep_z1.dat` | значения флуктуаций плотности (`time_index, rho, theta, d_dens`) |
| `z1.h5` | сконвертированные флуктуации (результат `converter_to_hdf.py`) |
| `results.h5` | результаты расчёта полей (Ea, Ex, eps, Te, Ti, Btot и др.) |

> ⚠️ Большие бинарные файлы (`*.h5`, `*.dat`, `*.rar`) не хранятся в git —
> получите их отдельно и положите в соответствующие папки.

## 🚀 Использование

### 1. Конвертация ELMFIRE → HDF5

Читает `.dat`-файлы из `Elmfire_WagD/` и сохраняет сжатый `z1.h5`:

```bash
uv run converter_to_hdf.py
```

### 2. Просмотр структуры .dat и подсчёт точек

```bash
uv run Elmfire_reader.py
uv run count_point_per_index.py
```

`count_point_per_index.py` сохранит статистику в `points_per_time_index.txt`.

### 3. 2D-визуализация полей

Строит графики полей (`psi`, `Ea`, `Ex`, `eps`, `Te`, `Ti`, `Btot`, `w0_wpe` и др.)
из `results.h5` и сохраняет их в PNG:

```bash
uv run main.py
```

### 4. Интерактивный просмотр флуктуаций

GUI с ползунком по времени на базе Tkinter + Matplotlib:

```bash
uv run app_tk.py
```

### 5. Численное интегрирование

Интеграл произведения флуктуаций и поля на новой регулярной полярной сетке:

```bash
uv run integrator.py          # интегрирование по кадру z1.h5 и полю Ea из results.h5
uv run integrator_test_pi.py  # проверка на единичных полях
```

### 6. Сборка видеоролика

Собирает все PNG из `plots_2d/` в `fluctuations_evolution.mp4` (fps=15):

```bash
uv run make_video.py
```

## 🧮 Формат HDF5 (`z1.h5`)

```
z1.h5
├── rho_mesh/
│   ├── rho          # 1D массив радиусов
│   └── N_theta      # число угловых точек на каждый радиус
├── time_indices     # 1D индексы времени
├── time_values      # 1D физическое время
└── fluctuations     # 3D (N_time, N_rho, N_theta), float32, gzip
```

## 📄 Лицензия

Проект распространяется под лицензией **MIT** — см. файл [LICENSE](LICENSE).
