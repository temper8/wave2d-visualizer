"""Навигация по каталогу данных.

У каждого навигатора — **своя** папка (слой данных): ``wave2d``, ``elmfire``,
``derived``. Папка задаётся при создании; если не задана, берётся сохранённая
настройка (:func:`src.common.settings.get_navigator_root`), а при её
отсутствии — дефолт ``data_root()/<SUBDIR>``. Общий корень ``data_root()``
(``WAVE2D_DATA_DIR`` или ``<repo>/data``) используется тем самым только «на
первом запуске», пока нет настроек.

Иерархия классов::

    Navigator              # база: собственная папка слоя + path()
    ├── Wave2DNavigator    # <wave2d>/<case_id>[/<stamp>]/...
    ├── ElmfireNavigator   # заглушка (TODO)
    └── DerivedNavigator   # заглушка (TODO)
    DataNavigator          # фасад: nav.wave2d / nav.elmfire / nav.derived

Раскладка Wave2D — трёхуровневая: ``<case_id>`` (постановка, напр. ``FT2``)
содержит прогоны ``<stamp>`` (timestamp, напр. ``2026-09-23_21-58-05``)::

    <wave2d>/<case_id>/<stamp>/results.h5            # общий файл серии
    <wave2d>/<case_id>/<stamp>/tasks/<task>/results.h5
    <wave2d>/<case_id>/results.h5                    # legacy-плоско

Кейсы не хардкодятся — они дискаверятся по файловой системе.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from src.common.settings import get_navigator_root

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


def _resolve_root(root: str | Path | None) -> Path:
    if root is not None:
        return Path(root).expanduser().resolve()
    return data_root()


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


# --- база ----------------------------------------------------------------

class Navigator:
    """База навигатора: собственная папка слоя данных и склейка путей.

    ``root`` — папка самого навигатора (напр. ``<data>/wave2d``). Если не
    задана, берётся сохранённая настройка
    :func:`~src.common.settings.get_navigator_root`, а при её отсутствии —
    дефолт ``data_root()/<SUBDIR>``. Подклассы задают ``NAME`` и ``SUBDIR``.
    """

    NAME: str = ""
    SUBDIR: str = ""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = self._resolve(root)

    def _resolve(self, root: str | Path | None) -> Path:
        if root is not None:
            return _resolve_root(root)
        saved = get_navigator_root(self.NAME) if self.NAME else None
        if saved is not None and saved.is_dir():
            return _resolve_root(saved)
        return data_root() / self.SUBDIR if self.SUBDIR else data_root()

    def path(self, *parts: str) -> Path:
        """Путь относительно папки навигатора."""
        return self.root.joinpath(*parts)


# --- Wave2D ---------------------------------------------------------------

class Wave2DNavigator(Navigator):
    """Навигатор по каталогу Wave2D.

    Кейсы (``case_id``) — подкаталоги своей папки; они не хардкодятся,
    а дискаверятся по файловой системе. Прогон внутри кейса задаётся либо
    как ``"<case_id>"`` (legacy, ``results.h5`` лежит прямо в кейсе), либо как
    ``"<case_id>/<stamp>"``.
    """

    NAME = "wave2d"
    SUBDIR = "wave2d"

    def wave2d_root(self) -> Path:
        """Папка Wave2D — собственная папка навигатора."""
        return self.root

    def cases(self) -> list[str]:
        """Список кейсов = подкаталогов папки Wave2D (каждый — постановка)."""
        root = self.root
        if not root.is_dir():
            return []
        return sorted(p.name for p in root.iterdir() if p.is_dir())

    def case_dir(self, case_id: str) -> Path:
        """Каталог кейса: ``<root>/<case_id>``."""
        return self.root / case_id

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

    def tasks(self, run_id: str) -> list[str]:
        """Список задач прогона = подкаталоги ``<run>/tasks``."""
        tasks_dir = self.run_dir(run_id) / "tasks"
        if not tasks_dir.is_dir():
            return []
        return sorted(p.name for p in tasks_dir.iterdir() if p.is_dir())

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


# --- ELMFIRE (заглушка) ---------------------------------------------------

class ElmfireNavigator(Navigator):
    """Навигатор по каталогу ELMFIRE — заглушка.

    Методы ещё не перенесены из :mod:`src.common.paths` (см. ``TODO.md``).
    """

    NAME = "elmfire"
    SUBDIR = "elmfire"

    def raw(self, run_id: str) -> Path:
        raise NotImplementedError("ElmfireNavigator.raw: см. TODO.md")

    def converted(self, run_id: str, name: str = "z1.h5") -> Path:
        raise NotImplementedError("ElmfireNavigator.converted: см. TODO.md")


# --- derived (заглушка) ---------------------------------------------------

class DerivedNavigator(Navigator):
    """Навигатор по ``derived/`` — заглушка.

    Методы ещё не перенесены из :mod:`src.common.paths` (см. ``TODO.md``).
    """

    NAME = "derived"
    SUBDIR = "derived"

    def plots(self, run_id: str | None = None) -> Path:
        raise NotImplementedError("DerivedNavigator.plots: см. TODO.md")

    def frames(self, run_id: str) -> Path:
        raise NotImplementedError("DerivedNavigator.frames: см. TODO.md")

    def video(self) -> Path:
        raise NotImplementedError("DerivedNavigator.video: см. TODO.md")

    def coupling(self, *parts: str) -> Path:
        raise NotImplementedError("DerivedNavigator.coupling: см. TODO.md")


# --- фасад ----------------------------------------------------------------

class DataNavigator:
    """Фасад: одна точка входа для всех слоёв данных.

    У каждого под-навигатора **своя** папка. Необязательный ``root`` — общий
    корень, используемый только чтобы вывести папки по умолчанию (условный
    «первый запуск»). При ``root=None`` каждый навигатор берёт свою папку из
    настроек или дефолт ``data_root()/<SUBDIR>``.

    Пример::

        nav = DataNavigator()
        nav.wave2d.latest("FT2")
        nav.elmfire.raw("WagD")        # пока NotImplementedError (TODO)
        nav.derived.plots("Globus")    # пока NotImplementedError (TODO)
    """

    def __init__(self, root: str | Path | None = None) -> None:
        base = _resolve_root(root) if root is not None else None
        self.wave2d = Wave2DNavigator(base / "wave2d" if base else None)
        self.elmfire = ElmfireNavigator(base / "elmfire" if base else None)
        self.derived = DerivedNavigator(base / "derived" if base else None)


def default_navigator() -> DataNavigator:
    """Фасад с папками по умолчанию (настройки или ``data_root()``)."""
    return DataNavigator()


def wave2d_dir(run_id: str) -> Path:
    """Каталог прогона (обёртка над :meth:`Wave2DNavigator.run_dir`)."""
    return default_navigator().wave2d.run_dir(run_id)


def wave2d_results(run_id: str, name: str = "results.h5") -> Path:
    """Общий файл прогона (обёртка над :meth:`Wave2DNavigator.results`)."""
    return default_navigator().wave2d.results(run_id, name)


def wave2d_task_results(
    run_id: str, task: str, name: str = "results.h5"
) -> Path:
    """Файл задачи (обёртка над :meth:`Wave2DNavigator.task_results`)."""
    return default_navigator().wave2d.task_results(run_id, task, name)


def wave2d_tasks(run_id: str) -> list[str]:
    """Задачи прогона (обёртка над :meth:`Wave2DNavigator.tasks`)."""
    return default_navigator().wave2d.tasks(run_id)


def wave2d_cases() -> list[str]:
    """Все кейсы (обёртка над :meth:`Wave2DNavigator.cases`)."""
    return default_navigator().wave2d.cases()


def wave2d_runs(case_id: str | None = None) -> list[str]:
    """Все прогоны (обёртка над :meth:`Wave2DNavigator.runs`)."""
    return default_navigator().wave2d.runs(case_id)


def wave2d_latest(case_id: str) -> str:
    """Свежий прогон кейса (обёртка над :meth:`Wave2DNavigator.latest`)."""
    return default_navigator().wave2d.latest(case_id)
