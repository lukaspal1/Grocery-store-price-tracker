# test_matcher.py
import sqlite3
from pipeline.matcher import ProductRecord, find_matches, score_pair

conn = sqlite3.connect("data/prices.db")
rows = conn.execute(
    "SELECT store, product_id, name, brand, unit, price FROM current_prices"
).fetchall()
conn.close()

products = [ProductRecord(*r) for r in rows]
rohlik = [p for p in products if p.store == "rohlik"]
kosik = [p for p in products if p.store == "kosik"]

print(f"Rohlík: {len(rohlik)} | Košík: {len(kosik)}")
print()

# Try matching a few specific products to sanity-check
test_names = ["Tatra Trvanlivé plnotučné mléko", "Olma", "Madeta", "Miil"]
for needle in test_names:
    target_candidates = [p for p in rohlik if needle.lower() in p.name.lower()]
    if not target_candidates:
        print(f"--- No Rohlík products matching '{needle}' ---\n")
        continue
    target = target_candidates[0]
    print(f"--- '{needle}' example: {target.name} ({target.brand}, {target.unit}) ---")
    matches = find_matches(target, kosik)
    if not matches:
        print("  no matches above threshold\n")
        continue
    for m, score in matches[:3]:
        print(f"  {score:.2f} | {m.name} ({m.brand}, {m.unit}) | {m.price} Kč")
    print()