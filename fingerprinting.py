import pandas as pd
import yaml
import requests
from lxml import html

def detect_type(url):
    try:
        r = requests.get(url, timeout=10)
        doc = html.fromstring(r.text)
    except Exception:
        return 'error'
    if doc.xpath('//div[contains(@class,"job-card")]'):
        return 'static'
    if doc.xpath('//input[@id="requestUrl"]/@data-request-url'):
        return 'ajax'
    scripts = "\n".join(doc.xpath('//script/text()')).lower()
    if 'graphql' in scripts or '/api/' in scripts:
        return 'api'
    return 'js'

# 1) Read your CSV into a DataFrame
df = pd.read_csv('sites.csv')  

# 3) Fingerprint each site
df['type'] = df['url'].apply(detect_type)

# 4) Build the config dicts and dump to YAML
configs = df.rename(columns={'url':'landing'})[['name','landing','type']].to_dict(orient='records')

with open('config_with_types.yaml','w') as f:
    yaml.safe_dump(configs, f, sort_keys=False)

print(f"Processed {len(df)} sites → sites/config_with_types.yaml")
