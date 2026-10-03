from pathlib import Path

import dask
from dask.diagnostics import ProgressBar

from ndvi_algoritmo import calculate_sepa_persistence, load_ndvi_stack

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "raw" / "ndvi"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "ndvi_persistence.zarr"


def main():
    print(f"cargandose serie temporal de rasters desde {INPUT_DIR}")
    dask.config.set(scheduler="processes")

    # Cargar todos los archivos en un stack crónologico
    stack = load_ndvi_stack(INPUT_DIR, chunk_size=1024, max_workers=4)
    print(
        f"Raster stack cargado con la dimensión: {stack.shape}, chunks={stack.chunks}"
    )

    # Calcular logicó de persistencía
    print("Corriendo la calculación de éstres SEPA")
    persistence = calculate_sepa_persistence(stack, cap_at_seven=True)

    # Guardarlo
    ds_out = persistence.to_dataset(name="ndvi_persistence")
    encoding = {
        "ndvi_persistence": {
            "dtype": "uint8",
        }
    }

    with ProgressBar():
        ds_out.to_zarr(OUTPUT_FILE, encoding=encoding, mode="w")
    print(f"\nGuardado prueba NetCDF a {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
