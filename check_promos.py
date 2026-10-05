# check_promos.py
import sqlite3

conn = sqlite3.connect("data/prices.db")
cur = conn.cursor()

total = cur.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
on_sale = cur.execute("SELECT COUNT(*) FROM price_snapshots WHERE is_on_sale = 1").fetchone()[0]
ending_future = cur.execute(
    "SELECT COUNT(*) FROM price_snapshots "
    "WHERE is_on_sale = 1 AND (promo_ends IS NULL OR promo_ends > datetime('now'))"
).fetchone()[0]

print(f"Total rows:        {total}")
print(f"On sale:           {on_sale}")
print(f"Active promos:     {ending_future}")
print()
print("Top 10 by discount:")
for row in cur.execute(
    "SELECT name, original_price, price, discount_pct, promo_ends "
    "FROM price_snapshots WHERE is_on_sale = 1 "
    "ORDER BY discount_pct DESC LIMIT 10"
):
    name, orig, price, pct, ends = row
    print(f"  {pct:>3}% | {orig:>6} → {price:<6} | ends {ends} | {name}")

conn.close()