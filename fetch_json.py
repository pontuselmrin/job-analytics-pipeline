import requests

url = "https://webtools.europa.eu/rest/service-inventory"

headers = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.amla.europa.eu",
    "referer": "https://www.amla.europa.eu/",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}

data = {
    "url": "https://www.amla.europa.eu/careers/vacancies_en",
    "lang": "en",
    "components": '[{"service":"preview","version":null,"provider":null,"id":null,"url":null,"maptype":null},{"service":"etrans","version":null,"provider":null,"id":null,"url":null,"maptype":null}]',
}

response = requests.post(url, headers=headers, data=data)

if response.ok:
    print(response.json())
else:
    print(f"Error: {response.status_code}")
    print(response.text)
