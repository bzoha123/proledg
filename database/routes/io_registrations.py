"""
Register master-page models with the generic import/export tool (io_tools).

Import this module's `register_all()` once at app startup (after models are
imported). Purchases and Sales documents are deliberately excluded.

Each entry: register_io(key, model, columns=[(header, attr), ...], unique=attr)
"""

from database.routes.io_tools import register_io


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