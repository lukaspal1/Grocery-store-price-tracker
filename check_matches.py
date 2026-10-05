# check_matches.py
import sqlite3

conn = sqlite3.connect("data/prices.db")
rows = conn.execute("""
    SELECT pm.score, ca.name, cb.name, ca.price, cb.price, ca.unit
    FROM product_matches pm
    JOIN current_prices ca ON ca.store = pm.store_a AND ca.product_id = pm.product_id_a
    JOIN current_prices cb ON cb.store = pm.store_b AND cb.product_id = pm.product_id_b
    ORDER BY pm.score DESC
    LIMIT 20
""").fetchall()

print(f"{'score':<6} {'product':<50} {'kosik':<8} {'rohlik':<8} {'diff'}")
print("-" * 90)
for score, na, nb, pa, pb, unit in rows:
    # Figure out which is which (order in the query isn't guaranteed to be consistent)
    # We'll just print both sides
    diff = pb - pa
    marker = "  " if abs(diff) < 0.01 else ("⬆" if diff > 0 else "⬇")
    print(f"{score:.2f}   {na[:48]:<50}")
    print(f"       {nb[:48]:<50} {pa:>6.2f}  {pb:>6.2f}  {marker}{abs(diff):.2f}")

conn.close()