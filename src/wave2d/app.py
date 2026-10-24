"""GUI-навигатор по каталогу Wave2D: выбор прогона и запуск viewer.

Дерево строится динамически по файловой системе через
:class:`~src.common.navigator.Wave2DNavigator` (кейсы → прогоны → папка
``tasks`` → задачи), в листьях — реальные HDF5-файлы (``results.h5``,
``report.h5``). Список задач и проверка их файлов выполняются лениво —
при раскрытии папки ``tasks`` и выборе конкретной задачи соответственно.
Правая панель — обычный текст (сводка прогона, логи, сведения о файле).
При выборе run-level файла (``report.h5``/``results.h5``) вместо него
показываются вкладки :class:`~src.wave2d.reportview.ReportTabs`
(``Summary`` с подробной сводкой и ``Tasks`` с таблицей задач); папка прогона
оставляет прежнюю короткую текстовую сводку. Выбор **папки прогона** включает
панель кнопок действий с прогоном. Кнопка (или двойной клик) открывает
:class:`~src.wave2d.viewer.W2DViewer` в отдельном окне ``Toplevel``.

Кнопка **«Слияние (nphi)»** (активна, когда у прогона ≥ 2 задачи-моды)
в фоне собирает задачи в 3D-стек по оси `nphi` —
``derived/runs/<case>/<stamp>/nphi_merged.h5``
(:mod:`src.wave2d.merge`); готовый файл появляется в дереве листом.

Кнопка **«Рендер полей»** (активна при наличии merged-файла) суммирует поля
мод по тороидальному спектру ``nphi`` (:mod:`src.wave2d.total_field`) при
заданном числе точек по углу ``phi`` и пишет ``total_fields.hdf5`` рядом с
merged-файлом; готовый файл открывается во viewer.

Кнопка **«Открыть»** в шапке позволяет выбрать другую папку Wave2D; выбранный
путь запоминается между запусками через :mod:`src.common.settings`.
При наличии WSL рядом добавляются кнопки с именами дистрибутивов
(:mod:`src.common.wsl`) — клик открывает диалог сразу в его файловой системе.
Имя текущей папки — меню с историей открытых папок (:mod:`src.common.settings`).

Точка входа — ``w2d_app.py`` в корне репозитория.
"""

from pathlib import Path

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from src.common import fsprobe
from src.common.h5reader import H5Reader
from src.common.navigator import Wave2DNavigator, data_root
from src.common.paths import merged_results, run_derived
from src.common.settings import (
    get_navigator_history,
    get_navigator_root,
    push_navigator_history,
    set_navigator_root,
)
from src.common.wsl import wsl_roots
from src.wave2d.merge import merge_nphi_tasks, nphi_tasks
from src.wave2d.total_field import total_field_pol_xs, write_total_fields
from src.wave2d.reportview import ReportTabs
from src.wave2d.run_info import collect_run_info, format_run_info, shallow_attrs
from src.wave2d.schema import (
    MANIFEST,
    REPORT,
    UnsupportedFormatError,
    ensure_supported_path,
)

from src.wave2d.viewer import W2DViewer

# Иконка окна — единый PNG рядом с модулем (генератор: tools/make_icon.py).
_ICON_PATH = Path(__file__).resolve().parent / "assets" / "w2d_app_icon.png"

# Кнопки-заглушки панели действий с прогоном (команды появятся позже).
# «Рендер полей» реализована отдельно — см. :meth:`W2DNavigatorApp.render_fields`.
RUN_ACTIONS = ("Spectrum", "Open folder")

