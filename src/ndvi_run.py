from pathlib import Path

from ndvi_algoritmo import calculate_sepa_persistence, make_mock_stack

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SINGLE_FILE = PROJECT_ROOT / "data" / "raw" / "sc-2026241.tif"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "persistence_test_output/nc"


def main():
    print(f"cargandose el raster individual desde {SINGLE_FILE}")

    # Cargarse el archivo duplicado en 12 pasos de tiempo
    mock_stack = make_mock_stack(SINGLE_FILE, num_steps=12)
    print(f"Raster stack simulado creado con la forma: {mock_stack.shape}")

    # Calcular logicó de persistencía
    print("Corriendo la calculación de persistencía SEPA")
    persistence = calculate_sepa_persistence(mock_stack, cap_at_seven=True)

    # Imprimir la revisión de validación
    p_vals = persistence.values
    print("\n=== TEST RESULTS ===")
    print(
        f"T=3 (4 pasos de estrés consecutivo): valor máximo calculado = {p_vals[3].max()}"
    )
    print(
        f"T=4 (Descanso de estrés inyectado):  valor máximo calculado = {p_vals[4].max()}"
    )
    print(
        f"T=11 (7 pasos después el reinicio):  valor máximo calculado = {p_vals[11].max()}"
    )

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
