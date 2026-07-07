import os, uuid
from datetime import datetime, date
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app, jsonify, session)
from flask_login import login_required, current_user
from models import (db, Employee, EmployeeAllowance, AllowanceType,
                    EmployeeBank, EmployeeDocument, ProfessionMaster, BuyerMaster,
                    EmployeeProfession)
from functools import wraps

employees_bp = Blueprint('employees', __name__)

def _t(en, ar): return ar if session.get('lang') == 'ar' else en

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            flash(_t('Access denied.', 'الوصول مرفوض'), 'danger')
            return redirect(url_for('employees.list_employees'))
        return f(*args, **kwargs)
    return decorated

def generate_code():
    last = Employee.query.order_by(Employee.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f'EMP-{num:04d}'

def parse_date(v):
    if not v: return None
    try: return datetime.strptime(v, '%Y-%m-%d').date()
    except (ValueError, TypeError): return None

def save_upload(file, emp_id, subfolder='employees'):
    if not file or not file.filename: return None
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in {'pdf', 'jpg', 'jpeg', 'png'}: return None
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, str(emp_id))
    os.makedirs(folder, exist_ok=True)
    fname = f'{uuid.uuid4().hex}.{ext}'
    file.save(os.path.join(folder, fname))
    return os.path.join(subfolder, str(emp_id), fname)


def save_photo(emp_id, req):
    """Save the employee photo (single image). Updates employees.photo_path."""
    f = req.files.get('photo')
    if not f or not f.filename:
        return
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in {'jpg', 'jpeg', 'png', 'webp'}:
        return
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'employees', str(emp_id))
    os.makedirs(folder, exist_ok=True)
    fname = f'photo_{uuid.uuid4().hex}.{ext}'
    f.save(os.path.join(folder, fname))
    emp = Employee.query.get(emp_id)
    if emp:
        emp.photo_path = os.path.join('employees', str(emp_id), fname)


def save_documents(emp_id, req):
    files = req.files.getlist('documents[]')
    types = req.form.getlist('document_type[]')
    for i, f in enumerate(files):
        if not f or not f.filename:
            continue
        path = save_upload(f, emp_id)
        if not path:
            continue
        dtype = types[i] if i < len(types) else ''
        db.session.add(EmployeeDocument(
            employee_id=emp_id,
            document_type=(dtype or '').strip(),
            file_path=path,
            original_name=f.filename,
        ))


def save_professions(emp_id, req):
    """Save multiple professions from profession_ids form field.
    Stores each profession's name (EN + AR) in employee_professions,
    and mirrors the first selected profession into the employee's single
    profession_id / profession / profession_ar columns (grid & view use them)."""
    from models import ProfessionMaster, Employee
    EmployeeProfession.query.filter_by(employee_id=emp_id).delete()
    prof_ids = req.form.getlist('profession_ids')
    clean_ids = [int(p) for p in prof_ids if p and str(p).strip()]
    for pid in clean_ids:
        pm = ProfessionMaster.query.get(pid)
        db.session.add(EmployeeProfession(
            employee_id=emp_id,
            profession_id=pid,
            profession_name=(pm.name_en if pm else None),
            profession_name_ar=(pm.name_ar if pm else None),
        ))
    # mirror primary (first) into single columns for grid/view display
    emp = Employee.query.get(emp_id)
    if emp is not None:
        if clean_ids:
            primary = ProfessionMaster.query.get(clean_ids[0])
            if primary:
                emp.profession_id = primary.id
                emp.profession    = primary.name_en
                emp.profession_ar = primary.name_ar or ''
        else:
            emp.profession_id = None
            emp.profession = ''
            emp.profession_ar = ''


