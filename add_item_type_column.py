"""One-time: add item_type to item_master. Run from project root. Idempotent."""
import sqlite3, os
DB = os.path.join('database', 'sellers.db')
conn = sqlite3.connect(DB); cur = conn.cursor()
cols = [r[1] for r in cur.execute("PRAGMA table_info(item_master)")]
if 'item_type' not in cols:
    cur.execute("ALTER TABLE item_master ADD COLUMN item_type VARCHAR(20) DEFAULT 'Product'")
    print("added item_master.item_type")
else:
    print("item_master.item_type already exists")
conn.commit(); print("Done.")