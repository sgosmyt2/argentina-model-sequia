"""
era5_pipeline.py

Script controlador: ejecuta el proceso completo de corrección de sesgo para ERA5 (precip_month mediante corrección de razón, t2m mediante corrección delta).
Toda la lógica real reside en core.py / config.py este archivo solo la activa para el era5.

Usar:
    python era5_pipeline.py
"""

from core import run_pipeline

if __name__ == "__main__":
    run_pipeline("era5")
