"""GUI-навигатор по каталогу Wave2D: выбор прогона и запуск viewer.

Дерево строится динамически по файловой системе через
:class:`~src.common.navigator.Wave2DNavigator` (кейсы → прогоны → задачи),
в листьях — реальные ``results.h5``. Выбор листа показывает сводку
``run_info``/``run_params``; кнопка (или двойной клик) открывает
:class:`~w2d_viewer.W2DViewer` в отдельном окне ``Toplevel``.

Запуск::

    uv run w2d_app.py [<data_root>]   # по умолчанию WAVE2D_DATA_DIR/<repo>/data
"""

import sys
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from src.common.h5reader import H5Reader
from src.common.navigator import Wave2DNavigator
from src.common.paths import data_root

from w2d_viewer import W2DViewer


class W2DNavigatorApp:
    """Окно выбора прогона Wave2D и запуска просмотрщика."""

    def __init__(self, root: tk.Tk, root_dir: str | None = None):
        self.root = root
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
        ttk.Label(header, text=f"Данные: {data_root()}", anchor="w").pack(side=tk.LEFT)
        ttk.Button(header, text="Обновить", command=self.populate).pack(side=tk.RIGHT)

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
        W2DViewer(tk.Toplevel(self.root), str(path))

    # --- инфо-панель -----------------------------------------------------

    def _show_file_info(self, path: Path) -> None:
        size_mb = path.stat().st_size / 1e6
        lines = [f"Файл  : {path}", f"Размер: {size_mb:.2f} MB", ""]
        try:
            with H5Reader(path) as reader:
                if reader.contains("/run_info"):
                    run_info = reader.run_info()
                    if run_info:
                        lines.append("run_info:")
                        lines.extend(self._format_params(run_info, "/run_info"))
                        lines.append("")
                if reader.contains("/run_params"):
                    lines.append("run_params:")
                    lines.extend(self._format_params(reader.params(), "/run_params"))
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


if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    app = W2DNavigatorApp(root, root_dir)
    root.mainloop()
