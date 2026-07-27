"""
Employee Payroll Management Module — 3-stage workflow.

Blueprint name and the list endpoint are kept as `payroll` / `payroll_list`
so the existing sidebar link (url_for('payroll.payroll_list')) keeps working.

Stages:  Initial  ->  Approved  ->  Post
    Initial   : fully editable, rows can be added/removed
    Approved  : values read-only, no add/remove (role-gated)
    Post      : locked entirely

Data sources (established from the schema):
    filter + kafeel/buyer/department/location/profession -> EmployeeWorkAllocation
    basic_salary/salary_category/salary_type/po_rate/nationality/iqama/name -> Employee
    bank_code/iban -> EmployeeBank (primary)
    buyer_name display -> BuyerMaster.buyer_name_en
    day_hour, ot_rate -> no master; editable, default 0
"""

from datetime import datetime, timedelta

from flask import (
    Blueprint, render_template, request, jsonify, session, current_app
)
from flask_login import login_required, current_user

from models import (
    db, SalaryConsolidation, Employee, EmployeeWorkAllocation,
    EmployeeBank, BuyerMaster, ActivityLog, next_payroll_id,
)

payroll_bp = Blueprint('payroll', __name__)


# ══════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════
def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en


def _pd(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return None


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _count_days_and_fridays(d1, d2):
    """Inclusive calendar-day count and Friday count between two dates."""
    if not d1 or not d2 or d2 < d1:
        return 0, 0
    days = (d2 - d1).days + 1
    fridays = sum(
        1 for i in range(days) if (d1 + timedelta(days=i)).weekday() == 4
    )
    return days, fridays


def _employee_bank(emp_id):
    """(bank_code, iban) from the employee's primary bank, else ('','')."""
    b = (EmployeeBank.query
         .filter_by(employee_id=emp_id)
         .order_by(EmployeeBank.is_primary.desc(), EmployeeBank.id.asc())
         .first())
    if not b:
        return '', ''
    return (b.bank_name or ''), (b.iban or '')


def _buyer_name(buyer_id):
    if not buyer_id:
        return ''
    b = BuyerMaster.query.get(buyer_id)
    return (b.buyer_name_en if b else '') or ''


def _audit(action, row_id, detail=''):
    """Best-effort audit entry. Never breaks the main transaction."""
    try:
        db.session.add(ActivityLog(
            user_id=getattr(current_user, 'id', None),
            action=action, target='payroll', target_id=row_id,
            detail=detail,
            ip_address=request.remote_addr,
        ))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  Calculation engine  (spec formulas)
# ══════════════════════════════════════════════════════════════════
def _recalc(row):
    """
    Recompute every derived field from the stored inputs, following the spec.

    Inputs (stored / editable): basic_salary, allowance, day_hour, days,
        fridays, holidays, absent, total_hours, extra_ot, ot_rate, bonus,
        deduction, advance, credit, paid_balance, po_rate, salary_type.
    """
    basic   = _num(row.basic_salary)
    allow   = _num(row.allowance)
    days    = _int(row.days)
    fridays = _int(row.fridays)
    holidays = _int(row.holidays)
    absent  = _int(row.absent)
    day_hour = _num(row.day_hour_salary)          # working hours per day
    total_hours = _num(row.total_hours)
    extra_ot = _num(row.extra_ot_hour)
    ot_rate = _num(row.ot_rate)
    bonus   = _num(row.bonus)
    deduction = _num(row.deduction)
    advance = _num(row.advance)
    credit  = _num(row.credit)
    paid    = _num(row.paid_balance)
    po_rate = _num(row.po_rate)

    # OT Hour = (Days - Fridays - Holidays - Absent) * Day Hour
    ot_hour = max(days - fridays - holidays - absent, 0) * day_hour
    row.ot_hour = round(ot_hour, 2)

    # Working Hour = Total Hours - OT Hour (never negative: Per-Hour starts
    # at 0 until the timesheet Total Hours is entered)
    working_hour = max(total_hours - ot_hour, 0)
    row.working_hour = round(working_hour, 2)

    # Monthly Salary
    stype = (row.salary_type or '').strip().lower()
    if stype in ('per hour', 'perhour', 'hour', 'hourly'):
        # Per Hour: Basic Salary x Working Hour (0 until timesheet entered)
        monthly = basic * working_hour
    else:
        # Per Month: Daily = (Basic + Allowance)/Days; x (Days - Absent)
        daily = (basic + allow) / days if days else 0.0
        monthly = daily * (days - absent)
    row.monthly_salary = round(monthly, 2)

    # OT Amount = (OT Hour x OT Rate) + (Extra OT x OT Rate)
    ot_amount = (ot_hour * ot_rate) + (extra_ot * ot_rate)
    row.ot_amount = round(ot_amount, 2)

    # Total Salary = Monthly + OT Amount + Bonus - Deduction
    total_salary = monthly + ot_amount + bonus - deduction
    row.total_salary = round(total_salary, 2)

    # Salary Payable = Total Salary - Advance - Credit
    salary_payable = total_salary - advance - credit
    row.salary_payable = round(salary_payable, 2)

    # Balance = Salary Payable - Paid
    row.balance = round(salary_payable - paid, 2)

    # Invoice Amount = PO Rate x Total Hours
    row.invoice_amount = round(po_rate * total_hours, 2)


# ══════════════════════════════════════════════════════════════════
#  Duplicate-employee (30-day) evaluation
# ══════════════════════════════════════════════════════════════════
def _duplicate_map(month):
    """
    For a given month, return {employee_id: total_days} across ALL payrolls
    (spec rule 11: regardless of payroll_id). Used for row colouring.
    """
    rows = (SalaryConsolidation.query
            .filter(SalaryConsolidation.month == month)
            .all())
    totals = {}
    counts = {}
    for r in rows:
        if r.employee_id is None:
            continue
        totals[r.employee_id] = totals.get(r.employee_id, 0) + _int(r.days)
        counts[r.employee_id] = counts.get(r.employee_id, 0) + 1
    return totals, counts


def _dupe_status(emp_id, month, totals=None, counts=None):
    """Return (color, is_duplicate, total_days). color: white/yellow/red."""
    if totals is None or counts is None:
        totals, counts = _duplicate_map(month)
    total_days = totals.get(emp_id, 0)
    is_dupe = counts.get(emp_id, 0) > 1
    if not is_dupe:
        return 'white', False, total_days
    return ('red' if total_days > 30 else 'yellow'), True, total_days


def _can_override(user):
    """Payroll Manager / Administrator may save >30-day duplicates."""
    role = (getattr(user, 'role', '') or '').lower()
    return role in ('admin', 'administrator', 'payroll manager', 'payroll_manager')


# ══════════════════════════════════════════════════════════════════
#  Pages
# ══════════════════════════════════════════════════════════════════
@payroll_bp.route('/')
@login_required
def payroll_list():
    return render_template('payroll/list.html')


# ── Filter dropdown sources ───────────────────────────────────────
@payroll_bp.route('/filters')
@login_required
def payroll_filters():
    """Distinct kafeel / buyer / department / location from work allocations."""
    def _distinct(col):
        vals = (db.session.query(col)
                .filter(col.isnot(None), col != '')
                .distinct().all())
        return sorted({v[0] for v in vals if v[0]})

    buyers = [{'id': b.id, 'name': b.buyer_name_en}
              for b in BuyerMaster.query
              .order_by(BuyerMaster.buyer_name_en).all()]

    return jsonify({
        'kafeel':      _distinct(EmployeeWorkAllocation.kafeel),
        'department':  _distinct(EmployeeWorkAllocation.buyer_department),
        'location':    _distinct(EmployeeWorkAllocation.location),
        'buyers':      buyers,
    })


# ── Grid data ─────────────────────────────────────────────────────
@payroll_bp.route('/data')
@login_required
def payroll_data():
    q = SalaryConsolidation.query
    pid = (request.args.get('payroll_id') or '').strip()
    month = (request.args.get('month') or '').strip()
    if pid:
        q = q.filter(SalaryConsolidation.payroll_id == pid)
    if month:
        q = q.filter(SalaryConsolidation.month == month)
    rows = q.order_by(SalaryConsolidation.payroll_id,
                      SalaryConsolidation.name).all()

    # Duplicate colouring is month-scoped and global across payrolls.
    cache = {}
    out = []
    for r in rows:
        if r.month not in cache:
            cache[r.month] = _duplicate_map(r.month)
        totals, counts = cache[r.month]
        color, is_dupe, total_days = _dupe_status(
            r.employee_id, r.month, totals, counts)
        d = r.to_dict()
        posted = (r.payroll_flow_status or 'Initial') == 'Post'
        d['row_color'] = 'gray' if posted else color
        d['is_duplicate'] = is_dupe
        d['dupe_total_days'] = total_days
        out.append(d)
    return jsonify(out)


@payroll_bp.route('/next-id')
@login_required
def payroll_next_id():
    return jsonify({'payroll_id': next_payroll_id()})


# ══════════════════════════════════════════════════════════════════
#  Stage 1 — Generation
# ══════════════════════════════════════════════════════════════════
def _match_key(month, buyer_id, department, location, kafeel, salary_order):
    return (month or '', str(buyer_id or ''), department or '',
            location or '', kafeel or '', salary_order or '')


def _build_row(e, wa, payroll_id, salary_order, d1, d2, month_name,
               days, fridays, buyer_id, department, location, kafeel):
    """Create one SalaryConsolidation row for an employee (unsaved)."""
    bank_code, iban = _employee_bank(e.id)
    row = SalaryConsolidation(
        payroll_id=payroll_id, payroll_status='Single',
        salary_order=salary_order,
        month_from=d1, month_to=d2, month=month_name,
        buyer_id=buyer_id, buyer_name=_buyer_name(buyer_id),
        department=department, location=location, kafeel=kafeel,
        sheet_no='',
        employee_id=e.id, name=(e.name or (wa.name if wa else '')),
        profession=(wa.profession if wa else ''),
        nationality=(e.nationality or ''),
        iqama=(e.iqama_number or ''),
        salary_category=(e.salary_category or ''),
        salary_type=(e.salary_type or ''),
        day_hour_salary=0,                     # day_hour: no master, editable
        basic_salary=_num(e.basic_salary),
        allowance=_num(e.total_allowances),
        days=days, fridays=fridays, holidays=0, absent=0,
        total_hours=0, extra_ot_hour=0, ot_rate=0,
        bonus=0, deduction=0, advance=0, credit=0, paid_balance=0,
        iqama_expiry=e.iqama_expiry,
        status='Active',
        bank_code=bank_code, iban_no=iban,
        po_rate=_num(e.po_rate),
        payroll_flow_status='Initial',
    )
    _recalc(row)
    return row


@payroll_bp.route('/check', methods=['POST'])
@login_required
def payroll_check():
    """Return an existing payroll_id if one already matches the criteria."""
    f = request.form
    d1 = _pd(f.get('month_from'))
    month_name = d1.strftime('%B-%Y') if d1 else ''
    buyer_id = _int(f.get('buyer_id')) or None
    department = (f.get('department') or '').strip()
    location = (f.get('location') or '').strip()
    kafeel = (f.get('kafeel') or '').strip()
    salary_order = (f.get('salary_order') or '').strip()

    existing = (SalaryConsolidation.query
                .filter(SalaryConsolidation.month == month_name)
                .filter(SalaryConsolidation.buyer_id == buyer_id)
                .filter(SalaryConsolidation.department == department)
                .filter(SalaryConsolidation.location == location)
                .filter(SalaryConsolidation.kafeel == kafeel)
                .filter(SalaryConsolidation.salary_order == salary_order)
                .first())
    if existing and existing.payroll_id:
        return jsonify({'exists': True, 'payroll_id': existing.payroll_id})
    return jsonify({'exists': False})


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
        return jsonify({'ok': False, 'error': _t('Month From cannot be after Month To.',
                                                 'تاريخ البداية لا يمكن أن يكون بعد النهاية.')}), 400

    buyer_id = _int(f.get('buyer_id')) or None
    department = (f.get('department') or '').strip()
    location = (f.get('location') or '').strip()
    kafeel = (f.get('kafeel') or '').strip()
    salary_order = (f.get('salary_order') or '').strip()
    month_name = d1.strftime('%B-%Y')

    # Duplicate-payroll guard (spec Stage 1 validation).
    existing = (SalaryConsolidation.query
                .filter(SalaryConsolidation.month == month_name)
                .filter(SalaryConsolidation.buyer_id == buyer_id)
                .filter(SalaryConsolidation.department == department)
                .filter(SalaryConsolidation.location == location)
                .filter(SalaryConsolidation.kafeel == kafeel)
                .filter(SalaryConsolidation.salary_order == salary_order)
                .first())
    if existing and existing.payroll_id:
        return jsonify({
            'ok': False, 'duplicate': True,
            'payroll_id': existing.payroll_id,
            'error': _t(f'Payroll already exists. Payroll ID: {existing.payroll_id}',
                        f'كشف الرواتب موجود بالفعل. رقم الكشف: {existing.payroll_id}')
        }), 409

    # Match employees through their work allocation.
    wq = EmployeeWorkAllocation.query.filter(
        EmployeeWorkAllocation.status == 'active')
    if kafeel:
        wq = wq.filter(EmployeeWorkAllocation.kafeel == kafeel)
    if buyer_id:
        wq = wq.filter(EmployeeWorkAllocation.buyer_id == buyer_id)
    if department:
        wq = wq.filter(EmployeeWorkAllocation.buyer_department == department)
    if location:
        wq = wq.filter(EmployeeWorkAllocation.location == location)
    allocations = wq.all()

    if not allocations:
        return jsonify({'ok': False, 'error': _t(
            'No active employees match the selected criteria.',
            'لا يوجد موظفون نشطون مطابقون للمعايير.')}), 400

    days, fridays = _count_days_and_fridays(d1, d2)
    payroll_id = next_payroll_id()
    created = 0
    seen = set()
    for wa in allocations:
        if wa.employee_id in seen:
            continue
        seen.add(wa.employee_id)
        e = Employee.query.get(wa.employee_id)
        if not e or not getattr(e, 'is_active', True):
            continue
        row = _build_row(e, wa, payroll_id, salary_order, d1, d2, month_name,
                         days, fridays, buyer_id, department, location, kafeel)
        db.session.add(row)
        created += 1

    if not created:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t(
            'No active employees match the selected criteria.',
            'لا يوجد موظفون نشطون مطابقون للمعايير.')}), 400

    _audit('create', None,
           f'Generated payroll {payroll_id}: {created} employees, {month_name}')
    try:
        db.session.commit()
        return jsonify({'ok': True, 'created': created,
                        'payroll_id': payroll_id})
    except Exception:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not generate payroll.',
                                                 'تعذّر إنشاء كشف الرواتب.')}), 500


