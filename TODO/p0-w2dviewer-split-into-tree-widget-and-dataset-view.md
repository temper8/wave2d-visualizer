# W2DViewer: разбиение на виджеты

- **Приоритет:** P0
- **Статус:** todo
- **Зависит от:** —
- **Файлы:** `src/wave2d/viewer.py`, `src/wave2d/h5tree.py` (новый),
  `src/wave2d/datasetview.py` (новый), `src/common/h5reader.py`

## Контекст

`W2DViewer` совмещает 5 ролей: доступ к данным, построение UI, раскладку,
рендеринг и обработку событий. Цель — тонкий оркестратор + два класса-виджета.

```
┌──────────────────── W2DViewer (viewer.py) ────────────────────┐
│  оркестратор: H5Reader, раскладка (Panedwindow), связка, закрытие │
│   H5TreeView (h5tree.py)          DatasetView (datasetview.py) │
│   ─ дерево содержимого H5         ─ область данных             │
│   ─ populate(reader)              ─ show(selection)            │
│   ─ колбэк on_select(path)        ─ 2D / 1D / attrs / message  │
└────────────────────────────────────────────────────────────────┘
```

Принятые решения:

- Имя области данных — **`DatasetView`**.
- **Атрибуты узла** — один из режимов `DatasetView` (когда рисовать нечего).
- При показанном 2D/1D **атрибуты скрыты**.
- **1D** — пока минимум (одна линия), расширение позже.
- Конструктор `W2DViewer(root, file_path)` сохранить — на нём `app.py`.

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