class W2DNavigatorApp:
    """Окно выбора прогона Wave2D и запуска просмотрщика."""

    def __init__(self, root: tk.Tk, root_dir: str | None = None):
        self.root = root
        self.root.title("W2D Navigator")
        self.root.geometry("980x640")
        self._set_window_icon()

        self._paths: dict[str, Path] = {}  # iid узла -> путь к HDF5-файлу
        self._runs: dict[str, str] = {}  # iid узла-прогона -> run_id
        # iid run-level файла (results.h5/report.h5) -> run_id: клик по файлу
        # показывает вкладки сводки/задач, а не дамп атрибутов.
        self._file_runs: dict[str, str] = {}
        # iid узлов, чьи дети (задачи) уже достроены (ленивое раскрытие).
        self._loaded: set[str] = set()
        # iid узла-папки ``tasks`` -> run_id.
        self._folders: dict[str, str] = {}
        # iid узла-задачи -> ожидаемый ``results.h5`` (ещё не проверен).
        self._task_files: dict[str, Path] = {}
        # iid задач без файла (проверено лениво — повторно не stat).
        self._missing: set[str] = set()
        self.selected: Path | None = None

        # Состояние выбранного прогона и фонового слияния по nphi.
        self.selected_run: str | None = None
        self.selected_run_node: str | None = None
        self._merge_busy = False
        self._merge_log: list[str] = []
        self._merge_queue: queue.Queue | None = None
        self._render_busy = False
        self._render_log: list[str] = []
        self._render_queue: queue.Queue | None = None

        # Проверяем доступность папки до построения навигатора: обращение
        # к мёртвой сетевой шаре иначе виснет на SMB-таймаут ещё до отрисовки.
        nav_root = self._resolve_data_root(root_dir)
        if nav_root is None:
            root.destroy()
            return
        self.nav = Wave2DNavigator(nav_root)
        # Запоминаем фактически открытую папку (в т.ч. выбранную в диалоге
        # недоступности) как последнюю — иначе следующий запуск снова попытается
        # открыть старую (мёртвую) папку и снова покажет диалог.
        self._remember_root()

        self.setup_ui()
        self.populate()

    # --- выбор корня данных ---------------------------------------------

    @staticmethod
    def _candidate_root(root_dir: str | None) -> Path:
        """Корень Wave2D до обращения к ФС: CLI -> настройки -> ``data_root()``."""
        if root_dir:
            return Path(root_dir).expanduser()
        saved = get_navigator_root(Wave2DNavigator.NAME)
        if saved is not None:
            return saved
        return data_root() / Wave2DNavigator.SUBDIR

    def _resolve_data_root(self, root_dir: str | None) -> Path | None:
        """Возвращает доступный корень; при недоступности — выбор из истории.

        ``None`` — пользователь отказался выбирать: приложение не открывается.
        """
        candidate = self._candidate_root(root_dir)
        if fsprobe.is_dir(candidate):
            return candidate
        return self._prompt_data_root(candidate)

    def _prompt_data_root(self, unavailable: Path) -> Path | None:
        """Модальный диалог выбора папки, когда текущая недоступна.

        Показывает доступные папки из истории (проверяются через
        :mod:`src.common.fsprobe`), кнопки «Обзор…» и «Выход». Возвращает
        выбранный путь или ``None``.
        """
        history = get_navigator_history(Wave2DNavigator.NAME)
        # Недоступную папку повторно не проверяем (иначе лишний таймаут).
        available = fsprobe.available_dirs(p for p in history if p != unavailable)
        chosen: dict[str, Path | None] = {"path": None}

        dlg = tk.Toplevel(self.root)
        dlg.title("Data folder unavailable")
        dlg.transient(self.root)
        dlg.resizable(False, False)

        ttk.Label(
            dlg,
            justify="left",
            text=(
                "Folder unavailable:\n"
                f"{unavailable}\n\n"
                "Pick another folder from history or choose one manually:"
            ),
        ).pack(fill=tk.X, padx=10, pady=(10, 6))

        listbox = tk.Listbox(
            dlg, height=min(8, max(1, len(available))), width=70, selectmode="browse"
        )
        for path in available:
            listbox.insert(tk.END, str(path))
        if available:
            listbox.selection_set(0)
            listbox.activate(0)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        def accept() -> None:
            sel = listbox.curselection()
            if not sel:
                return
            chosen["path"] = available[sel[0]]
            dlg.destroy()

        def browse() -> None:
            selected = filedialog.askdirectory(
                parent=dlg,
                title="Choose Wave2D folder",
                mustexist=True,
            )
            if not selected:
                return
            path = Path(selected)
            if not fsprobe.is_dir(path):
                messagebox.showwarning(
                    "Folder unavailable", f"Folder not found:\n{path}", parent=dlg
                )
                return
            chosen["path"] = path
            dlg.destroy()

        buttons = ttk.Frame(dlg)
        buttons.pack(fill=tk.X, padx=10, pady=(0, 10))
        open_btn = ttk.Button(buttons, text="Open", command=accept)
        open_btn.pack(side=tk.LEFT)
        if not available:
            open_btn.state(["disabled"])
        ttk.Button(buttons, text="Browse…", command=browse).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(buttons, text="Exit", command=dlg.destroy).pack(side=tk.RIGHT)

        listbox.bind("<Double-1>", lambda _e: accept())
        dlg.bind("<Return>", lambda _e: accept())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        dlg.grab_set()
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (
            self.root.winfo_width() - dlg.winfo_width()
        ) // 2
        y = self.root.winfo_rooty() + (
            self.root.winfo_height() - dlg.winfo_height()
        ) // 2
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.root.wait_window(dlg)
        return chosen["path"]

    # --- интерфейс -------------------------------------------------------

    def _set_window_icon(self) -> None:
        """Ставит иконку окна; ``default=True`` — её получают и дочерние Toplevel.

        Отсутствие ассета — не ошибка: окно откроется со стандартной иконкой.
        """
        try:
            self._icon = tk.PhotoImage(file=str(_ICON_PATH))
        except (OSError, tk.TclError):
            return
        self.root.iconphoto(True, self._icon)

    def setup_ui(self) -> None:
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=6, pady=4)
        self.data_label = ttk.Menubutton(header, text="")
        self.data_label.pack(side=tk.LEFT)
        self._update_folder_menu()
        ttk.Button(header, text="Refresh", command=self.populate).pack(side=tk.RIGHT)
        for name, path in wsl_roots():
            ttk.Button(
                header, text=name, command=lambda p=path: self.choose_data_root(p)
            ).pack(side=tk.RIGHT, padx=(0, 4))
        ttk.Button(header, text="Open", command=self.choose_data_root).pack(
            side=tk.RIGHT, padx=(0, 4)
        )

        paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # --- дерево ---
        left = ttk.Frame(paned)
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        tree_sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_sb.grid(row=0, column=1, sticky="ns")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.on_double)
        self.tree.bind("<<TreeviewOpen>>", self.on_open)

        # --- инфо-панель: обычный текст; вкладки — только для run-level файла ---
        right = ttk.Frame(paned)
        self._info_frame = ttk.Frame(right)
        self.info = tk.Text(self._info_frame, wrap="none", state="disabled")
        info_sb = ttk.Scrollbar(
            self._info_frame, orient="vertical", command=self.info.yview
        )
        self.info.configure(yscrollcommand=info_sb.set)
        self.info.grid(row=0, column=0, sticky="nsew")
        info_sb.grid(row=0, column=1, sticky="ns")
        self._info_frame.rowconfigure(0, weight=1)
        self._info_frame.columnconfigure(0, weight=1)
        self._info_frame.grid(row=0, column=0, sticky="nsew")

        # Вкладки Summary/Tasks — только при выборе run-level файла.
        self.report = ReportTabs(right)
        self.report.grid(row=0, column=0, sticky="nsew")
        self.report.grid_remove()
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.actions = ttk.LabelFrame(right, text="Run actions")
        self.actions.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 0)
        )
        self.run_buttons: list[ttk.Button] = []
        self.merge_btn = ttk.Button(
            self.actions, text="Merge (nphi)", command=self.merge_run,
            state="disabled",
        )
        self.merge_btn.pack(side=tk.LEFT, padx=(6, 4), pady=6)
        self.render_btn = ttk.Button(
            self.actions, text="Render fields", command=self.render_fields,
            state="disabled",
        )
        self.render_btn.pack(side=tk.LEFT, padx=(6, 4), pady=6)
        for text in RUN_ACTIONS:
            btn = ttk.Button(self.actions, text=text, state="disabled")
            btn.pack(side=tk.LEFT, padx=(6, 4), pady=6)
            self.run_buttons.append(btn)

        self.open_btn = ttk.Button(
            right, text="Open viewer", command=self.open_selected,
            state="disabled",
        )
        self.open_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=6, padx=6)

        paned.add(left, weight=2)
        paned.add(right, weight=3)

    def _update_folder_menu(self) -> None:
        """Обновляет подпись текущей папки и меню истории открытых папок."""
        self.data_label.configure(text=f"Wave2D: {self.nav.root}")
        menu = tk.Menu(self.data_label, tearoff=False)
        history = get_navigator_history(self.nav.NAME)
        if history:
            for path in history:
                menu.add_command(
                    label=str(path),
                    command=lambda p=path: self.open_from_history(p),
                )
        else:
            menu.add_command(label="(history is empty)", state="disabled")
        self.data_label["menu"] = menu

    def open_from_history(self, path: Path) -> None:
        """Переключается на папку из истории; если её нет — предупреждает."""
        if not fsprobe.is_dir(path):
            messagebox.showwarning(
                "Folder unavailable",
                f"Folder not found:\n{path}",
                parent=self.root,
            )
            return
        self._set_data_root(path)

    def _remember_root(self) -> None:
        """Сохраняет текущую папку навигатора как последнюю открытую."""
        set_navigator_root(self.nav.NAME, self.nav.root)
        push_navigator_history(self.nav.NAME, self.nav.root)

    def _set_data_root(self, path: str | Path) -> None:
        """Переключает навигатор на папку, сохраняет её и историю."""
        if not fsprobe.is_dir(path):
            messagebox.showwarning(
                "Folder unavailable", f"Folder not found:\n{path}", parent=self.root
            )
            return
        self.nav = Wave2DNavigator(path)
        self._remember_root()
        self._update_folder_menu()
        self.populate()

    def choose_data_root(self, initialdir: str | Path | None = None) -> None:
        """Выбор папки Wave2D через диалог; выбор сохраняется между запусками.

        ``initialdir`` позволяет открыть диалог сразу в заданной папке
        (напр. в корне WSL-дистрибутива по кнопке с его именем).
        """
        selected = filedialog.askdirectory(
            parent=self.root,
            title="Choose Wave2D folder",
            initialdir=str(initialdir or self.nav.root),
            mustexist=True,
        )
        if not selected:
            return
        self._set_data_root(selected)

    # --- построение дерева ----------------------------------------------

    def populate(self) -> None:
        """Перестраивает дерево по текущему состоянию файловой системы."""
        if not fsprobe.is_dir(self.nav.root):
            new_root = self._prompt_data_root(self.nav.root)
            if new_root is None:
                self._clear_tree(f"Folder unavailable:\n{self.nav.root}")
                return
            self._set_data_root(new_root)
            return

        self._clear_tree("")
        cases = self.nav.cases()
        if not cases:
            self.tree.insert("", "end", text="(no cases in the data folder)", open=True)
            return

        for case_id in cases:
            case_node = self.tree.insert("", "end", text=case_id, open=True)
            try:
                runs = self.nav.runs(case_id)
            except FileNotFoundError:
                runs = []
            for run_id in runs:
                if "/" not in run_id:  # legacy-плоско: файл лежит прямо в кейсе
                    node = case_node
                else:
                    node = self.tree.insert(
                        case_node, "end", text=run_id.split("/", 1)[1], open=False
                    )
                self._runs[node] = run_id
                self._add_run_artifacts(node, run_id)
                self._add_derived_node(node, run_id)
                self._add_tasks_folder(node, run_id)

    def _add_run_artifacts(self, parent: str, run_id: str) -> None:
        """Добавляет run-level файлы прогона: ``results.h5`` и/или ``report.h5``."""
        for path in self.nav.run_artifacts(run_id):
            self._add_results_node(parent, path, run_id)

    def _add_derived_node(self, parent: str, run_id: str) -> None:
        """Добавляет производные артефакты прогона (merged и total_fields)."""
        for path in (
            merged_results(run_id),
            run_derived(run_id, "total_fields.hdf5"),
        ):
            if path.is_file():
                self._add_results_node(parent, path)

    def _add_tasks_folder(self, parent: str, run_id: str) -> None:
        """Добавляет узел-папку ``tasks`` с ленивыми детьми.

        Список задач (сотни листингов и ``stat`` на сетевой шаре) строится не
        при раскрытии прогона, а только при раскрытии **самой папки** —
        ``<<TreeviewOpen>>`` (:meth:`on_open`). Прогон с 245 задачами
        раскрывается в один компактный узел.
        """
        tasks_dir = self.nav.run_dir(run_id) / "tasks"
        if not fsprobe.is_dir(tasks_dir):
            return
        iid = f"folder::{parent}"
        self.tree.insert(parent, "end", iid=iid, text="tasks", open=False)
        self._folders[iid] = run_id
        self.tree.insert(iid, "end", iid=self._lazy_iid(iid), text="…")

    @staticmethod
    def _lazy_iid(node: str) -> str:
        """iid заглушки-ребёнка для ленивого раскрытия узла."""
        return f"lazy::{node}"

    def on_open(self, event=None) -> None:
        """Догружает задачи при первом раскрытии папки ``tasks``."""
        iid = self.tree.focus()
        if not iid:
            return
        self._materialize_tasks(iid)

    def _materialize_tasks(self, node: str) -> None:
        """Один раз строит детей узла-папки ``tasks``, убирая заглушку.

        Узлы задач вставляются без проверки ``results.h5``: ``stat`` по каждой
        задаче (дорогой на сетевой шаре) выполняется лениво — при первом выборе
        узла-задачи (:meth:`_resolve_task`).
        """
        run_id = self._folders.get(node)
        if run_id is None or node in self._loaded:
            return
        self._loaded.add(node)
        dummy = self._lazy_iid(node)
        if self.tree.exists(dummy):
            self.tree.delete(dummy)
        for task in self.nav.tasks(run_id):
            task_node = self.tree.insert(node, "end", text=task)
            self._task_files[task_node] = self.nav.task_results(run_id, task)

    def _resolve_task(self, node: str) -> None:
        """Лениво проверяет ``results.h5`` задачи при первом выборе её узла."""
        if node not in self._task_files or node in self._missing:
            return
        if node in self._paths:
            return
        path = self._task_files[node]
        if fsprobe.is_file(path):
            self._paths[node] = path
        else:
            self._missing.add(node)

    def _add_results_node(
        self, parent: str, path: Path, run_id: str | None = None
    ) -> None:
        """Добавляет узел-файл; ``run_id`` — если файл run-level (вкладки сводки)."""
        if not path.is_file():
            return
        iid = f"file::{path}"
        if iid in self._paths:
            return
        self.tree.insert(parent, "end", iid=iid, text=path.name)
        self._paths[iid] = path
        if run_id is not None:
            self._file_runs[iid] = run_id

    def _clear_tree(self, info: str) -> None:
        """Очищает дерево и инфо-панель, сбрасывая выбор."""
        self.tree.delete(*self.tree.get_children())
        self._paths.clear()
        self._runs.clear()
        self._file_runs.clear()
        self._loaded.clear()
        self._folders.clear()
        self._task_files.clear()
        self._missing.clear()
        self.selected = None
        self.selected_run = None
        self.selected_run_node = None
        self.open_btn.configure(state="disabled")
        self._refresh_run_actions()
        self.report.clear()
        self._set_info(info)

    # --- обработчики -----------------------------------------------------

    def on_select(self, event=None) -> None:
        selection = self.tree.selection()
        iid = selection[0] if selection else None
        if iid is not None:
            self._resolve_task(iid)
        path = self._paths.get(iid) if iid else None
        run_id = self._runs.get(iid) if iid else None
        self.selected = path
        self.selected_run = run_id
        self.selected_run_node = iid if run_id is not None else None
        self.open_btn.configure(state="normal" if path else "disabled")
        self._refresh_run_actions()
        if path is not None:
            file_run = self._file_runs.get(iid) if iid else None
            if file_run is not None:
                self._show_run_report(file_run)
            else:
                self._show_file_info(path)
        elif iid is not None and iid in self._missing:
            self._set_info(
                f"Task file missing:\n{self._task_files.get(iid)}"
            )
        elif run_id is not None:
            self._show_run_summary(run_id)
        elif iid is not None and iid in self._folders:
            # Папка ``tasks``: показываем сводку прогона, но выбором прогона
            # не считается (иначе производные узлы цеплялись бы к папке).
            self._show_run_summary(self._folders[iid])
        else:
            # Выбрана папка кейса или ничего — правая панель пуста.
            self._set_info("")

    def on_double(self, event=None) -> None:
        if self.selected is not None:
            self._open_viewer(self.selected)

    def open_selected(self) -> None:
        if self.selected is not None:
            self._open_viewer(self.selected)

    def _open_viewer(self, path: Path) -> None:
        # Проверяем доступность файла и версию до создания окна: иначе при
        # недоступной шаре/несовместимом формате останется пустой Toplevel.
        if not fsprobe.is_file(path):
            messagebox.showerror(
                "File unavailable", f"File not found:\n{path}", parent=self.root
            )
            return
        try:
            ensure_supported_path(path)
        except UnsupportedFormatError as e:
            messagebox.showerror("Unsupported format", str(e), parent=self.root)
            return
        W2DViewer(tk.Toplevel(self.root), str(path))

    # --- инфо-панель -----------------------------------------------------

    def _set_run_buttons(self, enabled: bool) -> None:
        """Включает/гасит кнопки панели действий (активны для прогона)."""
        state = "normal" if enabled else "disabled"
        for btn in self.run_buttons:
            btn.configure(state=state)

    def _refresh_run_actions(self) -> None:
        """Синхронизирует панель действий с текущим выбором.

        Кнопка слияния активна, если у выбранного прогона ≥ 2 задачи-моды nphi
        и слияние сейчас не выполняется. Моды считаются **без** ``stat`` по
        каждой задаче (``check_files=False``): иначе выбор узла прогона с 245
        модами на сетевой шаре замирает на секунды.
        """
        run_id = self.selected_run
        self._set_run_buttons(run_id is not None)
        busy = self._merge_busy or self._render_busy
        can_merge = False
        if run_id is not None and not busy:
            try:
                can_merge = len(nphi_tasks(run_id, check_files=False)) >= 2
            except OSError:
                can_merge = False
        self.merge_btn.configure(state="normal" if can_merge else "disabled")
        can_render = (
            run_id is not None
            and not busy
            and fsprobe.is_file(merged_results(run_id))
        )
        self.render_btn.configure(state="normal" if can_render else "disabled")

    # --- слияние по nphi -------------------------------------------------

    def merge_run(self) -> None:
        """Собирает задачи-моды выбранного прогона в ``nphi_merged.h5``."""
        run_id = self.selected_run
        if run_id is None or self._merge_busy:
            return
        out = merged_results(run_id)
        if out.is_file() and not messagebox.askyesno(
            "Merge nphi",
            f"Merged file already exists:\n{out}\n\nRebuild?",
            parent=self.root,
        ):
            return

        self._merge_busy = True
        self._merge_log = []
        self._merge_queue = queue.Queue()
        self._refresh_run_actions()
        self._set_info(f"Merge nphi: {run_id}\nFile: {out}\n\nMerging…")

        queue_ = self._merge_queue

        def worker() -> None:
            try:
                merge_nphi_tasks(run_id, out, progress=queue_.put)
                queue_.put(("done", out))
            except Exception as e:  # noqa: BLE001
                queue_.put(("error", str(e)))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(150, self._poll_merge)

    def _poll_merge(self) -> None:
        """Опросом очереди обновляет панель, пока идёт слияние."""
        finished: tuple[str, object] | None = None
        while self._merge_queue is not None:
            try:
                item = self._merge_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, tuple):
                finished = item
            else:
                self._merge_log.append(str(item))
                self._set_info("Merge nphi:\n" + "\n".join(self._merge_log))

        if finished is None:
            self.root.after(150, self._poll_merge)
            return

        kind, payload = finished
        self._merge_busy = False
        self._refresh_run_actions()
        if kind == "done":
            self._show_merged(Path(payload))
        else:
            self._set_info(f"Merge nphi: error\n{payload}")
            messagebox.showerror("Merge nphi", str(payload), parent=self.root)

    def _show_merged(self, path: Path) -> None:
        """Сообщает о готовом файле и предлагает открыть его во viewer."""
        self._set_info(f"Merge nphi done:\n{path}")
        node = self.selected_run_node
        if node is not None and self.tree.exists(node):
            self._add_results_node(node, path)
        if messagebox.askyesno(
            "Merge nphi",
            f"Done:\n{path}\n\nOpen in viewer?",
            parent=self.root,
        ):
            self._open_viewer(path)

    # --- рендер полей (сумма по спектру nphi) ---------------------------

    def render_fields(self) -> None:
        """Суммирует поля мод merged-файла по спектру ``nphi``.

        Число точек по углу ``phi`` спрашивается у пользователя (по умолчанию
        4, равномерно по ``[0, 360°)``). Результат — ``total_fields.hdf5`` рядом
        с merged-файлом; по завершении предлагается открыть его во viewer.
        """
        run_id = self.selected_run
        if run_id is None or self._render_busy:
            return
        merged = merged_results(run_id)
        if not fsprobe.is_file(merged):
            messagebox.showinfo(
                "Render fields",
                f"No merged file:\n{merged}\n\n"
                "Run \"Merge (nphi)\" first.",
                parent=self.root,
            )
            return
        samples = simpledialog.askinteger(
            "Render fields",
            "Number of phi samples (evenly over [0, 360°)):",
            parent=self.root, initialvalue=4, minvalue=1, maxvalue=1000,
        )
        if samples is None:
            return
        phi = [0.0] if samples == 1 else [360.0 * i / samples for i in range(samples)]
        out = run_derived(run_id, "total_fields.hdf5")

        self._render_busy = True
        self._render_log = []
        self._render_queue = queue.Queue()
        self._refresh_run_actions()
        self._set_info(
            f"Render fields: {run_id}\n"
            f"Source: {merged}\n"
            f"phi: {samples} samples\nFile: {out}\n\nComputing…"
        )

        queue_ = self._render_queue

        def worker() -> None:
            try:
                result = total_field_pol_xs(merged, phi, progress=queue_.put)
                write_total_fields(out, result, merged)
                queue_.put(("done", out))
            except Exception as e:  # noqa: BLE001
                queue_.put(("error", str(e)))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(150, self._poll_render)

    def _poll_render(self) -> None:
        """Опросом очереди обновляет панель, пока идёт рендер полей."""
        finished: tuple[str, object] | None = None
        while self._render_queue is not None:
            try:
                item = self._render_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, tuple):
                finished = item
            else:
                self._render_log.append(str(item))
                self._set_info("Render fields:\n" + "\n".join(self._render_log))

        if finished is None:
            self.root.after(150, self._poll_render)
            return

        kind, payload = finished
        self._render_busy = False
        self._refresh_run_actions()
        if kind == "done":
            self._show_total_fields(Path(payload))
        else:
            self._set_info(f"Render fields: error\n{payload}")
            messagebox.showerror("Render fields", str(payload), parent=self.root)

    def _show_total_fields(self, path: Path) -> None:
        """Сообщает о готовом ``total_fields.hdf5`` и предлагает открыть его."""
        self._set_info(f"Render fields done:\n{path}")
        node = self.selected_run_node
        if node is not None and self.tree.exists(node):
            self._add_results_node(node, path)
        if messagebox.askyesno(
            "Render fields",
            f"Done:\n{path}\n\nOpen in viewer?",
            parent=self.root,
        ):
            self._open_viewer(path)

    def _show_run_summary(self, run_id: str) -> None:
        """Короткая сводка по прогону в обычной текстовой панели (как раньше).

        Показывается при выборе папки прогона/``tasks``: вкладок нет.
        """
        info = collect_run_info(self.nav, run_id)
        self._set_info(format_run_info(info, detailed=False))

    def _show_run_report(self, run_id: str) -> None:
        """Вкладки ``Summary``/``Tasks`` — подробный отчёт по run-level файлу."""
        self._show_report_panel()
        self.report.show_run(collect_run_info(self.nav, run_id))

    def _show_file_info(self, path: Path) -> None:
        if not fsprobe.is_file(path):
            self._set_info(f"File unavailable:\n{path}")
            return
        size_mb = path.stat().st_size / 1e6
        lines = [f"File : {path}", f"Size : {size_mb:.2f} MB", ""]
        try:
            with H5Reader(path) as reader:
                # Провенанс: в 0.95+ группа /report, в 0.94 — /manifest.
                provenance = next(
                    (p for p in (REPORT, MANIFEST) if reader.contains(p)),
                    None,
                )
                if provenance is not None:
                    manifest = shallow_attrs(reader, provenance)
                    if manifest:
                        lines.append(f"{provenance.strip('/')}:")
                        lines.extend(self._format_params(manifest, provenance))
                        lines.append("")
                if reader.contains("/input"):
                    lines.append("input:")
                    lines.extend(self._format_params(reader.params(), "/input"))
        except Exception as e:  # noqa: BLE001
            lines.append(f"(failed to read parameters: {e})")
        self._set_info("\n".join(lines))

    @staticmethod
    def _format_params(params: dict, start_path: str) -> list[str]:
        lines: list[str] = []
        for obj, attrs in params.items():
            prefix = "" if obj == start_path else f"{obj}  "
            for key, value in attrs.items():
                lines.append(f"  {prefix}{key} = {value}")
        return lines

    def _set_info(self, text: str) -> None:
        """Пишет текст в обычную инфо-панель (сводка прогона, логи, файл)."""
        self._show_text_panel()
        self.info.configure(state="normal")
        self.info.delete("1.0", tk.END)
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")

    def _show_text_panel(self) -> None:
        """Показывает обычный текстовый информационный блок."""
        self.report.grid_remove()
        self._info_frame.grid()

    def _show_report_panel(self) -> None:
        """Показывает вкладки отчёта (``Summary``/``Tasks``)."""
        self._info_frame.grid_remove()
        self.report.grid()