# ══════════════════════════════════════════════════════════════════
#  Stage 2 — Editing
# ══════════════════════════════════════════════════════════════════
_EDITABLE_NUM = ['absent', 'total_hours', 'extra_ot_hour', 'bonus',
                 'deduction', 'advance', 'credit', 'paid_balance',
                 'holidays', 'ot_rate', 'day_hour_salary']
_EDITABLE_INT = ('absent', 'holidays')


def _flow(row):
    return (row.payroll_flow_status or 'Initial')


@payroll_bp.route('/<int:row_id>/json')
@login_required
def payroll_json(row_id):
    return jsonify(SalaryConsolidation.query.get_or_404(row_id).to_dict())


@payroll_bp.route('/<int:row_id>/edit', methods=['POST'])
@login_required
def payroll_edit(row_id):
    row = SalaryConsolidation.query.get_or_404(row_id)
    if _flow(row) == 'Post':
        return jsonify({'ok': False, 'error': _t(
            'Posted payroll is locked.', 'كشف الرواتب المرحّل مقفل.')}), 403
    if _flow(row) == 'Approved':
        # Approved: values read-only except sheet_no/comments.
        f = request.form
        if 'sheet_no' in f:
            row.sheet_no = (f.get('sheet_no') or '').strip()
        try:
            db.session.commit()
            return jsonify({'ok': True, 'row': row.to_dict()})
        except Exception:
            db.session.rollback()
            return jsonify({'ok': False, 'error': _t('Could not update.',
                                                     'تعذّر التحديث.')}), 500

    # Initial: fully editable.
    f = request.form
    if 'sheet_no' in f:
        row.sheet_no = (f.get('sheet_no') or '').strip()
    for fld in _EDITABLE_NUM:
        if fld in f:
            val = _num(f.get(fld))
            setattr(row, fld, int(val) if fld in _EDITABLE_INT else val)
    _recalc(row)

    # Duplicate 30-day rule: block save >30 without override.
    color, is_dupe, total_days = _dupe_status(row.employee_id, row.month)
    if is_dupe and total_days > 30 and not _can_override(current_user):
        db.session.rollback()
        return jsonify({'ok': False, 'blocked': True, 'total_days': total_days,
                        'error': _t(
            f'Employee payroll exceeds 30 days ({total_days}). Override permission required.',
            f'رواتب الموظف تتجاوز 30 يومًا ({total_days}). يلزم إذن التجاوز.')}), 403

    _audit('edit', row.id, f'Edited payroll row {row.id}')
    try:
        db.session.commit()
        return jsonify({'ok': True, 'row': row.to_dict(),
                        'row_color': color, 'total_days': total_days})
    except Exception:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not update.',
                                                 'تعذّر التحديث.')}), 500


