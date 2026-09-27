from pathlib import Path

from ndvi_algoritmo import calculate_sepa_persistence, make_mock_stack

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SINGLE_FILE = PROJECT_ROOT / "data" / "raw" / "sc-2026241.tif"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "persistence_test_output/nc"
