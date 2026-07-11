from utils import dataset_reader, view2d, get_attributes_recursive_from, print_dict
def main():
    print("Hello from wave2d-visualizer!")
    file_path = 'results.h5'

    run_params = get_attributes_recursive_from(file_path, start_path='/run_params')
    print_dict(run_params)    
    nphi = run_params['w2grid']['nphi1']
    nphi = f"nphi-{abs(nphi):03d}" if nphi < 0 else f"nphi{nphi:03d}"
    print(nphi)
    #nphi = "nphi-014"
    R = dataset_reader(file_path, '/coord/X')
    Z = dataset_reader(file_path, '/coord/Y')

    psi = dataset_reader(file_path, '/flux_surf_2D/psi')
    view2d(R, Z, psi, "psi")

    theta_deg = dataset_reader(file_path, '/flux_surf_2D/theta_deg')
    view2d(R, Z, theta_deg, "theta_deg")

    Ea_field = dataset_reader(file_path, f'/{nphi}/field_2d/Ea')
    view2d(R, Z, Ea_field, "Ea")
    
    Ex_field = dataset_reader(file_path, f'/{nphi}/field_2d/Ex')
    view2d(R, Z, Ex_field.real, "Ex.real")
    view2d(R, Z, Ex_field.imag, "Ex.imag")

    eps = dataset_reader(file_path, f'/di_tensor_2D/eps')
    view2d(R, Z, eps.real, "eps.real")
    view2d(R, Z, eps.imag, "eps.imag")

    eta = dataset_reader(file_path, f'/di_tensor_2D/eta')
    view2d(R, Z, eta.real, "eps.real")
    view2d(R, Z, eta.imag, "eps.imag")

    gee = dataset_reader(file_path, f'/di_tensor_2D/gee')
    view2d(R, Z, eta.real, "gee.real")
    view2d(R, Z, eta.imag, "gee.imag")

    Te_2D = dataset_reader(file_path, '/plasma_par_2D/Te')
    view2d(R, Z, Te_2D, "Te")

    Ti_2D = dataset_reader(file_path, '/plasma_par_2D/Ti')
    view2d(R, Z, Ti_2D, "Ti")

    Btot = dataset_reader(file_path, '/magnt_fld_2D/Btot')
    view2d(R, Z, Btot, "Btot")

    w0_wpe = dataset_reader(file_path, '/resonance_2D/w0_wpe')
    view2d(R, Z, w0_wpe, "w0/wpe",  "w0_wpe")


    Xcutoff_at_0 = dataset_reader(file_path, '/resonance_2D/Xcutoff_at_0')
    view2d(R, Z, Xcutoff_at_0, "Xcutoff_at_0")


    PolRes_at_0 = dataset_reader(file_path, '/resonance_2D/PolRes_at_0')
    view2d(R, Z, PolRes_at_0, "PolRes_at_0")        

if __name__ == "__main__":
    main()
