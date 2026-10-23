"""Схема Wave2D ``results.h5`` (ридер).

Поддерживается **только** новый формат — :data:`MIN_FORMAT` и выше (текущий
канон ``0.96``). Файлы старых схем (``0.9``…``0.93``) не читаются: у них другая
раскладка групп и другой набор атрибутов. При попытке открыть такой файл
:func:`ensure_supported` бросает :class:`UnsupportedFormatError` с сообщением,
что формат не поддерживается.

Корневой атрибут версии — ``format_version`` (строка вида ``"0.96"``).

Схема 0.96: научные данные лежат в ``tasks/<task>/results.h5``; run-level
артефакт — report-only ``report.h5`` (группа :data:`REPORT`). Схема модуля
описана в ``docs/hdf5_schema.md``.

Здесь же собраны пути групп/датасетов, чтобы не размазывать литералы по коду,
и хелперы для имён групп ``nphi``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.common.h5reader import H5Reader

# --- версия формата ------------------------------------------------------

FORMAT_VERSION_ATTR = "format_version"
"""Корневой атрибут с версией схемы (строка вида ``"0.94"``)."""

MIN_FORMAT = (0, 94)
"""Минимальная поддерживаемая версия схемы: ``(major, minor)``.

Всё, что меньше, — другой формат; чтение не поддерживается.
"""


class UnsupportedFormatError(ValueError):
    """Файл создан по несовместимой (слишком старой) версии схемы."""


def format_min_str() -> str:
    """Строковое представление :data:`MIN_FORMAT` (``"0.94"``)."""
    return f"{MIN_FORMAT[0]}.{MIN_FORMAT[1]:02d}"


def parse_format_version(value: Any) -> tuple[int, int] | None:
    """Разбирает значение ``format_version`` в ``(major, minor)``.

    Возвращает ``None``, если атрибут отсутствует или не распознан.
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("ascii", "ignore")
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return None
    return major, minor


def format_version_of(reader: H5Reader) -> tuple[int, int] | None:
    """Версия схемы файла или ``None`` (нет/не распознан ``format_version``)."""
    return parse_format_version(reader.file.attrs.get(FORMAT_VERSION_ATTR))


def ensure_supported(reader: H5Reader) -> tuple[int, int]:
    """Проверяет, что формат файла поддерживается.

    Возвращает ``(major, minor)``. Бросает :class:`UnsupportedFormatError`,
    если атрибут ``format_version`` отсутствует или версия ниже
    :data:`MIN_FORMAT`.
    """
    version = format_version_of(reader)
    if version is None:
        raise UnsupportedFormatError(
            f"File '{reader.path}': format not supported — "
            f"missing attribute '{FORMAT_VERSION_ATTR}' or it is not recognized "
            f"(need >= {format_min_str()})."
        )
    if version < MIN_FORMAT:
        raise UnsupportedFormatError(
            f"File '{reader.path}': format {version[0]}.{version[1]:02d} "
            f"not supported (need >= {format_min_str()})."
        )
    return version


def ensure_supported_path(path: str | Path) -> tuple[int, int]:
    """Проверяет формат по пути к файлу (открывает и закрывает его сам)."""
    with H5Reader(path) as reader:
        return ensure_supported(reader)


def open_results(path: str | Path) -> H5Reader:
    """Открывает ``results.h5`` и проверяет версию схемы.

    Возвращает открытый :class:`H5Reader`; при неподдерживаемом формате
    соединение закрывается и бросается :class:`UnsupportedFormatError`.
    """
    reader = H5Reader(path).open()
    try:
        ensure_supported(reader)
    except UnsupportedFormatError:
        reader.close()
        raise
    return reader


# --- пути групп (формат >= 0.94) -----------------------------------------

# Провенанс. /manifest — legacy (0.94); с 0.95 группа называется /report.
MANIFEST = "/manifest"
MANIFEST_SYSTEM = f"{MANIFEST}/system"
MANIFEST_TOOLCHAIN = f"{MANIFEST}/toolchain"
MANIFEST_RUN = f"{MANIFEST}/run"

