# pipeline/storage.py
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS current_prices (
    store TEXT NOT NULL,
    product_id TEXT NOT NULL,
    name TEXT,
    brand TEXT,
    price REAL,
    unit_price REAL,
    unit TEXT,
    original_price REAL,
    is_on_sale INTEGER,
    discount_pct INTEGER,
    promo_ends TEXT,
    in_stock INTEGER,
    source_url TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (store, product_id)
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store TEXT NOT NULL,
    product_id TEXT NOT NULL,
    price REAL NOT NULL,
    original_price REAL,
    is_on_sale INTEGER,
    discount_pct INTEGER,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_lookup
    ON price_history (store, product_id, recorded_at);
"""


def init_db(path="data/prices.db"):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _fetch_last_price(cur, store, product_id):
    """Return the last recorded (price, original_price, is_on_sale, discount_pct)
    for a product, or None if it's never been recorded."""
    row = cur.execute(
        """SELECT price, original_price, is_on_sale, discount_pct
           FROM price_history
           WHERE store = ? AND product_id = ?
           ORDER BY recorded_at DESC
           LIMIT 1""",
        (store, product_id),
    ).fetchone()
    return row


def save_prices(conn, records):
    """Upsert into current_prices and append to price_history only when
    price or discount state actually changed."""
    now = datetime.utcnow().isoformat()
    cur = conn.cursor()
    history_added = 0
    upserted = 0

    for r in records:
        row = {
            "store": r["store"],
            "product_id": str(r["product_id"]),
            "name": r.get("name"),
            "brand": r.get("brand"),
            "price": r.get("price"),
            "unit_price": r.get("unit_price"),
            "unit": r.get("unit"),
            "original_price": r.get("original_price"),
            "is_on_sale": int(bool(r.get("is_on_sale"))),
            "discount_pct": r.get("discount_pct") or 0,
            "promo_ends": r.get("promo_ends"),
            "in_stock": int(bool(r.get("in_stock"))),
            "source_url": r.get("source_url"),
            "updated_at": now,
        }

        # 1. Upsert into current_prices
        cur.execute(
            """INSERT INTO current_prices
               (store, product_id, name, brand, price, unit_price, unit,
                original_price, is_on_sale, discount_pct, promo_ends,
                in_stock, source_url, updated_at)
               VALUES (:store, :product_id, :name, :brand, :price, :unit_price, :unit,
                       :original_price, :is_on_sale, :discount_pct, :promo_ends,
                       :in_stock, :source_url, :updated_at)
               ON CONFLICT(store, product_id) DO UPDATE SET
                   name = excluded.name,
                   brand = excluded.brand,
                   price = excluded.price,
                   unit_price = excluded.unit_price,
                   unit = excluded.unit,
                   original_price = excluded.original_price,
                   is_on_sale = excluded.is_on_sale,
                   discount_pct = excluded.discount_pct,
                   promo_ends = excluded.promo_ends,
                   in_stock = excluded.in_stock,
                   source_url = excluded.source_url,
                   updated_at = excluded.updated_at
            """,
            row,
        )
        upserted += 1

        # 2. Append to price_history only if price or discount state changed
        last = _fetch_last_price(cur, row["store"], row["product_id"])
        changed = (
            last is None
            or last[0] != row["price"]
            or last[1] != row["original_price"]
            or last[2] != row["is_on_sale"]
            or last[3] != row["discount_pct"]
        )
        if changed:
            cur.execute(
                """INSERT INTO price_history
                   (store, product_id, price, original_price, is_on_sale,
                    discount_pct, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["store"],
                    row["product_id"],
                    row["price"],
                    row["original_price"],
                    row["is_on_sale"],
                    row["discount_pct"],
                    now,
                ),
            )
            history_added += 1

    conn.commit()
    return {"upserted": upserted, "history_added": history_added}