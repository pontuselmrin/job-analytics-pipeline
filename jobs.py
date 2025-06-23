import yaml, json, scrapy
from scrapy.http import FormRequest, Request

class ConfigDrivenSpider(scrapy.Spider):
    name = "jobs"
    custom_settings = { "AUTOTHROTTLE_ENABLED": True }

    def start_requests(self):
        with open('sites/config.yaml') as f:
            self.sites = yaml.safe_load(f)
        for site in self.sites:
            yield Request(site['landing'], callback=self.parse_landing, meta={'site':site})

    def parse_landing(self, response):
        site = response.meta['site']
        t = site['type']

        if t == 'static':
            yield from self.parse_list(response)

        elif t == 'ajax':
            ajax_path = response.xpath(site['ajax_path_xpath']).get()
            yield FormRequest(
                response.urljoin(ajax_path),
                formdata={},
                callback=self.parse_list,
                meta=response.meta
            )

        elif t == 'graphql':
            yield Request(
                site['graphql_endpoint'],
                method='POST',
                body=json.dumps({'query': site['graphql_query']}),
                headers={'Content-Type':'application/json'},
                callback=self.parse_graphql,
                meta=response.meta
            )

        elif t == 'splash':
            yield Request(
                site['splash_endpoint'],
                method='GET',
                cb_kwargs={'args': site['splash_args']},
                callback=self.parse_splash,
                meta=response.meta
            )

        else:
            self.logger.error(f"Unknown type {t} for {site['name']}")

    def parse_list(self, response):
        site = response.meta['site']
        for card in response.xpath(site['list_xpath']):
            href = card.xpath(site['detail_link']).get()
            yield response.follow(href, self.parse_detail, meta=response.meta)

    def parse_graphql(self, response):
        site = response.meta['site']
        data = json.loads(response.text)
        for job in jsonpath_ng.parse(site['json_path']).find(data):
            yield scrapy.Request(job.value['url'], callback=self.parse_detail, meta=response.meta)

    def parse_splash(self, response, args):
        # Splash returns fully rendered HTML
        return self.parse_list(response)

    def parse_detail(self, response):
        # same for all sites:
        item = {}
        item['source'] = response.meta['site']['name']
        item['url']    = response.url
        item['title']  = response.xpath('//h1/text()').get().strip()
        # … etc …
        yield item