TEXT_FIELDS = [
    'name', 'name_ar', 'kafeel_name', 'kafeel_name_ar', 'kafeel_reference', 'kafeel_reference_ar',
    'nationality', 'nationality_ar', 'passport_number', 'entry_number', 'iqama_number',
    'profession', 'profession_ar', 'education', 'education_ar',
    'mobile', 'address', 'address_ar', 'email', 'home_city', 'home_city_ar',
    'employee_reference', 'employee_reference_ar',
    'po_number', 'salary_type', 'kafalat_number', 'po_rate_unit',
    'department', 'department_ar', 'section', 'section_ar',
    'company', 'company_ar', 'work_month', 'work_status', 'shift_type',
    'forman', 'forman_ar', 'hostel_name', 'hostel_name_ar', 'room_number',
    'hostel_location', 'hostel_location_ar',
    'crn', 'crn_ar', 'insurance_company', 'insurance_company_ar', 'labour_office',
    'passport_location', 'document_type',
]
FLOAT_FIELDS = ['po_rate', 'basic_salary', 'working_hours', 'overtime_ratio']
DATE_FIELDS  = ['arrival_date', 'birth_date', 'passport_expiry', 'iqama_expiry',
                'joining_date', 'insurance_expiry', 'end_date_work']

def _to_float(v):
    try: return float(v or 0)
    except (ValueError, TypeError): return 0.0

def bind_employee(emp, f):
    for field in TEXT_FIELDS:
        setattr(emp, field, (f.get(field, '') or '').strip())
    for field in FLOAT_FIELDS:
        setattr(emp, field, _to_float(f.get(field)))
    for field in DATE_FIELDS:
        setattr(emp, field, parse_date(f.get(field)))

    emp.is_active = f.get('is_active') == 'on'
    emp.is_muslim = f.get('is_muslim') == 'on'
    emp.auto_code = f.get('auto_code') == 'on'

    buyer_id = f.get('buyer_id')
    emp.buyer_id = int(buyer_id) if buyer_id else None

    emp.overtime_rate = _calc_overtime_rate(emp)
    emp.net_salary = (emp.basic_salary or 0) + (emp.total_allowances or 0)

def _calc_overtime_rate(emp):
    basic = float(emp.basic_salary or 0)
    ratio = float(emp.overtime_ratio or 0)
    if basic <= 0 or ratio <= 0:
        return 0
    return round(basic / 30 * 8 * ratio, 2)

def save_allowances(emp_id, f):
    EmployeeAllowance.query.filter_by(employee_id=emp_id).delete()
    type_ids = f.getlist('allow_type_id[]')
    amounts  = f.getlist('allow_amount[]')
    for type_id, amt in zip(type_ids, amounts):
        if not type_id:
            continue
        atype = AllowanceType.query.get(int(type_id))
        if not atype:
            continue
        db.session.add(EmployeeAllowance(
            employee_id=emp_id,
            allowance_type_id=atype.id,
            allowance_code=atype.allowance_code,
            name=atype.allowance_name_en,
            name_ar=atype.allowance_name_ar,
            amount=_to_float(amt),
        ))

def save_banks_from_form(emp_id, f):
    banks = {}
    for key in f:
        if key.startswith('banks['):
            rest = key[6:]
            close = rest.index(']')
            idx = rest[:close]
            field = rest[close+2:-1]
            banks.setdefault(idx, {})[field] = f[key]

    EmployeeBank.query.filter_by(employee_id=emp_id).delete()
    made_primary = False
    for idx in sorted(banks, key=lambda x: int(x) if x.isdigit() else 0):
        d = banks[idx]
        name = (d.get('bank_name') or '').strip()
        if not name:
            continue
        is_primary = str(d.get('is_primary', '')).lower() in ('1', 'true', 'on', 'yes')
        if is_primary and made_primary:
            is_primary = False
        if is_primary:
            made_primary = True
        db.session.add(EmployeeBank(
            employee_id=emp_id,
            bank_name=name,
            bank_name_ar=(d.get('bank_name_ar') or '').strip(),
            branch=(d.get('branch') or '').strip(),
            branch_ar=(d.get('branch_ar') or '').strip(),
            account_number=(d.get('account_number') or '').strip(),
            swift_code=(d.get('swift_code') or '').strip(),
            iban=(d.get('iban') or '').strip(),
            is_primary=is_primary,
        ))