@payroll_bp.route('/<int:row_id>/delete', methods=['POST'])
@login_required
def payroll_delete(row_id):
    row = SalaryConsolidation.query.get_or_404(row_id)
    if _flow(row) != 'Initial':
        return jsonify({'ok': False, 'error': _t(
            'Only Initial payroll rows can be deleted.',
            'يمكن حذف صفوف الكشف في حالة "أولي" فقط.')}), 403
    _audit('delete', row.id, f'Deleted payroll row {row.id} ({row.name})')
    try:
        db.session.delete(row)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not delete.',
                                                 'تعذّر الحذف.')}), 500


# ── Add missing employee (constrained to payroll criteria) ────────
@payroll_bp.route('/<payroll_id>/available-employees')
@login_required
def payroll_available_employees(payroll_id):
    """Employees matching the payroll criteria not already in this payroll."""
    ref = (SalaryConsolidation.query
           .filter_by(payroll_id=payroll_id).first())
    if not ref:
        return jsonify([])
    already = {r.employee_id for r in SalaryConsolidation.query
               .filter_by(payroll_id=payroll_id).all()}

    wq = EmployeeWorkAllocation.query.filter(
        EmployeeWorkAllocation.status == 'active')
    if ref.kafeel:
        wq = wq.filter(EmployeeWorkAllocation.kafeel == ref.kafeel)
    if ref.buyer_id:
        wq = wq.filter(EmployeeWorkAllocation.buyer_id == ref.buyer_id)
    if ref.department:
        wq = wq.filter(EmployeeWorkAllocation.buyer_department == ref.department)
    if ref.location:
        wq = wq.filter(EmployeeWorkAllocation.location == ref.location)

    out, seen = [], set()
    for wa in wq.all():
        eid = wa.employee_id
        if eid in seen:
            continue
        seen.add(eid)
        # allow_duplicate: an employee already present can be added again
        # (Double salary), so we still list them but flag it.
        out.append({
            'employee_id': eid, 'name': wa.name or '',
            'profession': wa.profession or '',
            'already_in_payroll': eid in already,
        })
    return jsonify(out)


