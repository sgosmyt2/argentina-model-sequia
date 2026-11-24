from dataclasses import dataclass

import numpy as np
import xarray as xr


@dataclass
class GridSpec:
    res: float
    lat: np.ndarray  # centros, ascendantes
    lon: np.ndarray  # centros, ascendantes
    lat_edges: np.ndarray  # bordes, ascendantes, len = len(lat) + 1
    lon_edges: np.ndarray


def make_target(lat_min, lat_max, lon_min, lon_max, res):
    """Grid objetivo cuyos bordes son multiplos del res"""
    lat_edges = np.round(
        np.arange(np.floor(lat_min / res), np.ceil(lat_max / res) + 1) * res, 10
    )
    lon_edges = np.round(
        np.arange(np.floor(lon_min / res), np.ceil(lon_max / res) + 1) * res, 10
    )
    lat = (lat_edges[:-1] + lat_edges[1:]) / 2
    lon = (lon_edges[:-1] + lon_edges[1:]) / 2
    return GridSpec(res, lat, lon, lat_edges, lon_edges)
