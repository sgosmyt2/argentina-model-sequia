# Script to download ERA5
# He hecho este script para descargar era5 y unzip, cuales variables queremos puede cambiar y tambien el marco de tiempo
# Tambien que tipo de datos por ejemplo cada hora o diario, solo elegí mensual

# Imports
import cdsapi
from pathlib import Path
import os
import zipfile
import xarray as xr
import shutil
import matplotlib.pyplot as plt
import geopandas as gpd
import regionmask

# Constants
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "era5"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

YEAR_START = 1980
YEAR_END = 2026
NORTH = -10
SOUTH = -60
WEST = -85
EAST = -30

client = cdsapi.Client()

era5_variables = {
    "single_levels": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "product_type": "monthly_averaged_reanalysis",
        "variables": [
            "total_precipitation",
            "2m_temperature",
            "maximum_2m_temperature_since_previous_post_processing",
            "minimum_2m_temperature_since_previous_post_processing",
        ],
    }
}

years = [str(year) for year in range(YEAR_START, YEAR_END + 1)]
months = [str(month).zfill(2) for month in range(1, 13)]

base_path = os.path.join(RAW_DIR, "era5_monthly_patagonia")

# Descarga archivos desde CDSAPI

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

# Revisar si los archivos son zip (es muy comun con descargando archivos con cdsapi que los ponen en un zip aunque no se pregunte)
file = f"{base_path}_{year}.nc"
all_zip = all(zipfile.is_zipfile(file) for year in years)
print(f"All files are zip files: {all_zip}")

avgad_dir = RAW_DIR / "avgad"
avgua_dir = RAW_DIR / "avgua"
avgad_dir.mkdir(exist_ok=True)
avgua_dir.mkdir(exist_ok=True)

for year in years:
    zip_file = f"{base_path}_{year}.nc"

    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        for member in zip_ref.namelist():
            if "avgad" in member:
                output_file = avgad_dir / f"avgad_{year}.nc"
            elif "avgua" in member:
                output_file = avgua_dir / f"avgua_{year}.nc"
            else:
                continue

            with zip_ref.open(member) as src, open(output_file, "wb") as dst:
                shutil.copyfileobj(src, dst)

print("Extracted all files.")

# Hacer un dataset es necesario unir los avgad (tipas de variables) y las avguas juntos antes de unirlos en 1 dataset
ds_avgad = xr.open_mfdataset(
    str(RAW_DIR / "avgad" / "*.nc"),
    combine="by_coords",
)

ds_avgua = xr.open_mfdataset(
    str(RAW_DIR / "avgua" / "*.nc"),
    combine="by_coords",
)


# Arreglar el horario (ciertas variables usan horas diferentes, no significa nada al menos que usamos datos horarios)
def normalize_time(ds, dim="valid_time"):
    ds[dim] = ds[dim].astype("datetime64[D]")
    return ds


ds_avgad = normalize_time(ds_avgad)
ds_avgua = normalize_time(ds_avgua)

ds_era5 = xr.merge(
    [ds_avgad, ds_avgua],
    compat="override",
    join="exact",
)

# Para conseguir todo los datos de Argentina, estoy descargando masomenos el cono sur y aplico un geoJSON de argentina en el ds_era5
gdf = gpd.read_file("data/json/ne_50m_admin_0_countries.json")
arg = gdf[gdf["ADMIN"] == "Argentina"].copy()
geom = arg.geometry.iloc[0]
geom = geom.simplify(tolerance=0.01, preserve_topology=True)

regions = regionmask.Regions([geom])

ds_era5 = ds_era5.rename({"latitude": "lat", "longitude": "lon"})

mask = regions.mask(ds_era5.lon, ds_era5.lat)
ds_argentina = ds_era5.where(mask == 0)

# Revisar si esta bien
print(ds_argentina)
ds_argentina["t2m"].isel(valid_time=0).plot()
plt.savefig("era5_check.png", dpi=200, bbox_inches="tight")
plt.close()

# Finalmente guardalo
ds_argentina.to_netcdf(PROCESSED_DIR / "era5_argentina_1980-2026.nc")
