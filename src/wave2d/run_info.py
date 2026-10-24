"""Сводка по прогону Wave2D: чтение, кэш и форматирование.

Модуль не зависит от tkinter, поэтому сводку можно вызывать из CLI и
тестировать без GUI. GUI-навигатор (:mod:`src.wave2d.app`) использует
:func:`get_run_info_text`: она берёт готовую сводку из кэша
``derived/runs/<case>/<stamp>/run_info.yaml`` либо считает заново.

Источники: run-level артефакт (``report.h5`` >= 0.96 или ``results.h5``
<= 0.95: группа ``/report`` либо ``/manifest``) и файловая система (список
задач, содержимое папки прогона). Ошибка чтения артефакта не бросается
наружу — попадает в :attr:`RunInfo.error`.

Кэш инвалидируется, если:
- версия сводки :data:`RUN_INFO_VERSION` не совпадает с сохранённой, либо
- исходный run-level артефакт новее файла кэша (``mtime``).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.common.h5reader import H5Reader
from src.common.navigator import Wave2DNavigator
from src.common.paths import run_derived
from src.wave2d.schema import MANIFEST, REPORT

#: Версия формата/содержания сводки. Поднимать при изменениях
#: :func:`format_run_info`/:func:`to_dict`; старый кэш тогда пересчитается.
RUN_INFO_VERSION = 0.2

#: Имя файла кэша в ``derived/runs/<case>/<stamp>/``.
RUN_INFO_CACHE_NAME = "run_info.yaml"


@dataclass
class ArtifactInfo:
    """Run-level файл прогона: имя и размер (``None``, если не удалось ``stat``)."""

    name: str
    size_mb: float | None = None


@dataclass
class RunInfo:
    """Структурная сводка по прогону (без форматирования)."""

    run_id: str
    run_dir: Path
    name: str | None = None
    description: str | None = None
    format_version: Any = None
    error: str | None = None
    artifacts: list[ArtifactInfo] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    wall_time_sec: float | None = None
    build: dict[str, Any] = field(default_factory=dict)
    system: dict[str, Any] = field(default_factory=dict)
    contains: list[str] | None = None


def get_run_info_text(
    nav: Wave2DNavigator, run_id: str, *, refresh: bool = False
) -> str:
    """Текст сводки по прогону, по возможности из кэша.

    Кэш берётся, если файл есть, его ``run_info_version`` совпадает с
    :data:`RUN_INFO_VERSION` и исходный артефакт не новее кэша. Иначе сводка
    считается заново и записывается в кэш (``refresh=True`` — принудительно).
    """
    cache_path = run_info_cache_path(run_id)
    if not refresh:
        cached = read_cached_run_info(cache_path)
        if cached is not None and not _source_newer(nav, run_id, cache_path):
            return format_run_info(cached)

    info = collect_run_info(nav, run_id)
    write_run_info_cache(cache_path, info)
    return format_run_info(info)


def collect_run_info(nav: Wave2DNavigator, run_id: str) -> RunInfo:
    """Собирает сводку по прогону из run-level артефакта и файловой системы.

    Читает только прямых детей ``/report`` (:func:`shallow_attrs`), чтобы не
    обходить всё поддерево на сетевой шаре.
    """
    info = RunInfo(run_id=run_id, run_dir=nav.run_dir(run_id))
    info.tasks = nav.tasks(run_id)
    info.name, info.description = _read_work_meta(info.run_dir)
    artifacts = nav.run_artifacts(run_id)
    info.artifacts = [_artifact_info(p) for p in artifacts]

    report: dict[str, dict[str, Any]] = {}
    if artifacts:
        source = artifacts[0]
        try:
            with H5Reader(source) as reader:
                info.format_version = reader.attrs("/").get("format_version")
                prov = next(
                    (p for p in (REPORT, MANIFEST) if reader.contains(p)),
                    None,
                )
                if prov is not None:
                    report = shallow_attrs(reader, prov)
        except Exception as e:  # noqa: BLE001
            info.error = f"failed to read {source.name}: {e}"

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

    if info.name:
        lines.append(f"Name   : {info.name}")

    if info.description:
        lines.append(f"Desc   : {info.description}")

    if info.error is not None:
        lines.append(f"({info.error})")

    if info.format_version is not None:
        lines.append(f"Format : {attr_text(info.format_version)}")

    if info.artifacts:
        parts = [
            f"{a.name} ({a.size_mb:.2f} MB)" if a.size_mb is not None else a.name
            for a in info.artifacts
        ]
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


# --- кэш ----------------------------------------------------------------


def run_info_cache_path(run_id: str) -> Path:
    """Путь кэша сводки: ``derived/runs/<case>/<stamp>/run_info.yaml``."""
    return run_derived(run_id, RUN_INFO_CACHE_NAME)


def read_cached_run_info(path: Path) -> RunInfo | None:
    """Читает кэш, если он валиден по версии; иначе ``None``.

    Любая ошибка (нет файла, битый YAML, чужая версия) — это ``None``,
    а не исключение.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("run_info_version") != RUN_INFO_VERSION:
        return None
    try:
        return from_dict(data)
    except (TypeError, ValueError):
        return None


