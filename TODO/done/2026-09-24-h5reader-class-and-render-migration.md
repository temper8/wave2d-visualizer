# H5Reader и перевод w2d_render на него

- **Приоритет:** P1
- **Статус:** done
- **Файлы:** `src/common/h5reader.py`, `src/utils.py`, `w2d_render.py`

## Что сделано

- [x] `src/common/h5reader.py` — класс `H5Reader` вместо
      `dataset_reader`/`get_*attributes*`: одно соединение, ленивый `dataset()`,
      исключения вместо `exit()`. Обёртки в `src/utils.py` сохранены.
- [x] `w2d_render.py` переведён на `with H5Reader(...)` — одно соединение на все
      чтения вместо N открытий файла.
