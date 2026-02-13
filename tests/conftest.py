from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Ensure project + scraper modules are importable in pytest.
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers"))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers_playwright"))
