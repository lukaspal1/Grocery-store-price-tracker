# scrapers/rohlik.py
import json
import time
import logging
from playwright.sync_api import sync_playwright
from scrapers.base import CompliantScraper

log = logging.getLogger(__name__)


class RohlikScraper(CompliantScraper):
    SEARCH_URL = "https://www.rohlik.cz/services/frontend-service/search-metadata"

    def __init__(self):
        super().__init__("https://www.rohlik.cz")
        self._playwright = None
        self._browser = None
        self._page = None

    def _start_browser(self):
        if self._page is not None:
            return
        log.info("Rohlík: starting Playwright browser")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        context = self._browser.new_context(locale="cs-CZ")
        self._page = context.new_page()
        log.info("Rohlík: loading homepage to pass Cloudflare")
        self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
        self._page.wait_for_load_state("networkidle", timeout=60000)
        log.info("Rohlík: browser ready")

    def _search(self, query, limit=30):
        self._start_browser()
        if not self.can_fetch(self.SEARCH_URL):
            return []
        time.sleep(self.DELAY_SECONDS)

        params = {
            "search": query,
            "offset": 0,
            "limit": limit,
            "companyId": 1,
            "filterData": json.dumps({"filters": []}),
            "canCorrect": "true",
        }
        headers = {"x-origin": "WEB", "x-ga-consent": "granted"}

        try:
            r = self._page.request.get(self.SEARCH_URL, params=params, headers=headers)
            if r.status != 200:
                log.error(f"Rohlík: status {r.status} for '{query}'")
                return []
            payload = r.json()
        except Exception as e:
            log.error(f"Rohlík: search failed for '{query}': {e}")
            return []

        products = payload.get("data", {}).get("productList", [])
        return [self._normalize(p) for p in products]

    def _normalize(self, product):
        shelf_price = product.get("price", {}).get("full")
        shelf_unit_price = product.get("pricePerUnit", {}).get("full")

        # Find a real public promotion (not a first-order welcome offer)
        sale = None
        for s in product.get("sales", []):
            if not s.get("welcomePrice", False) and s.get("discountPercentage", 0) > 0:
                sale = s
                break

        if sale:
            # What the customer actually pays during the promotion
            price = sale.get("price", {}).get("full")
            unit_price = sale.get("priceForUnit", {}).get("full", shelf_unit_price)
            original_price = sale.get("originalPrice", {}).get("full", shelf_price)
            discount_pct = sale.get("discountPercentage", 0)
            is_on_sale = True
            promo_ends = sale.get("endsAt")
        else:
            price = shelf_price
            unit_price = shelf_unit_price
            original_price = None
            discount_pct = 0
            is_on_sale = False
            promo_ends = None

        base_link = product.get("baseLink", "")
        product_url = f"{self.base_url}/produkt/{base_link}" if base_link else None

        return {
            "store": "rohlik",
            "product_id": str(product.get("productId", "")),
            "name": product.get("productName"),
            "brand": product.get("brand"),
            "price": price,                    # effective price customer pays
            "unit_price": unit_price,
            "unit": product.get("textualAmount"),
            "original_price": original_price,  # "was" price when on sale
            "is_on_sale": is_on_sale,
            "discount_pct": discount_pct,
            "promo_ends": promo_ends,
            "in_stock": product.get("inStock", False),
            "source_url": product_url,
        }
    def scrape(self, queries=None, limit_per_query=30):
        self._start_browser()
        if queries is None:
            queries = [
                "mléko", "chléb", "máslo", "jogurt", "sýr",
                "vejce", "kuřecí maso", "jablka", "banány", "rýže",
            ]

        records = []
        for query in queries:
            log.info(f"Rohlík: searching '{query}'")
            batch = self._search(query, limit=limit_per_query)
            records.extend(batch)
            log.info(f"Rohlík: got {len(batch)} records for '{query}'")

        return records

    def close(self):
        if self._page:
            self._page.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        super().close()