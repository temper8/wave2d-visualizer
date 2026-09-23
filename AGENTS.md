# AGENTS.md

Инструкции для AI-агентов и контрибьюторов, работающих с репозиторием
**wave2d-visualizer**. Читай этот файл перед изменениями.

## Правила работы агента

1. **Не менять код без одобрения идеи человеком.** Сначала описать предлагаемое
   изменение (что, зачем, какие файлы и риски) и дождаться явного «да». Только
   после одобрения писать/править код. Мелкие правки в этой памятке и `TODO.md`
   под это правило не попадают.
2. **Каждый коммит подписывать суффиксом** `[<agent name>/<model name>]`
   в конце сообщения, например:
   `feat: add PolarGrid domain type [pi/deepseek-v4.1-flash]`.
   Имена брать из переменных окружения: `PI_CODING_AGENT`/имя харнесса — агент,
   `PI_MODEL` — модель.

## Что это за проект

Python-комплекс для конвертации, 2D-визуализации и численного интегрирования
результатов моделирования плазмы. Объединяет **два независимых источника данных** —
не путай их:

| | **Wave2D** | **ELMFIRE** |
|---|---|---|
| Файлы | `results.h5`, `results_FT2.h5` | `Elmfire_WagD/*.dat` → `z1.h5` |
| Что это | стационарные 2D-поля (решение волнового уравнения) | временной ряд турбулентных флуктуаций |
| Сетка | `(rho, theta)`, обычно `(361, 1024)` | `(121, 600)` |
| Время | нет | 945 кадров |
| Тип данных | `complex128` (Ex/Ey/Ez, eps, eta, gee) | `float32`, вещественное |
| Параметр | тороидальное число `nphi` (`nphi-014`) | — |

**Единственное пересечение** — интеграл перекрытия
`∫ f_ELMFIRE(t,ρ,θ)·Ea_Wave2D(ρ,θ)·ρ dρ dθ` в `integrator.py`. Его целевое место —
отдельный слой `src/coupling/`. См. `TODO.md`.

## Окружение и команды

- Python **3.14** (см. `.python-version`), менеджер пакетов — **uv**.
- Устанавливать/синхронизировать: `uv sync`
- Запускать любой скрипт: `uv run <script.py>` (uv сам использует `.venv`).
- Не вызывать `pip` напрямую. Зависимости добавлять через `uv add` (dev — `uv add --dev`).

Основные скрипты:

```bash
uv run converter_to_hdf.py    # Elmfire_WagD/*.dat -> z1.h5
uv run main.py                # 2D-графики полей из results.h5
uv run app_tk.py              # GUI просмотра флуктуаций
uv run integrator.py          # интеграл перекрытия
uv run make_video.py          # plots_2d/*.png -> fluctuations_evolution.mp4
```

## Карта репозитория

```
src/
├── common/paths.py          # единая точка доступа к данным (WAVE2D_DATA_DIR)
├── utils.py                 # чтение HDF5, view2d/view_complex_2d, plot_polar_2d
├── integrate.py             # integrate_on_custom_grid() — интеграл перекрытия
├── interpolator.py          # get_periodic_interpolator / get_interpolator
└── plasma_fluctuations.py   # PlasmaFluctuations — ленивое чтение кадров z1.h5
converter_to_hdf.py          # ELMFIRE .dat -> HDF5
Elmfire_reader.py            # просмотр структуры .dat
count_point_per_index.py     # точек на временной индекс
main.py                      # 2D-визуализация полей Wave2D
app_tk.py / app_vis_fluct_tk.py  # GUI (дубликаты!)
integrator.py                # пример интеграла перекрытия
integrator_test_pi.py        # проверка на единичных полях
make_video.py                # сборка видео
```

## Где лежат данные

Код и данные разделены: данные живут **вне репозитория**, в корне из переменной
`WAVE2D_DATA_DIR` (по умолчанию `<repo>/data`, в `.gitignore`).

Фактическая структура:

```
data/
├── wave2d/
│   ├── Globus/results.h5     # nphi-014
│   └── FT2/results.h5        # nphi-122
├── elmfire/
│   └── WagD/
│       ├── raw/*.dat         # nep_z1.dat, polar/rho/time mesh, *.rar
│       └── converted/z1.h5   # результат converter_to_hdf.py
└── derived/
    ├── plots/{Globus,FT2}/   # карты полей (main.py)
    ├── frames/WagD/          # 945 PNG кадров флуктуаций
    ├── video/                # fluctuations_evolution.mp4
    └── coupling/             # результаты интеграла перекрытия
```

