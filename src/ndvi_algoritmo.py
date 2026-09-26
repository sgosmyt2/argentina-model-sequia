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


def calculate_sepa_persistence(anomaly_da, cap_at_seven=True):
    """
    Calcular duraciones de estres consecutivo (clases 4 y 5),
    y poner un tope maximo de la persistencia a 7 pasos como dice la
    metodología de SEPA.
    """
    arr = anomaly_da.values

    # mascara de estres binaraio (1 por los clases de estres 4 y 5, 0 si no)
    is_stress = np.isin(arr, [4, 5]).astype(np.int16)

    # Identificar los píxeles del fondo o máscara (agua/non veg clase 0 o 6)
    is_background = np.isin(arr, [0, 6])

    persistence = np.zeros_like(is_stress, dtype=np.int16)

    # loop temporal
    for t in range(is_stress.shape[0]):
        if t == 0:
            persistence[t] = is_stress[t]
        else:
            streak = (persistence[t - 1] + 1) * is_stress[t]
            if cap_at_seven:
                persistence[t] = np.minimum(streak, 7)
            else:
                persistence[t] = streak

    # aplica de nuevo la máscara del fondo como 0
    persistence[is_background] = 0

    # ponga el xarray como uint8 para mantener espacio
    result_da = anomaly_da.copy(data=persistence.astype(np.uint8))
    result_da.name = "ndvi_persistence"
    return result_da
