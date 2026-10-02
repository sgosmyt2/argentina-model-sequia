import re
from pathlib import Path

import numpy as np
import rioxarray
import xarray as xr


def extract_sort_key(filepath):
    """
    Extrae el año y el día del año para ordenar los archivos. Funciona con
    .img, .tif/tiff.
    """
    filename = Path(filepath).name
    # Si la forma del archivo cambia con NDVI diferente vas a necesitar cambiar el string aqui
    match = re.search(
        r"sc-iv-(\d{3}).*?(\d{4})-argentina\.(img|tif|tiff)$",
        filename,
        re.IGNORECASE,
    )
    if match:
        doy, year, _ = match.groups()
        return (int(year), int(doy))
    return (0, 0)


def load_ndvi_stack(folder_path, chunk_size=2024):
    """
    Carga todos los archivos .img/.tif en orden cronológico como un
    DataArray perezoso.
    """
    folder = Path(folder_path)
    valid_extensions = {".img", ".tif", ".tiff"}

    # Filtrar archivos válidos
    files = [
        f
        for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in valid_extensions
    ]
    files = sorted(files, key=extract_sort_key)

    if not files:
        raise FileNotFoundError(
            f"No se encontraron archivos .img o .tif en {folder_path}"
        )

    time_slices = []
    for f in files:
        # rioxarray abre tanto .img como .tif usando GDAL
        da = rioxarray.open_rasterio(f, chunks={"x": chunk_size, "y": chunk_size})
        da = da.squeeze(drop=True)

        year, doy = extract_sort_key(f)
        da = da.assign_coords(time=f"{year}_{doy:03d}")
        time_slices.append(da)

    return xr.concat(time_slices, dim="time")


def persistence_1d(arr_1d, cap_at_seven=True):
    """
    Operación 1d en numpy ejecutada por dask en paralelo para cada píxel
    individual. Recibe un vector a lo largo del eje del tiempo.
    """
    is_stress = np.isin(arr_1d, [4, 5])
    is_valid_non_stress = np.isin(arr_1d, [1, 2, 3])

    # Cualquier valor fuera de 1,2,3,4,5 (0, 6, NaN) es fondo o máscara
    is_bg = ~np.isin(arr_1d, [1, 2, 3, 4, 5])

    persistence = np.zeros_like(arr_1d, dtype=np.uint8)
    current_streak = 0

    for t in range(len(arr_1d)):
        if is_bg[t]:
            current_streak = 0
            persistence[t] = 0
        elif is_stress[t]:
            current_streak += 1
            persistence[t] = min(current_streak, 7) if cap_at_seven else current_streak
        else:
            current_streak = 0
            persistence[t] = 0

    return persistence


def calculate_sepa_persistence(anomaly_da, cap_at_seven=True):
    """
    Calcular duraciones de estres consecutivo (clases 4 y 5),
    y poner un tope maximo de la persistencia a 7 pasos como dice la
    metodología de SEPA.
    """
    anomaly_da = anomaly_da.chunk({"time": -1, "x": 1024, "y": 1024})

    # Vectorización paralela sobre las dimensiones especiales
    result_da = xr.apply_ufunc(
        persistence_1d,
        anomaly_da,
        kwargs={"cap_at_seven": cap_at_seven},
        input_core_dims=[["time"]],
        output_core_dims=[["time"]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[np.uint8],
    )

    # Asegurar que el orden de las dimensiones se mantenga como time, y, x
    result_da = result_da.transpose("time", "y", "x")
    result_da.name = "ndvi_persistence"
    return result_da
