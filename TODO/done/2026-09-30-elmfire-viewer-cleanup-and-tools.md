# ELMFIRE viewer: чистка дубликатов и tools

- **Приоритет:** P1/P2
- **Статус:** done
- **Файлы:** `src/elmfire/viewer.py`, `elmfire_viewer.py`, `tools/`

## Что сделано

- [x] `app_tk.py` и `app_vis_fluct_tk.py` — полные дубликаты. Оставлен один
      файл, позже переименован в `elmfire_viewer.py` (логика — `src/elmfire/`).
- [x] Двойной вызов `root.mainloop()` в GUI-файлах. Дубликат удалён, логика
      вынесена в `src/elmfire/viewer.py` (`ElmfireFluctuationsViewer`),
      `mainloop()` остался только в точке входа `elmfire_viewer.py`.
- [x] Диагностические утилиты вынесены в `tools/` (`elmfire_reader.py`,
      `count_points_per_index.py`). Путь рендера исправлен на
      `derived/frames/<run>/` (было `plots_2d/` в CWD).
