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
   Агент подставляет **свои** имя и модель — те, от имени которых реально сделан
   коммит. Не хардкодить чужое имя (в том числе `pi`): у другого агента/модели
   суффикс будет свой. Конкретные способы узнать имена (переменные окружения,
   конфиг харнесса) зависят от агента и в этом правиле не фиксируются.

## Что это за проект

Python-комплекс для конвертации, 2D-визуализации и численного интегрирования
результатов моделирования плазмы. Объединяет **два независимых источника данных** —
не путай их:

| | **Wave2D** | **ELMFIRE** |
|---|---|---|
| Файлы | `results.h5` (+ `tasks/<задача>/results.h5`) | `Elmfire_WagD/*.dat` → `z1.h5` |
| Что это | стационарные 2D-поля (решение волнового уравнения) | временной ряд турбулентных флуктуаций |
| Сетка | `(rho, theta)`: Globus `(361, 1024)`, FT2 `(51, 128)` | `(121, 600)` |
| Время | нет | 945 кадров |
| Тип данных | `complex128` (Ex/Ey/Ez, eps, eta, gee) | `float32`, вещественное |
| Параметр | тороидальное число `nphi` (`nphi+122`); бывает серия по `Nr` | — |

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
├── common/navigator.py      # Navigator + Wave2D/Elmfire/Derived/Data навигаторы
├── common/paths.py          # доступ к данным: реэкспорт Navigator + ELMFIRE/derived
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
│   ├── Globus/
│   │   └── results.h5               # один прогон, nphi-014, (361, 1024)
│   └── FT2/                         # кейс (`case_id`); внутри — прогоны `<stamp>`
│       └── <timestamp>/             # напр. 2026-09-23_21-58-05
│           ├── results.h5           # общий файл серии по nphi (5 мод)
│           ├── input.toml, done_tasks.txt, system_info.ini, ...
│           └── tasks/<задача>/results.h5   # по файлу на моду: nphi+000 … nphi-122
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
- Wave2D: кейсы (`case_id`: `Globus`, `FT2`, ...) — подкаталоги `data/wave2d/`;
  внутри кейса — прогоны `<stamp>` (`FT2/<stamp>/`). Legacy-плоско
  (`Globus/results.h5`) поддержано. Список кейсов не хардкодится — дискавери и
  пути даёт `navigator.DataNavigator` (фасад): `nav.wave2d.cases()/runs()/
  latest()/results()/task_results()`. База — `Navigator` (корень + `path()`),
  `Wave2DNavigator` — реализован, `ElmfireNavigator`/`DerivedNavigator` — заглушки
  (см. `TODO.md`). Всё реэкспортируется из `paths.py`, обёртки `wave2d_*` сохранены.
- ELMFIRE: `WagD`.
- Скрипты пока вызывают `wave2d_results(run_id)` со старым `run_id`; переход на
  `run_id = "<case_id>/<stamp>"` и флаг `--latest` — в `TODO.md`.

## Формат данных

Формат HDF5-файлов вынесен в отдельные спецификации — не дублировать его здесь:

- **Wave2D** (`results.h5`) — [`docs/hdf5_schema.md`](docs/hdf5_schema.md)
  (канон, продюсерская спека) и [`docs/results_h5.md`](docs/results_h5.md)
  (читательская: наблюдения, инварианты, подводные камни).
- **ELMFIRE** (`z1.h5`) — [`docs/elmfire_h5.md`](docs/elmfire_h5.md)
  (черновик, формат ещё не изучен).

При работе с файлами сверяйся со спеками; при изменении формата обновляй спеку.

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
3. **`coord/rho` = 397 ≠ Nr = 361 (Globus).** Первые `Nr` — физическая сетка,
   остальное — margin. Не используй `coord/rho` целиком.
4. **`integrator.py` хардкодит кадр 42.** Постановка интеграла ещё не зафиксирована.
5. **FT2 — вложенный каталог прогонов.** Единого `FT2/results.h5` нет: данные
   в `FT2/<stamp>/` (`results.h5` — общий файл серии по `nphi`,
   `tasks/<задача>/results.h5` — по моде). Учитывается `Navigator`
   (`run_id = "FT2/<stamp>"`); переход CLI — в `TODO.md`.
6. **Сентинелы на оси `ir = 0` — `0.0`, а не `NaN`.** Незаполненные точки равны
   нулю; в `plasma_par_2D` вне первой точки — мусор. Подробности —
   [`docs/results_h5.md`](docs/results_h5.md).

## Приоритеты

- **P0** — блокеры физики: единицы, постановка интеграла.
- **P1** — баг интерполятора, вынос `src/common/`, адаптеры, тесты.
- **P2/P3** — структура папок, pytest, gitignore бинарников, линтер.

Актуальный список задач — в `TODO.md`. Перед крупным рефакторингом сверяйся с ним
и предлагай инкрементальные шаги, не ломающие текущие скрипты.
