"""Test Playwright-based scrapers and log results."""

import importlib.util
import sys
from pathlib import Path

# Add parent for log_utils and playwright scrapers dir for base_pw module.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "scrapers_playwright"))
from log_utils import log_site, show_progress

SCRAPERS_DIR = Path(__file__).parent / "scrapers_playwright"

SCRAPER_INFO_PW = {
    "scrape_echa_pw.py": (
        "European Chemicals Agency [ECHA]",
        "https://jobs.echa.europa.eu/psp/pshrrcr/EMPLOYEE/HRMS/c/HRS_HRAM.HRS_APP_SCHJOB.GBL?FOCUS=Applicant&languageCd=ENG",
    ),
    "scrape_council_pw.py": (
        "European Council [Council]",
        "https://www.consilium.europa.eu/en/general-secretariat/jobs/vacancies/",
    ),
    "scrape_eca_pw.py": (
        "European Court of Auditors [ECA]",
        "https://www.eca.europa.eu/en/job-opportunities#page-search---index---lang---en_US",
    ),
    "scrape_efca_pw.py": (
        "European Fisheries Control Agency [EFCA]",
        "https://www.efca.europa.eu/en/content/recruitment",
    ),
    "scrape_eib_pw.py": (
        "European Investment Bank [EIB]",
        "https://erecruitment.eib.org/psc/hr/EIBJOBS/CAREERS/c/HRS_HRAM_FL.HRS_CG_SEARCH_FL.GBL?Page=HRS_APP_SCHJOB_FL&Action=U&Focus=Applicant&SiteId=1",
    ),
    "scrape_esm_pw.py": (
        "European Stability Mechanism [ESM]",
        "https://vacancies.esm.europa.eu/#en/sites/CX",
    ),
    "scrape_euipo_pw.py": (
        "European Union Intellectual Property Office [EUIPO]",
        "https://career012.successfactors.eu/career?company=C0001250580P",
    ),
    "scrape_eurojust_pw.py": (
        "The European Union's Judicial Cooperation Unit [EUROJUST]",
        "https://eurojust.tal.net/vx/lang-en-GB/mobile-0/appcentre-ext/brand-4/xf-c3c2cdbdccf8/candidate/jobboard/vacancy/3/adv/",
    ),
    "scrape_epo_pw.py": (
        "European Patent Office [EPO]",
        "https://jobs.epo.org/search/?createNewAlert=false&q=&optionsFacetsDD_department=&optionsFacetsDD_customfield1=",
    ),
    "scrape_ico_pw.py": (
        "International Coffee Organization [ICO]",
        "https://ico.org/resources/vacancies/",
    ),
    "scrape_iooc_pw.py": (
        "International Olive Oil Council [IOOC]",
        "https://www.internationaloliveoil.org/contracts-grants-vacancies/vacancies/page/2/",
    ),
    "scrape_nib_pw.py": (
        "Nordic Investment Bank [NIB]",
        "https://www.nib.int/careers",
    ),
}


def load_scraper(filepath):
    spec = importlib.util.spec_from_file_location("scraper", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scraper(filename):
    filepath = SCRAPERS_DIR / filename
    if not filepath.exists():
        return None, f"File not found: {filepath}"

    name, url = SCRAPER_INFO_PW.get(filename, (filename, ""))

    try:
        module = load_scraper(filepath)
        jobs = module.scrape()

        if jobs:
            return jobs, None
        return [], "No jobs found (may be empty or scraper issue)"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def main():
    print("Testing Playwright scrapers...\n")

    for filename, (name, url) in SCRAPER_INFO_PW.items():
        print(f"Testing {name}...")
        jobs, error = test_scraper(filename)

        if error:
            log_site(name, url, "failed", notes=error)
        elif len(jobs) == 0:
            log_site(
                name,
                url,
                "partial",
                script_file=f"scrapers_playwright/{filename}",
                vacancies_found=0,
                notes="Scraper works but found 0 jobs",
            )
        else:
            log_site(
                name,
                url,
                "success",
                script_file=f"scrapers_playwright/{filename}",
                vacancies_found=len(jobs),
                notes=f"Found {len(jobs)} jobs",
            )

    show_progress()


if __name__ == "__main__":
    main()
