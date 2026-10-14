# Общий домен: PolarGrid / Field2D / FieldTimeSeries

- **Приоритет:** P1
- **Статус:** todo
- **Зависит от:** [p1-extract-wave2dresults-from-render-and-utils.md](p1-extract-wave2dresults-from-render-and-utils.md)
- **Файлы:** `src/common/` (новые модули), `src/utils.py`

## Контекст

Шаг 1 рефакторинга: единый домен без знания о формате файлов, над которым
надстраиваются адаптеры Wave2D и ELMFIRE. Ничего не ломать — только добавить.

```
[источник A]  [источник B]      ← адаптеры (знают формат файлов)
      \        /
   [ общий домен ]              ← PolarGrid / Field2D / TimeSeries
          |
   [ операции ]                 ← interpolate, integrate, visualize
```

## Шаги

- [ ] Создать `src/common/` доменные типы: `PolarGrid`, `Field2D`,
      `FieldTimeSeries`.
- [ ] `regular_polar_grid()` — построение регулярной сетки `(rho, θ)`.
- [ ] `src/common/units.py` — явные константы единиц (см. блокеры физики в
      [p3-elmfire-overlap-integral-and-fluctuations-shelved.md](p3-elmfire-overlap-integral-and-fluctuations-shelved.md)):
      убрать неявные допущения о см/м.
- [ ] Не ломать текущие скрипты; перевод адаптеров — отдельными шагами.
