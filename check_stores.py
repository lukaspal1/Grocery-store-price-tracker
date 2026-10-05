# check_stores.py
import sqlite3

conn = sqlite3.connect("data/prices.db")
cur = conn.cursor()

print("=== Products per store ===")
for row in cur.execute(
    "SELECT store, COUNT(*) FROM current_prices GROUP BY store ORDER BY store"
):
    print(f"  {row[0]}: {row[1]}")

print()
print("=== Tatra products at both stores ===")
for row in cur.execute(
    "SELECT store, name, price, unit FROM current_prices "
    "WHERE name LIKE '%Tatra%' ORDER BY name, store"
):
    store, name, price, unit = row
    print(f"  [{store:7}] {price:>6} Kč | {unit or '':>6} | {name}")

conn.close()