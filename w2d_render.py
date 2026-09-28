import sys

import numpy as np

from src.common.paths import (
    plots_dir,
    wave2d_latest,
    wave2d_results,
    wave2d_task_results,
    wave2d_tasks,
)
from src.utils import view2d, print_dict
from src.wave2d.schema import (
    FLUX_SURF,
    GRID_PSI,
    GRID_X,
    GRID_Y,
    INPUT_W2GRID,
    PLASMA_BFIELD,
    PLASMA_DIELECTRIC,
    PLASMA_PARAMS,
    PLASMA_RESONANCE,
    field_dataset,
    nphi_group_name,
    open_results,
)

DEFAULT_CASE = "FT-2_LH_smoke_nphi"


def resolve_results(run_id: str):
    """Файл прогона; если общего нет — файл первой задачи."""
    path = wave2d_results(run_id)
    if path.is_file():
        return path
    tasks = wave2d_tasks(run_id)
    if tasks:
        return wave2d_task_results(run_id, tasks[0])
    return path


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else wave2d_latest(DEFAULT_CASE)
    file_path = str(resolve_results(run_id))
    out_dir = plots_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run: {run_id}\nFile: {file_path}\nPlots -> {out_dir}")

    # Одно соединение с HDF5 на все чтения; проверяет версию схемы (>= 0.94).
    with open_results(file_path) as reader:
        run_params = reader.params()
        print_dict(run_params)
        nphi = int(reader.attrs(INPUT_W2GRID)["nphi1"])
        print(nphi_group_name(nphi))

        def save(title: str) -> str:
            return str(out_dir / title)

        R = reader.array(GRID_X)
        Z = reader.array(GRID_Y)

        # grid/psi — 1D радиальная координата rho/a0; размножаем по θ для вида (R,Z)
        psi_1d = reader.array(GRID_PSI)
        psi = np.repeat(psi_1d[:, None], R.shape[1], axis=1)
        view2d(R, Z, psi, "psi", save("psi"))

        theta_deg = reader.array(f"{FLUX_SURF}/theta_deg")
        view2d(R, Z, theta_deg, "theta_deg", save("theta_deg"))

        Ea_field = reader.array(field_dataset(nphi, "Ea"))
        view2d(R, Z, Ea_field, "Ea", save("Ea"))

        Ex_field = reader.array(field_dataset(nphi, "Ex"))
        view2d(R, Z, Ex_field.real, "Ex.real", save("Ex.real"))
        view2d(R, Z, Ex_field.imag, "Ex.imag", save("Ex.imag"))

        eps = reader.array(f"{PLASMA_DIELECTRIC}/eps")
        view2d(R, Z, eps.real, "eps.real", save("eps.real"))
        view2d(R, Z, eps.imag, "eps.imag", save("eps.imag"))

        eta = reader.array(f"{PLASMA_DIELECTRIC}/eta")
        view2d(R, Z, eta.real, "eta.real", save("eta.real"))
        view2d(R, Z, eta.imag, "eta.imag", save("eta.imag"))

        gee = reader.array(f"{PLASMA_DIELECTRIC}/gee")
        view2d(R, Z, gee.real, "gee.real", save("gee.real"))
        view2d(R, Z, gee.imag, "gee.imag", save("gee.imag"))

        Te_2D = reader.array(f"{PLASMA_PARAMS}/Te")
        view2d(R, Z, Te_2D, "Te", save("Te"))

        Ti_2D = reader.array(f"{PLASMA_PARAMS}/Ti")
        view2d(R, Z, Ti_2D, "Ti", save("Ti"))

        Btot = reader.array(f"{PLASMA_BFIELD}/Btot")
        view2d(R, Z, Btot, "Btot", save("Btot"))

        w0_wpe = reader.array(f"{PLASMA_RESONANCE}/w0_wpe")
        view2d(R, Z, w0_wpe, "w0/wpe", save("w0_wpe"))

        Xcutoff_at_0 = reader.array(f"{PLASMA_RESONANCE}/Xcutoff_at_0")
        view2d(R, Z, Xcutoff_at_0, "Xcutoff_at_0", save("Xcutoff_at_0"))

        PolRes_at_0 = reader.array(f"{PLASMA_RESONANCE}/PolRes_at_0")
        view2d(R, Z, PolRes_at_0, "PolRes_at_0", save("PolRes_at_0"))


if __name__ == "__main__":
    main()
