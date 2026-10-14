# Каталог ранов: run.json sidecar + catalog.py + sha256 + хранилище

- **Приоритет:** P4
- **Статус:** todo
- **Зависит от:** —
- **Файлы:** `src/common/catalog.py` (новый), рядом с прогонами — `run.json`

## Контекст

`catalog.json` и sidecar `run.json` пока не реализованы. Нужен лёгкий
JSON-индекс прогонов (без SQL) с выжимкой из h5-атрибутов без чтения массивов.

## Шаги

- [ ] **Sidecar `run.json`** рядом с прогоном: выжимка из h5-атрибутов без чтения
      массивов (`nphi`, `Nr`, `R0`, `a0`, `wave_freq`, `sha256`, `size`,
      `format_version`).
- [ ] **`src/common/catalog.py`** — `RunCatalog`: чтение/запись `catalog.json`,
      поиск ранов по параметрам, учёт связок
      `couplings(elmfire_run, wave2d_run, params, result)`.
- [ ] **(P2) Чек-суммы `sha256`** в каталоге — контроль целостности при переносе
      (Globus/NAS).
- [ ] **(P3) Абстракция хранилища** за `RunCatalog`: локальный диск →
      DVC / Git LFS / S3.
