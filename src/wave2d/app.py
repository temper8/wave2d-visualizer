"""GUI-навигатор по каталогу Wave2D: выбор прогона и запуск viewer.

Дерево строится динамически по файловой системе через
:class:`~src.common.navigator.Wave2DNavigator` (кейсы → прогоны → задачи),
в листьях — реальные ``results.h5``. Выбор листа показывает сводку
``manifest``/``input``; кнопка (или двойной клик) открывает
:class:`~src.wave2d.viewer.W2DViewer` в отдельном окне ``Toplevel``.

Кнопка **«Открыть»** в шапке позволяет выбрать другую папку Wave2D; выбранный
путь запоминается между запусками через :mod:`src.common.settings`.
При наличии WSL рядом добавляются кнопки с именами дистрибутивов
(:mod:`src.common.wsl`) — клик открывает диалог сразу в его файловой системе.
Имя текущей папки — меню с историей открытых папок (:mod:`src.common.settings`).

Точка входа — ``w2d_app.py`` в корне репозитория.
"""

from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.common.h5reader import H5Reader
from src.common.navigator import Wave2DNavigator
from src.common.settings import (
    get_navigator_history,
    push_navigator_history,
    set_navigator_root,
)
from src.common.wsl import wsl_roots
from src.wave2d.schema import UnsupportedFormatError, ensure_supported_path

from src.wave2d.viewer import W2DViewer


class W2DNavigatorApp:
    """Окно выбора прогона Wave2D и запуска просмотрщика."""

    def __init__(self, root: tk.Tk, root_dir: str | None = None):
        self.root = root
        # root_dir с CLI главнее; иначе Wave2DNavigator сам возьмёт сохранённую
        # папку Wave2D из настроек или дефолт (data_root()/wave2d).
        self.nav = Wave2DNavigator(root_dir)

        self._paths: dict[str, Path] = {}  # iid узла -> путь к results.h5
        self.selected: Path | None = None

        self.root.title("W2D Navigator")
        self.root.geometry("980x640")
        self.setup_ui()
        self.populate()

    # --- интерфейс -------------------------------------------------------

    def setup_ui(self) -> None:
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=6, pady=4)
        self.data_label = ttk.Menubutton(header, text="")
        self.data_label.pack(side=tk.LEFT)
        self._update_folder_menu()
        ttk.Button(header, text="Обновить", command=self.populate).pack(side=tk.RIGHT)
        for name, path in wsl_roots():
            ttk.Button(
                header, text=name, command=lambda p=path: self.choose_data_root(p)
            ).pack(side=tk.RIGHT, padx=(0, 4))
        ttk.Button(header, text="Открыть", command=self.choose_data_root).pack(
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

        # --- инфо-панель ---
        right = ttk.Frame(paned)
        self.info = tk.Text(right, wrap="none", state="disabled")
        info_sb = ttk.Scrollbar(right, orient="vertical", command=self.info.yview)
        self.info.configure(yscrollcommand=info_sb.set)
        self.info.grid(row=0, column=0, sticky="nsew")
        info_sb.grid(row=0, column=1, sticky="ns")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.open_btn = ttk.Button(
            right, text="Открыть viewer", command=self.open_selected,
            state="disabled",
        )
        self.open_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6, padx=6)

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
            menu.add_command(label="(история пуста)", state="disabled")
        self.data_label["menu"] = menu

    def open_from_history(self, path: Path) -> None:
        """Переключается на папку из истории; если её нет — предупреждает."""
        if not path.is_dir():
            messagebox.showwarning(
                "Папка недоступна",
                f"Папка не найдена:\n{path}",
                parent=self.root,
            )
            return
        self._set_data_root(path)

    def _set_data_root(self, path: str | Path) -> None:
        """Переключает навигатор на папку, сохраняет её и историю."""
        self.nav = Wave2DNavigator(path)
        set_navigator_root(self.nav.NAME, self.nav.root)
        push_navigator_history(self.nav.NAME, self.nav.root)
        self._update_folder_menu()
        self.populate()

    def choose_data_root(self, initialdir: str | Path | None = None) -> None:
        """Выбор папки Wave2D через диалог; выбор сохраняется между запусками.

        ``initialdir`` позволяет открыть диалог сразу в заданной папке
        (напр. в корне WSL-дистрибутива по кнопке с его именем).
        """
        selected = filedialog.askdirectory(
            parent=self.root,
            title="Выберите папку Wave2D",
            initialdir=str(initialdir or self.nav.root),
            mustexist=True,
        )
        if not selected:
            return
        self._set_data_root(selected)

    # --- построение дерева ----------------------------------------------

    def populate(self) -> None:
        """Перестраивает дерево по текущему состоянию файловой системы."""
        self.tree.delete(*self.tree.get_children())
        self._paths.clear()
        self.selected = None
        self.open_btn.configure(state="disabled")
        self._set_info("Выберите results.h5 в дереве")

        cases = self.nav.cases()
        if not cases:
            self.tree.insert("", "end", text="(нет кейсов в каталоге данных)", open=True)
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
                self._add_results_node(node, self.nav.results(run_id))
                for task in self.nav.tasks(run_id):
                    task_path = self.nav.task_results(run_id, task)
                    if task_path.is_file():
                        task_node = self.tree.insert(
                            node, "end", text=f"tasks/{task}", open=False
                        )
                        self._add_results_node(task_node, task_path)

    def _add_results_node(self, parent: str, path: Path) -> None:
        if path.is_file():
            iid = f"file::{path}"
            self.tree.insert(parent, "end", iid=iid, text="results.h5")
            self._paths[iid] = path

    # --- обработчики -----------------------------------------------------

    def on_select(self, event=None) -> None:
        selection = self.tree.selection()
        path = self._paths.get(selection[0]) if selection else None
        self.selected = path
        self.open_btn.configure(state="normal" if path else "disabled")
        if path is not None:
            self._show_file_info(path)

    def on_double(self, event=None) -> None:
        if self.selected is not None:
            self._open_viewer(self.selected)

    def open_selected(self) -> None:
        if self.selected is not None:
            self._open_viewer(self.selected)

    def _open_viewer(self, path: Path) -> None:
        # Проверяем версию до создания окна: иначе при несовместимом
        # формате останется пустой Toplevel.
        try:
            ensure_supported_path(path)
        except UnsupportedFormatError as e:
            messagebox.showerror("Формат не поддерживается", str(e), parent=self.root)
            return
        W2DViewer(tk.Toplevel(self.root), str(path))

    # --- инфо-панель -----------------------------------------------------

    def _show_file_info(self, path: Path) -> None:
        size_mb = path.stat().st_size / 1e6
        lines = [f"Файл  : {path}", f"Размер: {size_mb:.2f} MB", ""]
        try:
            with H5Reader(path) as reader:
                if reader.contains("/manifest"):
                    manifest = reader.manifest()
                    if manifest:
                        lines.append("manifest:")
                        lines.extend(self._format_params(manifest, "/manifest"))
                        lines.append("")
                if reader.contains("/input"):
                    lines.append("input:")
                    lines.extend(self._format_params(reader.params(), "/input"))
        except Exception as e:  # noqa: BLE001
            lines.append(f"(не удалось прочитать параметры: {e})")
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
        self.info.configure(state="normal")
        self.info.delete("1.0", tk.END)
        self.info.insert("1.0", text)
        self.info.configure(state="disabled")