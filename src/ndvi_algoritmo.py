from pathlib import Path

import numpy as np
import rioxarray
import xarray as xr


def make_mock_stack(file_path, num_steps=12):
    """
    Hasta que puedo conseguir los archivos enteros, necesito probar el
    modulo. Para hacer eso, carga uno GeoTIFF y repitelo con una dimension
    de tiempo crear una pila multipasa para probar calculaciones.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Archivo no existe: {file_path}")

    # Abre una singular fotografia de raster
    single_frame = rioxarray.open_rasterio(file_path).squeeze(drop=True)

    # Repite las fotografías especiales a traves de los paso N tiempo
    mock_data = np.repeat(single_frame.values[np.newaxis, :, :], num_steps, axis=0)

    # Mantenga mascara del fondo, solo ponga un píxel de vegetacion valido al clase 3 si T=4
    veg_mask = ~np.isin(single_frame.values, [0, 6])
    mock_data[4, veg_mask] = 3

    # Construye DataArray que tiene los coordinatos originales
    mock_da = xr.DataArray(
        mock_data,
        dims=["time", "y", "x"],
        coords={"y": single_frame.y, "x": single_frame.x, "time": range(num_steps)},
        attrs=single_frame.attrs,
    )
    return mock_da
