import earthaccess
import xarray as xr
from pathlib import Path
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import glob
import geopandas as gpd
import regionmask

# Límites geográficos del conosur
NORTH = -10
SOUTH = -60
WEST = -85
EAST = -30

# Tengo que cambiar las coordenadas para funcionar con earthaccess
LON_START = int((WEST + 180) / 0.1)
LON_END = int((EAST + 180) / 0.1)
LAT_START = int((SOUTH + 90) / 0.1)
LAT_END = int((NORTH + 90) / 0.1)

OUT_DIR = Path("data/raw/imerg")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Número de descargas/procesos simultaneos (16 probablemente es el mas NASA puede usar pero quizas mas mejorar la velocidad de descargar)
WORKERS = 16

# Autenticación mediante credenciales guardadas en .netrc (tienes que hacer una cuenta y poner tu usuario y contraseña en un archivo se llama .ntrc)
earthaccess.login(strategy="netrc")

# Búsqueda de datos IMERG dentro del rango temporal y espacial definido
results = earthaccess.search_data(
    short_name="GPM_3IMERGDF",
    version="07",
    temporal=("2000-1-1", "2024-12-31"),
    bounding_box=(WEST, SOUTH, EAST, NORTH),
)

print(f"Found {len(results)} granules")

pending = []
for granule in results:
    granule_name = granule["umm"]["GranuleUR"]

    # Obtener la fecha (AAAAMMDD) a partir del nombre del gránulo
    match = re.search(r"\.(\d{8})-S", granule_name)

    # Si no aparece en el nombre, intentar extraerla del enlace de descarga
    if not match:
        for link in granule.data_links():
            match = re.search(r"\.(\d{8})-S", link)
            if match:
                break

    # Evitar reprocesar archivos que ya existen
    if match and not (OUT_DIR / f"IMERG_SC_{match.group(1)}.nc4").exists():
        pending.append(granule)

print(
    f"Skipping {len(results) - len(pending)} already done, processing {len(pending)} remaining"
)


def process_granule(granule):
    """
    Descarga un gránulo IMERG, recorta la región de estudio
    y guarda el resultado en formato NetCDF.
    """
    granule_name = granule["umm"]["GranuleUR"]
    match = re.search(r"\.(\d{8})-S", granule_name)
    if not match:
        for link in granule.data_links():
            match = re.search(r"\.(\d{8})-S", link)
            if match:
                break
    ymd = match.group(1)
    out_file = OUT_DIR / f"IMERG_SC_{ymd}.nc4"

    tmp_dir = Path(f"data/tmp/{ymd}")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Crear archivos temporales por los workers
        tmp_files = earthaccess.download(granule, tmp_dir)
        tmp_file = Path(tmp_files[0])

        ds = xr.open_dataset(tmp_file)

        # Recortar el dataset al área de estudio
        ds_sub = ds.sel(lon=slice(WEST, EAST), lat=slice(SOUTH, NORTH))
        ds_sub.to_netcdf(out_file)
        ds.close()
        tmp_file.unlink()
        tmp_dir.rmdir()
        return f"{out_file.name}"
    except Exception as e:

        if tmp_dir.exists():
            for f in tmp_dir.iterdir():
                f.unlink()
            tmp_dir.rmdir()
        return f"{ymd}: {e}"


# Procesar varios gránulos en paralelo para acelerar la descarga
with ThreadPoolExecutor(max_workers=WORKERS) as executor:
    futures = {executor.submit(process_granule, g): g for g in pending}
    for future in as_completed(futures):
        print(future.result())

files = sorted(glob.glob(str(OUT_DIR / "*.nc4")))

# Prueba ver si time esta roto, parece que en el descarga (al menos para mi) puede pasar donde un par de archivos no tienen coordenados del tiempo
for f in files:
    try:
        ds = xr.open_dataset(f)
        if "time" not in ds.coords:
            print(f"Missing time coord: {f}")
        ds.close()
    except Exception as e:
        print(f"Error {f}: {e}")

ds_imerg_sc = xr.open_mfdataset(
    files,
    combine="nested",
    concat_dim="time",
    chunks={"time": 365},
)
