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
import warnings

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


def compute_monthly_factors(pairs_df, method, min_overlap_months, ratio_min, ratio_max):
    """Por (estación, mes), calcular un ratio o factor de corrección
    delta a partir de las medias climatológicas de obs y modelo durante el
    periodo emparejado.

    Volver: station_id, lat, lon, mes, factor, n_months
    """
    if method not in ("ratio", "delta"):
        raise ValueError(f"Método desconocido '{method}', 'ratio' o 'delta' esperados")

    df = pairs_df.copy()
    df["month"] = df["date"].dt.month

    grouped = df.groupby(["station_id", "month"])
    counts = grouped.size().rename("n_months")

    means = grouped[["obs_value", "model_value"]].mean()
    means = means.join(counts)
    means = means[means["n_months"] >= min_overlap_months]

    if method == "ratio":
        factor = means["obs_value"] / means["model_value"]
        if ratio_min is not None or ratio_max is not None:
            factor = factor.clip(lower=ratio_min, upper=ratio_max)
    else:
        factor = means["obs_value"] - means["model_value"]

    result = means.copy()
    result["factor"] = factor
    result = result.reset_index()

    coords = df.drop_duplicates("station_id")[["station_id", "lat", "lon"]]
    result = result.merge(coords, on="station_id", how="left")

    result = result[["station_id", "lat", "lon", "month", "factor", "n_months"]]

    print(
        f"compute_monthly_factors ({method}): {len(result)} estacion-mes \nfactores calculado (min_overlap={min_overlap_months})"
    )
    return result


def krige_monthly_field(
    factors_df, target_lat, target_lon, kriging_config, ratio_min, ratio_max
):
    """Poner kriging ordinario por mes y predecir en la cuadricula objetiva.

    Volver month: 2D array (lat, lon)
    """
    fields: dict[int, np.ndarray] = {}
    lon_grid, lat_grid = np.meshgrid(target_lon, target_lat)

    for month in range(1, 13):
        month_df = factors_df[factors_df["month"] == month]
        n_points = len(month_df)

        if n_points == 0:
            print(
                f"AVISO: Mes {month}: nada factores de la estación disponsible, campo esta NaN"
            )
            fields[month] = np.full(lat_grid.shape, np.nan)
            continue

        if n_points < MIN_STATIONS_FOR_KRIG:
            flat_value = month_df["factor"].mean()
            print(
                f"AVISO: Mes {month}: solo {n_points} estación(es) disponsible. (< {MIN_STATIONS_FOR_KRIG}), volver al campo plano. (mean factor = {flat_value:.4f})"
            )
            fields[month] = np.full(lat_grid.shape, flat_value)
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ok = OrdinaryKriging(
                month_df["lon"].values,
                month_df["lat"].values,
                month_df["factor"].values,
                variogram_model=kriging_config["variogram_model"],
                nlags=kriging_config["nlags"],
                coordinates_type=kriging_config["coordinates_type"],
                verbose=kriging_config["verbose"],
                enable_plotting=kriging_config["enable_plotting"],
            )
            z, _ss = ok.execute("grid", target_lon, target_lat)

        z = np.asarray(z)
        if ratio_min is not None or ratio_max is not None:
            z = np.clip(z, ratio_min, ratio_max)

        fields[month] = z
        print(f"Mes {month:2d}: kriged desde {n_points} estaciónes")

    return fields


def apply_correction(ds, var, monthly_fields, method):
    """Aplicar el por mes campo de bias a cada tiempo de 'var', en todo el dataset."""
    raw = ds[var]
    months = raw["time"].dt.months.values

    field_stack = np.stack([monthly_fields[m] for m in range(1, 13)], axis=0)
    field_da = xr.DataArray(
        field_stack,
        dims=("month", "lat", "lon"),
        coords={"month": np.arange(1, 13), "lat": ds["lat"], "lon": ds["lon"]},
        name=f"{var}_bias_field",
    )

    field_per_time = field_da.sel(month=xr.DataArray(months, dims="time"))
    field_per_time = field_per_time.assign_coords(time=raw["time"])

    if method == "ratio":
        corrected = raw * field_per_time
    elif method == "delta":
        corrected = raw + field_per_time
    else:
        raise ValueError(f"metodo desconocido {method}")

    out = ds.copy()
    out[f"{var}_raw"] = raw
    out[var] = corrected
    out[f"{var}_bias_field"] = field_da
    return out


