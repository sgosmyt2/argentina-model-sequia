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
        with open(RAW_FILE, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192 * 16):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(
                        f"{downloaded / 1e9:.2f} / {total / 1e9:.2f} GB ({pct:.1f}%)",
                        end="",
                    )
    print("Descarga terminado")
else:
    print(f"Ya hay el archivo aquí: {RAW_FILE}, saltandose.")