@payroll_bp.route('/<payroll_id>/add-employee', methods=['POST'])
@login_required
def payroll_add_employee(payroll_id):
    ref = (SalaryConsolidation.query
           .filter_by(payroll_id=payroll_id).first())
    if not ref:
        return jsonify({'ok': False, 'error': _t('Payroll not found.',
                                                 'الكشف غير موجود.')}), 404
    if _flow(ref) != 'Initial':
        return jsonify({'ok': False, 'error': _t(
            'Employees can only be added while payroll is Initial.',
            'يمكن إضافة الموظفين في حالة "أولي" فقط.')}), 403

    emp_id = _int(request.form.get('employee_id'))
    e = Employee.query.get(emp_id)
    if not e:
        return jsonify({'ok': False, 'error': _t('Employee not found.',
                                                 'الموظف غير موجود.')}), 404

    # Confirm the employee matches the payroll criteria.
    wa = (EmployeeWorkAllocation.query
          .filter_by(employee_id=emp_id, status='active')
          .filter(EmployeeWorkAllocation.kafeel == ref.kafeel)
          .filter(EmployeeWorkAllocation.buyer_id == ref.buyer_id)
          .filter(EmployeeWorkAllocation.buyer_department == ref.department)
          .filter(EmployeeWorkAllocation.location == ref.location)
          .first())
    if not wa:
        return jsonify({'ok': False, 'error': _t(
            'Employee does not match this payroll\'s criteria.',
            'الموظف لا يطابق معايير هذا الكشف.')}), 400

    days, fridays = _count_days_and_fridays(ref.month_from, ref.month_to)
    row = _build_row(e, wa, ref.payroll_id, ref.salary_order,
                     ref.month_from, ref.month_to, ref.month, days, fridays,
                     ref.buyer_id, ref.department, ref.location, ref.kafeel)

    # If this employee is already present, mark both as Double.
    dupes = (SalaryConsolidation.query
             .filter_by(payroll_id=payroll_id, employee_id=emp_id).all())
    if dupes:
        row.payroll_status = 'Double'
        for d in dupes:
            d.payroll_status = 'Double'

    db.session.add(row)
    _audit('add_employee', None,
           f'Added employee {emp_id} to payroll {payroll_id}')
    try:
        db.session.commit()
        return jsonify({'ok': True, 'row': row.to_dict()})
    except Exception:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not add employee.',
                                                 'تعذّر إضافة الموظف.')}), 500


