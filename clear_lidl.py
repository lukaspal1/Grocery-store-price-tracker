# clear_lidl.py
import sqlite3
conn = sqlite3.connect("data/prices.db")
conn.execute("DELETE FROM current_prices WHERE store='lidl'")
conn.execute("DELETE FROM price_history WHERE store='lidl'")
conn.commit()
print("cleared lidl rows from both tables")
conn.close()