"""
One-time migration: adds kind / payment_method / bank_account_id columns to the
purchase & sales document tables. Safe to run multiple times (checks first).

Run from project root:  python add_kind_payment_columns.py
"""
import sqlite3, os

DB = os.path.join('database', 'sellers.db')
if not os.path.exists(DB):
    raise SystemExit("Run from project root (database/sellers.db not found).")

kind_only_tables = [
    'purchase_requests', 'purchase_quotations', 'purchase_orders',
    'goods_receipt_notes', 'goods_return_requests',
    'sales_requests', 'sales_quotations', 'sales_orders',
    'delivery_notes', 'sales_return_requests',
]
payment_tables = [
    'purchase_invoices', 'purchase_debit_memos',
    'sales_invoices', 'sales_credit_memos',
]

conn = sqlite3.connect(DB)
cur = conn.cursor()

def has_col(table, col):
    return col in [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]

def add_col(table, col, ddl):
    if not has_col(table, col):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        print(f"  + {table}.{col}")
    else:
        print(f"  = {table}.{col} (already exists)")

print("Adding 'kind' to document tables:")
for t in kind_only_tables + payment_tables:
    add_col(t, 'kind', "kind VARCHAR(20) DEFAULT 'Goods'")

print("Adding payment columns to invoice/memo tables:")
for t in payment_tables:
    add_col(t, 'payment_method', "payment_method VARCHAR(20) DEFAULT 'Credit'")
    add_col(t, 'bank_account_id', "bank_account_id INTEGER")

print("Adding seller_id to sales invoice/credit-memo tables:")
for t in ['sales_invoices', 'sales_credit_memos']:
    add_col(t, 'seller_id', "seller_id INTEGER")

conn.commit()
conn.close()
print("Done.")