# ══════════════════════════════════════════════════════════════════
#  Stage 3 — Approval & Posting
# ══════════════════════════════════════════════════════════════════
_FLOW_NEXT = {'Initial': 'Approved', 'Approved': 'Post'}


@payroll_bp.route('/<payroll_id>/set-flow', methods=['POST'])
@login_required
def payroll_set_flow(payroll_id):
    target = (request.form.get('flow') or '').strip()
    if target not in ('Approved', 'Post'):
        return jsonify({'ok': False, 'error': _t('Invalid state.',
                                                 'حالة غير صالحة.')}), 400
    if not _can_override(current_user):
        return jsonify({'ok': False, 'error': _t(
            'You are not authorized to change the payroll workflow state.',
            'ليس لديك صلاحية لتغيير حالة سير العمل.')}), 403

    rows = (SalaryConsolidation.query
            .filter_by(payroll_id=payroll_id).all())
    if not rows:
        return jsonify({'ok': False, 'error': _t('Payroll not found.',
                                                 'الكشف غير موجود.')}), 404

    current = _flow(rows[0])
    if _FLOW_NEXT.get(current) != target:
        return jsonify({'ok': False, 'error': _t(
            f'Cannot move from {current} to {target}.',
            f'لا يمكن الانتقال من {current} إلى {target}.')}), 400

    for r in rows:
        r.payroll_flow_status = target
    _audit(target.lower(), None,
           f'Payroll {payroll_id} -> {target}')
    try:
        db.session.commit()
        return jsonify({'ok': True, 'flow': target})
    except Exception:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not update state.',
                                                 'تعذّر تحديث الحالة.')}), 500


