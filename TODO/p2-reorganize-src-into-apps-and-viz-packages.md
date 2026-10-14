# Разнести src/ на apps/ и viz/

- **Приоритет:** P2
- **Статус:** todo
- **Зависит от:** [p1-extract-common-domain-model-polargrid-field2d-timeseries.md](p1-extract-common-domain-model-polargrid-field2d-timeseries.md)
- **Файлы:** `src/` (структура), точки входа в корне

## Контекст

Шаг 6 рефакторинга: домен отдельно, адаптеры источников отдельно, общая
визуализация и приложения — отдельно.

```
src/
├── common/      # домен, без знания о файлах
├── wave2d/      # адаптер Wave2D: reader.py, visualize.py
├── elmfire/     # адаптер ELMFIRE: raw_reader.py, convert.py, fluctuations.py
├── coupling/    # пересечение: overlap.py
├── viz/         # общая визуализация
└── apps/        # w2d_render.py, w2d_app.py, w2d_viewer.py, elmfire_convert.py,
                 # elmfire_viewer.py, elmfire_video.py
```

## Шаги

- [ ] Выделить `src/viz/` — общая визуализация (в т.ч. возможный общий
      canvas/teardown для обоих viewer'ов).
- [ ] Выделить `src/apps/` — тонкие точки входа; корневые скрипты остаются
      обёртками.
- [ ] Согласовать с [p3-elmfire-overlap-integral-and-fluctuations-shelved.md](p3-elmfire-overlap-integral-and-fluctuations-shelved.md)
      (слой `coupling/`).
