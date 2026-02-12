# Scraping Project Progress

## Summary
Building scrapers for ~88 job vacancy sites from `sites.csv`.


## Files Structure
```
/scrapers/           - 42 scraper scripts (each has scrape() function)
/test_scrapers.py    - Test runner for all scrapers
/scrape_log.json     - Results log (auto-updated by test runner)
/log_utils.py        - Logging utilities (log_site, show_progress)
/sites.csv           - Source list of ~88 sites
/venv/               - Python virtual environment
/PROGRESS.md         - This file
```


## API Patterns Reference

### Taleo
```
POST https://{domain}/careersection/rest/jobboard/searchjobs
Headers:
  tz: GMT+01:00
  tzname: Europe/Berlin
  Content-Type: application/json
Body: {"multilineEnabled":true,"sortingSelection":{"sortBySelectionParam":"3","ascendingSortingOrder":"false"},"fieldData":{"fields":{"KEYWORD":"","LOCATION":""},"valid":true},"filterSelectionParam":{"searchFilterSelections":[{"id":"POSTING_DATE","selectedValues":[]},{"id":"LOCATION","selectedValues":[]},{"id":"JOB_FIELD","selectedValues":[]}]},"pageNo":1}
```

### Workday
```
POST https://{company}.wd{N}.myworkdayjobs.com/wday/cxs/{company}/{site}/jobs
Headers:
  Content-Type: application/json
  Accept: application/json
Body: {"appliedFacets":{},"limit":20,"offset":0,"searchText":""}
```

### SmartRecruiters
```
GET https://api.smartrecruiters.com/v1/companies/{COMPANY}/postings?offset=0&limit=100
```

### ECMWF-style
```
GET /Home/_JobCard?Skip=0
Headers:
  X-Requested-With: XMLHttpRequest
```
