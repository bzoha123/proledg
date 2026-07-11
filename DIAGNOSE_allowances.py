"""
Run this from your project root:  python DIAGNOSE_allowances.py

It tells you, without touching the UI, whether the allowance problem is
(a) no data in the DB, (b) the backend, or (c) the frontend file.
"""
import sqlite3, os

DB = os.path.join('database', 'sellers.db')
if not os.path.exists(DB):
    print("!! Cannot find database/sellers.db from here. Run from project root.")
    raise SystemExit

c = sqlite3.connect(DB)
emps = c.execute("SELECT id, employee_code FROM employees").fetchall()
allow = c.execute("SELECT COUNT(*) FROM employee_allowances").fetchone()[0]
print(f"Employees in DB: {len(emps)} -> {emps}")
print(f"Rows in employee_allowances: {allow}")

if allow == 0:
    print("\n=> DIAGNOSIS: your database has NO saved allowances for anyone.")
    print("   Edit correctly shows 'No allowances'. This is DATA, not a bug.")
    print("   Fix: open an employee > Manage > add an allowance > Save,")
    print("        then re-open Edit. It will appear.")
else:
    by_emp = c.execute(
        "SELECT employee_id, COUNT(*) FROM employee_allowances GROUP BY employee_id"
    ).fetchall()
    print(f"   Allowances per employee: {by_emp}")
    print("\n=> Data exists. If Edit still shows nothing, the template file")
    print("   being served is the OLD one. Confirm the line below exists in")
    print("   templates/employees/list.html:")
    print('     _pendingAllows = (d.allowances || []).map(')

# Check the template file on disk
tpl = os.path.join('templates', 'employees', 'list.html')
if os.path.exists(tpl):
    txt = open(tpl, encoding='utf-8').read()
    has_fix = '_pendingAllows = (d.allowances' in txt
    print(f"\nTemplate on disk has the allowance-seeding fix: {has_fix}")
    if not has_fix:
        print("   !! You are running the OLD list.html. Replace it with the")
        print("      delivered fix4/templates/employees/list.html.")
else:
    print("\n(could not find templates/employees/list.html from here)")