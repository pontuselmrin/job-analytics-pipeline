"""Example scraper demonstrating common patterns.

This file shows how to use the utilities in base.py for scraping job listings.
Replace example.com with your target website and adapt the selectors/patterns.
"""

from bs4 import BeautifulSoup
from base import fetch, extract_links, scrape_api_json_paginated, DEFAULT_HEADERS


# Example 1: Simple HTML scraping with link extraction
def scrape_html_example():
    """Extract job links from HTML pages using BeautifulSoup."""
    url = "https://example.com/careers"
    resp = fetch(url, headers=DEFAULT_HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Use the extract_links helper to find job postings
    # Adjust href_pattern to match your target site's URL structure
    jobs = extract_links(
        soup,
        href_pattern="/jobs/",  # Links containing "/jobs/"
        base_url="https://example.com",
        min_title_len=5,
        exclude_patterns=["archive", "closed"],
    )

    return jobs


# Example 2: API scraping with pagination
def scrape_api_example():
    """Scrape from a paginated JSON API."""
    jobs = []
    page = 1
    per_page = 20

    while True:
        url = f"https://api.example.com/v1/jobs?page={page}&per_page={per_page}"
        resp = fetch(url, headers=DEFAULT_HEADERS)
        data = resp.json()

        # Adjust based on your API's response structure
        postings = data.get("results", [])
        if not postings:
            break

        for job in postings:
            jobs.append(
                {
                    "title": job.get("title", ""),
                    "url": f"https://example.com/jobs/{job.get('id', '')}",
                    "location": job.get("location", ""),
                    "department": job.get("department", ""),
                }
            )

        # Stop if we've reached the last page
        if len(postings) < per_page:
            break
        page += 1

    return jobs


# Example 3: Using the generic API helper for certain platforms
def scrape_using_helper():
    """Use scrape_api_json_paginated for compatible APIs."""
    base_url = "https://careers.example.com"
    api_url = f"{base_url}/api/jobs"

    # This helper works with APIs that use a standard pagination format
    return scrape_api_json_paginated(base_url, api_url)


# Main scrape function - choose the appropriate method for your use case
def scrape():
    """Main entry point for the scraper.

    Choose one of the example methods above based on your target site:
    - scrape_html_example() for HTML pages
    - scrape_api_example() for JSON APIs
    - scrape_using_helper() for compatible API platforms
    """
    # For this example, we'll use the HTML method
    return scrape_html_example()


if __name__ == "__main__":
    # Test the scraper when run directly
    try:
        jobs = scrape()
        print(f"Found {len(jobs)} job listings:\n")
        for job in jobs[:5]:  # Show first 5
            print(f"- {job.get('title', 'No title')}")
            print(f"  URL: {job.get('url', 'No URL')}")
            if job.get("location"):
                print(f"  Location: {job['location']}")
            print()
    except Exception as e:
        print(f"Error: {e}")
        print("This is an example scraper - replace example.com with a real target.")
