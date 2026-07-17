# Central configuration for the ERA5 / IMERG bias correction pipelines.

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RESULTS_DIR = PROJECT_ROOT / "results"
BIAS_RESULTS_DIR = RESULTS_DIR / "bias_correction"

STATION_CSV = PROCESSED_DIR / "fixed_station.csv"
ERA5_DATA = PROCESSED_DIR / "era5_arg_monthly_clean.nc"
IMERG_DATA = PROCESSED_DIR / "imerg_arg_monthly_clean.nc"
CHIRPS_DATA = PROCESSED_DIR / "chirps_arg_monthly_clean.nc"
ERA5_OUTPUT_NC = BIAS_RESULTS_DIR / "era5_arg_monthly_corrected.nc"
IMERG_OUTPUT_NC = BIAS_RESULTS_DIR / "imerg_arg_monthly_corrected.nc"
CHIRPS_OUTPUT_NC = BIAS_RESULTS_DIR / "chirps_arg_monthly_corrected.nc"

STATION_COLUMNS = {
    "station_id": "Estacion",
    "lat": "Latitud",
    "lon": "Longitud",
    "date": "Fecha",
    "precip": "Precipitacion",
    "tmed": "Tmed",
    "departamento": "Departamento",
    "provincia": "Provincia",
}

PRODUCT_CONFIG = {
    "era5": {
        "input_nc": ERA5_DATA,
        "output_nc": ERA5_OUTPUT_NC,
        "variables": {
            "precip_month": {"station_var": "precip", "method": "ratio"},
            "t2m": {"station_var": "tmed", "method": "delta"},
        },
    },
    "imerg": {
        "input_nc": IMERG_DATA,
        "output_nc": IMERG_OUTPUT_NC,
        "variables": {
            "precip_month": {"station_var": "precip", "method": "ratio"},
        },
    },
    "chirps": {
        "input_nc": CHIRPS_DATA,
        "output_nc": CHIRPS_OUTPUT_NC,
        "variables": {
            "precip_month": {"station_var": "precip", "method": "ratio"},
        },
    },
}

# Filtrar de la estacion
# Este es los minimos meses de datos sin NaNs que una estacion tiene que tener para estar usado.
# Puede cambiar si es demasiado fuerte
MIN_OVERLAP_MONTHS = 24

# Límites aplicados a la relación entre las observaciones de las estaciones y el
# modelo antes del kriging.
PRECIP_RATIO_MIN = 0.2
PRECIP_RATIO_MAX = 5.0

KRIGING_CONFIG = {
    "variogram_model": "spherical",
    "nlags": 6,
    "coordinates_type": "geographic",
    "verbose": False,
    "enable_plotting": False,
}

# Validacion, solo estoy usando "leave one station out" pero si queremos, podemos usar una manera mas fuerte como
# k fold repeats pero depende de que preciso la queremos
RUN_LOO_VALIDATION = True
VALIDATION_OUTPUT_CSV = BIAS_RESULTS_DIR / "loo_validation_summary.csv"
