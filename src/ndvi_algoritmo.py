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