def _recalc_totals(emp_id):
    emp = Employee.query.get(emp_id)
    if not emp:
        return
    total = sum(float(a.amount or 0) for a in emp.allowance_rows.all())
    emp.total_allowances = total
    emp.net_salary = float(emp.basic_salary or 0) + total


# ═══════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════

@employees_bp.route('/employees')
@login_required
def list_employees():
    return render_template('employees/list.html')

@employees_bp.route('/employees/data')
@login_required
def employees_data():
    lang = session.get('lang', 'en'); ar = lang == 'ar'
    emps = Employee.query.order_by(Employee.created_at.desc()).all()
    rows = []
    for e in emps:
        age = ''
        if e.birth_date:
            today = date.today()
            y = today.year - e.birth_date.year - ((today.month, today.day) < (e.birth_date.month, e.birth_date.day))
            age = f'{y} {"سنة" if ar else "Yrs"}'
        rows.append({
            'id': e.id, 'employee_code': e.employee_code,
            'name': e.name_ar if ar and e.name_ar else e.name,
            'name_en': e.name, 'name_ar': e.name_ar or '',
            'profession': (e.profession_ar if ar and e.profession_ar else e.profession) or '',
            'kafeel_name': (e.kafeel_name_ar if ar and e.kafeel_name_ar else e.kafeel_name) or '',
            'kafeel_reference': e.kafeel_reference or '',
            'nationality': (e.nationality_ar if ar and e.nationality_ar else e.nationality) or '',
            'birth_date': e.birth_date.strftime('%Y-%m-%d') if e.birth_date else '',
            'age': age,
            'iqama_number': e.iqama_number or '',
            'iqama_expiry': e.iqama_expiry.strftime('%Y-%m-%d') if e.iqama_expiry else '',
            'passport_number': e.passport_number or '',
            'department': (e.department_ar if ar and e.department_ar else e.department) or '',
            'salary_type': e.salary_type or '',
            'basic_salary': float(e.basic_salary or 0),
            'total_allowances': float(e.total_allowances or 0),
            'net_salary': float(e.net_salary or 0),
            'is_active': e.is_active,
        })
    return jsonify(rows)

