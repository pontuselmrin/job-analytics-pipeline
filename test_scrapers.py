"""Test all scrapers and log results"""
import sys
import importlib.util
from pathlib import Path

# Add parent to path for log_utils
sys.path.insert(0, str(Path(__file__).parent))
from log_utils import log_site, show_progress

SCRAPERS_DIR = Path(__file__).parent / "scrapers"

# Map scraper files to site info
SCRAPER_INFO = {
    # EU Agencies - HTML scraping
    "scrape_acer.py": ("Agency for the Cooperation of Energy Regulators [ACER]", "https://www.acer.europa.eu/the-agency/careers/vacancies"),
    "scrape_berec.py": ("Body of European Regulators for Electronic Communications [BEREC]", "https://www.berec.europa.eu/en/vacancies"),
    "scrape_cor.py": ("Committee of Regions [CR]", "https://cor.europa.eu/en/about/work-us/jobs"),
    "scrape_frontex.py": ("European Agency for the Management of Operational Cooperation at the External Borders [FRONTEX]", "https://www.frontex.europa.eu/careers/vacancies/open-vacancies/"),
    "scrape_euaa.py": ("European Asylum Support Office [EASO]", "https://euaa.europa.eu/careers/vacancies"),
    "scrape_cedefop.py": ("European Centre for the Development of Vocational Training [CEDEFOP]", "https://www.cedefop.europa.eu/en/about-cedefop/job-opportunities/vacancies"),
    "scrape_eda.py": ("European Defence Agency [EDA]", "https://eda.europa.eu/careers/current-vacancies"),
    "scrape_emsa.py": ("European Maritime Safety Agency [EMSA]", "https://www.emsa.europa.eu/jobs/vacancies.html"),
    "scrape_enisa.py": ("European Network and Information Security Agency [ENISA]", "https://www.enisa.europa.eu/careers"),
    "scrape_srb.py": ("Single Resolution Board [SRB]", "https://www.srb.europa.eu/en/vacancies"),
    "scrape_europol.py": ("European Police Office [EUROPOL]", "https://www.europol.europa.eu/careers-procurement/open-vacancies"),
    "scrape_ep.py": ("European Parliament [EP]", "https://apply4ep.gestmax.eu/search/index/lang/en_US"),
    # API-based scrapers
    "scrape_oecd.py": ("Organisation for Economic Co-operation and Development [OECD]", "https://careers.smartrecruiters.com/OECD"),
    # Taleo API scrapers
    "scrape_who.py": ("World Health Organization [WHO]", "https://careers.who.int/careersection/ex/jobsearch.ftl"),
    "scrape_fao.py": ("Food and Agricultural Organization [FAO]", "https://jobs.fao.org/careersection/fao_external/jobsearch.ftl"),
    "scrape_wipo.py": ("World Intellectual Property Organization [WIPO]", "https://wipo.taleo.net/careersection/wp_2_pd/jobsearch.ftl"),
    "scrape_iaea.py": ("International Atomic Energy Agency [IAEA]", "https://iaea.taleo.net/careersection/ex/jobsearch.ftl"),
    # More EU/International agencies
    "scrape_ecb.py": ("European Central Bank [ECB]", "https://talent.ecb.europa.eu/careers/SearchJobs"),
    "scrape_eea.py": ("European Environment Agency [EEA]", "https://jobs.eea.europa.eu/"),
    "scrape_era.py": ("European Railway Agency [ERA]", "https://www.era.europa.eu/agency-you/recruitment/vacancies"),
    "scrape_edps.py": ("European Data Protection Supervisor [EDPS]", "https://www.edps.europa.eu/about/office-edps/careers/our-vacancies_en"),
    "scrape_eiopa.py": ("European Insurance and Occupational Pensions Authority [EIOPA]", "https://eiopa.gestmax.eu/search"),
    "scrape_efsa.py": ("European Food Safety Authority [EFSA]", "https://careers.efsa.europa.eu/jobs/search"),
    "scrape_ecdc.py": ("European Centre for Disease Prevention and Control [ECDC]", "https://erecruitment.ecdc.europa.eu/?page=advertisement"),
    "scrape_fra.py": ("European Union Agency for Fundamental Rights [FRA]", "https://fra.gestmax.eu/search"),
    "scrape_eba.py": ("European Banking Authority [EBA]", "https://www.careers.eba.europa.eu/en"),
    "scrape_esma.py": ("European Securities and Markets Authority [ESMA]", "https://esmacareers.adequasys.com/?page=advertisement"),
    "scrape_iea.py": ("International Energy Agency [IEA]", "https://careers.smartrecruiters.com/OECD/iea"),
    "scrape_ceb.py": ("Council of Europe Development Bank [CEB]", "https://jobs.coebank.org/search"),
    "scrape_esa.py": ("European Space Agency [ESA]", "https://jobs.esa.int/search/"),
    "scrape_unesco.py": ("UNESCO", "https://careers.unesco.org/go/All-jobs-openings/784002/"),
    "scrape_wmo.py": ("World Meteorological Organization [WMO]", "https://erecruit.wmo.int/public/"),
    "scrape_easa.py": ("European Aviation Safety Agency [EASA]", "https://careers.easa.europa.eu/search/"),
    "scrape_eutelsat.py": ("EUTELSAT", "https://careers.eutelsat.com/search/"),
    "scrape_ebrd.py": ("European Bank for Reconstruction and Development [EBRD]", "https://jobs.ebrd.com/search/"),
    "scrape_eso.py": ("European Southern Observatory [ESO]", "https://recruitment.eso.org/"),
    "scrape_ema.py": ("European Medicines Agency [EMA]", "https://careers.ema.europa.eu/search/"),
    "scrape_ecmwf.py": ("European Centre for Medium-Range Weather Forecasts [ECMWF]", "https://jobs.ecmwf.int/Home/Job"),
    # Workday API scrapers
    "scrape_wto.py": ("World Trade Organization [WTO]", "https://wto.wd103.myworkdayjobs.com/External"),
    "scrape_embl.py": ("European Molecular Biology Laboratory [EMBL]", "https://embl.wd103.myworkdayjobs.com/EMBL"),
    "scrape_unhcr.py": ("UNHCR", "https://unhcr.wd3.myworkdayjobs.com/External"),
    "scrape_globalfund.py": ("The Global Fund", "https://theglobalfund.wd1.myworkdayjobs.com/External"),
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
