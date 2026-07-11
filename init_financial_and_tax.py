"""
One-time setup for the Financial Year + Tax Code modules.

Run from the project root:  python init_financial_and_tax.py

- Creates the new tables (financial_year, financial_year_detail,
  purchase_tax_code, sales_tax_code) if they don't already exist.
- Seeds the default purchase & sales tax codes (idempotent).

Safe to run multiple times.
"""
from app import create_app
from models import db, seed_tax_codes, PurchaseTaxCode, SalesTaxCode

app = create_app()
with app.app_context():
    db.create_all()          # creates only missing tables; leaves existing ones untouched
    n = seed_tax_codes()
    print(f"Tables ensured. Tax codes seeded: {n} new record(s).")
    print(f"  Purchase tax codes: {PurchaseTaxCode.query.count()}")
    print(f"  Sales tax codes:    {SalesTaxCode.query.count()}")
    print("Done.")