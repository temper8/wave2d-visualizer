from utils import dataset_reader, view2d
def main():
    print("Hello from wave2d-visualizer!")
    file_path = 'results.h5'

    R = dataset_reader(file_path, '/nphi-122/grid_2d/X')
    Z = dataset_reader(file_path, '/nphi-122/grid_2d/Y')

    #R = dataset_reader(file_path, '/flux_surf_2D/X')
    #Z = dataset_reader(file_path, '/flux_surf_2D/Y')
    psi = dataset_reader(file_path, '/flux_surf_2D/psi')
    view2d(R, Z, psi, "psi")

    theta_deg = dataset_reader(file_path, '/flux_surf_2D/theta_deg')
    view2d(R, Z, theta_deg, "theta_deg")
    #Ea_field = dataset_reader(file_path, '/nphi-122/field_2d/Ea')
    #view2d(R, Z, Ea_field, "Ea field")


    R = dataset_reader(file_path, '/plasma_par_2D/X')
    Z = dataset_reader(file_path, '/plasma_par_2D/Y')
    Te_2D = dataset_reader(file_path, '/plasma_par_2D/Te')
    view2d(R, Z, Te_2D, "Te")

    Btot = dataset_reader(file_path, '/magnt_fld_2D/Btot')
    view2d(R, Z, Btot, "Btot")

    w0_wpe = dataset_reader(file_path, '/resonance_2D/w0_wpe')
    view2d(R, Z, w0_wpe, "w0/wpe",  "w0_wpe")

if __name__ == "__main__":
    main()
