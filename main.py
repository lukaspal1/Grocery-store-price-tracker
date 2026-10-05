# main.py
import logging
from scrapers.rohlik import RohlikScraper
from scrapers.kosik import KosikScraper
from pipeline.storage import init_db, save_prices

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

SCRAPERS = [
    RohlikScraper,
    KosikScraper,
]


def run():
    conn = init_db()
    for ScraperClass in SCRAPERS:
        scraper = ScraperClass()
        try:
            records = scraper.scrape()
            stats = save_prices(conn, records)
            log.info(
                f"{ScraperClass.__name__}: upserted {stats['upserted']}, "
                f"history +{stats['history_added']}"
            )
        except Exception as e:
            log.error(f"{ScraperClass.__name__} failed: {e}")
        finally:
            scraper.close()
    conn.close()


if __name__ == "__main__":
    run()