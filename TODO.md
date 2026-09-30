# TODO

План развития и известные проблемы проекта.
Формат: `- [ ]` — не сделано, `- [x]` — сделано. Приоритет в скобках.

> **ELMFIRE отложен.** Его задачи и наработки вынесены в
> [`TODO_elmfire.md`](TODO_elmfire.md). Здесь — Wave2D и общий домен/инфраструктура.

## 🎯 Цель рефакторинга

В репозитории смешаны две независимые задачи:

1. **Wave2D** — чтение и визуализация `results.h5` (стационарные 2D-поля, комплексные).
2. **ELMFIRE** — чтение/конвертация `*.dat` и временных рядов флуктуаций (`z1.h5`).

Пересечение одно — интеграл перекрытия `∫ f_ELMFIRE(t,ρ,θ)·Ea_Wave2D(ρ,θ)·ρ dρ dθ`
(взаимодействие турбулентности с ВЧ-полем). Его надо вынести в отдельный слой `coupling/`,
а не держать внутри одного из источников.

**Принцип:** не «два репозитория», а слои с общим доменом:

```
[источник A]  [источник B]      ← адаптеры (знают формат файлов)
      \        /
   [ общий домен ]              ← PolarGrid / Field2D / TimeSeries
          |
   [ операции ]                 ← interpolate, integrate, visualize
          |
      [ apps ]                  ← w2d_render.py, w2d_app.py, w2d_viewer.py, elmfire_convert.py, elmfire_viewer.py, elmfire_video.py
```

## 🏗️ Рефакторинг (инкрементально, без «большого взрыва»)

- [ ] **(P1) Шаг 1.** Создать `src/common/`: `PolarGrid`, `Field2D`, `FieldTimeSeries`,
      `regular_polar_grid()`, `units.py`. Ничего не ломать.
- [x] **(P1) `H5Reader`** (`src/common/h5reader.py`) — класс вместо
      `dataset_reader`/`get_*attributes*`: одно соединение, ленивый `dataset()`,
      исключения вместо `exit()`. Обёртки в `src/utils.py` сохранены (бросают).
- [x] **(P1) `w2d_render.py` переведён на `with H5Reader(...)`** — одно соединение на
      все чтения вместо N открытий файла.
- [x] **(P1) `src/wave2d/viewer.py`** — GUI `W2DViewer`: дерево `results.h5`
      (через `H5Reader.walk`) + изображение выбранного датасета; единое
      соединение, виды `(R,Z)`/`(rho,θ)`, `real/imag/abs`, панель атрибутов,
      `NavigationToolbar`.
- [x] **(P1) `src/wave2d/app.py`** — GUI `W2DNavigatorApp`: выбор прогона по ФС
      (`Wave2DNavigator`: кейсы/прогоны/задачи), сводка `run_info`/`run_params`,
      запуск `W2DViewer` в `Toplevel`. Добавлены `Wave2DNavigator.tasks()` +
      `wave2d_tasks()`.
- [x] **(P2) Корневые `w2d_viewer.py`/`w2d_app.py`** — тонкие точки входа
      (`main()`); GUI-логика в `src/wave2d/`. `w2d_render.py` пока оставлен как
      есть (переделать позже).
- [ ] **(P1) Шаг 2.** Вынести `Wave2DResults` из `w2d_render.py` + `src/utils.py`
      (сейчас логика размазана между скриптом и утилитами).
- [ ] **(P2) Шаг 6.** Разнести по папкам `apps/` и `viz/`:

      ```
      src/
      ├── common/      # домен, без знания о файлах
      ├── wave2d/      # адаптер Wave2D: reader.py, visualize.py
      ├── elmfire/     # адаптер ELMFIRE: raw_reader.py, convert.py, fluctuations.py
      ├── coupling/    # пересечение: overlap.py
      ├── viz/         # общая визуализация
      └── apps/        # w2d_render.py, w2d_app.py, w2d_viewer.py, elmfire_convert.py, elmfire_viewer.py, elmfire_video.py
      ```

- [ ] **(P3) Шаг 7.** После стабилизации слоёв — оценить физическое разделение на репозитории
      (границы уже позволят сделать это без переписывания).

## 🗄️ Организация исходных данных

Данных будет много (Wave2D-ранов), поэтому код и данные разделяем.
Данные живут **вне репозитория**, корень задаётся переменной `WAVE2D_DATA_DIR`
(по умолчанию `./data`, в `.gitignore`).

```
data/                              # корень = WAVE2D_DATA_DIR (по умолчанию <repo>/data)
├── wave2d/<case_id>/<stamp>/results.h5          # + tasks/<task>/results.h5
├── wave2d/<case_id>/results.h5                  # legacy-плоско (напр. Globus)
├── elmfire/WagD/{raw/*.dat, converted/z1.h5}
├── derived/
│   ├── plots/{FT-2_LH_smoke,FT-2_LH_smoke_nphi,FT2}/
│   ├── frames/WagD/
│   ├── video/
│   └── coupling/
└── catalog.json                    # JSON-индекс ранов (без SQL) — ещё нет
```

