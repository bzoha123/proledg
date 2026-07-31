"""
Register master-page models with the generic import/export tool (io_tools).

Import this module's `register_all()` once at app startup (after models are
imported). Purchases and Sales documents are deliberately excluded.

Each entry: register_io(key, model, columns=[(header, attr), ...], unique=attr)
"""

from database.routes.io_tools import register_io, register_bundle


def _to_bool(v):
    return str(v).strip().lower() in ('1', 'true', 'yes', 'y', 'active')


def _to_dec(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


def register_all():
    from models import (UnitMeasurement, AllowanceType, ProfessionMaster,
                        TaxCategory, EmployeeWorkAllocation)

    # ── Unit of Measurement ──
    register_io(
        'unit-measurement', UnitMeasurement,
        columns=[('Code', 'code'), ('Name (EN)', 'name_en'), ('Name (AR)', 'name_ar'),
                 ('Pack Size (EN)', 'pac_size_en'), ('Pack Size (AR)', 'pac_size_ar'),
                 ('Multiply', 'multiply'), ('Status', 'status')],
        unique='code', label='Unit of Measurement',
        coerce={'multiply': _to_dec},
    )

    # ── Allowance Types ──
    register_io(
        'allowance-types', AllowanceType,
        columns=[('Code', 'allowance_code'), ('Name (EN)', 'allowance_name_en'),
                 ('Name (AR)', 'allowance_name_ar'), ('Active', 'is_active')],
        unique='allowance_code', label='Allowance Types',
        coerce={'is_active': _to_bool},
    )

    # ── Professions ──
    register_io(
        'professions', ProfessionMaster,
        columns=[('Name (EN)', 'name_en'), ('Name (AR)', 'name_ar'),
                 ('Active', 'is_active')],
        unique='name_en', label='Professions',
        coerce={'is_active': _to_bool},
    )

    # ── Tax Categories ──
    register_io(
        'tax-categories', TaxCategory,
        columns=[('Name (EN)', 'name_en'), ('Name (AR)', 'name_ar'), ('Rate', 'rate')],
        unique='name_en', label='Tax Categories',
        coerce={'rate': _to_dec},
    )

    # ── Work Allocations (export-focused; import add-new by employee+month) ──
    register_io(
        'work-allocations', EmployeeWorkAllocation,
        columns=[('Employee ID', 'employee_id'), ('Kafeel', 'kafeel'), ('Name', 'name'),
                 ('Nationality', 'nationality'), ('Profession', 'profession'),
                 ('Iqama', 'iqama'), ('Month', 'month'),
                 ('Joining Date', 'joining_date'), ('End Date', 'end_date'),
                 ('Buyer', 'buyer_name'), ('Department', 'buyer_department'),
                 ('Location', 'location'), ('Shift', 'shift'), ('Status', 'status')],
        unique='iqama', label='Work Allocations',
    )

    # ── Sellers ──
    from models import Seller, BuyerMaster, Employee, VendorMaster, ItemMaster, FinancialYear
    register_io(
        'sellers', Seller,
        columns=[('Code', 'seller_code'), ('Name', 'name'), ('Name (AR)', 'name_ar'),
                 ('VAT Number', 'vat_number'), ('CRN', 'crn'), ('Phone', 'phone'),
                 ('Fax', 'fax'), ('Email', 'email'), ('Website', 'website'),
                 ('Building', 'building_number'), ('Street', 'street_name'),
                 ('District', 'district'), ('City', 'city'), ('Postal Code', 'postal_code'),
                 ('Country', 'country'), ('Status', 'status'),
                 ('Account Code', 'levelfive_code')],
        unique='seller_code', label='Sellers',
    )

    # ── Buyers ──
    register_io(
        'buyers', BuyerMaster,
        columns=[('Code', 'buyer_code'), ('Name (EN)', 'buyer_name_en'),
                 ('Name (AR)', 'buyer_name_ar'), ('VAT Number', 'vat_number'),
                 ('CRN', 'crn'), ('Phone', 'phone'), ('Fax', 'fax'), ('Email', 'email'),
                 ('Website', 'website'), ('Building', 'building_number'),
                 ('Street', 'street_name'), ('District', 'district'), ('City', 'city'),
                 ('Postal Code', 'postal_code'), ('Country', 'country'),
                 ('Status', 'status'), ('Account Code', 'levelfive_code')],
        unique='buyer_code', label='Buyers',
    )

    # ── Vendors ──
    register_io(
        'vendors', VendorMaster,
        columns=[('Code', 'vendor_code'), ('Name (EN)', 'vendor_name_en'),
                 ('Name (AR)', 'vendor_name_ar'), ('VAT Number', 'vat_number'),
                 ('CRN', 'crn'), ('Phone', 'phone'), ('Fax', 'fax'), ('Email', 'email'),
                 ('Website', 'website'), ('Contact Person', 'contact_person'),
                 ('Building', 'building_number'), ('Street', 'street_name'),
                 ('District', 'district'), ('City', 'city'), ('Postal Code', 'postal_code'),
                 ('Country', 'country'), ('Payment Term', 'payment_term'),
                 ('Status', 'status'), ('Account Code', 'levelfive_code')],
        unique='vendor_code', label='Vendors',
    )

    # ── Employees ──
    register_io(
        'employees', Employee,
        columns=[('Code', 'employee_code'), ('Name', 'name'), ('Name (AR)', 'name_ar'),
                 ('Nationality', 'nationality'), ('Passport Number', 'passport_number'),
                 ('Iqama Number', 'iqama_number'), ('Mobile', 'mobile'), ('Email', 'email'),
                 ('Joining Date', 'joining_date'), ('Salary Type', 'salary_type'),
                 ('Basic Salary', 'basic_salary'), ('Net Salary', 'net_salary'),
                 ('Active', 'is_active'), ('Account Code', 'levelfive_code')],
        unique='employee_code', label='Employees',
        coerce={'is_active': _to_bool, 'basic_salary': _to_dec, 'net_salary': _to_dec},
    )

    # ── Item Master ──
    register_io(
        'items', ItemMaster,
        columns=[('Code', 'item_code'), ('Type', 'item_type'), ('Article No', 'article_no'),
                 ('Name (EN)', 'name_en'), ('Name (AR)', 'name_ar'),
                 ('Print Name', 'print_name'), ('UOM', 'uom'), ('Description', 'item_desc'),
                 ('Main Rate', 'main_rate'), ('Retail Rate', 'retail_rate'),
                 ('Wholesale Rate', 'wholesale_rate'), ('MRP', 'mrp'),
                 ('Active', 'is_active'), ('Account Code', 'levelfive_code')],
        unique='item_code', label='Item Master',
        coerce={'is_active': _to_bool, 'main_rate': _to_dec, 'retail_rate': _to_dec,
                'wholesale_rate': _to_dec, 'mrp': _to_dec},
    )

    # ── Financial Year ──
    register_io(
        'financial-year', FinancialYear,
        columns=[('Financial Year', 'financial_year'), ('Range', 'range'),
                 ('Year', 'year'), ('Status', 'status')],
        unique='year', label='Financial Year',
    )

    # ══════════════════════════════════════════════════════════════
    #  Multi-sheet bundles: parent + child tables in one workbook
    # ══════════════════════════════════════════════════════════════
    from models import (SellerBank, SellerWarehouse, BuyerBank,
                        VendorBank, EmployeeBank)

    _bank_cols = [('Bank Name', 'bank_name'), ('Bank Name (AR)', 'bank_name_ar'),
                  ('Account Number', 'account_number'), ('Branch', 'branch'),
                  ('Branch (AR)', 'branch_ar'), ('SWIFT', 'swift_code'),
                  ('IBAN', 'iban'), ('Primary', 'is_primary')]

    # ── Seller + Banks + Warehouses ──
    register_bundle(
        'seller-full', Seller, 'seller_code',
        parent_columns=[('Code', 'seller_code'), ('Name', 'name'), ('Name (AR)', 'name_ar'),
                        ('VAT Number', 'vat_number'), ('CRN', 'crn'), ('Phone', 'phone'),
                        ('Email', 'email'), ('City', 'city'), ('Country', 'country'),
                        ('Status', 'status'), ('Account Code', 'levelfive_code')],
        children=[
            {'sheet': 'Banks', 'model': SellerBank, 'fk': 'seller_id',
             'parent_ref': 'Seller Code', 'columns': _bank_cols,
             'coerce': {'is_primary': _to_bool}},
            {'sheet': 'Warehouses', 'model': SellerWarehouse, 'fk': 'seller_id',
             'parent_ref': 'Seller Code',
             'columns': [('Warehouse Name', 'warehouse_name'),
                         ('Warehouse Name (AR)', 'warehouse_name_ar'),
                         ('Location', 'location'), ('Location (AR)', 'location_ar')]},
        ],
        label='Sellers',
    )

    # ── Buyer + Banks ──
    register_bundle(
        'buyer-full', BuyerMaster, 'buyer_code',
        parent_columns=[('Code', 'buyer_code'), ('Name (EN)', 'buyer_name_en'),
                        ('Name (AR)', 'buyer_name_ar'), ('VAT Number', 'vat_number'),
                        ('CRN', 'crn'), ('Phone', 'phone'), ('Email', 'email'),
                        ('City', 'city'), ('Country', 'country'), ('Status', 'status'),
                        ('Account Code', 'levelfive_code')],
        children=[
            {'sheet': 'Banks', 'model': BuyerBank, 'fk': 'buyer_id',
             'parent_ref': 'Buyer Code', 'columns': _bank_cols,
             'coerce': {'is_primary': _to_bool}},
        ],
        label='Buyers',
    )

    # ── Vendor + Banks (vendor bank uses *_en field names) ──
    register_bundle(
        'vendor-full', VendorMaster, 'vendor_code',
        parent_columns=[('Code', 'vendor_code'), ('Name (EN)', 'vendor_name_en'),
                        ('Name (AR)', 'vendor_name_ar'), ('VAT Number', 'vat_number'),
                        ('CRN', 'crn'), ('Phone', 'phone'), ('Email', 'email'),
                        ('City', 'city'), ('Country', 'country'), ('Status', 'status'),
                        ('Account Code', 'levelfive_code')],
        children=[
            {'sheet': 'Banks', 'model': VendorBank, 'fk': 'vendor_id',
             'parent_ref': 'Vendor Code',
             'columns': [('Bank Name', 'bank_name_en'), ('Bank Name (AR)', 'bank_name_ar'),
                         ('Account Number', 'account_number'), ('Branch', 'branch_en'),
                         ('Branch (AR)', 'branch_ar'), ('SWIFT', 'swift_code'),
                         ('IBAN', 'iban'), ('Primary', 'is_primary')],
             'coerce': {'is_primary': _to_bool}},
        ],
        label='Vendors',
    )

    # ── Employee + Banks ──
    register_bundle(
        'employee-full', Employee, 'employee_code',
        parent_columns=[('Code', 'employee_code'), ('Name', 'name'), ('Name (AR)', 'name_ar'),
                        ('Nationality', 'nationality'), ('Iqama Number', 'iqama_number'),
                        ('Mobile', 'mobile'), ('Email', 'email'), ('Active', 'is_active'),
                        ('Account Code', 'levelfive_code')],
        children=[
            {'sheet': 'Banks', 'model': EmployeeBank, 'fk': 'employee_id',
             'parent_ref': 'Employee Code', 'columns': _bank_cols,
             'coerce': {'is_primary': _to_bool}},
        ],
        label='Employees',
    )

    # ══════════════════════════════════════════════════════════════
    #  Child tables as their OWN standalone import/export files.
    #  Each carries a parent-code column so rows link back on import.
    #  unique=None -> no dedupe (children have no natural unique key);
    #  every row imports and attaches to its parent by code.
    # ══════════════════════════════════════════════════════════════

    # Seller Banks
    register_io(
        'seller-banks', SellerBank,
        columns=[('Seller Code', '_parent'), ('Bank Name', 'bank_name'),
                 ('Bank Name (AR)', 'bank_name_ar'), ('Account Number', 'account_number'),
                 ('Branch', 'branch'), ('Branch (AR)', 'branch_ar'),
                 ('SWIFT', 'swift_code'), ('IBAN', 'iban'), ('Primary', 'is_primary')],
        unique=None, label='Seller Banks',
        parents=[('Seller Code', '_parent', Seller, 'seller_code', 'seller_id')],
        coerce={'is_primary': _to_bool},
    )

    # Seller Warehouses
    register_io(
        'seller-warehouses', SellerWarehouse,
        columns=[('Seller Code', '_parent'), ('Warehouse Name', 'warehouse_name'),
                 ('Warehouse Name (AR)', 'warehouse_name_ar'),
                 ('Location', 'location'), ('Location (AR)', 'location_ar')],
        unique=None, label='Seller Warehouses',
        parents=[('Seller Code', '_parent', Seller, 'seller_code', 'seller_id')],
    )

    # Buyer Banks
    register_io(
        'buyer-banks', BuyerBank,
        columns=[('Buyer Code', '_parent'), ('Bank Name', 'bank_name'),
                 ('Bank Name (AR)', 'bank_name_ar'), ('Account Number', 'account_number'),
                 ('Branch', 'branch'), ('Branch (AR)', 'branch_ar'),
                 ('SWIFT', 'swift_code'), ('IBAN', 'iban'), ('Primary', 'is_primary')],
        unique=None, label='Buyer Banks',
        parents=[('Buyer Code', '_parent', BuyerMaster, 'buyer_code', 'buyer_id')],
        coerce={'is_primary': _to_bool},
    )

    # Vendor Banks (uses *_en field names)
    register_io(
        'vendor-banks', VendorBank,
        columns=[('Vendor Code', '_parent'), ('Bank Name', 'bank_name_en'),
                 ('Bank Name (AR)', 'bank_name_ar'), ('Account Number', 'account_number'),
                 ('Branch', 'branch_en'), ('Branch (AR)', 'branch_ar'),
                 ('SWIFT', 'swift_code'), ('IBAN', 'iban'), ('Primary', 'is_primary')],
        unique=None, label='Vendor Banks',
        parents=[('Vendor Code', '_parent', VendorMaster, 'vendor_code', 'vendor_id')],
        coerce={'is_primary': _to_bool},
    )

    # Employee Banks
    register_io(
        'employee-banks', EmployeeBank,
        columns=[('Employee Code', '_parent'), ('Bank Name', 'bank_name'),
                 ('Bank Name (AR)', 'bank_name_ar'), ('Account Number', 'account_number'),
                 ('Branch', 'branch'), ('Branch (AR)', 'branch_ar'),
                 ('SWIFT', 'swift_code'), ('IBAN', 'iban'), ('Primary', 'is_primary')],
        unique=None, label='Employee Banks',
        parents=[('Employee Code', '_parent', Employee, 'employee_code', 'employee_id')],
        coerce={'is_primary': _to_bool},
    )

    # ══════════════════════════════════════════════════════════════
    #  Payroll (Salary Consolidation) and Journal Entry
    # ══════════════════════════════════════════════════════════════
    from models import SalaryConsolidation, JournalEntry

    # Salary Consolidation — export + import (add-new by sheet_no)
    register_io(
        'salary-consolidation', SalaryConsolidation,
        columns=[('Sheet No', 'sheet_no'), ('Month', 'month'), ('Name', 'name'),
                 ('Profession', 'profession'), ('Nationality', 'nationality'),
                 ('Iqama', 'iqama'), ('Department', 'department'), ('Kafeel', 'kafeel'),
                 ('Day/Hour Salary', 'day_hour_salary'), ('Allowance', 'allowance'),
                 ('Days', 'days'), ('Fridays', 'fridays'), ('Holidays', 'holidays'),
                 ('Absent', 'absent'), ('Monthly Salary', 'monthly_salary'),
                 ('OT Hours', 'ot_hour'), ('OT Amount', 'ot_amount'), ('Bonus', 'bonus'),
                 ('Total Salary', 'total_salary'), ('Advance', 'advance'),
                 ('Salary Payable', 'salary_payable'), ('Status', 'status'),
                 ('Bank Code', 'bank_code'), ('IBAN', 'iban_no')],
        unique='sheet_no', label='Salary Consolidation',
        coerce={'day_hour_salary': _to_dec, 'allowance': _to_dec, 'days': _to_dec,
                'monthly_salary': _to_dec, 'ot_hour': _to_dec, 'ot_amount': _to_dec,
                'bonus': _to_dec, 'total_salary': _to_dec, 'advance': _to_dec,
                'salary_payable': _to_dec},
    )

    # Journal Entry — EXPORT ONLY in practice (page is view-only).
    register_io(
        'journal-entries', JournalEntry,
        columns=[('JE No', 'je_no'), ('Origin', 'origion'), ('Origin Type', 'origin_type'),
                 ('Reference', 'refrence'), ('Posting Date', 'posting_date'),
                 ('Due Date', 'due_date'), ('Document Date', 'document_date'),
                 ('Narration', 'narration')],
        unique='je_no', label='Journal Entries',
    )