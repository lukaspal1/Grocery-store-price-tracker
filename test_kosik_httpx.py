# test_kosik_httpx.py
import httpx

url = "https://www.kosik.cz/api/front/page/products/flexible"
params = {
    "vendor": 1,
    "slug": "vyhledavani",
    "limit": 30,
    "search_term": "mléko",
    "platform": "web",
}
headers = {
    "User-Agent": "PortfolioPriceTracker/1.0 (+https://github.com/lukaspal1)",
    "Accept": "*/*",
    "Referer": "https://www.kosik.cz/",
}

r = httpx.get(url, params=params, headers=headers, timeout=20)
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}")
if r.status_code == 200:
    data = r.json()
    items = data.get("products", {}).get("items", [])
    print(f"Got {len(items)} products, total available: {data.get('products', {}).get('totalCount')}")
    if items:
        p = items[0]
        print(f"First: {p['name']} | {p['price']} Kč | {p['pricePerUnit']['price']} Kč/{p['pricePerUnit']['unit']}")
else:
    print(r.text[:500])