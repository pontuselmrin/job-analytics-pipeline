"""Constants for the enrichment module."""

from pathlib import Path

from .org_config import (
    PLAYWRIGHT_ORGS,
    PLAYWRIGHT_DOMAINS,
    NEXTJS_PLATFORMS,
    PLATFORM_A_DOMAINS,
    API_BASED_V1_DOMAINS,
    API_BASED_V2_DOMAINS,
    TABLE_INTERFACE_DOMAINS,
    PREFER_EMBEDDED_PDF_ORGS,
    SSL_INSECURE_DOMAINS,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Base directory for run reports
RUNS_DIR = PROJECT_ROOT / "ops" / "runs"

# Flat output directory for per-org enrichment state
OUTPUT_DIR = RUNS_DIR / "output"


def get_run_dir(run_id: str) -> Path:
    """Get the directory for a specific run."""
    return RUNS_DIR / run_id


def get_logs_path(run_id: str) -> Path:
    """Get the logs file path for a specific run."""
    run_dir = get_run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / "logs.ndjson"


def get_pdf_dir(run_id: str) -> Path:
    """Get the PDF directory for a specific run."""
    return get_run_dir(run_id) / "pdfs"


def get_profile_dir(run_id: str) -> Path:
    """Get the profile directory for a specific run."""
    return get_run_dir(run_id) / "profiles"


# Rate limiting
REQUEST_DELAY = 1.5  # seconds between requests within same org

# Timeouts
REQUEST_TIMEOUT = 30  # seconds for HTTP requests
PLAYWRIGHT_TIMEOUT = 45000  # milliseconds

# Content limits
MAX_DESCRIPTION_CHARS = 50_000

# Re-export for convenience
__all__ = [
    "PROJECT_ROOT",
    "RUNS_DIR",
    "OUTPUT_DIR",
    "get_run_dir",
    "get_logs_path",
    "get_pdf_dir",
    "get_profile_dir",
    "REQUEST_DELAY",
    "REQUEST_TIMEOUT",
    "PLAYWRIGHT_TIMEOUT",
    "MAX_DESCRIPTION_CHARS",
    "PLAYWRIGHT_ORGS",
    "PLAYWRIGHT_DOMAINS",
    "NEXTJS_PLATFORMS",
    "PLATFORM_A_DOMAINS",
    "API_BASED_V1_DOMAINS",
    "API_BASED_V2_DOMAINS",
    "TABLE_INTERFACE_DOMAINS",
    "PREFER_EMBEDDED_PDF_ORGS",
    "SSL_INSECURE_DOMAINS",
]
