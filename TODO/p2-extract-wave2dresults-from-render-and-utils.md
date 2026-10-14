# Wave2DResults: вынести из w2d_render.py и utils.py

- **Приоритет:** P2
- **Статус:** todo
- **Зависит от:** [p1-extract-common-domain-model-polargrid-field2d-timeseries.md](p1-extract-common-domain-model-polargrid-field2d-timeseries.md)
- **Файлы:** `w2d_render.py`, `src/utils.py`, `src/wave2d/`

## Контекст

Шаг 2 рефакторинга. Сейчас логика чтения `results.h5` размазана между скриптом
`w2d_render.py`, утилитами `src/utils.py` и схемой `src/wave2d/schema.py`.
Доменная обёртка `Wave2DResults` должна собрать это в одном месте (адаптер
Wave2D над общим доменом).

## Шаги

- [ ] Ввести `Wave2DResults` (адаптер поверх `H5Reader` + `schema.py`),
      возвращающий доменные типы (`Field2D` и т.п.).
- [ ] Перевести `w2d_render.py` и `src/utils.py` на неё.
- [ ] Убрать хардкод кейса `wave2d_latest("FT-2_LH_smoke_nphi")` из
      `src/utils.py` — см.
      [p3-add-latest-flag-and-remove-hardcoded-wave2d-case.md](p3-add-latest-flag-and-remove-hardcoded-wave2d-case.md).
