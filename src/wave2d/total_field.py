"""Суммирование полей Wave2D по тороидальному спектру ``nphi``.

Порт легаси-процедуры ``PrintTotalFieldPolXS`` (опция 7 ``wave2D.exe``) на
данные объединённого файла ``nphi_merged.h5``; сам контракт описан в
``docs/viewer-total-field-pol-xs.md``. В отличие от viewer-скрипта из документа
(он обходит ``tasks/*/results.h5``), здесь источник — **только** производный
merged-файл с раскладкой ``merged_layout="nphi-axis"``:

* ``/fields/{Ex,Ey,Ez}`` — ``(Nr, Ntheta, Nnphi)``;
* ``/spectrum/{n,An}`` — серийный спектр (одинаков во всех модах серии);
* ``/nphi`` (жёсткая ссылка ``/fields/nphi``) — координата оси мод.

Полное поле при тороидальном угле ``phi`` — линейная комбинация мод::

    E_total(ir, itheta, iphi) = Σ_nphi An(n)·exp(i·n·phi)·E_nphi(ir, itheta)
    |E_total| = sqrt(|Ex|² + |Ey|² + |Ez|²)   (модуль ПОСЛЕ суммы)

Модуль считается **после** комплексной суммы по модам, а не как сумма модулей.
Ось ``phi`` задаётся набором углов (в градусах) и становится третьей осью
результата; пишется в ``total_fields.hdf5`` (:func:`write_total_fields`).

Моды читаются **лениво, по срезу** (``/fields/Ex[..., k]``): полный стек
``(Nr, Ntheta, Nnphi)`` целиком не материализуется.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import h5py
import numpy as np

from src.wave2d.schema import (
    FIELDS,
    FORMAT_VERSION_ATTR,
    GEOMETRY,
    GRID,
    MERGED_LAYOUT,
    MERGED_LAYOUT_NPHI_AXIS,
    NPHI,
    PHI,
    SPECTRUM,
    STACK_COORD,
    STACK_NAME,
)

#: Поддерживаемые версии схемы (как в viewer-контракте).
SUPPORTED_FORMAT = ("0.96",)

ANT_GRILL, ANT_GAUSS_BEAM = 1, 4

#: Компоненты поля, участвующие в сумме.
COMPONENTS = ("Ex", "Ey", "Ez")

Progress = Callable[[str], None]


def _open_read(path: Path) -> h5py.File:
    """Открывает HDF5 на чтение без блокировки (WSL/SMB-пути)."""
    return h5py.File(path, "r", locking=False)


def _decode(value: object) -> object:
    """Декодирует ``bytes``-атрибут HDF5 в ``str`` (остальное — как есть)."""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value


@dataclass
class TotalField:
    """Сумма полей по спектру: 3D-массивы ``(Nr, Ntheta, Nphi)``.

    ``ex/ey/ez`` — комплексные амплитуды поля при каждом угле ``phi``;
    ``Ea`` — модуль ``sqrt(|Ex|²+|Ey|²+|Ez|²)``; ``modes`` — использованные
    моды ``nphi``; ``phi_rad`` — ось тороидального угла (радианы).
    """

    ex: np.ndarray
    ey: np.ndarray
    ez: np.ndarray
    Ea: np.ndarray
    modes: np.ndarray
    modes_available: int
    phi_rad: np.ndarray
    attrs: dict[str, object] = field(default_factory=dict)

    @property
    def phi_deg(self) -> np.ndarray:
        """Ось ``phi`` в градусах."""
        return np.rad2deg(self.phi_rad)

    def components(self) -> dict[str, np.ndarray]:
        """Компоненты поля по именам (``Ex``/``Ey``/``Ez``) для записи/отрисовки."""
        return {"Ex": self.ex, "Ey": self.ey, "Ez": self.ez}


def ensure_merged(path: str | Path) -> Path:
    """Проверяет, что файл — merged-раскладка ``nphi-axis``; возвращает путь.

    Бросает :class:`ValueError`, если файла нет или раскладка другая.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"No merged file: {path}")
    with _open_read(path) as fh:
        layout = _decode(fh.attrs.get(MERGED_LAYOUT))
    if layout != MERGED_LAYOUT_NPHI_AXIS:
        raise ValueError(
            f"'{path}': layout {layout!r} is not supported "
            f"(expected {MERGED_LAYOUT_NPHI_AXIS!r})"
        )
    return path


def _read_spectrum(fh: h5py.File, path: Path) -> tuple[np.ndarray, np.ndarray, dict]:
    """Читает ``/spectrum``: ``(n, An, attrs)``."""
    if SPECTRUM not in fh:
        raise ValueError(f"'{path}': missing group {SPECTRUM}")
    group = fh[SPECTRUM]
    n = np.asarray(group["n"][...], dtype=int)
    an = np.asarray(group["An"][...], dtype=complex)
    attrs = {key: _decode(group.attrs[key]) for key in group.attrs}
    return n, an, attrs


