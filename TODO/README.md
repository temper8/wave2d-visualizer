# Задачи проекта

Каталог задач. **Одна задача — один файл** в этой папке; выполненные переносятся
в `done/`. Имена файлов — длинные и описательные (kebab-case, `.md`), чтобы по
имени было понятно содержимое без открытия.

## Формат задачи

Шапка каждого файла:

- **Приоритет:** `P0`…`P3`.
- **Статус:** `todo` | `doing` | `blocked` | `done`.
- **Зависит от:** ссылки на другие задачи (если есть).
- **Файлы:** какие модули/скрипты затрагиваются.

Тело: раздел «Контекст» (зачем и принятые решения) и чеклист «Шаги».

## Приоритеты

- **P0** — блокеры физики: единицы измерения, постановка интеграла перекрытия.
- **P1** — баги и архитектура, мешающие работе (интерполятор, слои, адаптеры).
- **P2** — структура папок, тесты, гигиена.
- **P3** — README, линтер, косметика, отдалённые планы.

## Открытые задачи

| Файл | Приоритет | Статус | Кратко |
|---|---|---|---|
| [w2dviewer-split-into-tree-widget-and-dataset-view.md](w2dviewer-split-into-tree-widget-and-dataset-view.md) | P1 | todo | Разбить `W2DViewer` на оркестратор + `H5TreeView` + `DatasetView` |
| [extract-common-domain-model-polargrid-field2d-timeseries.md](extract-common-domain-model-polargrid-field2d-timeseries.md) | P1 | todo | `src/common/`: `PolarGrid`, `Field2D`, `FieldTimeSeries`, `units.py` |
| [extract-wave2dresults-from-render-and-utils.md](extract-wave2dresults-from-render-and-utils.md) | P1 | todo | Вынести `Wave2DResults` из `w2d_render.py`/`utils.py` |
| [add-latest-flag-and-remove-hardcoded-wave2d-case.md](add-latest-flag-and-remove-hardcoded-wave2d-case.md) | P1 | todo | Флаг `--latest`, убрать хардкод кейса |
| [add-catalog-json-and-run-sidecar-with-checksums.md](add-catalog-json-and-run-sidecar-with-checksums.md) | P1 | todo | `run.json` sidecar + `catalog.py` + `sha256` + хранилище |
| [add-pytest-and-tests-for-paths-runid-and-fieldmap.md](add-pytest-and-tests-for-paths-runid-and-fieldmap.md) | P2 | todo | `pytest` + `tests/` (пути, `run_id`, чистые части viewer) |
| [reorganize-src-into-apps-and-viz-packages.md](reorganize-src-into-apps-and-viz-packages.md) | P2 | todo | Разнести `src/` на `apps/` и `viz/` |
| [hdf5-dimension-scales.md](hdf5-dimension-scales.md) | P2 | todo | Привязать dimension scales к осям `grid` |
| [evaluate-splitting-repositories-after-layering.md](evaluate-splitting-repositories-after-layering.md) | P3 | todo | Оценить физическое разделение репозиториев |
| [write-readme-with-physical-units-and-screenshots.md](write-readme-with-physical-units-and-screenshots.md) | P3 | todo | README: физ. величины и скриншоты |
| [setup-ruff-linter-and-ci.md](setup-ruff-linter-and-ci.md) | P3 | todo | ruff + CI |
| [elmfire-overlap-integral-and-fluctuations-shelved.md](elmfire-overlap-integral-and-fluctuations-shelved.md) | P0/P1 | отложено | ELMFIRE + интеграл перекрытия (слой `coupling`) |

## Выполненные задачи

Перенесены в [`done/`](done/), сгруппированы по направлениям.
