import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import dask.array as da
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


def load_ndvi_stack(folder_path, chunk_size=2024, max_workers=4):
    """
    Carga archivos en paralelo (lectura I/O), luego concatena.
    Mantiene el eje time sin trocear (lo necesita la recurrencia).
    """
    folder = Path(folder_path)
    valid_extensions = {".img", ".tif", ".tiff"}

    files = sorted(
        [
            f
            for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in valid_extensions
        ],
        key=extract_sort_key,
    )

    if not files:
        raise FileNotFoundError(f"No .img/.tif en {folder_path}")

    def load_single(f):
        # Carga un archivo individual
        da_single = rioxarray.open_rasterio(
            f, chunks={"x": chunk_size, "y": chunk_size}
        )
        da_single = da_single.squeeze(drop=True)
        year, doy = extract_sort_key(f)
        return da_single, f"{year}_{doy:03d}"

    # Paralleliza la lectura
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(load_single, files))

    time_slices, time_labels = zip(*results)
    stack = xr.concat(time_slices, dim="time")
    stack = stack.assign_coords(time=list(time_labels))

    # Fuerza time como un solo chunk
    stack = stack.chunk({"time": -1, "y": chunk_size, "x": chunk_size})
    return stack


def persistence_block(block, cap_at_seven=True):
    """
    Núcleo vectorizado en NumPy: bucle solo sobre time (corto),
    vectorización completa del espacio (rápido).
    Block: (time, chunk_y, chunk_x)
    """
    is_stress = np.isin(block, [4, 5]).astype(np.uint8)
    persistence = np.zeros_like(is_stress, dtype=np.uint8)

    for t in range(block.shape[0]):
        if t == 0:
            persistence[t] = is_stress[t]
        else:
            streak = (persistence[t - 1] + 1) * is_stress[t]
            persistence[t] = np.minimum(streak, 7) if cap_at_seven else streak

    return persistence.astype(np.uint8)


def calculate_sepa_persistence(anomaly_da, cap_at_seven=True):
    """
    Calcular duraciones de estres consecutivo (clases 4 y 5),
    y poner un tope maximo de la persistencia a 7 pasos como dice la
    metodología de SEPA.
    """
    if not isinstance(anomaly_da.data, da.Array):
        raise TypeError("anomaly_da debe estar respaldado por dask")

    time_chunks = anomaly_da.chunksizes.get("time")
    if time_chunks is not None and len(time_chunks) != 1:
        raise ValueError("time tiene múltiples chunks pero necesita uno")

    result_data = anomaly_da.data.map_blocks(
        persistence_block, cap_at_seven=cap_at_seven, dtype=np.uint8
    )

    result_da = xr.DataArray(
        result_data,
        coords=anomaly_da.coords,
        dims=anomaly_da.dims,
        name="ndvi_persistence",
        attrs=anomaly_da.attrs,
    )

    result_da.encoding = {}

    return result_da
