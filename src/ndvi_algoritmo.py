from pathlib import Path
import numpy as np
import xarray as xr
import rioxarray


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