- [x] **(P1) Ввести `WAVE2D_DATA_DIR`** и `src/common/paths.py` — единая точка доступа к данным.
- [x] **(P1) Перевести скрипты на `paths.py`** (run_id первым аргументом).
- [x] **(P1) Мигрировать текущие данные:** `Globus`/`FT2` → `wave2d/<run>/`,
      `z1.h5` → `elmfire/WagD/converted/`, `.dat` → `elmfire/WagD/raw/`,
      `plots_2d/` → `derived/frames/WagD/`.
- [x] **(P2) Разделить source и derived:** PNG/MP4/интегралы — только в `derived/`.
- [x] **(P3) Автосоздание структуры `data/`** — реализовано `paths.ensure_data_root()`.
- [x] **(P1) `Navigator` для Wave2D** — вынесен в `src/common/navigator.py`.
      База `Navigator` (корень + `path()`); `Wave2DNavigator` — рабочий;
      `ElmfireNavigator`/`DerivedNavigator` — заглушки (`NotImplementedError`);
      `DataNavigator` — фасад (`nav.wave2d/elmfire/derived`). Корень задаётся
      при создании, кейсы дискаверятся по ФС, прогон = `<case_id>/<stamp>`;
      legacy-плоско (`Globus/results.h5`) поддержано. Обёртки `wave2d_*`
      сохранены, `paths.py` реэкспортирует навигаторы.
- [x] **(P1) `w2d_render.py` открывает `run_id = <case_id>/<stamp>`**; по умолчанию —
      свежий прогон `FT-2_LH_smoke_nphi` (`wave2d_latest("FT-2_LH_smoke_nphi")`).
      Заодно исправлено: формат
      группы `nphi+122` и путь `field_2D` (было `field_2d`), `print_dict` без
      cp1251-непечатаемых символов.
- [x] **(P1) Поддержать схему `results.h5` >= 0.94.** Введён
      `src/wave2d/schema.py` (`MIN_FORMAT`, `UnsupportedFormatError`,
      `ensure_supported`/`open_results`, константы путей, `nphi`-хелперы);
      старые форматы отклоняются с сообщением «формат не поддерживается».
      `w2d_render.py`/`viewer.py`/`app.py`/`integrator*.py`/`src/utils.py`
      переведены на новые пути (`/grid`, `/input`, `/plasma/*`, `/fields/nphi*`,
      `/manifest`), спекa обновлена (`docs/results_h5.md`).
- [ ] **(P1) Флаг `--latest`** в `w2d_render.py` (явный выбор свежего прогона кейса).
- [ ] **(P1) Убрать хардкод кейса `wave2d_latest("FT-2_LH_smoke_nphi")`** из
      `src/utils.py`.
- [ ] **(P2) `tests/test_paths.py`** — разбор `run_id`, legacy, дискавери, `latest`
      (нужен `pytest`).
- [ ] **(P1) `run_id` + `run.json`** (sidecar): выжимка из h5-атрибутов без чтения массивов
      (`nphi`, `Nr`, `R0`, `a0`, `wave_freq`, `sha256`, `size`, `format_version`).
- [ ] **(P1) `src/common/catalog.py`** — `RunCatalog` (чистый JSON, без SQL):
      читает/пишет `catalog.json`, поиск ранов по параметрам, учёт связок
      `couplings(elmfire_run, wave2d_run, params, result)`.
- [ ] **(P2) Чек-суммы (`sha256`)** в каталоге для контроля целостности при переносе
      (Globus/NAS).
- [ ] **(P3) Абстракция хранилища** за `RunCatalog`: локальный диск → DVC / Git LFS / S3.

## 🧹 Инфраструктура и гигиена

- [ ] **(P2) Добавить `pytest` в dev-зависимости** (`uv add --dev pytest`) и папку `tests/`.
- [x] **(P2) Не коммитить крупные бинарники.** Данные исключены через `data/.gitignore`
      (`*` + `!.gitignore`); глобальные `*.png`/`*.h5`/… убраны из корневого `.gitignore`
      (прятали легитимные файлы вне `data/`, напр. будущие скриншоты в README).
- [x] **(P3) `uv.lock` закоммичен** (убран из `.gitignore`) для воспроизводимости.
- [ ] **(P3) Дописать README** — раздел с физическими величинами и скриншотами.
- [ ] **(P3) Настроить линтер/форматтер** (ruff) и добавить в CI.

## ❓ Открытые вопросы

- Тороидальное мод. число `nphi` берётся из `/input/w2grid/nphi1` — единственный источник?
