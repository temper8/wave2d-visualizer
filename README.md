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
│   ├── common/paths.py          # единая точка доступа к данным (WAVE2D_DATA_DIR)
│   ├── utils.py                 # чтение HDF5, 2D-визуализация полей, вывод атрибутов
│   ├── integrate.py             # интеграл произведения флуктуаций и поля
│   ├── interpolator.py          # построение интерполяторов (с замыканием theta и без)
│   └── plasma_fluctuations.py   # класс PlasmaFluctuations: ленивое чтение кадров
├── data/                        # данные вне git, см. AGENTS.md
│   ├── wave2d/{Globus,FT2}/     # результаты Wave2D (results.h5)
│   ├── elmfire/WagD/            # ELMFIRE: raw/*.dat и converted/z1.h5
│   └── derived/                 # plots/, frames/, video/, coupling/
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

Все данные лежат в каталоге `data/` (вне git). Корень можно переопределить
переменной окружения `WAVE2D_DATA_DIR`. Структура:

```
data/
├── wave2d/
│   ├── Globus/results.h5     # nphi-014
│   └── FT2/results.h5        # nphi-122
├── elmfire/
│   └── WagD/
│       ├── raw/*.dat         # исходные файлы ELMFIRE
│       └── converted/z1.h5   # результат converter_to_hdf.py
└── derived/
    ├── plots/{Globus,FT2}/   # карты полей (main.py)
    ├── frames/WagD/          # PNG-кадры флуктуаций
    ├── video/                # fluctuations_evolution.mp4
    └── coupling/             # результаты интеграла перекрытия
```

| Файл | Описание |
|------|----------|
| `data/elmfire/WagD/raw/polar_mesh_z1.dat` | полярная сетка (R, Z) |
| `data/elmfire/WagD/raw/rho_mesh_z1.dat` | радиальная сетка `rho` и число точек по углу `Ntet` |
| `data/elmfire/WagD/raw/time_z1.dat` | временные индексы и физическое время |
| `data/elmfire/WagD/raw/nep_z1.dat` | значения флуктуаций плотности (`time_index, rho, theta, d_dens`) |
| `data/elmfire/WagD/converted/z1.h5` | сконвертированные флуктуации |
| `data/wave2d/Globus/results.h5` | поля Wave2D, ран Globus (nphi-014) |
| `data/wave2d/FT2/results.h5` | поля Wave2D, ран FT2 (nphi-122) |

> ⚠️ Большие бинарные файлы (`*.h5`, `*.dat`, `*.rar`) не хранятся в git.
> Пути в коде берутся через `src/common/paths.py`, а не задаются вручную.

## 🚀 Использование

### 1. Конвертация ELMFIRE → HDF5

Читает `.dat`-файлы из `data/elmfire/<run>/raw/` и сохраняет сжатый `z1.h5`:

```bash
uv run converter_to_hdf.py WagD
```

### 2. Просмотр структуры .dat и подсчёт точек

```bash
uv run Elmfire_reader.py WagD
uv run count_point_per_index.py WagD
```

`count_point_per_index.py` сохранит статистику в
`data/derived/WagD/points_per_time_index.txt`.

### 3. 2D-визуализация полей

Строит графики полей (`psi`, `Ea`, `Ex`, `eps`, `Te`, `Ti`, `Btot`, `w0_wpe` и др.)
из `results.h5` и сохраняет их в `data/derived/plots/<run>/`:

```bash
uv run main.py Globus
uv run main.py FT2
```

### 4. Интерактивный просмотр флуктуаций

GUI с ползунком по времени на базе Tkinter + Matplotlib:

```bash
uv run app_tk.py
```

### 5. Численное интегрирование

Интеграл произведения флуктуаций и поля на новой регулярной полярной сетке:

```bash
uv run integrator.py          # кадр z1.h5 (WagD) + поле Ea из results.h5 (Globus)
uv run integrator_test_pi.py  # проверка на единичных полях
```

### 6. Сборка видеоролика

Собирает все PNG из `data/derived/frames/WagD/` в
`data/derived/video/fluctuations_evolution.mp4` (fps=15):

```bash
uv run make_video.py WagD
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
