from pathlib import Path
import requests

import geopandas as gpd
import matplotlib.pyplot as plt
import regionmask
import xarray as xr

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "chirps"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

CHIRPS_URL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/netcdf/chirps-v2.0.monthly.nc"
RAW_FILE = RAW_DIR / "chirp_monthly_argentina.nc"

NORTH, SOUTH, WEST, EAST = -20, -56, -76, -52

# Descargar, y fija si ya existe
if not RAW_FILE.exists():
    print(f"Descargar archivo de CHIRPS mensual global desde {CHIRPS_URL} ...")
    with requests.get(CHIRPS_URL, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        last_reported_pct = -1
        with open(RAW_FILE, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192 * 16):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    if pct - last_reported_pct >= 5:
                        print(
                            f"  {downloaded / 1e9:.2f} / {total / 1e9:.2f} GB ({pct:.1f}%)"
                        )
                        last_reported_pct = pct
    print("Descarga terminado")
else:
    print(f"Ya hay el archivo aquí: {RAW_FILE}, saltandose.")

# Cambiar a Argentina
ds = xr.open_dataset(RAW_FILE, chunks={"time": 60})
print(ds)

rename_map = {}
if "latitude" in ds.coords:
    rename_map["latitude"] = "lat"
if "longitude" in ds.coords:
    rename_map["longitude"] = "lon"
ds = ds.rename(rename_map)

lat_vals = ds["lat"].values
lat_slice = slice(NORTH, SOUTH) if lat_vals[0] > lat_vals[-1] else slice(SOUTH, NORTH)
ds = ds.sel(lat=lat_slice, lon=slice(WEST, EAST))

# Aplicar el mask a los datos de chirps hacer solo de argentina
gdf = gpd.read_file(BASE_DIR / "data" / "json" / "ne_50m_admin_0_countries.json")
arg = gdf[gdf["ADMIN"] == "Argentina"].copy()
geom = arg.geometry.iloc[0].simplify(tolerance=0.01, preserve_topology=True)
regions = regionmask.Regions([geom])

mask = regions.mask(ds["lon"], ds["lat"])
ds = ds.where(mask == 0)

# Cambiar los nombres y unidades y tambien guardar para correr con el pipeline
ds = ds.rename({"precip": "precip_month"})
ds["precip_month"].attrs["units"] = "mm/month"
ds["precip_month"].attrs["long_name"] = "CHIRPS Total Monthly Precipitation"
ds = ds[["precip_month"]]

save_path = PROCESSED_DIR / "chirps_arg_monthly_clean.nc"
ds.to_netcdf(save_path)
print(f"Guardado: {save_path}")

ds["precip_month"].isel(time=0).plot()
plt.title("Spatial Coverage Check: CHIRPS Argentina Mask")
plt.savefig(BASE_DIR / "chirps_check.png", dpi=200, bbox_inches="tight")
plt.close()

print("\nDataset final:")
print(ds)