# ══════════════════════════════════════════════════════════════════
#  Reports  (15 reports, spec section)
# ══════════════════════════════════════════════════════════════════
REPORT_DEFS = [
    ('summary',      'Payroll Summary',            'ملخص الرواتب'),
    ('detail',       'Payroll Detail Report',      'تقرير تفصيلي'),
    ('salary_sheet', 'Salary Sheet',               'كشف الرواتب'),
    ('bank_transfer','Bank Transfer Report',       'تقرير التحويل البنكي'),
    ('overtime',     'Overtime Report',            'تقرير العمل الإضافي'),
    ('advance',      'Advance Report',             'تقرير السلف'),
    ('deduction',    'Deduction Report',           'تقرير الخصومات'),
    ('buyer_wise',   'Buyer-wise Payroll',         'الرواتب حسب المشتري'),
    ('department_wise','Department-wise Payroll',   'الرواتب حسب القسم'),
    ('location_wise','Location-wise Payroll',      'الرواتب حسب الموقع'),
    ('kafeel_wise',  'Kafeel-wise Payroll',        'الرواتب حسب الكفيل'),
    ('invoice',      'Invoice Summary',            'ملخص الفواتير'),
    ('audit',        'Payroll Audit Report',       'تقرير التدقيق'),
    ('duplicate',    'Duplicate Employee Report',  'تقرير الموظفين المكررين'),
    ('exceeding',    'Employees Exceeding 30 Days','تجاوز 30 يومًا'),
]


