import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Add project + scrapers dir for imports.
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers"))
from log_utils import log_site, show_progress
from scraper_registry import SCRAPER_INFO

SCRAPERS_DIR = PROJECT_ROOT / "scrapers"


def load_scraper(filepath):
    spec = importlib.util.spec_from_file_location("scraper", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scraper(filename):
    filepath = SCRAPERS_DIR / filename
    if not filepath.exists():
        return None, f"File not found: {filepath}"

    name, url = SCRAPER_INFO.get(filename, (filename, ""))

    try:
        module = load_scraper(filepath)
        jobs = module.scrape()

        if jobs:
            return jobs, None
        else:
            return [], "No jobs found (may be empty or scraper issue)"
    except Exception as e:
        return None, str(e)


def main():
    print("Testing all scrapers...\n")

    for filename, (name, url) in SCRAPER_INFO.items():
        print(f"Testing {name}...")
        jobs, error = test_scraper(filename)

        if error:
            log_site(name, url, "failed", notes=error)
        elif len(jobs) == 0:
            log_site(name, url, "partial", script_file=f"scrapers/{filename}",
                     vacancies_found=0, notes="Scraper works but found 0 jobs")
        else:
            log_site(name, url, "success", script_file=f"scrapers/{filename}",
                     vacancies_found=len(jobs), notes=f"Found {len(jobs)} jobs")

    show_progress()


if __name__ == "__main__":
    main()
