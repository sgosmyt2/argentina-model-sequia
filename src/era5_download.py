# Script to download ERA5
# He hecho este script para descargar era5 y unzip, cuales variables queremos puede cambiar y tambien el marco de tiempo
# Tambien que tipo de datos por ejemplo cada hora o diario, solo elegí mensual

# Imports
import cdsapi
from pathlib import Path
import os

# Constants
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

YEAR_START = 1980
YEAR_END = 2026
NORTH = -21
SOUTH = -55
WEST = -74
EAST = -53

client = cdsapi.Client()

era5_variables = {
    "single_levels": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "product_type": "monthly_averaged_reanalysis",
        "variables": [
            "total_precipitation",
            "volumetric_soil_water_layer_1",
            "volumetric_soil_water_layer_2",
            "volumetric_soil_water_layer_3",
            "volumetric_soil_water_layer_4",
            "high_vegetation_cover",
            "low_vegetation_cover",
            "2m_temperature",
            "runoff",
        ],
    }
}

years = [str(year) for year in range(YEAR_START, YEAR_END + 1)]
months = [str(month).zfill(2) for month in range(1, 13)]

base_path = os.path.join(RAW_DIR, "era5_monthly_patagonia")

# Descarga este archivo desde CDSAPI

for year in years:
    out_file = f"{base_path}_{year}.nc"

    if os.path.exists(out_file):
        continue

    client.retrieve(
        era5_variables["single_levels"]["dataset"],
        {
            "product_type": era5_variables["single_levels"]["product_type"],
            "variable": era5_variables["single_levels"]["variables"],
            "year": year,
            "month": months,
            "time": "00:00",
            "area": [-21, -74, -55, -53],
            "format": "netcdf",
        },
        out_file,
    )
