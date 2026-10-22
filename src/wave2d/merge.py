"""Слияние задач Wave2D по моде ``nphi`` в один HDF5-файл.

Схема 0.96 держит научные данные только в ``tasks/<task>/results.h5`` и
объединение по модам оставляет внешнему viewer'у (``docs/hdf5_schema.md``,
раздел «Контракт для внешнего потребителя»). Здесь эта сборка: за основу
берётся файл первой задачи (``/input``, ``/grid``, ``/geometry``, ``/plasma``,
``/flux_surf``, ``/spectrum``, ...), а из остальных задач дописываются
модо-зависимые группы ``/fields/nphi*`` и ``/power_balance/nphi*``. Атрибуты
``/input/w2grid`` (``nphi1/nphi2/nphistep``) перезаписываются диапазоном серии
из ``input.toml`` — как в старом общем файле серии (``docs/results_h5.md``).

Готовый файл пишется в ``derived/runs/<case>/<stamp>/nphi_merged.h5``
(:func:`~src.common.paths.merged_results`).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Callable

import h5py

from src.common.paths import (
    merged_results,
    wave2d_dir,
    wave2d_task_results,
    wave2d_tasks,
)
from src.wave2d.schema import FIELDS, POWER_BALANCE

Progress = Callable[[str], None]

# Группы, зависящие от моды: их набор различается по задачам и дописывается.
MODE_GROUPS = (FIELDS, POWER_BALANCE)

# Группа входных параметров с диапазоном серии.
W2GRID = "/input/w2grid"


def _open_read(path: Path) -> h5py.File:
    """Открывает HDF5 на чтение без блокировки (WSL/SMB-пути)."""
    return h5py.File(path, "r", locking=False)


def nphi_of_task(task: str) -> int | None:
    """Мода ``nphi`` из имени задачи (``nphi+122`` → 122); иначе ``None``."""
    if not task.startswith("nphi"):
        return None
    rest = task[len("nphi"):]
    if not rest or rest[0] not in "+-":
        return None
    try:
        return int(rest)
    except ValueError:
        return None


def series_modes(run_id: str) -> list[int] | None:
    """Список мод серии из ``[series]`` в ``input.toml`` прогона (или ``None``)."""
    path = wave2d_dir(run_id) / "input.toml"
    if not path.is_file():
        return None
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    series = data.get("series")
    if not isinstance(series, dict) or series.get("var") != "nphi":
        return None
    try:
        start = int(series["start"])
        step = int(series["step"])
        number = int(series["number"])
    except (KeyError, TypeError, ValueError):
        return None
    return [start + step * i for i in range(number)]


def nphi_tasks(run_id: str) -> list[tuple[int, str, Path]]:
    """Задачи-моды прогона: ``(nphi, имя задачи, путь к results.h5)``.

    Порядок — как в ``[series]`` из ``input.toml``; если секции нет — по
    возрастанию ``nphi``. Задачи без файла ``results.h5`` пропускаются.
    """
    found: dict[int, tuple[str, Path]] = {}
    for task in wave2d_tasks(run_id):
        nphi = nphi_of_task(task)
        if nphi is None:
            continue
        path = wave2d_task_results(run_id, task)
        if path.is_file():
            found[nphi] = (task, path)

    modes = series_modes(run_id)
    if modes:
        order = [m for m in modes if m in found]
        order += [m for m in sorted(found) if m not in order]
    else:
        order = sorted(found)
    return [(nphi, found[nphi][0], found[nphi][1]) for nphi in order]


def _format_version(path: Path) -> str | None:
    """Корневой атрибут ``format_version`` файла (строкой)."""
    with _open_read(path) as fh:
        value = fh.attrs.get("format_version")
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return None if value is None else str(value)


def merge_nphi_tasks(
    run_id: str,
    out_path: Path | None = None,
    *,
    progress: Progress | None = None,
) -> Path:
    """Собирает задачи-моды прогона в один HDF5-файл и возвращает его путь.

    ``progress`` — необязательный колбэк ``progress(сообщение)`` по шагам.
    Бросает :class:`ValueError`, если задач меньше двух или у них разные версии
    схемы.
    """
    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    tasks = nphi_tasks(run_id)
    if len(tasks) < 2:
        raise ValueError(
            f"Для слияния нужно минимум 2 задачи-моды nphi, найдено {len(tasks)}"
            f" ({run_id})"
        )

    versions = {_format_version(path) for _, _, path in tasks}
    if len(versions) > 1:
        raise ValueError(
            f"Разные версии схемы в задачах: {sorted(str(v) for v in versions)}"
        )

    out_path = Path(out_path) if out_path is not None else merged_results(run_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    modes = [nphi for nphi, _, _ in tasks]
    base_nphi, base_task, base_path = tasks[0]
    report(
        f"База: {base_task} (nphi={base_nphi}), схема {next(iter(versions)) or '?'}, "
        f"мод: {len(tasks)}"
    )

    with h5py.File(out_path, "w") as out:
        # База — корневые атрибуты (format_version) и все объекты задачи.
        with _open_read(base_path) as src:
            for key, value in src.attrs.items():
                out.attrs[key] = value
            for name in src.keys():
                src.copy(name, out, name=name)

        # Модо-зависимые группы из остальных задач.
        total = len(tasks) - 1
        for index, (nphi, task, path) in enumerate(tasks[1:], start=1):
            with _open_read(path) as src:
                for root in MODE_GROUPS:
                    if root not in src:
                        continue
                    names = list(src[root].keys())
                    if not names:
                        continue
                    out.require_group(root)
                    for name in names:
                        dest = f"{root}/{name}"
                        if dest in out:
                            continue
                        src.copy(dest, out, name=dest)
            report(f"[{index}/{total}] {task} (nphi={nphi})")

        _write_series_range(out, modes)

    report(f"Готово: {out_path}")
    return out_path


def _write_series_range(out: h5py.File, modes: list[int]) -> None:
    """Перезаписывает ``/input/w2grid`` диапазоном серии (как в старом файле)."""
    if W2GRID not in out or not modes:
        return
    attrs = out[W2GRID].attrs
    attrs["nphi1"] = modes[0]
    attrs["nphi2"] = modes[-1]
    attrs["nphistep"] = (modes[1] - modes[0]) if len(modes) > 1 else 1
