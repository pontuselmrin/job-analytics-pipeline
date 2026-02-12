import requests
from bs4 import BeautifulSoup
import time

BASE_URL = "https://eu-careers.europa.eu"
LIST_URL = f"{BASE_URL}/en/temporary-agents-other-institutions-vacancies"

headers = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}


def scrape_page(page_num):
    """Scrape a single page of job listings."""
    url = f"{LIST_URL}?page={page_num}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []

    table = soup.find("table")
    if not table:
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    rows = tbody.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 7:
            continue

        title_cell = cells[0]
        title_link = title_cell.find("a")
        if not title_link:
            continue

        job = {
            "title": title_link.get_text(strip=True),
            "url": BASE_URL + title_link.get("href") if title_link.get("href") else None,
            "domain": cells[1].get_text(strip=True),
            "grade": cells[2].get_text(strip=True),
            "institution": cells[3].get_text(strip=True),
            "location": cells[4].get_text(strip=True),
            "publication_date": cells[5].get_text(strip=True),
            "deadline": cells[6].get_text(strip=True),
        }
        jobs.append(job)

    return jobs


def scrape_all_jobs():
    """Scrape all pages of job listings."""
    all_jobs = []
    page = 0

    while True:
        print(f"Scraping page {page}...")
        jobs = scrape_page(page)

        if not jobs:
            print(f"No jobs found on page {page}, stopping.")
            break

        all_jobs.extend(jobs)
        print(f"  Found {len(jobs)} jobs (total: {len(all_jobs)})")

        page += 1
        time.sleep(0.5)

    return all_jobs


if __name__ == "__main__":
    jobs = scrape_all_jobs()

    print(f"\n{'='*60}")
    print(f"Total jobs found: {len(jobs)}")
    print(f"{'='*60}\n")

    for i, job in enumerate(jobs, 1):
        print(f"{i}. {job['title']}")
        print(f"   URL: {job['url']}")
        print(f"   Domain: {job['domain']}")
        print(f"   Grade: {job['grade']}")
        print(f"   Institution: {job['institution']}")
        print(f"   Location: {job['location']}")
        print(f"   Published: {job['publication_date']}")
        print(f"   Deadline: {job['deadline']}")
        print()
