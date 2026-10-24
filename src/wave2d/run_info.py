"""Сводка по прогону Wave2D: чтение run-level артефакта и форматирование.

Модуль не зависит от tkinter, поэтому сводку можно вызывать из CLI и
тестировать без GUI. GUI-навигатор (:mod:`src.wave2d.app`) использует
:func:`collect_run_info` (данные) + :func:`format_run_info` (текст).

Источники: run-level артефакт (``report.h5`` >= 0.96 или ``results.h5``
<= 0.95: группа ``/report`` либо ``/manifest``) и файловая система (список
задач, содержимое папки прогона). Ошибка чтения артефакта не бросается
наружу — попадает в :attr:`RunInfo.error`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.common.h5reader import H5Reader
from src.common.navigator import Wave2DNavigator
from src.wave2d.schema import MANIFEST, REPORT


@dataclass
class RunInfo:
    """Структурная сводка по прогону (без форматирования)."""

    run_id: str
    run_dir: Path
    format_version: Any = None
    error: str | None = None
    artifacts: list[Path] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    wall_time_sec: float | None = None
    build: dict[str, Any] = field(default_factory=dict)
    system: dict[str, Any] = field(default_factory=dict)
    contains: list[str] | None = None


def collect_run_info(nav: Wave2DNavigator, run_id: str) -> RunInfo:
    """Собирает сводку по прогону из run-level артефакта и файловой системы.

    Читает только прямых детей ``/report`` (:func:`shallow_attrs`), чтобы не
    обходить всё поддерево на сетевой шаре.
    """
    info = RunInfo(run_id=run_id, run_dir=nav.run_dir(run_id))
    info.artifacts = nav.run_artifacts(run_id)
    info.tasks = nav.tasks(run_id)

    report: dict[str, dict[str, Any]] = {}
    if info.artifacts:
        try:
            with H5Reader(info.artifacts[0]) as reader:
                info.format_version = reader.attrs("/").get("format_version")
                prov = next(
                    (p for p in (REPORT, MANIFEST) if reader.contains(p)),
                    None,
                )
                if prov is not None:
                    report = shallow_attrs(reader, prov)
        except Exception as e:  # noqa: BLE001
            info.error = f"failed to read {info.artifacts[0].name}: {e}"

    # Статусы задач: ключи ``/report/<task>`` со своим атрибутом status.
    task_set = set(info.tasks)
    info.statuses = [
        attrs["status"]
        for key, attrs in report.items()
        if key in task_set and "status" in attrs
    ]

    wall = report.get(REPORT, {}).get("wall_time_sec")
    if wall is not None:
        info.wall_time_sec = float(wall)

    # Сборка: 0.96 — /report/build, 0.94 — /manifest/toolchain.
    info.build = report.get("build") or report.get("toolchain") or {}
    info.system = report.get("system_info") or report.get("system") or {}

    try:
        info.contains = sorted(p.name for p in info.run_dir.iterdir())
    except OSError:
        info.contains = None

    return info


def format_run_info(info: RunInfo) -> str:
    """Форматирует сводку в текст (те же строки, что показывает GUI)."""
    lines = [f"Run    : {info.run_id}", f"Path   : {info.run_dir}"]

    if info.error is not None:
        lines.append(f"({info.error})")

    if info.format_version is not None:
        lines.append(f"Format : {attr_text(info.format_version)}")

    if info.artifacts:
        parts: list[str] = []
        for p in info.artifacts:
            try:
                parts.append(f"{p.name} ({p.stat().st_size / 1e6:.2f} MB)")
            except OSError:
                parts.append(p.name)
        lines.append("File   : " + ", ".join(parts))
    else:
        lines.append("File   : no run-level file")

    lines.append(f"Tasks  : {_task_summary(info.tasks)}")

    if info.statuses:
        ok = sum(1 for s in info.statuses if attr_text(s) == "SUCCESS")
        lines.append(f"Status : {ok}/{len(info.statuses)} SUCCESS")

    if info.wall_time_sec is not None:
        lines.append(f"Time   : wall {info.wall_time_sec:.2f} s")

    if info.build:
        lines.append(f"Build  : {_format_build(info.build)}")

    if info.system:
        lines.append(f"System : {_format_system(info.system)}")

    if info.contains is not None:
        lines.append(f"Contains: {', '.join(info.contains)}")

    return "\n".join(lines)


def shallow_attrs(reader: H5Reader, root: str) -> dict[str, dict]:
    """Атрибуты ``root`` и его прямых детей (без глубокого обхода).

    :meth:`H5Reader.attrs_recursive` обходит всё поддерево ``/report`` —
    у прогона с 245 задачами это ~1200 объектов и ~7000 атрибутов, а на
    сетевой шаре ~1.5 с на каждый клик. Для сводки нужны лишь статусы
    задач и ``build``/``system_info`` — это прямые дети ``/report``.
    """
    result: dict[str, dict] = {}
    if root not in reader.file:
        return result
    result[root] = reader.attrs(root)
    for key in reader.keys(root):
        try:
            result[key] = reader.attrs(f"{root}/{key}")
        except (KeyError, OSError):
            continue
    return result


def attr_text(value: object) -> str:
    """Приводит значение атрибута HDF5 к строке (``bytes`` → utf-8)."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _task_summary(tasks: list[str]) -> str:
    """Краткое описание задач: ``5 (nphi -122…+122)`` или просто число."""
    if not tasks:
        return "none"
    rng = _axis_range(tasks)
    return f"{len(tasks)} ({rng})" if rng else str(len(tasks))


def _axis_range(tasks: list[str]) -> str | None:
    """Диапазон ``<ось>±NNN`` по именам задач; ``None`` — имена не такие."""
    axis = ""
    values: list[int] = []
    for name in tasks:
        pos = name.find("+")
        idx = pos if pos > 0 else name.find("-")
        if idx <= 0:
            return None
        try:
            values.append(int(name[idx:]))
        except ValueError:
            return None
        if not axis:
            axis = name[:idx]
        elif axis != name[:idx]:
            return None
    return f"{axis} {min(values)}…{max(values)}" if values else None


def _format_build(build: dict[str, Any]) -> str:
    """Строка паспорта сборки: ``branch@commit (compiler, hdf5 ver)``."""
    commit = attr_text(build.get("git_commit", ""))[:7]
    if attr_text(build.get("git_dirty", "")) in ("True", "dirty"):
        commit += "*"
    branch = attr_text(build.get("git_branch", "?"))
    compiler = attr_text(build.get("compiler") or build.get("compiler_ver") or "?")
    hdf5 = build.get("hdf5") or build.get("hdf5_ver")
    suffix = f", hdf5 {attr_text(hdf5)}" if hdf5 is not None else ""
    return f"{branch}@{commit} ({compiler}{suffix})"


def _format_system(system: dict[str, Any]) -> str:
    """Строка окружения: ``host — sysname``."""
    host = attr_text(system.get("host") or system.get("hostname") or "?")
    sysname = attr_text(system.get("system", "?"))
    return f"{host} — {sysname}"