def total_field_pol_xs(
    merged_path: str | Path,
    phi_deg: Iterable[float],
    mode_filter: Iterable[int] | None = None,
    *,
    progress: Progress | None = None,
) -> TotalField:
    """Суммирует поля мод ``nphi`` merged-файла при заданных углах ``phi_deg``.

    ``mode_filter`` — ограничить набор мод (иначе берутся все найденные в
    merged). Отсутствующие в серии моды пропускаются с предупреждением.
    """

    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    path = ensure_merged(merged_path)
    phi_rad = np.deg2rad(np.asarray(list(phi_deg), dtype=float).ravel())
    if phi_rad.size == 0:
        raise ValueError("Empty set of phi angles")
    n_phi = phi_rad.size

    with _open_read(path) as fh:
        fmt = _decode(fh.attrs.get(FORMAT_VERSION_ATTR))
        if fmt not in SUPPORTED_FORMAT:
            report(f"warning: format_version={fmt!r} not in {SUPPORTED_FORMAT}")
        n, an, attrs = _read_spectrum(fh, path)

        ant_type = int(attrs.get("ant_type", -1))
        if ant_type not in (ANT_GRILL, ANT_GAUSS_BEAM):
            report(f"warning: ant_type={ant_type} — neither grill nor gbeam")

        if NPHI not in fh:
            raise ValueError(f"'{path}': missing axis {NPHI}")
        axis = np.asarray(fh[NPHI][...], dtype=int)

        fields = fh[FIELDS]
        first = fields[COMPONENTS[0]]
        if first.ndim != 3:
            raise ValueError(
                f"'{path}': {FIELDS}/{COMPONENTS[0]} has rank "
                f"{first.ndim}, expected 3 (Nr, Ntheta, Nnphi)"
            )
        nr, ntheta, n_modes = first.shape
        if len(axis) != n_modes:
            raise ValueError(
                f"'{path}': axis {NPHI} length {len(axis)} does not match "
                f"mode count {n_modes} in {FIELDS}"
            )

        weights = {int(k): complex(v) for k, v in zip(n, an)}
        wanted = None if mode_filter is None else {int(m) for m in mode_filter}

        acc = {name: np.zeros((nr, ntheta, n_phi), dtype=np.complex128)
               for name in COMPONENTS}
        used: list[int] = []
        missing: list[int] = []
        skipped: list[int] = []

        for index in range(n_modes):
            mode = int(axis[index])
            if wanted is not None and mode not in wanted:
                continue
            weight = weights.get(mode)
            if weight is None:
                skipped.append(mode)
                continue
            phase = weight * np.exp(1j * mode * phi_rad)  # (Nphi,)
            for name in COMPONENTS:
                slice_ = np.asarray(fields[name][..., index])
                acc[name] += slice_[..., None] * phase
            used.append(mode)
            report(f"mode {mode} [{len(used)}/{n_modes}]")

        if wanted is not None:
            missing = sorted(wanted - set(int(m) for m in axis))
        if skipped:
            report(f"warning: no An for modes {skipped} — skipped")

    if not used:
        raise RuntimeError("No suitable modes found for summation")
    if missing:
        report(f"warning: modes not in series: {missing}")

    ex, ey, ez = (acc[name] for name in COMPONENTS)
    ea = np.sqrt(np.abs(ex) ** 2 + np.abs(ey) ** 2 + np.abs(ez) ** 2)
    return TotalField(
        ex=ex,
        ey=ey,
        ez=ez,
        Ea=ea,
        modes=np.asarray(used, dtype=np.int32),
        modes_available=n_modes,
        phi_rad=phi_rad,
        attrs=attrs,
    )


def write_total_fields(
    out_path: str | Path,
    result: TotalField,
    merged_path: str | Path,
) -> Path:
    """Пишет результат в ``total_fields.hdf5`` (перезаписывая файл).

    Раскладка: ``/fields/{Ex,Ey,Ez,Ea}`` — ``(Nr, Ntheta, Nphi)``; ``/phi`` —
    ось угла (радианы); ``/nphi`` — использованные моды; ``/spectrum``,
    ``/grid`` и ``/geometry`` копируются из merged для трассируемости, отрисовки
    и топ-вида экваториального сечения (``/geometry/R`` — большой радиус, см).

    Ось стека помечена корневыми атрибутами ``stack_coord``/``stack_name``
    (``"/phi"``/``"phi"``) — viewer рисует по ней слайдер.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path = Path(merged_path)

    with _open_read(merged_path) as src, h5py.File(out_path, "w") as out:
        fmt = src.attrs.get(FORMAT_VERSION_ATTR)
        if fmt is not None:
            out.attrs[FORMAT_VERSION_ATTR] = fmt
        out.attrs["source"] = merged_path.name
        out.attrs[STACK_COORD] = PHI
        out.attrs[STACK_NAME] = "phi"
        out.attrs["phi_samples"] = int(result.phi_rad.size)
        if result.phi_rad.size:
            out.attrs["phi_min_deg"] = float(result.phi_deg[0])
            out.attrs["phi_max_deg"] = float(result.phi_deg[-1])
        out.attrs["modes_used"] = int(result.modes.size)
        out.attrs["modes_available"] = int(result.modes_available)
        if result.modes.size:
            out.attrs["mode_min"] = int(result.modes.min())
            out.attrs["mode_max"] = int(result.modes.max())

        axis = out.create_dataset(NPHI, data=result.modes)
        axis.attrs["units"] = "1"
        phi = out.create_dataset(PHI, data=result.phi_rad)
        phi.attrs["units"] = "rad"

        group = out.create_group(FIELDS)
        for name, data in result.components().items():
            dataset = group.create_dataset(name, data=data)
            dataset.attrs["units"] = "arb. units"
        ea = group.create_dataset("Ea", data=result.Ea)
        ea.attrs["units"] = "arb. units"

        for absolute in (SPECTRUM, GRID, GEOMETRY):
            if absolute in src:
                src.copy(absolute, out, name=absolute.lstrip("/"))

    return out_path
