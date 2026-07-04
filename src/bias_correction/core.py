# el pipeline primario corregir ERA5 y IMERG datos con los datos de las estaciones.
# Con este podemos corregir cualquier datos facilmente (si necesitamos mas tipos de datos)

# 1. load_stations            - leer + estandarizar estacion CSV
# 2. get_station_coords       - uno (lat, lon) por cada estacion
# 3. extract_product_at_stations - Búsqueda de cuadrícula de vecinos más cercanos en cada estación
# 4. build_pairs              - unir obs y model mediante (station, date), eliminar valores nulos y calcular la razón o diferencia por estación y mes
# 5. compute_monthly_factors  - calculando la razón o la diferencia por (station, mes del calendario)
# 6. krige_monthly_field      - interpolar los factores a la cuadrícula nativa para cada mes
# 7. apply_correction         - aplicar el campo mensual correspondiente a todos los pasos temporales
# 8. cross_validate_loo       - validación cruzada dejando una estación fuera
# 9. run_pipeline             - ejecuta los pasos 1–8 para un único producto

# Imports
import config
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from pykrige.ok import OrdinaryKriging

# El minimo estaciones necesario intentar el variogram
# Bajo de este, pykrige puede ser mal
MIN_STATIONS_FOR_KRIG = 5


def load_stations(csv_path):
    """Leer el csv de los datos de estaciones y arreglarlo si hay problemas.

    Volver un dataframe con columnos:
    station_id, lat, lon, date, precip, tmed
    """
    cols = config.STATION_COLUMNS
    df = pd.read_csv(csv_path)

    rename_cols = {
        cols["station_id"]: "station_id",
        cols["lat"]: "lat",
        cols["lon"]: "lon",
        cols["date"]: "date",
        cols["precip"]: "precip",
        cols["tmed"]: "tmed",
    }
    core_cols = ["station_id", "lat", "lon", "date", "precip", "tmed"]

    for internal_name in ("departamento", "provincia"):
        source_col = cols.get(internal_name)
        if source_col is not None and source_col in df.columns:
            rename_cols[source_col] = internal_name
            core_cols.append(internal_name)

    df = df.rename(columns=rename_cols)
    df["date"] = pd.to_datetime(df["date"])
    df = df[core_cols]
    print(
        f"Cargado {len(df)} estacion mes filas de ancho {df['station_id'].nunique()} estaciones"
    )
    return df


def validate_stations(station_df):
    """Terminar la programa rapida si el dataframe de estacion no esta bien"""
    expected_cols = {"station_id", "lat", "lon", "date", "precip", "tmed"}
    missing = expected_cols - set(station_df.columns)
    assert not missing, f"station_df missing expected columns: {missing}"

    assert pd.api.types.is_datetime64_any_dtype(
        station_df["date"]
    ), "station_df['date'] did not parse to datetime"
    assert (
        station_df["station_id"].notna().all()
    ), "station_df has null station_id values"
    assert (
        station_df["lat"].between(-90, 90).all()
    ), "station_df has out-of-range latitude values"
    assert (
        station_df["lon"].between(-180, 180).all()
    ), "station_df has out-of-range longitude values"


def get_station_coords(station_df):
    """Una fila por cada estacion con su lat y lon"""
    coords = (
        station_df[["station_id", "lat", "lon"]]
        .drop_duplicates(subset="station_id")
        .reset_index(drop=True)
    )
    return coords


def extract_product_at_station(ds, var, station_coords):
    """Para cada estacion, conseguir el timeseries de 'var' de la cuadricula mas cerca

    Volver dataframe de la forma larga: station_id, date, model_value
    """
    records = []
    for _, row in station_coords.iterrows():
        try:
            series = ds[var].sel(lat=row["lat"], lon=row["lon"], method="nearest")
        except KeyError:
            print(f"AVISO: Estacion {row['station_id']} afuera de la cuadricula")
            continue
        vals = series.values
        times = pd.to_datetime(series["time"].values)
        records.append(
            pd.DataFrame(
                {
                    "station_id": row["station_id"],
                    "date": times,
                    "model_value": vals,
                }
            )
        )
    if not records:
        raise ValueError(f"Nada estaciones cerca de la cuadricula con variable {var}")
    return pd.concat(records, ignore_index=True)


def build_pairs(station_df, model_df, station_var):
    """Inner join de obs estacion y valores modelos (station_id, date)"""
    obs = station_df[["station_id", "lat", "lon", "date", station_var]].rename(
        columns={station_var: "obs_value"}
    )
    pairs = obs.merge(model_df, on=["station_id", "date"], how="inner")
    pairs = pairs.dropna(subset=["obs_value", "model_value"])
    return pairs
