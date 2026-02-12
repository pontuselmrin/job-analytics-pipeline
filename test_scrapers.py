"""Test all scrapers and log results"""
import sys
import importlib.util
from pathlib import Path

# Add parent to path for log_utils, and scrapers dir for base module
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "scrapers"))
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
    "scrape_ombudsman.py": ("European Ombudsman [Ombudsman]", "https://www.ombudsman.europa.eu/en/office/careers"),
    "scrape_srb.py": ("Single Resolution Board [SRB]", "https://www.srb.europa.eu/en/vacancies"),
    "scrape_europol.py": ("European Police Office [EUROPOL]", "https://www.europol.europa.eu/careers-procurement/open-vacancies"),
    "scrape_ep.py": ("European Parliament [EP]", "https://apply4ep.gestmax.eu/search/index/lang/en_US"),
    "scrape_cpvo.py": ("Community Plant Variety Office [CPVO]", "https://cpvo.europa.eu/en/about-us/recruitment#page-search---index"),
    "scrape_eu_osha.py": ("European Agency for Safety and Health at Work [EU-OSHA]", "https://osha.europa.eu/en/careers"),
    "scrape_eeas.py": ("European External Action Service [EEAS]", "https://www.eeas.europa.eu/eeas/vacancies_en?f%5B0%5D=vacancy_site%3AEEAS"),
    "scrape_eurofound.py": ("European Foundation for the Improvement of Living and Working Conditions [EUROFOUND]", "https://www.eurofound.europa.eu/en/vacancies"),
    "scrape_euspa.py": ("European GNSS Agency [GSA]", "https://www.euspa.europa.eu/opportunities/careers"),
    "scrape_eige.py": ("European Institute for Gender Equality [EIGE]", "https://eige.europa.eu/about/recruitment"),
    "scrape_eit.py": ("European Institute of Innovation and Technology [EIT]", "https://www.eit.europa.eu/work-with-us/careers/vacancies/open"),
    "scrape_etf.py": ("European Training Foundation [ETF]", "https://www.etf.europa.eu/en/about/recruitment"),
    "scrape_cepol.py": ("European Police College [CEPOL]", "https://www.cepol.europa.eu/work-us/careers/vacancies"),
    "scrape_efta.py": ("European Free Trade Association [EFTA]", "https://www.efta.int/careers/open-vacancies"),
    "scrape_ices.py": ("International Council for the Exploration of the Sea [ICES]", "https://www.ices.dk/about-ICES/Jobs-in-ICES/Pages/default.aspx"),
    "scrape_cern.py": ("European Organization for Nuclear Research [CERN]", "https://careers.cern/"),
    "scrape_wcc.py": ("World Council of Churches [WCC]", "https://wcccoe.hire.trakstar.com/?#content"),
    "scrape_f4e.py": ("Fusion for Energy [F4E]", "https://fusionforenergy.europa.eu/vacancies/"),
    "scrape_euiss.py": ("European Union Institute for Security Studies [EUISS]", "https://www.iss.europa.eu/opportunities"),
    "scrape_bis.py": ("Bank for International Settlements [BIS]", "https://www.bis.org/careers/vacancies.htm"),
    "scrape_eumetsat.py": ("European Organisation for the Exploitation of Meteorological Satellites [EUMETSAT]", "https://eumetsat.onlyfy.jobs/"),
    "scrape_ndf.py": ("Nordic Development Fund [NDF]", "https://www.ndf.int/contact-us/jobs.html"),
    "scrape_unfccc.py": ("United Nations Framework Convention for Climate Change [UNFCCC]", "https://unfccc.int/secretariat/employment/recruitment"),
    "scrape_satcen.py": ("European Union Satellite Centre [SATCEN]", "https://www.satcen.europa.eu/recruitment/jobs"),
    "scrape_nato.py": ("North Atlantic Treaty Organisation [NATO]", "https://www.nato.int/en/work-with-us/careers/vacancies"),
    "scrape_coe.py": ("Council of Europe [CE]", "https://talents.coe.int/en_GB/careersmarketplace"),
    "scrape_eulisa.py": ("European Agency for the operational management of large-scale IT systems in the area of freedom, security and justice [EU-LISA]", "https://erecruitment.eulisa.europa.eu/en"),
    "scrape_efsf.py": ("European Financial Stability Facility [EFSF]", "https://www.esm.europa.eu/careers/vacancies"),
    "scrape_ec.py": ("European Commission [EC]", "https://eu-careers.europa.eu/en/job-opportunities/open-vacancies/ec_vacancies"),
    "scrape_euratom.py": ("European Atomic Energy Community [Euratom]", "https://eu-careers.europa.eu/en/job-opportunities/open-for-application"),
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
    "scrape_euda.py": ("European Union Drugs Agency [EUDA]", "https://www.euda.europa.eu/about/jobs_en#open-vacancies"),
    "scrape_fra.py": ("European Union Agency for Fundamental Rights [FRA]", "https://fra.gestmax.eu/search"),
    "scrape_eba.py": ("European Banking Authority [EBA]", "https://www.careers.eba.europa.eu/en"),
    "scrape_esma.py": ("European Securities and Markets Authority [ESMA]", "https://esmacareers.adequasys.com/?page=advertisement"),
    "scrape_iea.py": ("International Energy Agency [IEA]", "https://careers.smartrecruiters.com/OECD/iea"),
    "scrape_ceb.py": ("Council of Europe Development Bank [CEB]", "https://jobs.coebank.org/search"),
    "scrape_esa.py": ("European Space Agency [ESA]", "https://jobs.esa.int/search/"),
    "scrape_unesco.py": ("UNESCO", "https://careers.unesco.org/go/All-jobs-openings/784002/"),
    "scrape_unwto.py": ("World Tourism Organization [UNWTO]", "https://www.untourism.int/work-with-us"),
    "scrape_imo.py": ("International Maritime Organization [IMO]", "https://recruit.imo.org/vacancies"),
    "scrape_wmo.py": ("World Meteorological Organization [WMO]", "https://erecruit.wmo.int/public/"),
    "scrape_easa.py": ("European Aviation Safety Agency [EASA]", "https://careers.easa.europa.eu/search/"),
    "scrape_eutelsat.py": ("EUTELSAT", "https://careers.eutelsat.com/search/"),
    "scrape_ebrd.py": ("European Bank for Reconstruction and Development [EBRD]", "https://jobs.ebrd.com/search/"),
    "scrape_ebu.py": ("European Broadcasting Union [EBU]", "https://www.ebu.ch/careers"),
    "scrape_eso.py": ("European Southern Observatory [ESO]", "https://recruitment.eso.org/"),
    "scrape_ema.py": ("European Medicines Agency [EMA]", "https://careers.ema.europa.eu/search/"),
    "scrape_ecmwf.py": ("European Centre for Medium-Range Weather Forecasts [ECMWF]", "https://jobs.ecmwf.int/Home/Job"),
    "scrape_eurocontrol.py": ("European Organisation for the Safety of Air Navigation [EUROCONTROL]", "https://jobs.eurocontrol.int/eurocontrol-vacancies/"),
    # Workday API scrapers
    "scrape_wto.py": ("World Trade Organization [WTO]", "https://wto.wd103.myworkdayjobs.com/External"),
    "scrape_embl.py": ("European Molecular Biology Laboratory [EMBL]", "https://embl.wd103.myworkdayjobs.com/EMBL"),
    "scrape_unhcr.py": ("UNHCR", "https://unhcr.wd3.myworkdayjobs.com/External"),
    "scrape_globalfund.py": ("The Global Fund", "https://theglobalfund.wd1.myworkdayjobs.com/External"),
    # EU institution scrapers
    "scrape_eu_careers.py": ("EU Careers", "https://eu-careers.europa.eu/en/non-permanent-contract-ec"),
    "scrape_vacancies.py": ("Anti-Money Laundering Authority [AMLA]", "https://www.amla.europa.eu/careers/vacancies_en"),
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
