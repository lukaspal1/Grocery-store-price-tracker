# pipeline/run_matcher.py
import logging
import sqlite3
from itertools import combinations
from pipeline.matcher import (
    ProductRecord, score_pair, canonical_key, MIN_MATCH_SCORE,
)

log = logging.getLogger(__name__)


def run(db_path="data/prices.db"):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM product_matches")
    conn.commit()
    rows = conn.execute(
        "SELECT store, product_id, name, brand, unit, price FROM current_prices"
    ).fetchall()

    products = [ProductRecord(*r) for r in rows]
    log.info(f"Loaded {len(products)} products")

    by_store = {}
    for p in products:
        by_store.setdefault(p.store, []).append(p)

    stores = sorted(by_store.keys())
    log.info(f"Stores: {stores}")

    matches = []
    for store_a, store_b in combinations(stores, 2):
        a_products = by_store[store_a]
        b_products = by_store[store_b]
        log.info(f"Matching {store_a} ({len(a_products)}) x {store_b} ({len(b_products)})")

        for a in a_products:
            for b in b_products:
                score, breakdown = score_pair(a, b)
                if score >= MIN_MATCH_SCORE:
                    key = canonical_key(a) if a.brand else canonical_key(b)
                    matches.append({
                        "canonical_key": key,
                        "store_a": a.store,
                        "product_id_a": a.product_id,
                        "store_b": b.store,
                        "product_id_b": b.product_id,
                        "score": round(score, 3),
                        "brand_score": round(breakdown["brand"], 3),
                        "quantity_score": round(breakdown["quantity"], 3),
                        "name_score": round(breakdown["name"], 3),
                    })

    log.info(f"Found {len(matches)} matches above threshold {MIN_MATCH_SCORE}")

    from pipeline.storage import save_matches
    inserted = save_matches(conn, matches)
    log.info(f"Saved {inserted} matches to database")
    conn.close()
    return matches


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run()