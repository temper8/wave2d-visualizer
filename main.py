import sys

from src.common.paths import wave2d_results, plots_dir
from src.utils import dataset_reader, view2d, get_attributes_recursive_from, print_dict


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else "Globus"
    file_path = str(wave2d_results(run_id))
    out_dir = plots_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run: {run_id}\nFile: {file_path}\nPlots -> {out_dir}")

    run_params = get_attributes_recursive_from(file_path, start_path='/run_params')
    print_dict(run_params)
    nphi = run_params['w2grid']['nphi1']
    nphi = f"nphi-{abs(nphi):03d}" if nphi < 0 else f"nphi{nphi:03d}"
    print(nphi)

    def save(title: str) -> str:
        return str(out_dir / title)

    R = dataset_reader(file_path, '/coord/X')
    Z = dataset_reader(file_path, '/coord/Y')

    psi = dataset_reader(file_path, '/flux_surf_2D/psi')
    view2d(R, Z, psi, "psi", save("psi"))

    theta_deg = dataset_reader(file_path, '/flux_surf_2D/theta_deg')
    view2d(R, Z, theta_deg, "theta_deg", save("theta_deg"))

    Ea_field = dataset_reader(file_path, f'/{nphi}/field_2d/Ea')
    view2d(R, Z, Ea_field, "Ea", save("Ea"))

    Ex_field = dataset_reader(file_path, f'/{nphi}/field_2d/Ex')
    view2d(R, Z, Ex_field.real, "Ex.real", save("Ex.real"))
    view2d(R, Z, Ex_field.imag, "Ex.imag", save("Ex.imag"))

    eps = dataset_reader(file_path, '/di_tensor_2D/eps')
    view2d(R, Z, eps.real, "eps.real", save("eps.real"))
    view2d(R, Z, eps.imag, "eps.imag", save("eps.imag"))

    eta = dataset_reader(file_path, '/di_tensor_2D/eta')
    view2d(R, Z, eta.real, "eta.real", save("eta.real"))
    view2d(R, Z, eta.imag, "eta.imag", save("eta.imag"))

    gee = dataset_reader(file_path, '/di_tensor_2D/gee')
    view2d(R, Z, gee.real, "gee.real", save("gee.real"))
    view2d(R, Z, gee.imag, "gee.imag", save("gee.imag"))

    Te_2D = dataset_reader(file_path, '/plasma_par_2D/Te')
    view2d(R, Z, Te_2D, "Te", save("Te"))

    Ti_2D = dataset_reader(file_path, '/plasma_par_2D/Ti')
    view2d(R, Z, Ti_2D, "Ti", save("Ti"))

    Btot = dataset_reader(file_path, '/magnt_fld_2D/Btot')
    view2d(R, Z, Btot, "Btot", save("Btot"))

    w0_wpe = dataset_reader(file_path, '/resonance_2D/w0_wpe')
    view2d(R, Z, w0_wpe, "w0/wpe", save("w0_wpe"))

    Xcutoff_at_0 = dataset_reader(file_path, '/resonance_2D/Xcutoff_at_0')
    view2d(R, Z, Xcutoff_at_0, "Xcutoff_at_0", save("Xcutoff_at_0"))

    PolRes_at_0 = dataset_reader(file_path, '/resonance_2D/PolRes_at_0')
    view2d(R, Z, PolRes_at_0, "PolRes_at_0", save("PolRes_at_0"))


if __name__ == "__main__":
    main()
