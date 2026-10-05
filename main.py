# main.py
import logging
from scrapers.rohlik import RohlikScraper
from pipeline.storage import init_db, save_prices

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def run():
    conn = init_db()
    scraper = RohlikScraper()
    try:
        records = scraper.scrape()
        stats = save_prices(conn, records)
        log.info(
            f"Upserted {stats['upserted']} products, "
            f"added {stats['history_added']} history rows"
        )
    finally:
        scraper.close()
        conn.close()


if __name__ == "__main__":
    run()