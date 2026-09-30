import re
from pathlib import Path
from unittest import result

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


def calculate_sepa_persistence(anomaly_da, cap_at_seven=True, block_size=1000):
    """
    Calcular duraciones de estres consecutivo (clases 4 y 5),
    y poner un tope maximo de la persistencia a 7 pasos como dice la
    metodología de SEPA.
    """
    time_len, height, width = anomaly_da.shape
    persistence = np.zeros((time_len, height, width), dtype=np.uint8)

    # Procesar en bloques a lo largo del eje Y para controlar el uso de ram
    for y_start in range(0, height, block_size):
        y_end = min(y_start + block_size, height)

        # Extraer solo un bloque especial para todos los pasos de tiempo
        block = anomaly_da[:, y_start:y_end, :].values

        is_stress = np.isin(block, [4, 5]).astype(np.int16)
        is_background = np.isin(block, [0, 6])

        block_persistence = np.zeros_like(is_stress, dtype=np.int16)

        for t in range(time_len):
            if t == 0:
                block_persistence[t] = is_stress[t]
            else:
                streak = (block_persistence[t - 1] + 1) * is_stress[t]
                if cap_at_seven:
                    block_persistence[t] = np.minimum(streak, 7)
                else:
                    block_persistence[t] = streak

        block_persistence[is_background] = 0
        persistence[:, y_start:y_end, :] = block_persistence.astype(np.uint8)

    result_da = anomaly_da.copy(data=persistence)
    result_da.name = "ndvi_persistence"
    return result_da