def cross_valid_loo(
    pairs_df, method, min_overlap_mths, kriging_config, ratio_min, ratio_max
):
    """LOO Validacion, por cada estación hace una reparación de los factores + kriging excluirlo,
    predecir la correcion a su locación y comparar corregido contra crudo error
    """
    station_ids = pairs_df["station_id"].unique()
    raw_errors = []
    corrected_errors = []

    for held_out in station_ids:
        train = pairs_df[pairs_df["station_id"] != held_out]
        test = pairs_df[pairs_df["station_id"] == held_out]
        if test.empty:
            continue

        factors = compute_monthly_factors(
            train, method, min_overlap_mths, ratio_min, ratio_max
        )
        if factors.empty:
            continue

        station_lat = test["lat"].iloc[0]
        station_lon = test["lon"].iloc[0]

        # krige en un punto singular por esta estación
        fields = krige_monthly_field(
            factors,
            target_lat=np.array([station_lat]),
            target_lon=np.array([station_lon]),
            kriging_config=kriging_config,
            ratio_min=ratio_min,
            ratio_max=ratio_max,
        )

        for _, row in test.iterrows():
            month = row["date"].month
            field_val = fields[month][0, 0]
            if np.isnan(field_val):
                continue

            raw_val = row["model_value"]
            obs_val = row["obs_value"]

            if method == "ratio":
                corrected_val = raw_val * field_val
            else:
                corrected_val = raw_val + field_val

            raw_errors.append(raw_val - obs_val)
            corrected_errors.append(corrected_val - obs_val)

    raw_errors = np.array(raw_errors)
    corrected_errors = np.array(corrected_errors)

    if len(raw_errors) == 0:
        print("AVISO: LOO validación no creyó nada puntos comparables")
        return {
            "rmse_raw": np.nan,
            "rmse_corrected": np.nan,
            "bias_raw": np.nan,
            "bias_corrected": np.nan,
            "n_stations": len(station_ids),
            "n_obs": 0,
        }

    return {
        "rmse_raw": float(np.sqrt(np.mean(raw_errors**2))),
        "rmse_corrected": float(np.sqrt(np.mean(corrected_errors**2))),
        "bias_raw": float(np.mean(raw_errors)),
        "bias_corrected": float(np.mean(corrected_errors)),
        "n_stations": len(station_ids),
        "n_obs": len(raw_errors),
    }


def run_pipeline(product_name):
    """Empezar el pipeline entero por un producto (por ejemplo IMERG e ERA5).

    Usa el config en config.py PRODUCT_CONFIG, así que podemos añadir más productos si es
    necesario.
    """
    cfg = config.PRODUCT_CONFIG[product_name]
    print(f"Empezando bias correccion por {product_name}")

    ds = xr.open_dataset(cfg["input_nc"])
    station_df = load_stations(config.STATION_CSV)
    validate_stations(station_df)
    station_coords = get_station_coords(station_df)

    validation_rows = []

    for var, var_cfg in cfg["variables"].items():
        print(f" Variable: {var} (metodo={var_cfg['method']})")
        station_var = var_cfg["station_var"]
        method = var_cfg["method"]
        ratio_min = config.PRECIP_RATIO_MIN if method == "ratio" else None
        ratio_max = config.PRECIP_RATIO_MAX if method == "ratio" else None

        model_df = extract_product_at_station(ds, var, station_coords)
        pairs = build_pairs(station_df, model_df, station_var)

        factors = compute_monthly_factors(
            pairs, method, config.MIN_OVERLAP_MONTHS, ratio_min, ratio_max
        )
        fields = krige_monthly_field(
            factors,
            target_lat=ds["lat"].values,
            target_lon=ds["lon"].values,
            kriging_config=config.KRIGING_CONFIG,
            ratio_min=ratio_min,
            ratio_max=ratio_max,
        )
        ds = apply_correction(ds, var, fields, method)

        if config.RUN_LOO_VALIDATION:
            summary = cross_valid_loo(
                pairs,
                method,
                config.MIN_OVERLAP_MONTHS,
                config.KRIGING_CONFIG,
                ratio_min,
                ratio_max,
            )
            summary = {"product": product_name, "variable": var, **summary}
            validation_rows.append(summary)
            print(
                f"LOO ({var}): RMSE raw={summary['rmse_raw']:.3f} -> "
                f"corrected={summary['rmse_corrected']:.3f} | "
                f"bias raw={summary['bias_raw']:.3f} -> "
                f"corrected={summary['bias_corrected']:.3f} "
                f"(n={summary['n_obs']} obs, {summary['n_stations']} stations)"
            )

    cfg["output_nc"].parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(cfg["output_nc"])
    print(f"Escribió dataset corregido a {cfg['output_nc']}")

    if config.RUN_LOO_VALIDATION and validation_rows:
        val_df = pd.DataFrame(validation_rows)
        config.VALIDATION_OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
        if config.VALIDATION_OUTPUT_CSV.exists():
            existing = pd.read_csv(config.VALIDATION_OUTPUT_CSV)
            existing = existing[existing["product"] != product_name]
            val_df = pd.concat([existing, val_df], ignore_index=True)
        val_df.to_csv(config.VALIDATION_OUTPUT_CSV, index=False)
        print(f"Wrote validation summary -> {config.VALIDATION_OUTPUT_CSV}")

    return ds
