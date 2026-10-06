# scrapers/lidl.py
import logging
from scrapers.base import CompliantScraper

log = logging.getLogger(__name__)

APP_VERSION = "17.0.5"

# Lidl's `category` field describes the redemption channel (Store / OnlineShop),
# not the product type. Since Lidl mixes grocery and non-grocery offers in the
# same feed, we filter with an allowlist of food-related keywords. The alternative
# — a blocklist of all possible non-grocery items — is unbounded and unmaintainable.
GROCERY_KEYWORDS = [
    # dairy & eggs
    "mléko", "mléčn", "sýr", "jogurt", "kefír", "smetan", "máslo", "tvaroh",
    "skyr", "vejce", "vaječn", "zakysan",
    # meat & fish
    "maso", "kuře", "kuřec", "vepřov", "hověz", "ryb", "losos", "šunk",
    "salám", "párk", "klobás", "slanin", "sekan",
    # produce
    "jablk", "banán", "citron", "pomeran", "hrušk", "jahod", "borůvk",
    "rajč", "okurk", "paprik", "brambor", "cibul", "mrkev", "zelí",
    "salát", "okur", "brokolic", "květák", "ovoce", "zelenin", "bylin",
    # bakery
    "chléb", "rohlík", "bageta", "housk", "pečiv", "moučník", "koláč",
    # pantry
    "těstovin", "rýže", "mouk", "cukr", "olej", "ocet", "hořčic",
    "kečup", "majonéz", "čokolád", "sušenk", "keks", "bonbón",
    "káva", "čaj", "nápoj", "voda", "džus", "limonád",
    "piv", "vín", "prosecco", "šumiv",
    # prepared / frozen
    "pizza", "mražen", "hotov", "polévk", "omáčk", "konzerv",
    "luncheon", "paštik", "pomazán",
]

class LidlScraper(CompliantScraper):
    STORES_BASE = "https://stores.lidlplus.com/api"
    OFFERS_BASE = "https://offers.lidlplus.com/app/api"
    COUNTRY = "CZ"
    LANGUAGE = "cs-CZ"

    def __init__(self, cities=None, grocery_only=True):
        super().__init__("https://www.lidl.cz")
        self.cities = cities or ["Praha", "Brno", "Ostrava", "Plzeň"]
        self.grocery_only = grocery_only
        self.client.headers.update({
            "Accept": "application/json",
            "Accept-Language": self.LANGUAGE,
            "User-Agent": f"LidlPlus/{APP_VERSION} Android okhttp/4.12.0",
            "X-Client-Version": APP_VERSION,
            "X-Client-Platform": "android",
        })

    def _find_stores(self, city):
        url = f"{self.STORES_BASE}/v1/autocomplete/{self.COUNTRY}"
        params = {
            "input": city,
            "language": self.LANGUAGE.split("-", 1)[0],
            "latitude": 50.0755,
            "longitude": 14.4378,
        }
        r = self.get(url, params=params)
        if not r:
            return []
        try:
            return r.json()
        except ValueError:
            log.error(f"Lidl: non-JSON store response for {city}")
            return []

    def _fetch_offers(self, store_key):
        url = f"{self.OFFERS_BASE}/v4/{self.COUNTRY}/{store_key}/offers"
        r = self.get(url)
        if not r:
            return []
        try:
            return r.json().get("offers", [])
        except ValueError:
            log.error(f"Lidl: non-JSON offers for {store_key}")
            return []

    def _classify(self, offer):
        """Return 'food' or 'nonfood' based on offer title and alt text.
        This is a best-effort hint, not a filter."""
        if not self.grocery_only:
            return "food"
        haystack = " ".join(filter(None, [
            (offer.get("title") or "").lower(),
            (offer.get("imageAltText") or "").lower(),
        ]))
        return "food" if any(kw in haystack for kw in GROCERY_KEYWORDS) else "nonfood"
    def _normalize(self, offer, store_key):
        box = offer.get("priceBox") or {}
        price = box.get("largePartNumeric")
        original = box.get("smallPartNumeric")

        discount_pct = 0
        if price is not None and original is not None and original > 0 and price < original:
            discount_pct = round((original - price) / original * 100)

        brand = offer.get("brand")
        title = offer.get("title") or ""
        full_name = f"{brand} {title}".strip() if brand else title

        # Best-effort classification. Kept as a hint, not a filter.
        haystack = " ".join(filter(None, [
            (offer.get("title") or "").lower(),
            (offer.get("imageAltText") or "").lower(),
        ]))
        food_score = sum(1 for kw in GROCERY_KEYWORDS if kw in haystack)
        category_hint = "food" if food_score > 0 else "nonfood"

        return {
            "store": "lidl",
            "product_id": str(offer.get("id", "")),
            "name": full_name,
            "brand": brand,
            "price": price,
            "unit_price": None,
            "unit": offer.get("packaging"),
            "original_price": original,
            "is_on_sale": discount_pct > 0,
            "discount_pct": discount_pct,
            "promo_ends": offer.get("endValidityDateUTC"),
            "in_stock": True,
            "source_url": "https://www.lidl.cz/l/cs/letak/",
            "category_hint": self._classify(offer),
        }

    def scrape(self, **kwargs):
        all_records = []
        seen_ids = set()
        skipped_non_grocery = 0
        skipped_no_price = 0

        for city in self.cities:
            log.info(f"Lidl: searching stores near '{city}'")
            stores = self._find_stores(city)
            if not stores:
                continue

            for store in stores[:3]:
                store_key = store.get("storeKey")
                if not store_key:
                    continue
                log.info(f"Lidl: fetching offers for {store.get('name', store_key)}")
                offers = self._fetch_offers(store_key)
                if not offers:
                    continue

                added = 0
                for offer in offers:
                    pid = str(offer.get("id", ""))
                    if not pid or pid in seen_ids:
                        continue

                    price = (offer.get("priceBox") or {}).get("largePartNumeric")
                    if price is None:
                        skipped_no_price += 1
                        continue

                    # No longer filtering — we keep everything and just tag it
                    seen_ids.add(pid)
                    all_records.append(self._normalize(offer, store_key))
                    added += 1

                log.info(f"Lidl: got {added} new offers")
                break

        if skipped_non_grocery:
            log.info(f"Lidl: skipped {skipped_non_grocery} non-grocery offers")
        if skipped_no_price:
            log.info(f"Lidl: skipped {skipped_no_price} offers without a numeric price")

        return all_records