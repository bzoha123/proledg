"""
recreate_employee_tables.py
Run once from the project root (venv active):  python recreate_employee_tables.py

Drops and rebuilds the employee-related tables from the updated models.
work_allocations is NOT touched. sellers/buyers/warehouses are NOT touched.
Because db.create_all() uses CREATE TABLE (not batch ALTER), the
"Constraint must have a name" SQLite error cannot occur here.
"""
from app import app, db
from sqlalchemy import text
# import the models so create_all knows about them
from models import (Employee, EmployeeBank, EmployeeAllowance,
                    AllowanceType, EmployeeDocument)

# child tables first (FK dependency order)
DROP_ORDER = [
    'employee_documents',
    'employee_allowances',
    'employee_banks',
    'employees',
    'allowance_types',
]

with app.app_context():
    for tbl in DROP_ORDER:
        try:
            db.session.execute(text(f'DROP TABLE IF EXISTS {tbl}'))
            db.session.commit()
            print('dropped', tbl)
        except Exception as e:
            db.session.rollback()
            print('skip', tbl, '->', e)

    # recreate only the missing (just-dropped) tables
    db.create_all()
    print('recreated employee tables (employees, employee_banks, '
          'employee_allowances, allowance_types, employee_documents)')