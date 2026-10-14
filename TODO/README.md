# Задачи проекта

Каталог задач. **Одна задача — один файл** в этой папке; выполненные переносятся
в `done/`. Имена файлов — длинные и описательные (kebab-case, `.md`), чтобы по
имени было понятно содержимое без открытия.

Имя открытой задачи начинается с префикса приоритета — `p0-`…`p9-`, чтобы
сортировка по имени давала порядок работ (**меньше номер — выше приоритет**).
Закрытые задачи переносятся в `done/`, где вместо приоритета в имени стоит
префикс даты закрытия `ГГГГ-ММ-ДД-` (это архив).

## Формат задачи

Шапка каждого файла:

- **Приоритет:** `P0`…`P9`.
- **Статус:** `todo` | `doing` | `blocked` | `done`.
- **Зависит от:** ссылки на другие задачи (если есть).
- **Файлы:** какие модули/скрипты затрагиваются.

Тело: раздел «Контекст» (зачем и принятые решения) и чеклист «Шаги».

## Приоритеты

Шкала `P0`…`P9`, меньше номер — выше приоритет. Ориентир:

- **P0–P2** — высокий: фундамент и архитектура, мешающие работе
  (`PolarGrid`/`Field2D`, вынос `Wave2DResults`).
- **P3–P5** — средний: инструменты и данные (флаг `--latest`, `catalog.json`,
  тесты).
- **P6–P8** — низкий: структура папок, dimension scales, README, линтер,
  разделение репозиториев.
- **P9** — отложено (ниже P8): ELMFIRE и интеграл перекрытия. Именно здесь
  лежат блокеры физики (единицы, постановка интеграла) — задача отложена,
  поэтому стоит последней, а не первой.

## Открытые задачи

| Файл | Приоритет | Статус | Кратко |
|---|---|---|---|
| [p0-multi-select-and-multi-curve-1d-dataset-view.md](p0-multi-select-and-multi-curve-1d-dataset-view.md) | P0 | todo | Несколько 1D-рядов в `DatasetView`: multi-select, наложение, легенда |
| [p1-extract-common-domain-model-polargrid-field2d-timeseries.md](p1-extract-common-domain-model-polargrid-field2d-timeseries.md) | P1 | todo | `src/common/`: `PolarGrid`, `Field2D`, `FieldTimeSeries`, `units.py` |
| [p2-extract-wave2dresults-from-render-and-utils.md](p2-extract-wave2dresults-from-render-and-utils.md) | P2 | todo | Вынести `Wave2DResults` из `w2d_render.py`/`utils.py` |
| [p3-add-latest-flag-and-remove-hardcoded-wave2d-case.md](p3-add-latest-flag-and-remove-hardcoded-wave2d-case.md) | P3 | todo | Флаг `--latest`, убрать хардкод кейса |
| [p4-add-catalog-json-and-run-sidecar-with-checksums.md](p4-add-catalog-json-and-run-sidecar-with-checksums.md) | P4 | todo | `run.json` sidecar + `catalog.py` + `sha256` + хранилище |
| [p5-add-pytest-and-tests-for-paths-runid-and-fieldmap.md](p5-add-pytest-and-tests-for-paths-runid-and-fieldmap.md) | P5 | todo | `pytest` + `tests/` (пути, `run_id`, чистые части viewer) |
| [p6-reorganize-src-into-apps-and-viz-packages.md](p6-reorganize-src-into-apps-and-viz-packages.md) | P6 | todo | Разнести `src/` на `apps/` и `viz/` |
| [p7-hdf5-dimension-scales.md](p7-hdf5-dimension-scales.md) | P7 | todo | Привязать dimension scales к осям `grid` |
| [p8-evaluate-splitting-repositories-after-layering.md](p8-evaluate-splitting-repositories-after-layering.md) | P8 | todo | Оценить физическое разделение репозиториев |
| [p8-write-readme-with-physical-units-and-screenshots.md](p8-write-readme-with-physical-units-and-screenshots.md) | P8 | todo | README: физ. величины и скриншоты |
| [p8-setup-ruff-linter-and-ci.md](p8-setup-ruff-linter-and-ci.md) | P8 | todo | ruff + CI |
| [p9-elmfire-overlap-integral-and-fluctuations-shelved.md](p9-elmfire-overlap-integral-and-fluctuations-shelved.md) | P9 | отложено | ELMFIRE + интеграл перекрытия (слой `coupling`) |

## Выполненные задачи

Перенесены в [`done/`](done/), сгруппированы по направлениям.