# Run-level отчёт (>= 0.95). Пишется в report.h5; в файле задачи может не быть.
REPORT = "/report"
REPORT_TOOLCHAIN = f"{REPORT}/toolchain"
REPORT_SYSTEM_INFO = f"{REPORT}/system_info"
REPORT_BUILD = f"{REPORT}/build"

INPUT = "/input"
INPUT_W2GRID = f"{INPUT}/w2grid"
INPUT_PLASMA = f"{INPUT}/plasma"
INPUT_TEMPER = f"{INPUT}/temper"
INPUT_KNGRID = f"{INPUT}/kngrid"
INPUT_DENS = f"{INPUT}/dens"

GRID = "/grid"
GRID_RHO = f"{GRID}/rho"
GRID_PSI = f"{GRID}/psi"
GRID_X = f"{GRID}/X"
GRID_Y = f"{GRID}/Y"

GEOMETRY = "/geometry"
#: Большой радиус ``R(rho, theta)`` (см) — для топ-вида экваториального сечения.
GEOMETRY_R = f"{GEOMETRY}/R"
FLUX_SURF = "/flux_surf"

PLASMA = "/plasma"
PLASMA_PARAMS = f"{PLASMA}/params"
PLASMA_BFIELD = f"{PLASMA}/bfield"
PLASMA_DIELECTRIC = f"{PLASMA}/dielectric"
PLASMA_RESONANCE = f"{PLASMA}/resonance"
PLASMA_WKB = f"{PLASMA}/wkb"

FIELDS = "/fields"

# 1D-энергобаланс по модам nphi (>= 0.96); группы ``nphi*`` как в /fields.
POWER_BALANCE = "/power_balance"

# Run-level тороидальный спектр антенны An(n) (>= 0.96): n, An, abs2.
SPECTRUM = "/spectrum"

# --- объединённый файл (производный артефакт viewer'а, см. src/wave2d/merge.py) ---

#: Раскладка, где данные уложены по новой последней оси ``nphi``.
MERGED_LAYOUT = "merged_layout"
MERGED_LAYOUT_NPHI_AXIS = "nphi-axis"

#: Координата оси мод в объединённом файле.
NPHI = "/nphi"

#: Группы, датасеты которых могут нести ось ``nphi`` последней.
MERGED_GROUPS = (FIELDS, POWER_BALANCE, SPECTRUM)

# --- произвольная ось стека (напр. ``total_fields.hdf5`` по ``phi``) -----

#: Корневой атрибут: путь к 1D-координате оси стека (напр. ``/phi``).
STACK_COORD = "stack_coord"

#: Корневой атрибут: имя оси стека для подписи слайдера (``"phi"``/``"nphi"``).
STACK_NAME = "stack_name"

#: Тороидальный угол в ``total_fields.hdf5`` (радианы, длина = число точек).
PHI = "/phi"


# --- поля по модам nphi --------------------------------------------------

def nphi_group_name(nphi: int) -> str:
    """Каноническое имя группы моды: ``nphi+122`` / ``nphi-061`` / ``nphi+000``."""
    sign = "+" if nphi >= 0 else "-"
    return f"nphi{sign}{abs(nphi):03d}"


def field_group(nphi: int, root: str = FIELDS) -> str:
    """Путь группы поля моды: ``/fields/nphi+122``."""
    return f"{root}/{nphi_group_name(nphi)}"


def field_dataset(nphi: int, component: str = "Ea", root: str = FIELDS) -> str:
    """Путь датасета поля моды: ``/fields/nphi+122/Ea``."""
    return f"{field_group(nphi, root)}/{component}"


def nphi_modes(reader: H5Reader, root: str = FIELDS) -> dict[int, str]:
    """Карта ``nphi -> путь группы`` по атрибуту ``nphi`` (а не по имени)."""
    modes: dict[int, str] = {}
    if not reader.contains(root):
        return modes
    for name in reader.keys(root):
        group = f"{root}/{name}"
        attrs = reader.attrs(group)
        if "nphi" in attrs:
            modes[int(attrs["nphi"])] = group
    return modes
