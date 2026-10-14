# Расширить 1D-режим `DatasetView`: оси, подписи, несколько кривых

- **Приоритет:** P3
- **Статус:** todo
- **Зависит от:** — (рендереры уже вынесены в `src/wave2d/renderers.py` задачей
  [done/2026-10-14-w2dviewer-split-into-tree-widget-and-dataset-view.md](done/2026-10-14-w2dviewer-split-into-tree-widget-and-dataset-view.md))
- **Файлы:** `src/wave2d/datasetview.py`, `src/wave2d/renderers.py`,
  `src/wave2d/viewer.py`

## Контекст

1D-режим `DatasetView` сейчас минимален: `redraw()` вызывает
`renderers.draw_1d`, который делает `ax.plot(data)` — одна линия против
**индекса**, без подписей осей. Полезные 1D-данные уже есть: `/grid/rho`
(`units=cm`), `/grid/psi` (`units=1`) и
`/power_balance/nphi*/{Sflux, dP*_dpsi, dV, p_ld, p_tt, p_mx, psi}` — радиальные
профили с атрибутом `units`. Без осей и единиц их не прочитать осмысленно, а
несколько родственных рядов (например, `p_ld`/`p_tt`/`p_mx`) хочется видеть
вместе.

Задача вынесена из пункта F задачи p0 (там закрыт только вынос рендереров).

## Шаги

### F1 — полноценный 1D (без смены модели `Selection`)

- [ ] `DatasetView.set_axes(rho, psi)` (или расширить `set_coords`): оси 1D и их
      единицы; `None`, если в файле их нет. Вызывается из `W2DViewer`.
- [ ] Переключатель оси **`index` / `rho` / `psi`** в `controls` (виден только в
      1D-режиме; `_layout` уже умеет перекладывать панель).
- [ ] `draw_1d(ax, data, *, title, x, xlabel, ylabel, comps)`: x — выбранная
      ось, если её длина совпадает с `len(data)`, иначе `index`; `ylabel` — из
      атрибута `units` (decode из bytes: `kW`, `kW/cm^3`, `cm^3`, `1`);
      `xlabel` — `rho, cm` / `psi, 1` / `index`; для комплексных данных —
      `real/imag/abs` линиями + легенда.
- [ ] `W2DViewer` передаёт оси при создании `DatasetView`.

### F2 — несколько кривых (отдельным шагом; меняет контракт)

- [ ] Выбрать источник рядов: multi-select в `H5TreeView`
      (`selectmode="extended"`) → `on_select` отдаёт список →
      `DatasetView.show(list[Selection])` (наложение 1D + легенда); либо
      ограничиться `real/imag/abs` (уже в F1).
- [ ] При multi-select согласовать поведение для 2D/групп (что показывать, если
      выбраны разнородные узлы).

## Критерии готовности

- `/power_balance/nphi*/p_ld` рисуется против `rho` с подписями «rho, cm» и
  «p_ld, kW/cm^3».
- Комплексный 1D-датасет показывает выбранную составляющую.
- Режимы 2D/attrs/message — без регрессий.

## Риски / открытые вопросы

- Единицы и нормировка `rho`/`psi` ещё не подтверждены физиком
  (`docs/results_h5.md`, §11) — подписи осей могут уточниться.
- `/power_balance` бывает плоской или вложенной (`docs/results_h5.md`, §12) — на
  саму 1D-отрисовку не влияет, но учесть при выборе родственных рядов.
