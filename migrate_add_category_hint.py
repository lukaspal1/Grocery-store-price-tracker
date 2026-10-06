# migrate_add_category_hint.py
import sqlite3

conn = sqlite3.connect("data/prices.db")
try:
    conn.execute("ALTER TABLE current_prices ADD COLUMN category_hint TEXT")
    conn.commit()
    print("Added category_hint column")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("Column already exists — nothing to do")
    else:
        raise
conn.close()