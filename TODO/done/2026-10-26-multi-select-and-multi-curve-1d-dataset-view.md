# Наложение нескольких 1D-рядов (multi-select и общий слой)

- **Приоритет:** P0
- **Статус:** done
- **Зависит от:** [2026-10-14-extend-1d-dataset-view-with-axes-and-multiple-curves.md](2026-10-14-extend-1d-dataset-view-with-axes-and-multiple-curves.md)
  (F1: оси `index/rho/psi`, подписи из `units`, комплексный рендер-заглушка)
- **Файлы:** `src/wave2d/renderers.py`, `src/wave2d/h5tree.py`,
  `src/wave2d/datasetview.py`, `src/wave2d/viewer.py`

## Контекст

В F1 (см. зависимость) 1D-режим `DatasetView` получил оси, подписи и
комплексный рендер-заглушку, но по-прежнему рисует **один** ряд. Полезные
радиальные профили идут родственными группами — `/power_balance/nphi*/`
`p_ld`/`p_tt`/`p_mx`, `dP*_dpsi` и т.п., — и их хочется видеть вместе.

Тот же слой наложения нужен **MultiView**
([../p2-multiview-compare-runs.md](../p2-multiview-compare-runs.md)): 1D-вкладка
сравнивает одноимённые ряды из **разных** прогонов. Поэтому рендер нескольких
кривых вынесен в общий `renderers.draw_curves`, а не живёт только внутри
`DatasetView`; 2D-часть — отдельная задача
[../p2-multiview-2d-grid-rendering.md](../p2-multiview-2d-grid-rendering.md).

Смена контракта — ключевая сложность: `on_select(path)` и
`DatasetView.show(Selection)` теперь работают со списком.

## Шаги

- [x] **Выбрать источник рядов.** Multi-select в `H5TreeView`:
      `selectmode="extended"`, `on_select` отдаёт список путей,
      `DatasetView.show(list[Selection])`.
- [x] **Модель выбора.** `Selection`/`show` расширены до списка;
      одиночный узел — список из одного элемента (`DatasetView._as_list`).
- [x] **Общий слой наложения.** `renderers.draw_curves(ax, series, *, xlabel,
      ylabel)`: несколько линий + легенда (серия = `(x, y, label, color)`);
      переиспользуется `DatasetView` (`_draw_1d`, `_draw_stacked`) и
      `MultiView` (`_build_plot_tab`).
- [x] **Наложение 1D + легенда в `DatasetView`.** Подписи — имя датасета +
      `units`; оси `rho`/`psi`/`index` применяются, только если длина оси
      совпадает у **всех** рядов, иначе — `index`.
- [x] **Smoke.** Выбрать `p_ld`/`p_tt`/`p_mx` → наложение с легендой;
      одиночный выбор, 2D/attrs/message — без регрессий. Проверено headless
      (Tk `withdraw`, без окна); при появлении `pytest` (P5) — тесты на
      диспетчер режимов без Tk.

## Критерии готовности

- Несколько однотипных 1D-рядов рисуются вместе с легендой и общими осями.
- `draw_curves` пригоден к переиспользованию в `MultiView`.
- Одиночный выбор, 2D/attrs/message — без регрессий.
- Поведение при разнородном/неподдерживаемом выборе определено и не роняет
  окно.

## Итог

- Multi-select в дереве (`H5TreeView`, `selectmode="extended"`), `on_select`
  отдаёт `list[str]`; `W2DViewer.on_select` собирает `list[Selection]`.
- `DatasetView` хранит `_selections`; `_mode` даёт `1d`, если **все**
  выбранные узлы — 1D-датасеты, иначе поведение по первому узлу (2D при
  multi-select — в `p2-multiview-2d-grid-rendering`).
- `renderers.draw_curves` — общий слой: несколько линий, общая легенда,
  `x` применяется, только если задан и совпадает по длине у всех рядов.
- Кнопка «Add to comparison» (`_emit_add_to_comparison`) отдаёт **каждый**
  выбранный датасет, а не только первый.

**Smoke (headless, Tk `withdraw`):**

- 3×1D (`p_ld`/`p_tt`/`p_mx`) → режим `1d`, 3 линии, легенда
  `p_ld, kW/cm^3`, `p_tt, …`, `p_mx, …`;
- ось `rho` → `xlabel="rho, cm"`, x-данные совпадают с `rho`; при разных
  длинах рядов ось `rho` недоступна → `index`;
- одиночный 1D → 1 линия, без легенды; 2D → colorbar; группа → `attrs`;
  пусто → `message`; комплексный 1D → линии по выбранной составляющей.

## Риски / открытые вопросы

- **Разнородный выбор** (1D + 2D одновременно) пока показывает только первый
  узел — поведение 2D при multi-select вынесено в
  [../p2-multiview-2d-grid-rendering.md](../p2-multiview-2d-grid-rendering.md).
- Единицы и нормировка `rho`/`psi` ещё не подтверждены физиком
  (`docs/results_h5.md`, §11) — при наложении рядов с разными единицами это
  станет заметнее.
