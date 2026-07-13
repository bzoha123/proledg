"""Salary Consolidation (payroll) module.

Routes:
    /payroll                     list page (AG-Grid)
    /payroll/data                JSON rows for the grid
    /payroll/filters             distinct company / department / kafeel values
    /payroll/generate            build rows for matching employees (preview+save)
    /payroll/<id>/json           single row (for edit)
    /payroll/<id>/edit           update editable fields + recalc
    /payroll/<id>/delete         delete

DEFAULT CALCULATION ASSUMPTIONS (Stage 1 — adjust after review):
    days            = calendar days in the month range (inclusive)
    fridays         = number of Fridays in the range
    monthly_salary  = employee.basic_salary + employee.total_allowances
    allowance       = employee.total_allowances
    day_hour_salary = monthly_salary / days           (per-day rate)
    working_hour    = employee.working_hours (per day, default 8)
    total_hours     = days * working_hour
    ot_rate         = employee.overtime_rate, or (day_hour_salary/working_hour)*overtime_ratio if 0
    ot_amount       = ot_hour * ot_rate
    total_salary    = monthly_salary + ot_amount + bonus - (absent * day_hour_salary)
    salary_payable  = total_salary - advance
    paid_balance    = salary_payable - (already paid)   [starts equal to salary_payable]
    holidays/absent/bonus/advance/ot_hour/extra_ot_hour default 0 and are user-editable.
"""
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required

from models import (db, SalaryConsolidation, next_salary_order,
                    Employee, EmployeeBank)

payroll_bp = Blueprint('payroll', __name__, url_prefix='/payroll')


def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en


