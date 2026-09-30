from pathlib import Path

from ndvi_algoritmo import calculate_sepa_persistence, load_ndvi_stack

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ndvi"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "persistence_test_output.nc"


def main():
    print(f"cargandose serie temporal de rasters desde {INPUT_DIR}")

    # Cargarse el archivo duplicado en 12 pasos de tiempo
    stack = load_ndvi_stack(INPUT_DIR, num_steps=12)
    print(f"Raster stack cargado con la dimensión: {stack.shape}")

    # Calcular logicó de persistencía
    print("Corriendo la calculación de éstres SEPA")
    persistence = calculate_sepa_persistence(stack, cap_at_seven=True)

    # Guardarlo
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ds_out = persistence.to_dataset(name="ndvi_persistence")
    encoding = {
        "ndvi_persistence": {
            "zlib": True,
            "complevel": 5,
            "dtype": "uint8",
            "_FillValue": 0,
        }
    }
    ds_out.to_netcdf(OUTPUT_FILE, encoding=encoding)
    print(f"\nGuardado prueba NetCDF a {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
