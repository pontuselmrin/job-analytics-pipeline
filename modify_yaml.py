import yaml

# 1) Load your typed config
with open('config_with_types.yaml', 'r', encoding='utf-8') as f:
    sites = yaml.safe_load(f)

# 2) Fill in defaults based on type
for site in sites:
    t = site.get('type')
    if t == 'ajax':
        site.setdefault('ajax_path_xpath',
            '//input[@id="requestUrl"]/@data-request-url'
        )
        site.setdefault('list_xpath',
            '//div[contains(@class,"job-card")]'
        )
        site.setdefault('detail_link',
            './/a[starts-with(@data-testid,"a-job-detail")]/@href'
        )

    elif t == 'static':
        site.setdefault('list_xpath',
            '//div[contains(@class,"job-card")]'
        )
        site.setdefault('detail_link',
            './/a[starts-with(@data-testid,"a-job-detail")]/@href'
        )

    elif t == 'api':
        # you’ll likely need to tweak these per‐site
        site.setdefault('api_endpoint',   '/api/jobs')
        site.setdefault('json_path',      '$.data.jobs[*]')
        site.setdefault('detail_url_key', 'url')

    elif t == 'js':
        # leave blank or point at your splash/playwright handler
        site.setdefault('render_with', 'splash')  # or 'playwright'
        site.setdefault('list_xpath',   '//div[contains(@class,"job-card")]')
        site.setdefault('detail_link',  './/a/@href')

    else:
        site.setdefault('list_xpath',   '//div[contains(@class,"job-card")]')
        site.setdefault('detail_link',  './/a/@href')

# 3) Write out the “fully-populated” config
with open('config_enriched.yaml', 'w', encoding='utf-8') as f:
    yaml.safe_dump(sites, f, sort_keys=False)

print(f"Enriched {len(sites)} sites → sites/config_enriched.yaml")
