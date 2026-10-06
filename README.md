# Czech Grocery Price Tracker

An ETL pipeline that scrapes current prices from major Czech online grocers, matches identical products across stores, and visualizes the results in an interactive dashboard.

<img width="1876" height="840" alt="image" src="https://github.com/user-attachments/assets/1dac8cf0-f5fc-4a3e-9b61-3f5b04357560" />

## What it does

- **Scrapes three Czech grocery stores** using technique-specific approaches (browser automation, JSON APIs, and Lidl Plus endpoints)
- **Tracks ~750 products** with full price history and promotion data
- **Matches identical products across stores** using a rule-based matcher with per-category vetos
- **Shows cross-store price comparisons** and calculates potential savings on a matched basket
- **Runs on a schedule** and accumulates price history over time

## Architecture

```
Scrapers        →  Compliance       →  Storage       →  Matcher          →  Dashboard
(per-store)        (base.py)           (SQLite)         (rule-based)        (Streamlit)

rohlik.py          robots.txt          current_prices   brand 45%           comparison
kosik.py           rate limiting       price_history    quantity 25%        browse
lidl.py            User-Agent          product_matches  name 30%            discounts
                   logging                              vetos               history
```


### Layers

| Layer | Responsibility | Key files |
|---|---|---|
| **Scrapers** | Fetch data from each store using the technique the store requires | `scrapers/` |
| **Compliance** | robots.txt, rate limiting, honest User-Agent, structured logging | `scrapers/base.py` |
| **Storage** | Two-table SQLite design with change detection | `pipeline/storage.py` |
| **Matcher** | Cross-store product matching with confidence scores and per-category vetos | `pipeline/matcher.py` |
| **Dashboard** | Streamlit UI for comparison, browsing, and history | `dashboard/app.py` |

## Stores covered

| Store | Data source | Technique | Scope |
|---|---|---|---|
| **Rohlík.cz** | Internal JSON API | Playwright (Cloudflare bypass) | Full catalog slices |
| **Košík.cz** | Public JSON API | httpx | Full catalog slices |
| **Lidl.cz** | Lidl Plus offers API | httpx | In-store promotions |
perhaps more coming later

### Two-table storage with change detection

Storing a full snapshot every scrape would grow linearly (~300 rows per store per run). Instead:
- `current_prices` holds the latest state, upserted on each run
- `price_history` appends a row **only when** a price or discount state actually changes

This keeps the database small and makes `price_history` a genuine event log — every row represents a real price change. After a year of daily scrapes, the DB is a few MB instead of hundreds.

### Rule-based product matching

A naive fuzzy matcher produces false positives: `Vodňanské Kuře Kuřecí stehna` (thighs) vs `Vodňanské Kuře Kuřecí prsní řízky` (breasts) both share brand, size, and 4/5 of their name tokens. The matcher combines brand + quantity + fuzzy name into a confidence score, but applies **hard vetos** when two products differ on a defining feature:

- Fat content (1.5% vs 3.5%)
- Shelf-life type (fresh vs long-life)
- One-sided keywords (BIO, slané, bez laktózy, meat cut, rice variety, etc.)

Wrong matches are worse than no matches for a price comparison tool, so the matcher errs on the side of rejecting.
## Ethical compliance

- Every scraper checks `robots.txt` before fetching and respects disallowed paths
- Rate limited to ~2 seconds per request
- Honest User-Agent identifying the project with contact info
- No bypassing of authentication, CAPTCHAs, or anti-bot measures beyond rendering a browser normally
- The scraped database is not committed to the repository — only the code is public

## Limitations

- **Search-based coverage:** Rohlík and Košík are scraped via their search APIs with a fixed set of product queries, so the catalog is a representative sample rather than exhaustive. This is a scope decision — enumerating the full catalog requires category-by-category traversal.
- **Lidl category ambiguity:** The Lidl Plus API returns grocery and non-grocery offers in the same feed, with `category` meaning the redemption channel (Store/OnlineShop) rather than product type. Offers are tagged with a best-effort `category_hint` and filtered in the dashboard.
- **No EAN matching:** Neither Rohlík nor Košík expose EAN/UPC codes in their search APIs, so cross-store matching relies on brand + name + size heuristics rather than barcodes.

## Setup

```bash
git clone https://github.com/lukaspal1/Grocery-store-price-tracker.git
cd Grocery-store-price-tracker
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Scrape all stores
python main.py

# Run the product matcher
python -m pipeline.run_matcher

# Launch the dashboard
streamlit run dashboard/app.py

