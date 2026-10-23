#!/usr/bin/env python3
"""Сумма полей Wave2D по спектру ``nphi`` -> ``total_fields.hdf5``.

Источник — только merged-файл прогона (``nphi_merged.h5``, раскладка
``merged_layout="nphi-axis"``). Полное поле считается для набора углов ``phi``
(третья ось результата) и пишется в ``derived/runs/<case>/<stamp>/total_fields.hdf5``.

Примеры::

    uv run w2d_total_field.py FT-2_LH_nphi_lite/2026-10-23_00-26-35 --phi-samples 36
    uv run w2d_total_field.py <run_id> --phi-samples 1 --phi-min 30
    uv run w2d_total_field.py <run_id> --phi-samples 12 --nphi 0 61 -122
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from src.common.paths import merged_results, run_derived
from src.wave2d.total_field import total_field_pol_xs, write_total_fields


def build_phi(phi_samples: int, phi_min: float, phi_max: float) -> np.ndarray:
    """Ось ``phi`` (градусы): ``phi_samples`` точек равномерно по ``[min, max)``."""
    if phi_samples < 1:
        raise SystemExit("--phi-samples должен быть >= 1")
    if phi_samples == 1:
        return np.asarray([phi_min], dtype=float)
    return np.linspace(phi_min, phi_max, phi_samples, endpoint=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id", help="<case_id>/<stamp>, напр. FT-2_LH_nphi_lite/2026-10-23_00-26-35")
    parser.add_argument("--phi-samples", type=int, default=36,
                        help="число точек по тороидальному углу phi (по умолчанию 36)")
    parser.add_argument("--phi-min", type=float, default=0.0, help="начальный phi, градусы")
    parser.add_argument("--phi-max", type=float, default=360.0, help="конечный phi, градусы")
    parser.add_argument("--nphi", type=int, nargs="*", default=None,
                        help="ограничить набор мод nphi (по умолчанию — все из merged)")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="путь к total_fields.hdf5 (по умолчанию — derived-папка прогона)")
    args = parser.parse_args(argv)

    merged = merged_results(args.run_id)
    if not merged.is_file():
        raise SystemExit(
            f"Нет merged-файла: {merged}\n"
            "Соберите его кнопкой «Слияние» в w2d_viewer (нужно >= 2 задач-мод nphi)."
        )

    phi = build_phi(args.phi_samples, args.phi_min, args.phi_max)
    print(f"Источник: {merged}")
    print(f"phi: {phi.size} точек, {phi[0]:g}..{phi[-1]:g} град")

    result = total_field_pol_xs(merged, phi, mode_filter=args.nphi,
                                progress=lambda message: print(f"  {message}"))
    out = Path(args.output) if args.output else run_derived(args.run_id, "total_fields.hdf5")
    write_total_fields(out, result, merged)

    attrs = result.attrs
    print(f"мод использовано: {result.modes.size} из {result.modes_available} "
          f"(nphi in [{int(result.modes.min())}, {int(result.modes.max())}])")
    print(f"Nsmax={attrs.get('Nsmax')} ant_type={attrs.get('ant_type')} "
          f"grill_type={attrs.get('grill_type')}")
    print(f"записано: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
