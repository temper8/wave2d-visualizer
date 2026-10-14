# Привязать dimension scales к осям grid

- **Приоритет:** P2
- **Статус:** todo
- **Зависит от:** —
- **Файлы:** producer `results.h5`, `docs/hdf5_schema.md`, `src/wave2d/schema.py`

## Контекст

Сейчас dimension scales **не привязаны** (нет атрибутов `CLASS`,
`DIMENSION_LIST`). Оси заданы неявно порядком осей; координаты — `grid/rho`,
`grid/psi`, а полоидальный угол будет добавлен (`grid/theta_deg`) вместе со
scales. Ссылка из `docs/hdf5_schema.md`.

## Шаги

- [ ] Добавить `grid/theta_deg` (полоидальный угол).
- [ ] Привязать dimension scales: атрибуты `CLASS` / `DIMENSION_LIST` к осям
      `grid/X`, `grid/Y` и 2D-полям.
- [ ] Обновить `docs/hdf5_schema.md` и `docs/results_h5.md`.
- [ ] Учесть при чтении в `src/wave2d/schema.py` (хелперы осей).