@employees_bp.route('/employees/<int:id>/json')
@login_required
def employee_json(id):
    e = Employee.query.get_or_404(id)
    def d(v): return v.strftime('%Y-%m-%d') if v else ''
    def g(f): return getattr(e, f, None) or ''
    allowance_rows = [a.to_dict() for a in e.allowance_rows.order_by(EmployeeAllowance.id).all()]

    # Get multiple professions
    profession_list = [{
        'id': p.id,
        'name_en': p.name_en,
        'name_ar': p.name_ar or '',
    } for p in e.professions.all()]
    profession_ids = [p.id for p in e.professions.all()]

    return jsonify({
        'id': e.id, 'employee_code': e.employee_code, 'is_active': e.is_active, 'is_muslim': e.is_muslim,
        'name': g('name'), 'name_ar': g('name_ar'),
        'kafeel_name': g('kafeel_name'), 'kafeel_name_ar': g('kafeel_name_ar'),
        'kafeel_reference': g('kafeel_reference'), 'kafeel_reference_ar': g('kafeel_reference_ar'),
        'nationality': g('nationality'), 'nationality_ar': g('nationality_ar'),
        'arrival_date': d(e.arrival_date), 'birth_date': d(e.birth_date),
        'passport_number': g('passport_number'), 'passport_expiry': d(e.passport_expiry),
        'entry_number': g('entry_number'), 'iqama_number': g('iqama_number'), 'iqama_expiry': d(e.iqama_expiry),
        'profession': g('profession'), 'profession_ar': g('profession_ar'),
        'professions': profession_list,
        'profession_ids': profession_ids,
        'education': g('education'), 'education_ar': g('education_ar'),
        'mobile': g('mobile'), 'address': g('address'), 'address_ar': g('address_ar'), 'email': g('email'),
        'home_city': g('home_city'), 'home_city_ar': g('home_city_ar'),
        'employee_reference': g('employee_reference'), 'employee_reference_ar': g('employee_reference_ar'),
        'po_rate': float(e.po_rate or 0), 'po_rate_unit': e.po_rate_unit or 'hour',
        'po_number': g('po_number'), 'kafalat_number': g('kafalat_number'),
        'salary_type': g('salary_type') or 'salary',
        'basic_salary': float(e.basic_salary or 0),
        'total_allowances': float(e.total_allowances or 0),
        'net_salary': float(e.net_salary or 0),
        'working_hours': float(e.working_hours or 8),
        'overtime_ratio': float(e.overtime_ratio or 1.5),
        'overtime_rate': float(e.overtime_rate or 0),
        'joining_date': d(e.joining_date), 'end_date_work': d(e.end_date_work),
        'work_month': g('work_month'), 'work_status': g('work_status') or 'active',
        'company': g('company'), 'company_ar': g('company_ar'),
        'section': g('section'), 'section_ar': g('section_ar'),
        'department': g('department'), 'department_ar': g('department_ar'),
        'shift_type': g('shift_type') or 'day', 'forman': g('forman'), 'forman_ar': g('forman_ar'),
        'hostel_name': g('hostel_name'), 'hostel_name_ar': g('hostel_name_ar'),
        'room_number': g('room_number'), 'hostel_location': g('hostel_location'), 'hostel_location_ar': g('hostel_location_ar'),
        'crn': g('crn'), 'crn_ar': g('crn_ar'),
        'insurance_company': g('insurance_company'), 'insurance_company_ar': g('insurance_company_ar'),
        'insurance_expiry': d(e.insurance_expiry), 'labour_office': g('labour_office'),
        'passport_location': g('passport_location') or 'IN',
        'document_type': g('document_type'), 'buyer_id': e.buyer_id or '',
        'photo_path': e.photo_path or '',
        'photo_url': (url_for('employees.employee_photo', emp_id=e.id) if e.photo_path else ''),
        'allowances': allowance_rows,
        'banks': [b.to_dict() for b in e.banks.order_by(EmployeeBank.id).all()],
        'documents': [d.to_dict() for d in e.documents.order_by(EmployeeDocument.id).all()],
    })

@employees_bp.route('/employees/add', methods=['POST'])
@login_required
@admin_required
def add_employee():
    emp = Employee(created_by=current_user.id)
    emp.employee_code = generate_code()
    bind_employee(emp, request.form)
    db.session.add(emp)
    db.session.flush()
    save_allowances(emp.id, request.form)
    save_banks_from_form(emp.id, request.form)
    save_documents(emp.id, request)
    save_photo(emp.id, request)
    save_professions(emp.id, request)
    _recalc_totals(emp.id)
    db.session.commit()
    flash(_t(f'Employee {emp.employee_code} added.', f'تم إضافة الموظف {emp.employee_code}'), 'success')
    return redirect(url_for('employees.list_employees'))

