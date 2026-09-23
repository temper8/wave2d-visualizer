import sys

from src.common.h5reader import H5Reader
from src.common.paths import wave2d_results, plots_dir, wave2d_latest
from src.utils import view2d, print_dict


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else wave2d_latest("FT2")
    file_path = str(wave2d_results(run_id))
    out_dir = plots_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run: {run_id}\nFile: {file_path}\nPlots -> {out_dir}")

    # Одно соединение с HDF5 на все чтения (ленивое, закрывается на выходе).
    with H5Reader(file_path) as reader:
        run_params = reader.params()
        print_dict(run_params)
        nphi = run_params['w2grid']['nphi1']
        nphi = f"nphi{nphi:+04d}"  # канон: nphi+122 / nphi-014
        print(nphi)

        def save(title: str) -> str:
            return str(out_dir / title)

        R = reader.array('/coord/X')
        Z = reader.array('/coord/Y')

        psi = reader.array('/flux_surf_2D/psi')
        view2d(R, Z, psi, "psi", save("psi"))

        theta_deg = reader.array('/flux_surf_2D/theta_deg')
        view2d(R, Z, theta_deg, "theta_deg", save("theta_deg"))

        Ea_field = reader.array(f'/{nphi}/field_2D/Ea')
        view2d(R, Z, Ea_field, "Ea", save("Ea"))

        Ex_field = reader.array(f'/{nphi}/field_2D/Ex')
        view2d(R, Z, Ex_field.real, "Ex.real", save("Ex.real"))
        view2d(R, Z, Ex_field.imag, "Ex.imag", save("Ex.imag"))

        eps = reader.array('/di_tensor_2D/eps')
        view2d(R, Z, eps.real, "eps.real", save("eps.real"))
        view2d(R, Z, eps.imag, "eps.imag", save("eps.imag"))

        eta = reader.array('/di_tensor_2D/eta')
        view2d(R, Z, eta.real, "eta.real", save("eta.real"))
        view2d(R, Z, eta.imag, "eta.imag", save("eta.imag"))

        gee = reader.array('/di_tensor_2D/gee')
        view2d(R, Z, gee.real, "gee.real", save("gee.real"))
        view2d(R, Z, gee.imag, "gee.imag", save("gee.imag"))

        Te_2D = reader.array('/plasma_par_2D/Te')
        view2d(R, Z, Te_2D, "Te", save("Te"))

        Ti_2D = reader.array('/plasma_par_2D/Ti')
        view2d(R, Z, Ti_2D, "Ti", save("Ti"))

        Btot = reader.array('/magnt_fld_2D/Btot')
        view2d(R, Z, Btot, "Btot", save("Btot"))

        w0_wpe = reader.array('/resonance_2D/w0_wpe')
        view2d(R, Z, w0_wpe, "w0/wpe", save("w0_wpe"))

        Xcutoff_at_0 = reader.array('/resonance_2D/Xcutoff_at_0')
        view2d(R, Z, Xcutoff_at_0, "Xcutoff_at_0", save("Xcutoff_at_0"))

        PolRes_at_0 = reader.array('/resonance_2D/PolRes_at_0')
        view2d(R, Z, PolRes_at_0, "PolRes_at_0", save("PolRes_at_0"))


if __name__ == "__main__":
    main()
