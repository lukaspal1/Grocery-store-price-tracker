# scrapers/kosik.py
import time
import logging
from scrapers.base import CompliantScraper

log = logging.getLogger(__name__)


class KosikScraper(CompliantScraper):
    SEARCH_URL = "https://www.kosik.cz/api/front/page/products/flexible"

    def __init__(self):
        super().__init__("https://www.kosik.cz")
        self.client.headers.update({
            "Accept": "*/*",
            "Referer": "https://www.kosik.cz/",
        })

    def _search(self, query, limit=30):
        if not self.can_fetch(self.SEARCH_URL):
            return []
        time.sleep(self.DELAY_SECONDS)

        params = {
            "vendor": 1,
            "slug": "vyhledavani",
            "limit": limit,
            "search_term": query,
            "platform": "web",
        }

        r = self.get(self.SEARCH_URL, params=params)
        if not r:
            return []

        try:
            payload = r.json()
        except ValueError:
            log.error(f"Košík: non-JSON response for '{query}'")
            return []

        products = payload.get("products", {}).get("items", [])
        return [self._normalize(p) for p in products]

    def _normalize(self, product):
        price = product.get("price")
        recommended = product.get("recommendedPrice")
        discount_pct = product.get("percentageDiscount", 0)
        is_on_sale = discount_pct > 0 and recommended and recommended > price

        # Package size from productQuantity
        qty = product.get("productQuantity") or {}
        unit = f"{qty.get('value', '')} {qty.get('unit', '')}".strip() or None

        # Normalized unit price from pricePerUnit
        ppu = product.get("pricePerUnit") or {}
        unit_price = ppu.get("price")
        unit_price_unit = ppu.get("unit")

        base_link = product.get("url", "")
        product_url = f"{self.base_url}{base_link}" if base_link else None

        return {
            "store": "kosik",
            "product_id": str(product.get("id", "")),
            "name": product.get("name"),
            "brand": (product.get("brand") or {}).get("name"),
            "price": price,
            "unit_price": unit_price,
            "unit": unit,
            "original_price": recommended if is_on_sale else None,
            "is_on_sale": is_on_sale,
            "discount_pct": discount_pct if is_on_sale else 0,
            "promo_ends": None,   # Košík exposes end date in free-text actionLabel only
            "in_stock": bool(product.get("availability")),
            "source_url": product_url,
        }

    def scrape(self, queries=None, limit_per_query=30):
        if queries is None:
            queries = [
                "mléko", "chléb", "máslo", "jogurt", "sýr",
                "vejce", "kuřecí maso", "jablka", "banány", "rýže",
            ]

        records = []
        for query in queries:
            log.info(f"Košík: searching '{query}'")
            batch = self._search(query, limit=limit_per_query)
            records.extend(batch)
            log.info(f"Košík: got {len(batch)} records for '{query}'")

        return records