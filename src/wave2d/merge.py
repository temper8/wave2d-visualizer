"""Слияние задач Wave2D по моде ``nphi`` в один HDF5-файл со стеком по 3-й оси.

Схема 0.96 держит научные данные только в ``tasks/<task>/results.h5``, по
одной моде на файл. Объединение по модам оставляет внешнему viewer'у
(``docs/hdf5_schema.md``, раздел «Контракт для внешнего потребителя»), и здесь
оно делается **не** повторением старых per-mode групп, а укладкой в новую
последнюю ось ``nphi``:

* ``/fields/<имя>`` — ``(Nr, Ntheta, Nnphi)``;
* ``/power_balance/<имя>`` — ``(Nr, Nnphi)``;
* ``/spectrum/<имя>`` — копируется как есть: в файлах задач он одинаков во
  всех модах и его атрибуты уже описывают всю серию (если датасет всё же
  зависит от моды — он укладывается по оси ``nphi``, как остальные).

Координата оси — ``/nphi`` (int32), на неё же заведены жёсткие ссылки
``/<группа>/nphi``. Диапазон серии пишется в ``/input/w2grid``
(``nphi1/nphi2/nphistep``), как в старом общем файле серии. Чанки нарезаны по
одной моде (``..., 1``), поэтому чтение одного среза остаётся ленивым.

Модо-независимые группы (``/input``, ``/grid``, ``/geometry``, ``/plasma``,
``/flux_surf``) копируются из базовой задачи; ``/report`` базовой моды не
переносится — вместо него корневые атрибуты ``merged_layout``/``merged_from``/
``merged_modes``. Корневой ``format_version`` сохраняется (>= 0.94), чтобы
файл открывался viewer'ом.

Готовый файл пишется в ``derived/runs/<case>/<stamp>/nphi_merged.h5``
(:func:`~src.common.paths.merged_results`).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Callable

import h5py
import numpy as np

from src.common.paths import (
    merged_results,
    wave2d_dir,
    wave2d_task_results,
    wave2d_tasks,
)
from src.wave2d.schema import (
    MERGED_GROUPS,
    MERGED_LAYOUT,
    MERGED_LAYOUT_NPHI_AXIS,
    NPHI,
    REPORT,
    SPECTRUM,
)

Progress = Callable[[str], None]

# Группы, которые укладываются по новой оси ``nphi``.
STACKED_GROUPS = MERGED_GROUPS

# Группы, которые не переносятся из базовой задачи: ``/report`` — отчёт одной
# моды, для объединённого файла он неверен (провенанс — в корневых атрибутах).
SKIP_GROUPS = (REPORT,)

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


def nphi_tasks(
    run_id: str, check_files: bool = True
) -> list[tuple[int, str, Path]]:
    """Задачи-моды прогона: ``(nphi, имя задачи, путь к results.h5)``.

    Порядок — как в ``[series]`` из ``input.toml``; если секции нет — по
    возрастанию ``nphi``. При ``check_files=True`` задачи без файла
    ``results.h5`` пропускаются. При ``check_files=False`` ``stat`` по каждой
    задаче не делается (в GUI это 245 обращений к сетевой шаре на каждый
    клик) — возвращённые пути не гарантированно существуют, годится только
    для подсчёта мод (напр. включения кнопки слияния).
    """
    found: dict[int, tuple[str, Path]] = {}
    for task in wave2d_tasks(run_id):
        nphi = nphi_of_task(task)
        if nphi is None:
            continue
        path = wave2d_task_results(run_id, task)
        if not check_files or path.is_file():
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
    n_modes = len(tasks)
    base_nphi, base_task, base_path = tasks[0]
    report(
        f"База: {base_task} (nphi={base_nphi}), схема {next(iter(versions)) or '?'}, "
        f"мод: {n_modes}"
    )

    with h5py.File(out_path, "w") as out:
        # База — корневые атрибуты (format_version) и модо-независимые группы.
        with _open_read(base_path) as src:
            for key, value in src.attrs.items():
                out.attrs[key] = value
            for name in src.keys():
                if f"/{name}" in STACKED_GROUPS or f"/{name}" in SKIP_GROUPS:
                    continue
                src.copy(name, out, name=name)
        out.attrs[MERGED_LAYOUT] = MERGED_LAYOUT_NPHI_AXIS
        out.attrs["merged_from"] = run_id
        out.attrs["merged_modes"] = n_modes
        report("Скопированы общие группы (input/grid/geometry/plasma/flux_surf)")

        # Ось мод: координата + жёсткие ссылки в каждой стековой группе.
        axis = out.create_dataset(NPHI, data=np.asarray(modes, dtype=np.int32))
        axis.attrs["units"] = "1"

        for group in STACKED_GROUPS:
            if _stack_group(out, group, tasks, report):
                out[f"{group}/nphi"] = out[NPHI]

        _write_series_range(out, modes)

    report(f"Готово: {out_path}")
    return out_path


def _mode_container(src: h5py.File, group: str, task: str) -> str:
    """Путь до датасетов группы в файле задачи.

    У ``/fields`` и ``/power_balance`` это подгруппа моды
    (``/fields/nphi+000``), у ``/spectrum`` — сама группа (датасеты лежат прямо
    в ней).
    """
    candidate = f"{group}/{task}"
    return candidate if candidate in src else group


def _stack_group(
    out: h5py.File,
    group: str,
    tasks: list[tuple[int, str, Path]],
    report: Progress,
) -> bool:
    """Укладывает одноимённые датасеты группы по новой последней оси ``nphi``.

    Схема группы берётся из базовой задачи. Датасеты, совпадающие во всех модах
    (напр. вся ``/spectrum`` — она общая для серии), копируются как есть — они
    не зависят от ``nphi``. Чанки — по одной моде (``..., 1``).

    Возвращает ``True``, если хотя бы один датасет получил ось ``nphi``.
    """
    n_modes = len(tasks)
    with _open_read(tasks[0][2]) as src:
        if group not in src:
            return False
        container = _mode_container(src, group, tasks[0][1])
        schema = [
            (name, src[f"{container}/{name}"].shape, src[f"{container}/{name}"].dtype,
             dict(src[f"{container}/{name}"].attrs))
            for name in src[container]
        ]
        # Атрибуты самой группы — только если датасеты лежат прямо в ней
        # (у ``/fields`` контейнер — подгруппа моды, её атрибут ``nphi`` лишний).
        group_attrs = dict(src[group].attrs) if container == group else {}

    constant = {
        name for name, _, _, _ in schema
        if group == SPECTRUM and _is_constant(group, name, tasks)
    }

    stacked = False
    datasets: dict[str, h5py.Dataset] = {}
    for name, shape, dtype, attrs in schema:
        if name in constant:
            ds = out.create_dataset(f"{group}/{name}", shape=shape, dtype=dtype)
        else:
            ds = out.create_dataset(
                f"{group}/{name}", shape=shape + (n_modes,), dtype=dtype,
                chunks=shape + (1,),
            )
            stacked = True
        ds.attrs.update(attrs)
        datasets[name] = ds
    if group_attrs and group in out:
        out[group].attrs.update(group_attrs)

    for index, (_nphi, task, path) in enumerate(tasks, start=1):
        with _open_read(path) as src:
            container = _mode_container(src, group, task)
            for name, ds in datasets.items():
                source = f"{container}/{name}"
                if source not in src:
                    continue
                if name in constant:
                    if index == 1:
                        ds[...] = src[source][()]
                else:
                    ds[..., index - 1] = src[source][()]
        report(f"{group} [{index}/{n_modes}]")

    return stacked

def _is_constant(group: str, name: str, tasks: list[tuple[int, str, Path]]) -> bool:
    """Одинаков ли датасет во всех задачах (тогда он не зависит от ``nphi``)."""
    def read(path: Path, task: str) -> np.ndarray:
        with _open_read(path) as fh:
            container = _mode_container(fh, group, task)
            return fh[f"{container}/{name}"][()]

    base = read(tasks[0][2], tasks[0][1])
    for _, task, path in tasks[1:]:
        if not np.array_equal(read(path, task), base):
            return False
    return True


def _write_series_range(out: h5py.File, modes: list[int]) -> None:
    """Перезаписывает ``/input/w2grid`` диапазоном серии (как в старом файле)."""
    if W2GRID not in out or not modes:
        return
    attrs = out[W2GRID].attrs
    attrs["nphi1"] = modes[0]
    attrs["nphi2"] = modes[-1]
    attrs["nphistep"] = (modes[1] - modes[0]) if len(modes) > 1 else 1
