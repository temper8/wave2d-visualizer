# pytest и тесты: пути, run_id, чистые части viewer

- **Приоритет:** P2
- **Статус:** todo
- **Зависит от:** [p1-w2dviewer-split-into-tree-widget-and-dataset-view.md](p1-w2dviewer-split-into-tree-widget-and-dataset-view.md)
- **Файлы:** `pyproject.toml`, `tests/` (новый)

## Контекст

Тестов нет. Начать с дешёвых чистых частей (без Tk и без реальных данных).

## Шаги

- [ ] `uv add --dev pytest`, папка `tests/`.
- [ ] `tests/test_paths.py` — разбор `run_id`, legacy-плоско, дискавери кейсов,
      `latest`.
- [ ] Тесты на чистые части viewer: `Selection`, диспетчер режимов
      (`attrs` / `1D` / `2D` / `message`), выбор `(R,Z)` vs `(rho,θ)`,
      `real/imag/abs`.
- [ ] (из ELMFIRE) превратить `tools/integrator_test_pi.py` в
      `tests/test_integrate.py` — проверка `∫1·1·ρ dρ dθ = π(hi²−lo²)`.
