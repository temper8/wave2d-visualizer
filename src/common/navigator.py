"""Навигация по каталогу данных.

Корень данных задаётся при создании :class:`Navigator`; по умолчанию берётся
из переменной окружения ``WAVE2D_DATA_DIR`` или ``<repo>/data``.

Раскладка Wave2D — трёхуровневая: ``<case_id>`` (постановка, напр. ``FT2``)
содержит прогоны ``<stamp>`` (timestamp, напр. ``2026-09-23_21-58-05``)::

    <root>/wave2d/<case_id>/<stamp>/results.h5            # общий файл серии
    <root>/wave2d/<case_id>/<stamp>/tasks/<task>/results.h5
    <root>/wave2d/<case_id>/results.h5                    # legacy-плоско

Кейсы не хардкодятся — они дискаверятся по файловой системе. Пока реализована
только часть Wave2D; ELMFIRE и ``derived`` живут в :mod:`src.common.paths`
(см. ``TODO.md``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Корень репозитория: <repo>/src/common/navigator.py -> parents[2] == <repo>
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Имя папки прогона: YYYY-MM-DD_HH-MM-SS
_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")


def data_root() -> Path:
    """Корень данных: ``WAVE2D_DATA_DIR`` или ``<repo>/data``."""
    env = os.environ.get("WAVE2D_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _REPO_ROOT / "data"


def split_run_id(run_id: str) -> tuple[str, str | None]:
    """Разбирает ссылку на прогон.

    ``"FT2/2026-09-23_21-58-05"`` -> ``("FT2", "2026-09-23_21-58-05")``;
    legacy-плоско ``"Globus"`` -> ``("Globus", None)``.
    """
    parts = [p for p in run_id.replace("\\", "/").split("/") if p]
    if len(parts) == 1:
        return parts[0], None
    if len(parts) == 2:
        return parts[0], parts[1]
    raise ValueError(
        f"Некорректный run_id: {run_id!r} "
        "(ожидается '<case_id>' или '<case_id>/<stamp>')"
    )


# --- Wave2D ---------------------------------------------------------------

class Navigator:
    """Навигатор по каталогу Wave2D. Корень задаётся при создании.

    Кейсы (``case_id``) — подкаталоги ``<root>/wave2d``; они не хардкодятся,
    а дискаверятся по файловой системе. Прогон внутри кейса задаётся либо
    как ``"<case_id>"`` (legacy, ``results.h5`` лежит прямо в кейсе), либо как
    ``"<case_id>/<stamp>"``.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = (
            Path(root).expanduser().resolve()
            if root is not None
            else data_root()
        )

    def wave2d_root(self) -> Path:
        """Корень данных Wave2D: ``<root>/wave2d``."""
        return self.root / "wave2d"

    def cases(self) -> list[str]:
        """Список кейсов = подкаталогов ``wave2d`` (каждый — постановка)."""
        root = self.wave2d_root()
        if not root.is_dir():
            return []
        return sorted(p.name for p in root.iterdir() if p.is_dir())

    def case_dir(self, case_id: str) -> Path:
        """Каталог кейса: ``wave2d/<case_id>``."""
        return self.wave2d_root() / case_id

    def run_dir(self, run_id: str) -> Path:
        """Каталог прогона: ``wave2d/<case_id>[/<stamp>]``."""
        case_id, stamp = split_run_id(run_id)
        base = self.case_dir(case_id)
        return base / stamp if stamp else base

    def results(self, run_id: str, name: str = "results.h5") -> Path:
        """Общий файл прогона (напр. серия по ``nphi``)."""
        return self.run_dir(run_id) / name

    def task_results(
        self, run_id: str, task: str, name: str = "results.h5"
    ) -> Path:
        """Файл отдельной задачи: ``<run>/tasks/<task>/results.h5``."""
        return self.run_dir(run_id) / "tasks" / task / name

    def runs(self, case_id: str | None = None) -> list[str]:
        """Список прогонов: внутри кейса или по всем кейсам (``case_id=None``)."""
        if case_id is not None:
            return self._case_runs(case_id)
        result: list[str] = []
        for cid in self.cases():
            result.extend(self._case_runs(cid))
        return result

    def latest(self, case_id: str) -> str:
        """Свежий прогон кейса (максимальный ``<stamp>``)."""
        candidates = self._case_runs(case_id)
        stamped = sorted(r for r in candidates if "/" in r)
        if stamped:
            return stamped[-1]
        if candidates:
            return candidates[0]  # legacy: единственный плоский прогон
        raise FileNotFoundError(
            f"В кейсе '{case_id}' не найдено ни одного прогона: "
            f"{self.case_dir(case_id)}"
        )

    def _case_runs(self, case_id: str) -> list[str]:
        case_dir = self.case_dir(case_id)
        if not case_dir.is_dir():
            raise FileNotFoundError(
                f"Кейс '{case_id}' не найден: {case_dir}. "
                f"Доступные кейсы: {self.cases()}"
            )
        runs: list[str] = []
        if (case_dir / "results.h5").is_file():
            runs.append(case_id)
        runs.extend(
            f"{case_id}/{p.name}"
            for p in sorted(case_dir.iterdir(), key=lambda p: p.name)
            if p.is_dir() and _STAMP_RE.match(p.name)
        )
        return runs


def default_navigator() -> Navigator:
    """Navigator для корня по умолчанию (``WAVE2D_DATA_DIR`` или ``<repo>/data``)."""
    return Navigator()


def wave2d_dir(run_id: str) -> Path:
    """Каталог прогона (обёртка над :meth:`Navigator.run_dir`)."""
    return default_navigator().run_dir(run_id)


def wave2d_results(run_id: str, name: str = "results.h5") -> Path:
    """Общий файл прогона (обёртка над :meth:`Navigator.results`)."""
    return default_navigator().results(run_id, name)


def wave2d_task_results(
    run_id: str, task: str, name: str = "results.h5"
) -> Path:
    """Файл задачи (обёртка над :meth:`Navigator.task_results`)."""
    return default_navigator().task_results(run_id, task, name)


def wave2d_cases() -> list[str]:
    """Все кейсы (обёртка над :meth:`Navigator.cases`)."""
    return default_navigator().cases()


def wave2d_runs(case_id: str | None = None) -> list[str]:
    """Все прогоны (обёртка над :meth:`Navigator.runs`)."""
    return default_navigator().runs(case_id)


def wave2d_latest(case_id: str) -> str:
    """Свежий прогон кейса (обёртка над :meth:`Navigator.latest`)."""
    return default_navigator().latest(case_id)
