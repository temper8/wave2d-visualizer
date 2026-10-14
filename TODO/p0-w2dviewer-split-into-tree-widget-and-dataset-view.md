# W2DViewer: разбиение на виджеты

- **Приоритет:** P0
- **Статус:** todo
- **Зависит от:** —
- **Файлы:** `src/wave2d/viewer.py`, `src/wave2d/h5tree.py` (новый),
  `src/wave2d/datasetview.py` (новый), `src/common/h5reader.py`

## Контекст

Сейчас `W2DViewer` (в `src/wave2d/viewer.py`) — «god-class»: он одновременно
читает HDF5, строит UI, раскладывает панели, рендерит графики и обрабатывает
события. Такое смешение мешает и правкам, и тестам: чтобы что-то поправить в
рендеринге, приходится трогать класс, который вдобавок держит соединение с
файлом.

Цель — оставить в `viewer.py` тонкий оркестратор `W2DViewer`, а роли разнести по
виджетам. Оркестратор владеет `H5Reader`, строит `Panedwindow`, связывает две
панели и закрывает файл в `on_closing`. Левая панель — `H5TreeView`
(`src/wave2d/h5tree.py`): дерево содержимого H5 со скроллбаром, метод
`populate(reader)` обходит файл через `H5Reader.walk`, а по выбору узла
вызывается колбэк `on_select(path)`. Правая панель — `DatasetView`
(`src/wave2d/datasetview.py`): область данных с методом `show(selection)`,
который по `Selection` выбирает один из режимов — 2D, 1D, attrs или message.

Принятые решения: имя области данных — **`DatasetView`**; **атрибуты узла** —
это один из режимов `DatasetView` (показывается, когда рисовать нечего), а при
показанном 2D/1D **атрибуты скрыты**; **1D** пока минимален (одна линия),
расширение позже; конструктор `W2DViewer(root, file_path)` сохраняем — на нём
держится `app.py`.

## Шаги

- [ ] **A.** `H5Reader.kind(path)` / `is_group(path)` в `src/common/h5reader.py`;
      переиспользовать `kind()` внутри `walk()`, чтобы viewer/дерево не
      импортировали `h5py`.
- [ ] **B.** `src/wave2d/h5tree.py` — `H5TreeView(ttk.Frame)`: дерево + скроллбар
      + `populate(reader)` (через `H5Reader.walk`), колбэк `on_select(path)`;
      корень файла не показывается (как сейчас).
- [ ] **C.** `src/wave2d/datasetview.py` — `DatasetView(ttk.Frame)` +
      `Selection(path, kind, attrs, data)`. Режимы: **2D** (`(R,Z)`/`(rho,θ)` ×
      `real/imag/abs`, colorbar), **1D** (одна линия), **attrs** (текст атрибутов
      узла), **message** (нет выбора / неподдерживаемая размерность).
      Переключатели `(R,Z)/(rho,θ)`, `real/imag/abs` и `NavigationToolbar` —
      внутри `DatasetView`.
- [ ] **D.** `src/wave2d/viewer.py` — оставить оркестрацию: `H5Reader`,
      `Panedwindow`, связка `H5TreeView` + `DatasetView`, `on_closing`. Убрать из
      файла `import h5py` и `pyplot`. Поведение: есть 2D/1D → атрибуты скрыты;
      нет данных (группа/ошибка) → режим attrs.
- [ ] **E.** Smoke вручную: `uv run w2d_viewer.py`, `uv run w2d_app.py`. После
      появления `pytest` — тесты на `Selection` и диспетчер режимов (без Tk).
- [ ] **F.** (позже) Расширить 1D (несколько кривых, подписи осей); вынести
      рендереры в отдельный модуль, если `datasetview.py` разрастётся.