@employees_bp.route('/employees/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_employee(id):
    emp = Employee.query.get_or_404(id)
    bind_employee(emp, request.form)
    emp.updated_at = datetime.utcnow()
    save_allowances(emp.id, request.form)
    save_banks_from_form(emp.id, request.form)
    save_documents(emp.id, request)
    save_photo(emp.id, request)
    save_professions(emp.id, request)
    _recalc_totals(emp.id)
    db.session.commit()
    flash(_t('Employee updated.', 'تم تحديث الموظف'), 'success')
    return redirect(url_for('employees.list_employees'))

@employees_bp.route('/employees/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_employee(id):
    db.session.delete(Employee.query.get_or_404(id))
    db.session.commit()
    flash(_t('Employee deleted.', 'تم حذف الموظف'), 'success')
    return redirect(url_for('employees.list_employees'))


# ─── ALLOWANCE API ────────────────────────────────────────────────

@employees_bp.route('/employees/<int:emp_id>/allowances')
@login_required
def get_allowances(emp_id):
    rows = EmployeeAllowance.query.filter_by(employee_id=emp_id).order_by(EmployeeAllowance.id).all()
    return jsonify([r.to_dict() for r in rows])

@employees_bp.route('/employees/<int:emp_id>/allowances/add', methods=['POST'])
@login_required
@admin_required
def add_allowance(emp_id):
    Employee.query.get_or_404(emp_id)
    data = request.get_json() or {}
    type_id = data.get('allowance_type_id')
    amount  = _to_float(data.get('amount'))
    if not type_id:
        return jsonify({'ok': False, 'error': 'Allowance type required'}), 400
    atype = AllowanceType.query.get_or_404(int(type_id))
    if EmployeeAllowance.query.filter_by(employee_id=emp_id, allowance_type_id=atype.id).first():
        return jsonify({'ok': False, 'error': f'Allowance "{atype.allowance_name_en}" already exists.'}), 409
    a = EmployeeAllowance(employee_id=emp_id, allowance_type_id=atype.id,
                          allowance_code=atype.allowance_code,
                          name=atype.allowance_name_en, name_ar=atype.allowance_name_ar, amount=amount)
    db.session.add(a); db.session.commit()
    _recalc_totals(emp_id); db.session.commit()
    return jsonify({'ok': True, 'allowance': a.to_dict()})

@employees_bp.route('/employees/allowances/<int:a_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_allowance_api(a_id):
    a = EmployeeAllowance.query.get_or_404(a_id)
    data = request.get_json() or {}
    type_id = data.get('allowance_type_id')
    if type_id and int(type_id) != a.allowance_type_id:
        existing = EmployeeAllowance.query.filter_by(employee_id=a.employee_id, allowance_type_id=int(type_id)).first()
        if existing and existing.id != a_id:
            return jsonify({'ok': False, 'error': 'Allowance type already exists for this employee.'}), 409
        atype = AllowanceType.query.get(int(type_id))
        if atype:
            a.allowance_type_id = atype.id
            a.allowance_code = atype.allowance_code
            a.name = atype.allowance_name_en
            a.name_ar = atype.allowance_name_ar
    a.amount = _to_float(data.get('amount', a.amount))
    db.session.commit()
    _recalc_totals(a.employee_id); db.session.commit()
    return jsonify({'ok': True, 'allowance': a.to_dict()})

@employees_bp.route('/employees/allowances/<int:a_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_allowance_api(a_id):
    a = EmployeeAllowance.query.get_or_404(a_id)
    emp_id = a.employee_id
    db.session.delete(a); db.session.commit()
    _recalc_totals(emp_id); db.session.commit()
    return jsonify({'ok': True})


# ─── EMPLOYEE BANK API ────────────────────────────────────────────

@employees_bp.route('/employees/<int:emp_id>/banks')
@login_required
def employee_banks(emp_id):
    Employee.query.get_or_404(emp_id)
    rows = EmployeeBank.query.filter_by(employee_id=emp_id).order_by(EmployeeBank.id).all()
    return jsonify([b.to_dict() for b in rows])

@employees_bp.route('/employees/banks/<int:bank_id>')
@login_required
def employee_bank_get(bank_id):
    b = EmployeeBank.query.get_or_404(bank_id)
    return jsonify(b.to_dict())

@employees_bp.route('/employees/<int:emp_id>/banks/add', methods=['POST'])
@login_required
@admin_required
def add_employee_bank(emp_id):
    Employee.query.get_or_404(emp_id)
    d = request.get_json() or {}
    if not (d.get('bank_name') or '').strip():
        return jsonify({'ok': False, 'error': 'Bank name required'}), 400
    is_primary = bool(d.get('is_primary'))
    if is_primary:
        EmployeeBank.query.filter_by(employee_id=emp_id, is_primary=True).update({'is_primary': False})
    b = EmployeeBank(
        employee_id=emp_id,
        bank_name=(d.get('bank_name') or '').strip(),
        bank_name_ar=(d.get('bank_name_ar') or '').strip(),
        branch=(d.get('branch') or '').strip(),
        branch_ar=(d.get('branch_ar') or '').strip(),
        account_number=(d.get('account_number') or '').strip(),
        swift_code=(d.get('swift_code') or '').strip(),
        iban=(d.get('iban') or '').strip(),
        is_primary=is_primary,
    )
    db.session.add(b); db.session.commit()
    return jsonify({'ok': True, 'bank': b.to_dict()})

@employees_bp.route('/employees/banks/<int:bank_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_employee_bank(bank_id):
    b = EmployeeBank.query.get_or_404(bank_id)
    d = request.get_json() or {}
    b.bank_name      = (d.get('bank_name', b.bank_name) or '').strip()
    b.bank_name_ar   = (d.get('bank_name_ar', b.bank_name_ar) or '').strip()
    b.branch         = (d.get('branch', b.branch) or '').strip()
    b.branch_ar      = (d.get('branch_ar', b.branch_ar) or '').strip()
    b.account_number = (d.get('account_number', b.account_number) or '').strip()
    b.swift_code     = (d.get('swift_code', b.swift_code) or '').strip()
    b.iban           = (d.get('iban', b.iban) or '').strip()
    if 'is_primary' in d:
        b.is_primary = bool(d.get('is_primary'))
        if b.is_primary:
            EmployeeBank.query.filter(EmployeeBank.employee_id == b.employee_id,
                                      EmployeeBank.id != b.id).update({'is_primary': False})
    db.session.commit()
    return jsonify({'ok': True, 'bank': b.to_dict()})

@employees_bp.route('/employees/banks/<int:bank_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_employee_bank(bank_id):
    b = EmployeeBank.query.get_or_404(bank_id)
    db.session.delete(b); db.session.commit()
    return jsonify({'ok': True})


# ─── EMPLOYEE PHOTO ───────────────────────────────────────────────

@employees_bp.route('/employees/<int:emp_id>/photo')
@login_required
def employee_photo(emp_id):
    from flask import send_file, abort
    e = Employee.query.get_or_404(emp_id)
    if not e.photo_path:
        abort(404)
    full = os.path.join(current_app.config['UPLOAD_FOLDER'], e.photo_path)
    if not os.path.exists(full):
        abort(404)
    return send_file(full)


# ─── EMPLOYEE DOCUMENT API ────────────────────────────────────────

@employees_bp.route('/employees/<int:emp_id>/documents')
@login_required
def employee_documents(emp_id):
    Employee.query.get_or_404(emp_id)
    rows = EmployeeDocument.query.filter_by(employee_id=emp_id).order_by(EmployeeDocument.id).all()
    return jsonify([d.to_dict() for d in rows])

@employees_bp.route('/employees/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_employee_document(doc_id):
    d = EmployeeDocument.query.get_or_404(doc_id)
    try:
        full = os.path.join(current_app.config['UPLOAD_FOLDER'], d.file_path)
        if os.path.exists(full):
            os.remove(full)
    except Exception:
        pass
    db.session.delete(d); db.session.commit()
    return jsonify({'ok': True})


@employees_bp.route('/employees/export')
@login_required
def export_employees():
    import csv, io
    from flask import make_response
    emps = Employee.query.all()
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(['Code', 'Name', 'Nationality', 'Profession', 'Iqama', 'Birth Date',
                'Mobile', 'Dept', 'Salary Type', 'Basic', 'Total Allow', 'Net Salary', 'Status'])
    for e in emps:
        w.writerow([e.employee_code, e.name, e.nationality or '', e.profession or '',
                    e.iqama_number or '', e.birth_date or '', e.mobile or '',
                    e.department or '', e.salary_type or '', e.basic_salary or '',
                    e.total_allowances or 0, e.net_salary or '',
                    'Active' if e.is_active else 'Inactive'])
    resp = make_response(out.getvalue())
    resp.headers['Content-Disposition'] = 'attachment; filename=employees.csv'
    resp.headers['Content-type'] = 'text/csv'
    return resp