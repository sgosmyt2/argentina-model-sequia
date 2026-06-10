# Usar este solo verificar que el dataset de imerg esta bien, debería dar una mapa buena y informacion bien

import xarray as xr
import matplotlib.pyplot as plt

ds = xr.open_dataset("data/processed/imerg_argentina.nc")
print(ds)

# Check time range
print("\nFirst date:", ds.time.values[0])
print("Last date:", ds.time.values[-1])
print("Total timesteps:", len(ds.time))

# Check no data outside Argentina (should be all NaN outside)
print("\nMin precipitation:", float(ds.precipitation.isel(time=100).min()))
print("Max precipitation:", float(ds.precipitation.isel(time=100).max()))

# Plot a single day
ds["precipitation"].isel(time=100).plot(x="lon", y="lat")
plt.savefig("imerg_test.png", dpi=200, bbox_inches="tight")
plt.close()
print("\nPlot saved to imerg_test.png")
