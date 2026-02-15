"""Central registry of all scrapers and their org metadata.

Copy this file to scraper_registry.py and add your own scrapers.
Each entry maps scraper filename -> (org_full_name, listing_url).
"""

# Standard (requests/BeautifulSoup) scrapers
SCRAPER_INFO = {
    "scrape_example.py": (
        "Example Organisation [EXAMPLE]",
        "https://example.com/careers",
    ),
}

# Playwright-based scrapers
SCRAPER_INFO_PW = {
    "scrape_example_pw.py": (
        "Example Playwright Organisation [EXAMPLE-PW]",
        "https://example.com/careers",
    ),
}


def get_all_scrapers() -> dict:
    """Return combined registry with playwright flag as third tuple element."""
    combined = {}
    for filename, (name, url) in SCRAPER_INFO.items():
        combined[filename] = (name, url, False)
    for filename, (name, url) in SCRAPER_INFO_PW.items():
        combined[filename] = (name, url, True)
    return combined


def find_scraper_by_abbrev(abbrev: str) -> tuple[str, str, str, bool] | None:
    """Find a scraper by org abbreviation.

    Returns (filename, org_name, url, is_playwright) or None.
    """
    import re

    abbrev_upper = abbrev.upper()

    for filename, (name, url) in SCRAPER_INFO.items():
        match = re.search(r"\[([^\]]+)\]", name)
        if match and match.group(1).upper() == abbrev_upper:
            return filename, name, url, False

    for filename, (name, url) in SCRAPER_INFO_PW.items():
        match = re.search(r"\[([^\]]+)\]", name)
        if match and match.group(1).upper() == abbrev_upper:
            return filename, name, url, True

    # Also try matching org names without brackets
    for filename, (name, url) in SCRAPER_INFO.items():
        if name.upper() == abbrev_upper:
            return filename, name, url, False

    for filename, (name, url) in SCRAPER_INFO_PW.items():
        if name.upper() == abbrev_upper:
            return filename, name, url, True

    return None
