"""
Run from your project root:  python DIAGNOSE_allowance_save.py

Checks the ALLOWANCE-SAVE fix specifically (not just the display fix).
"""
import os, re

tpl = os.path.join('templates', 'employees', 'list.html')
if not os.path.exists(tpl):
    print("!! Run this from your project root (where templates/ lives).")
    raise SystemExit

txt = open(tpl, encoding='utf-8').read()

checks = {
    "1. seeding fix (allowances show in edit)":
        "_pendingAllows = (d.allowances" in txt,
    "2. injectAllowances() function defined":
        "function injectAllowances" in txt,
    "3. Save button CALLS injectAllowances()":
        bool(re.search(r"injectAllowances\(\)\s*;\s*document\.getElementById\('empForm'\)\.submit", txt)),
}

print("Allowance-save fix status in templates/employees/list.html:\n")
all_ok = True
for label, ok in checks.items():
    print(f"  [{'OK' if ok else 'MISSING'}] {label}")
    all_ok = all_ok and ok

print()
if all_ok:
    print("=> All three fixes are present on disk.")
    print("   If allowances STILL don't save after this, it is browser cache.")
    print("   Do a HARD refresh: Ctrl+Shift+R (Windows) so the browser loads")
    print("   the new JavaScript instead of the cached old version.")
    print()
    print("   Then: open employee > Manage > add allowance > click the main")
    print("   SAVE button on the form (not just close the popup) > re-open.")
else:
    print("=> The file on disk is an OLDER version missing the save fix.")
    print("   Replace templates/employees/list.html with the latest delivered")
    print("   list.html (the one that contains injectAllowances).")

# Bonus: check the backend behavior that makes injection mandatory
route = os.path.join('database', 'routes', 'employees.py')
if os.path.exists(route):
    r = open(route, encoding='utf-8').read()
    deletes = "EmployeeAllowance.query.filter_by(employee_id=emp_id).delete()" in r
    reads = "getlist('allow_type_id[]')" in r
    print(f"\nBackend save_allowances deletes-then-reinserts: {deletes}")
    print(f"Backend reads allow_type_id[] from form:        {reads}")
    if deletes and reads:
        print("  -> Confirms: without injectAllowances(), every save WIPES allowances.")