- Все пути — только через `src/common/paths.py` (`wave2d_results`, `elmfire_raw`,
  `elmfire_converted`, `frames_dir`, `video_dir`, `plots_dir`, `derived`, ...).
  Не хардкодить `results.h5` / `z1.h5` / `Elmfire_WagD`.
- Скрипты принимают `run_id` первым аргументом (`uv run main.py Globus`,
  `uv run converter_to_hdf.py WagD`). Значения по умолчанию — `Globus` / `WagD`.
- Всё, что генерирует код (PNG, MP4, интегралы), писать **только** в `derived/`.
- `catalog.json` и sidecar `run.json` пока **не реализованы** — см. `TODO.md`.
- Раны: Wave2D `Globus`/`FT2`, ELMFIRE `WagD`. Список — в `src/common/paths.py`.

## Формат данных (важно)

### `results.h5` (Wave2D)

```
/coord/{X,Y}                 (361,1024)  meshgrid для pcolormesh
/coord/rho                   (397,)      397 = Nrmargin, физическая часть = 361
/run_params/w2grid           attrs: Nr=361, Nrmargin=397, nphi1=-14, Msmax=1024
/{nphi}/field_2d/{Ea,Ex,Ey,Ez}
/di_tensor_2D/{eps,eta,gee,L,aMX,aTT}
/flux_surf_2D/{psi,theta_deg,theta_pi_diff}
/magnt_fld_2D/{Btot,Bpol,Btor,Nparall,...}
/plasma_par_2D/{Te,Ti,ne,VRe,VRi,coll_rate,damp_rate}
/resonance_2D/{w0_wpe,w0_wce,w0_wlh,w0_wuh,Xcutoff_at_0,PolRes_at_0}
/wkb_2D/{Nrho1,Nrho2}
```

Имя группы `nphi` формируется из `run_params['w2grid']['nphi1']`:
`f"nphi-{abs(n):03d}"` при `n<0`, иначе `f"nphi{n:03d}"`.

### `z1.h5` (ELMFIRE)

```
/rho_mesh/rho       (121,)        1D радиусы (в исходнике — сантиметры!)
/rho_mesh/N_theta   (121,)        число угловых точек на радиус
/time_indices       (945,)
/time_values        (945,)        физическое время
/fluctuations       (945,121,600) (time, rho, theta), float32, gzip
```

## Соглашения

- **Комментарии и docstring — на русском** (как в существующем коде).
- Чтение HDF5 — через `h5py`, крупные датасеты читать **лениво** (по кадру),
  не грузить `results.h5`/`z1.h5` целиком.
- Для GUI использовать `matplotlib.use('TkAgg')` **до** импорта `pyplot`.
- Новые модули класть в `src/`, скрипты-точки входа — в корне.
- Не плодить дубликаты (сейчас `app_tk.py` == `app_vis_fluct_tk.py` — это долг, не пример).

## Известные подводные камни

1. **Единицы.** ELMFIRE `rho(cm)` — сантиметры; Wave2D, похоже, метры.
   Не строишь интеграл, пока не убедился в согласованности единиц (множитель 100).
2. **`get_interpolator` (непериодический) содержит баг** с `endpoint=True`.
   Использовать `get_periodic_interpolator`. Подробности — в `TODO.md`.
3. **`coord/rho` = 397 ≠ Nr = 361.** Первые 361 — физическая сетка, остальное — margin.
   Не используй `coord/rho` целиком.
4. **`integrator.py` хардкодит кадр 42.** Постановка интеграла ещё не зафиксирована.

## Приоритеты

- **P0** — блокеры физики: единицы, постановка интеграла.
- **P1** — баг интерполятора, вынос `src/common/`, адаптеры, тесты.
- **P2/P3** — структура папок, pytest, gitignore бинарников, линтер.

Актуальный список задач — в `TODO.md`. Перед крупным рефакторингом сверяйся с ним
и предлагай инкрементальные шаги, не ломающие текущие скрипты.
