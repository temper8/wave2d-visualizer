# GUI Wave2D: viewer, navigator, точки входа

- **Приоритет:** P1
- **Статус:** done
- **Файлы:** `src/wave2d/viewer.py`, `src/wave2d/app.py`,
  `w2d_viewer.py`, `w2d_app.py`

## Что сделано

- [x] `src/wave2d/viewer.py` — GUI `W2DViewer`: дерево `results.h5` (через
      `H5Reader.walk`) + изображение выбранного датасета; единое соединение,
      виды `(R,Z)`/`(rho,θ)`, `real/imag/abs`, панель атрибутов,
      `NavigationToolbar`.
- [x] `src/wave2d/app.py` — GUI `W2DNavigatorApp`: выбор прогона по ФС
      (`Wave2DNavigator`: кейсы/прогоны/задачи), сводка `run_info`/`run_params`,
      запуск `W2DViewer` в `Toplevel`. Добавлены `Wave2DNavigator.tasks()` +
      `wave2d_tasks()`.
- [x] Корневые `w2d_viewer.py`/`w2d_app.py` — тонкие точки входа (`main()`);
      GUI-логика в `src/wave2d/`.

Дальнейшее развитие — в
[2026-10-14-w2dviewer-split-into-tree-widget-and-dataset-view.md](2026-10-14-w2dviewer-split-into-tree-widget-and-dataset-view.md).