def _pd(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


def _count_days_and_fridays(d1, d2):
    """Inclusive calendar-day count and Friday count between two dates."""
    if not d1 or not d2 or d2 < d1:
        return 0, 0
    days = (d2 - d1).days + 1
    fridays = 0
    cur = d1
    while cur <= d2:
        if cur.weekday() == 4:      # Monday=0 ... Friday=4
            fridays += 1
        cur += timedelta(days=1)
    return days, fridays


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _employee_bank(emp_id):
    b = (EmployeeBank.query
         .filter_by(employee_id=emp_id)
         .order_by(EmployeeBank.is_primary.desc(), EmployeeBank.id.asc())
         .first())
    if not b:
        return '', ''
    return (b.bank_name or ''), (b.iban or '')


def _recalc(row):
    """Recompute derived money fields from the stored inputs on a row."""
    day_rate = float(row.day_hour_salary or 0)
    ot_amount = float(row.ot_hour or 0) * float(row.ot_rate or 0)
    row.ot_amount = round(ot_amount, 2)
    absent_deduction = float(row.absent or 0) * day_rate
    total = float(row.monthly_salary or 0) + ot_amount + float(row.bonus or 0) - absent_deduction
    row.total_salary = round(total, 2)
    row.salary_payable = round(total - float(row.advance or 0), 2)
    # paid_balance left as-is if already set, else mirror payable
    if row.paid_balance is None:
        row.paid_balance = row.salary_payable


# ── Pages ─────────────────────────────────────────────────────────
@payroll_bp.route('/')
@login_required
def payroll_list():
    return render_template('payroll/list.html')


@payroll_bp.route('/data')
@login_required
def payroll_data():
    rows = SalaryConsolidation.query.order_by(SalaryConsolidation.id.desc()).all()
    return jsonify([r.to_dict() for r in rows])


@payroll_bp.route('/filters')
@login_required
def payroll_filters():
    """Distinct company / department / kafeel values for the Add-Payroll form."""
    def distinct(col):
        q = (db.session.query(col).filter(col.isnot(None), col != '')
             .distinct().order_by(col).all())
        return [r[0] for r in q]
    return jsonify({
        'companies':   distinct(Employee.company),
        'departments': distinct(Employee.department),
        'kafeels':     distinct(Employee.kafeel_name),
    })


@payroll_bp.route('/next-order')
@login_required
def payroll_next_order():
    return jsonify({'salary_order': next_salary_order()})


# ── Generate payroll rows for matching employees ──────────────────
@payroll_bp.route('/generate', methods=['POST'])
@login_required
def payroll_generate():
    f = request.form
    d1 = _pd(f.get('month_from'))
    d2 = _pd(f.get('month_to'))
    if not d1 or not d2:
        return jsonify({'ok': False, 'error': _t('Select a valid month range.',
                                                 'اختر نطاق شهر صالح.')}), 400
    if d2 < d1:
        return jsonify({'ok': False, 'error': _t('End date must be after start date.',
                                                 'تاريخ النهاية يجب أن يكون بعد البداية.')}), 400

    company    = (f.get('company', '') or '').strip()
    department = (f.get('department', '') or '').strip()
    kafeel     = (f.get('kafeel', '') or '').strip()
    salary_order = (f.get('salary_order', '') or '').strip() or next_salary_order()

    # Filter employees by the chosen criteria (only non-empty filters apply).
    q = Employee.query
    if company:
        q = q.filter(Employee.company == company)
    if department:
        q = q.filter(Employee.department == department)
    if kafeel:
        q = q.filter(Employee.kafeel_name == kafeel)
    employees = q.order_by(Employee.name).all()
    if not employees:
        return jsonify({'ok': False, 'error': _t('No employees match the selected filters.',
                                                 'لا يوجد موظفون مطابقون.')}), 400

    days, fridays = _count_days_and_fridays(d1, d2)
    month_name = d1.strftime('%B')
    created = 0
    for e in employees:
        basic = float(e.basic_salary or 0)
        allow = float(e.total_allowances or 0)
        monthly = basic + allow
        working_hr = float(e.working_hours or 8) or 8
        day_rate = round(monthly / days, 2) if days else 0.0
        ot_rate = float(e.overtime_rate or 0)
        if ot_rate == 0 and working_hr:
            ot_rate = round((day_rate / working_hr) * float(e.overtime_ratio or 1.5), 2)
        bank_code, iban = _employee_bank(e.id)

        row = SalaryConsolidation(
            employee_id=e.id, salary_order=salary_order,
            month_from=d1, month_to=d2, month=month_name,
            department=e.department, kafeel=e.kafeel_name,
            name=e.name, profession=e.profession, nationality=e.nationality,
            iqama=e.iqama_number, iqama_expiry=e.iqama_expiry,
            day_hour_salary=day_rate, allowance=allow,
            days=days, fridays=fridays, holidays=0, absent=0,
            monthly_salary=round(monthly, 2),
            working_hour=working_hr, total_hours=round(days * working_hr, 2),
            ot_hour=0, extra_ot_hour=0, ot_rate=ot_rate, ot_amount=0,
            bonus=0, advance=0,
            bank_code=bank_code, iban_no=iban,
            status='Draft',
        )
        _recalc(row)
        db.session.add(row)
        created += 1

    try:
        db.session.commit()
        return jsonify({'ok': True, 'created': created, 'salary_order': salary_order})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not generate payroll.',
                                                 'تعذّر إنشاء كشف الرواتب.')}), 500


# ── Edit editable fields + recalc ─────────────────────────────────
_EDITABLE_NUM = ['holidays', 'absent', 'ot_hour', 'extra_ot_hour',
                 'bonus', 'advance', 'paid_balance', 'ot_rate']


@payroll_bp.route('/<int:row_id>/json')
@login_required
def payroll_json(row_id):
    return jsonify(SalaryConsolidation.query.get_or_404(row_id).to_dict())


@payroll_bp.route('/<int:row_id>/edit', methods=['POST'])
@login_required
def payroll_edit(row_id):
    row = SalaryConsolidation.query.get_or_404(row_id)
    f = request.form
    for fld in _EDITABLE_NUM:
        if fld in f:
            val = _num(f.get(fld), 0.0)
            if fld in ('holidays', 'absent'):
                setattr(row, fld, int(val))
            else:
                setattr(row, fld, val)
    if 'status' in f:
        st = (f.get('status') or 'Draft').strip()
        row.status = st if st in ('Draft', 'Approved', 'Posted', 'Cancelled') else 'Draft'
    _recalc(row)
    try:
        db.session.commit()
        return jsonify({'ok': True, 'row': row.to_dict()})
    except Exception:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not update.', 'تعذّر التحديث.')}), 500


@payroll_bp.route('/<int:row_id>/delete', methods=['POST'])
@login_required
def payroll_delete(row_id):
    row = SalaryConsolidation.query.get_or_404(row_id)
    try:
        db.session.delete(row)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not delete.', 'تعذّر الحذف.')}), 500