@payroll_bp.route('/reports')
@login_required
def payroll_reports():
    return render_template('payroll/reports.html',
                           reports=REPORT_DEFS,
                           payroll_id=(request.args.get('payroll_id') or ''))


@payroll_bp.route('/reports/<report>/data')
@login_required
def payroll_report_data(report):
    """Return {columns, rows, title} for the requested report."""
    pid = (request.args.get('payroll_id') or '').strip()
    month = (request.args.get('month') or '').strip()

    q = SalaryConsolidation.query
    if pid:
        q = q.filter(SalaryConsolidation.payroll_id == pid)
    if month:
        q = q.filter(SalaryConsolidation.month == month)
    rows = q.order_by(SalaryConsolidation.payroll_id,
                      SalaryConsolidation.name).all()
    data = [r.to_dict() for r in rows]

    def money(xs, k):
        return round(sum(_num(x.get(k)) for x in xs), 2)

    title = next((en for key, en, ar in REPORT_DEFS if key == report), report)

    # ── Grouping helper for the *-wise reports ────────────────────
    def grouped(key_field, key_label):
        buckets = {}
        for x in data:
            k = x.get(key_field) or '—'
            b = buckets.setdefault(k, {'k': k, 'count': 0, 'total_salary': 0,
                                       'salary_payable': 0, 'invoice_amount': 0})
            b['count'] += 1
            b['total_salary'] += _num(x.get('total_salary'))
            b['salary_payable'] += _num(x.get('salary_payable'))
            b['invoice_amount'] += _num(x.get('invoice_amount'))
        out = [{'group': v['k'], 'employees': v['count'],
                'total_salary': round(v['total_salary'], 2),
                'salary_payable': round(v['salary_payable'], 2),
                'invoice_amount': round(v['invoice_amount'], 2)}
               for v in buckets.values()]
        cols = [(key_label, 'group'), ('Employees', 'employees'),
                ('Total Salary', 'total_salary'),
                ('Salary Payable', 'salary_payable'),
                ('Invoice', 'invoice_amount')]
        return cols, out

    if report == 'summary':
        summary = [{
            'metric': 'Employees', 'value': len(data),
        }, {'metric': 'Total Monthly Salary', 'value': money(data, 'monthly_salary')},
           {'metric': 'Total OT Amount', 'value': money(data, 'ot_amount')},
           {'metric': 'Total Salary', 'value': money(data, 'total_salary')},
           {'metric': 'Total Advance', 'value': money(data, 'advance')},
           {'metric': 'Total Deduction', 'value': money(data, 'deduction')},
           {'metric': 'Total Salary Payable', 'value': money(data, 'salary_payable')},
           {'metric': 'Total Paid', 'value': money(data, 'paid_balance')},
           {'metric': 'Total Balance', 'value': money(data, 'balance')},
           {'metric': 'Total Invoice Amount', 'value': money(data, 'invoice_amount')}]
        cols = [('Metric', 'metric'), ('Value', 'value')]
        return jsonify({'title': title, 'columns': cols, 'rows': summary})

    if report == 'detail':
        cols = [('Payroll', 'payroll_id'), ('Employee', 'name'),
                ('Profession', 'profession'), ('Iqama', 'iqama'),
                ('Type', 'salary_type'), ('Days', 'days'),
                ('Monthly', 'monthly_salary'), ('OT Amt', 'ot_amount'),
                ('Bonus', 'bonus'), ('Deduction', 'deduction'),
                ('Total', 'total_salary'), ('Advance', 'advance'),
                ('Credit', 'credit'), ('Payable', 'salary_payable'),
                ('Paid', 'paid_balance'), ('Balance', 'balance')]
        return jsonify({'title': title, 'columns': cols, 'rows': data})

    if report == 'salary_sheet':
        cols = [('Employee', 'name'), ('Iqama', 'iqama'),
                ('Bank', 'bank_code'), ('IBAN', 'iban_no'),
                ('Total Salary', 'total_salary'),
                ('Advance', 'advance'), ('Deduction', 'deduction'),
                ('Payable', 'salary_payable'), ('Paid', 'paid_balance'),
                ('Balance', 'balance')]
        return jsonify({'title': title, 'columns': cols, 'rows': data})

    if report == 'bank_transfer':
        rows2 = [x for x in data if _num(x.get('salary_payable')) > 0]
        cols = [('Employee', 'name'), ('Bank', 'bank_code'),
                ('IBAN', 'iban_no'), ('Amount', 'salary_payable')]
        return jsonify({'title': title, 'columns': cols, 'rows': rows2})

    if report == 'overtime':
        rows2 = [x for x in data if _num(x.get('ot_amount')) > 0]
        cols = [('Employee', 'name'), ('OT Hrs', 'ot_hour'),
                ('Extra OT', 'extra_ot_hour'), ('OT Rate', 'ot_rate'),
                ('OT Amount', 'ot_amount')]
        return jsonify({'title': title, 'columns': cols, 'rows': rows2})

    if report == 'advance':
        rows2 = [x for x in data if _num(x.get('advance')) > 0]
        cols = [('Employee', 'name'), ('Advance', 'advance'),
                ('Total Salary', 'total_salary'), ('Payable', 'salary_payable')]
        return jsonify({'title': title, 'columns': cols, 'rows': rows2})

    if report == 'deduction':
        rows2 = [x for x in data if _num(x.get('deduction')) > 0]
        cols = [('Employee', 'name'), ('Deduction', 'deduction'),
                ('Total Salary', 'total_salary'), ('Payable', 'salary_payable')]
        return jsonify({'title': title, 'columns': cols, 'rows': rows2})

    if report == 'buyer_wise':
        cols, out = grouped('buyer_name', 'Buyer')
        return jsonify({'title': title, 'columns': cols, 'rows': out})
    if report == 'department_wise':
        cols, out = grouped('department', 'Department')
        return jsonify({'title': title, 'columns': cols, 'rows': out})
    if report == 'location_wise':
        cols, out = grouped('location', 'Location')
        return jsonify({'title': title, 'columns': cols, 'rows': out})
    if report == 'kafeel_wise':
        cols, out = grouped('kafeel', 'Kafeel')
        return jsonify({'title': title, 'columns': cols, 'rows': out})

    if report == 'invoice':
        cols = [('Payroll', 'payroll_id'), ('Employee', 'name'),
                ('PO Rate', 'po_rate'), ('Total Hrs', 'total_hours'),
                ('Invoice Amount', 'invoice_amount')]
        return jsonify({'title': title, 'columns': cols, 'rows': data})

    if report == 'audit':
        logs = (ActivityLog.query
                .filter(ActivityLog.target == 'payroll')
                .order_by(ActivityLog.created_at.desc())
                .limit(500).all())
        rows2 = [{
            'action': l.action or '', 'detail': l.detail or '',
            'user_id': l.user_id, 'ip': l.ip_address or '',
            'when': l.created_at.strftime('%Y-%m-%d %H:%M') if l.created_at else '',
        } for l in logs]
        cols = [('Action', 'action'), ('Detail', 'detail'),
                ('User', 'user_id'), ('IP', 'ip'), ('When', 'when')]
        return jsonify({'title': title, 'columns': cols, 'rows': rows2})

    if report in ('duplicate', 'exceeding'):
        # Month-scoped duplicate totals across all payrolls.
        months = {x.get('month') for x in data if x.get('month')}
        rows2 = []
        for m in months:
            totals, counts = _duplicate_map(m)
            for eid, cnt in counts.items():
                if cnt <= 1:
                    continue
                td = totals.get(eid, 0)
                if report == 'exceeding' and td <= 30:
                    continue
                sample = next((x for x in data
                               if x.get('employee_id') == eid), {})
                rows2.append({
                    'name': sample.get('name', ''), 'month': m,
                    'entries': cnt, 'total_days': td,
                    'flag': 'RED >30' if td > 30 else 'YELLOW ≤30',
                })
        cols = [('Employee', 'name'), ('Month', 'month'),
                ('Entries', 'entries'), ('Total Days', 'total_days'),
                ('Flag', 'flag')]
        return jsonify({'title': title, 'columns': cols, 'rows': rows2})

    return jsonify({'title': title, 'columns': [], 'rows': []})