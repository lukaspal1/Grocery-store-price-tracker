# test_rohlik_playwright.py
import json
from playwright.sync_api import sync_playwright

SEARCH_URL = "https://www.rohlik.cz/services/frontend-service/search-metadata"
PARAMS = {
    "search": "mléko",
    "offset": 0,
    "limit": 30,
    "companyId": 1,
    "filterData": json.dumps({"filters": []}),
    "canCorrect": "true",
}
HEADERS = {
    "x-origin": "WEB",
    "x-ga-consent": "granted",
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(locale="cs-CZ")
    page = context.new_page()

    # Step 1: Visit the homepage to pass Cloudflare's challenge
    print("Loading rohlik.cz homepage...")
    page.goto("https://www.rohlik.cz", wait_until="domcontentloaded", timeout=60000)
    print("Homepage loaded. Waiting for network idle...")
    page.wait_for_load_state("networkidle", timeout=60000)
    print("Ready.")

    # Step 2: Call the search API from within the browser context
    print("\nCalling search API...")
    response = page.request.get(SEARCH_URL, params=PARAMS, headers=HEADERS)
    print(f"Status: {response.status}")

    if response.status == 200:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
    else:
        print(response.text()[:1000])

    browser.close()