def write_run_info_cache(path: Path, info: RunInfo) -> bool:
    """Пишет кэш сводки; ``False`` — если запись не удалась (напр. read-only)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                to_dict(info),
                f,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
    except OSError:
        return False
    return True


def to_dict(info: RunInfo) -> dict[str, Any]:
    """``RunInfo`` → YAML-совместимый словарь (с :data:`RUN_INFO_VERSION`)."""
    return {
        "run_info_version": RUN_INFO_VERSION,
        "run_id": info.run_id,
        "run_dir": str(info.run_dir),
        "name": info.name,
        "description": info.description,
        "format_version": (
            None if info.format_version is None else attr_text(info.format_version)
        ),
        "error": info.error,
        "artifacts": [
            {"name": a.name, "size_mb": a.size_mb} for a in info.artifacts
        ],
        "tasks": list(info.tasks),
        "statuses": list(info.statuses),
        "wall_time_sec": info.wall_time_sec,
        "build": _sanitize(info.build),
        "system": _sanitize(info.system),
        "contains": None if info.contains is None else list(info.contains),
    }


def from_dict(data: dict[str, Any]) -> RunInfo:
    """YAML-словарь → ``RunInfo`` (обратное к :func:`to_dict`)."""
    artifacts = [
        ArtifactInfo(name=str(a.get("name", "")), size_mb=a.get("size_mb"))
        for a in data.get("artifacts") or []
    ]
    return RunInfo(
        run_id=str(data.get("run_id", "")),
        run_dir=Path(data.get("run_dir", "")),
        name=data.get("name"),
        description=data.get("description"),
        format_version=data.get("format_version"),
        error=data.get("error"),
        artifacts=artifacts,
        tasks=list(data.get("tasks") or []),
        statuses=list(data.get("statuses") or []),
        wall_time_sec=data.get("wall_time_sec"),
        build=dict(data.get("build") or {}),
        system=dict(data.get("system") or {}),
        contains=None if data.get("contains") is None else list(data["contains"]),
    )


def _source_newer(
    nav: Wave2DNavigator, run_id: str, cache_path: Path
) -> bool:
    """Новее ли исходный run-level артефакт файла кэша (по ``mtime``)."""
    try:
        cache_mtime = cache_path.stat().st_mtime
    except OSError:
        return True
    sources = [*nav.run_artifacts(run_id), nav.run_dir(run_id) / "input.toml"]
    for path in sources:
        try:
            if path.stat().st_mtime > cache_mtime:
                return True
        except OSError:
            continue
    return False


def _read_work_meta(run_dir: Path) -> tuple[str | None, str | None]:
    """``name`` и ``description`` из секции ``[work]`` файла ``input.toml``.

    ``None`` (без исключения), если файла нет, он битый или поля пусты.
    """
    try:
        with open(run_dir / "input.toml", "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None, None
    work = data.get("work")
    if not isinstance(work, dict):
        return None, None
    name = work.get("name")
    description = work.get("description")
    return (
        str(name) if name else None,
        str(description) if description else None,
    )


def _artifact_info(path: Path) -> ArtifactInfo:
    """``ArtifactInfo`` для файла: имя + размер в MB (``None`` при ``OSError``)."""
    try:
        return ArtifactInfo(path.name, path.stat().st_size / 1e6)
    except OSError:
        return ArtifactInfo(path.name, None)


def _sanitize(value: Any) -> Any:
    """Рекурсивно приводит значение к YAML-совместимым примитивам.

    ``bytes`` → utf-8, ``Path``/прочее нестроковое — через :func:`attr_text`.
    """
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return attr_text(value)


# --- общие хелперы ------------------------------------------------------


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


_VERSION_RE = re.compile(r"\d+(?:\.\d+)+")


def _format_build(build: dict[str, Any]) -> str:
    """Строка паспорта сборки: ``branch@commit (compiler ver, hdf5 ver)``."""
    commit = attr_text(build.get("git_commit", ""))[:7]
    if attr_text(build.get("git_dirty", "")) in ("True", "dirty"):
        commit += "*"
    branch = attr_text(build.get("git_branch", "?"))
    compiler = _format_compiler(build)
    hdf5 = build.get("hdf5") or build.get("hdf5_ver")
    suffix = f", hdf5 {attr_text(hdf5)}" if hdf5 is not None else ""
    return f"{branch}@{commit} ({compiler}{suffix})"


def _format_compiler(build: dict[str, Any]) -> str:
    """Компилятор с версией: ``gfortran 9.4.0`` / ``GCC version 9.4.0``.

    0.96: ``compiler`` (``gfortran``) + ``compiler_version`` (полная строка) —
    версия сокращается до числа. 0.94: только ``compiler_ver`` — как есть.
    """
    compiler = build.get("compiler")
    version = build.get("compiler_version") or build.get("compiler_ver")
    if compiler and version:
        return f"{attr_text(compiler)} {_short_version(attr_text(version))}"
    if compiler:
        return attr_text(compiler)
    if version:
        return attr_text(version)
    return "?"


def _short_version(text: str) -> str:
    """Первое «версионное» число в строке (``9.4.0``) или строка целиком."""
    match = _VERSION_RE.search(text)
    return match.group(0) if match else text


def _format_system(system: dict[str, Any]) -> str:
    """Строка окружения: ``host — sysname``."""
    host = attr_text(system.get("host") or system.get("hostname") or "?")
    sysname = attr_text(system.get("system", "?"))
    return f"{host} — {sysname}"
