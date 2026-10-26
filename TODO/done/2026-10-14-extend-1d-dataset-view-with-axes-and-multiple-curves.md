# Расширить 1D-режим `DatasetView`: оси и подписи

- **Приоритет:** P3
- **Статус:** done
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

Задача вынесена из пункта F задачи p0 (там закрыт только вынос
рендереров). F1 закрыт здесь, F2 (несколько кривых / multi-select) — отдельной
задачей.

## Шаги

### F1 — полноценный 1D (без смены модели `Selection`)

- [x] `DatasetView.set_axes(rho, psi)`: оси 1D как пары `(массив, units)`;
      `None` — оси нет, кнопка оси disabled. `W2DViewer` передаёт `rho`/`psi`
      при создании через `_load_axis(/grid/rho | /grid/psi)`.
- [x] Переключатель оси **`index` / `rho` / `psi`** в `controls` (виден только в
      1D-режиме, см. `_sync_axis_visibility`).
- [x] `draw_1d(ax, data, *, title, x, xlabel, ylabel)`: x — выбранная ось, если
      её длина совпадает с `len(data)`, иначе `index`; `xlabel` — `rho, cm` /
      `psi, 1` / `index`; `ylabel` — имя датасета + `units` (`decode` из bytes:
      `kW`, `kW/cm^3`, `cm^3`, `1`; нет `units` → только имя).
- [x] Комплексные 1D — **отдельный рендер-заглушка** `draw_1d_complex`
      (одна составляющая, слушает `real/imag/abs`); полноценные
      `real/imag/abs` линиями + легенда — доработано в
      [2026-10-26-multi-select-and-multi-curve-1d-dataset-view.md](2026-10-26-multi-select-and-multi-curve-1d-dataset-view.md).
- [x] `W2DViewer` передаёт оси при создании `DatasetView`. Проверено вручную на
      `/power_balance/nphi+122/p_ld` (вложенный) и `/power_balance/p_ld`
      (плоский, без `units`).

### F2 — несколько кривых

Вынесено в отдельную задачу (меняет контракт `Selection`/`show`):
[2026-10-26-multi-select-and-multi-curve-1d-dataset-view.md](2026-10-26-multi-select-and-multi-curve-1d-dataset-view.md).

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
