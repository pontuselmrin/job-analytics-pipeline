"""Configuration template for scrapers.

Copy this file to config.py and fill in your own values.
The config.py file should not be committed to version control.
"""

# HTTP headers for standard requests
DEFAULT_HEADERS = {
    "user-agent": "Mozilla/5.0 (Your OS) Browser/Version",
}

# Headers for JSON API requests
API_JSON_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Your OS) Browser/Version",
}

# Headers for advanced API requests with extended options
API_EXTENDED_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Your OS) Browser/Version",
    "X-Requested-With": "XMLHttpRequest",
    "tz": "GMT+01:00",
    "tzname": "Europe/Berlin",
}

# User agent for Playwright-based browser automation
USER_AGENT = "Mozilla/5.0 (Your OS) Browser/Version"

# Patterns that indicate a page is blocked or showing a CAPTCHA
BLOCK_MARKERS = (
    "attention required",
    "verify you are human",
    "access denied",
    "request blocked",
)
