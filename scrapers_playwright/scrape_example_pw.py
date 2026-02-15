"""Example Playwright scraper demonstrating common patterns.

This file shows how to use the utilities in base_pw.py for browser-based scraping.
Replace example.com with your target website and adapt the patterns.
"""

from base_pw import (
    extract_from_main_page,
    extract_from_frames,
    run_scraper,
    collect_anchor_jobs_from_html,
)


# Example 1: Simple page scraping
def scrape_simple_example():
    """Extract job links from a simple HTML page."""
    url = "https://example.com/careers"
    base_url = "https://example.com"

    def _extract(page, context):
        # Extract jobs from the main page content
        jobs = extract_from_main_page(
            page,
            base_url=base_url,
            include_patterns=["job", "career", "position", "vacancy"],
            exclude_patterns=["archive", "closed", "expired"],
        )
        return jobs

    # Run with Playwright
    # wait_selectors: CSS selectors to wait for before extracting
    return run_scraper(
        url,
        _extract,
        wait_selectors=["a[href*='job']", "main", ".careers"],
        timeout_ms=45000,
    )


# Example 2: Scraping from iframes
def scrape_iframe_example():
    """Extract job links from pages with iframes."""
    url = "https://example.com/careers"
    base_url = "https://example.com"

    def _extract(page, context):
        # Extract jobs from iframes matching certain patterns
        jobs = extract_from_frames(
            page,
            include_frame_patterns=["talentreef", "jobboard", "careers"],
            base_url=base_url,
            include_patterns=["job", "position"],
            exclude_patterns=["login", "apply"],
        )
        return jobs

    return run_scraper(url, _extract, wait_selectors=["iframe"])


# Example 3: Custom extraction with page interaction
def scrape_interactive_example():
    """Extract jobs with custom page interactions."""
    url = "https://example.com/careers"
    base_url = "https://example.com"

    def _extract(page, context):
        # Wait for dynamic content to load
        try:
            page.wait_for_selector(".job-listing", timeout=5000)
        except Exception:
            pass

        # Optionally interact with the page
        # page.click("button.load-more")
        # page.wait_for_timeout(1000)

        # Get the page HTML and extract jobs manually
        html = page.content()
        jobs = collect_anchor_jobs_from_html(
            html,
            base_url=base_url,
            include_patterns=["job", "career"],
            exclude_patterns=["privacy", "terms"],
            min_title_len=5,
        )

        return jobs

    return run_scraper(
        url,
        _extract,
        wait_selectors=[".job-listing", "main"],
        allow_headful_fallback=True,  # Try headful browser if headless fails
    )


# Main scrape function
def scrape():
    """Main entry point for the Playwright scraper.

    Choose one of the example methods above based on your needs:
    - scrape_simple_example() for standard pages
    - scrape_iframe_example() for iframe-based sites
    - scrape_interactive_example() for custom interactions
    """
    # For this example, we'll use the simple method
    return scrape_simple_example()


if __name__ == "__main__":
    # Test the scraper when run directly
    try:
        jobs = scrape()
        print(f"Found {len(jobs)} job listings:\\n")
        for job in jobs[:5]:  # Show first 5
            print(f"- {job.get('title', 'No title')}")
            print(f"  URL: {job.get('url', 'No URL')}")
            print()
    except Exception as e:
        print(f"Error: {e}")
        print("This is an example scraper - replace example.com with a real target.")
