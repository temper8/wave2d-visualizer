# Данные: WAVE2D_DATA_DIR, paths, Navigator, миграция

- **Приоритет:** P1
- **Статус:** done
- **Файлы:** `src/common/paths.py`, `src/common/navigator.py`, данные

## Что сделано

- [x] Введён `WAVE2D_DATA_DIR` и `src/common/paths.py` — единая точка доступа
      к данным.
- [x] Скрипты переведены на `paths.py` (`run_id` первым аргументом).
- [x] Мигрированы данные: `Globus`/`FT2` → `wave2d/<run>/`,
      `z1.h5` → `elmfire/WagD/converted/`, `.dat` → `elmfire/WagD/raw/`,
      `plots_2d/` → `derived/frames/WagD/`.
- [x] Разделены source и derived: PNG/MP4/интегралы — только в `derived/`.
- [x] Автосоздание структуры `data/` — `paths.ensure_data_root()`.
- [x] `Navigator` для Wave2D — вынесен в `src/common/navigator.py`
      (база `Navigator` + рабочий `Wave2DNavigator`; `ElmfireNavigator`/
      `DerivedNavigator` — заглушки; фасад `DataNavigator`). Legacy-плоско
      (`Globus/results.h5`) поддержано. Обёртки `wave2d_*` сохранены,
      `paths.py` реэкспортирует навигаторы.
- [x] `w2d_render.py` открывает `run_id = <case_id>/<stamp>`; по умолчанию —
      свежий прогон `FT-2_LH_smoke_nphi`. Заодно исправлены формат группы
      `nphi+122` и путь `field_2D` (было `field_2d`), `print_dict` без
      cp1251-непечатаемых символов.
