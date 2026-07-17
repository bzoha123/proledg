import os, uuid
from datetime import datetime, date
from decimal import Decimal
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app, jsonify, session)
from flask_login import login_required, current_user
from models import (db, Employee, EmployeeAllowance, AllowanceType,
                    EmployeeBank, EmployeeDocument, ProfessionMaster, BuyerMaster,
                    EmployeeProfession)


def _emp_profession_str(e, ar=False):
    """Comma-joined profession names from the employee_professions junction."""
    try:
        profs = e.professions.all()
    except Exception:
        profs = []
    names = [((p.name_ar or p.name_en) if ar else p.name_en) for p in profs]
    return ', '.join([n for n in names if n])
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


def _photo_abs_path(emp):
    """Absolute path of an employee's photo, tolerating either slash style."""
    if not emp or not emp.photo_path:
        return None
    parts = emp.photo_path.replace('\\', '/').split('/')
    return os.path.join(current_app.config['UPLOAD_FOLDER'], *parts)


def _photo_url(emp):
    """Return a cache-busted photo URL, or '' when there is no usable file.

    Returning '' for a missing/broken path lets the UI fall back to the
    placeholder instead of rendering a broken <img>.
    """
    full = _photo_abs_path(emp)
    if not full or not os.path.exists(full):
        return ''
    try:
        stamp = int(os.path.getmtime(full))
    except OSError:
        stamp = 0
    return url_for('employees.employee_photo', emp_id=emp.id) + f'?v={stamp}'


# Extensions we refuse outright, regardless of content. Everything else is
# decided by *reading* the bytes: if Pillow can open it as an image, we take
# it. That way new formats (.jfif, .avif, .heic, ...) never need a code change.
BLOCKED_PHOTO_EXT = {
    'exe', 'dll', 'bat', 'cmd', 'com', 'scr', 'msi', 'ps1', 'sh',
    'js', 'jar', 'vbs', 'php', 'py', 'html', 'htm', 'svg',
}

# Formats every browser renders natively — anything else gets converted to JPEG.
BROWSER_SAFE_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP'}

# Pillow format -> file extension to store on disk.
FORMAT_EXT = {'JPEG': 'jpg', 'PNG': 'png', 'GIF': 'gif', 'WEBP': 'webp'}

MAX_PHOTO_BYTES = 10 * 1024 * 1024   # 10 MB


def save_photo(emp_id, req):
    """Save the employee photo. Updates employees.photo_path.

    The file is accepted or rejected by *content*, not by filename: whatever
    Pillow can decode as an image is allowed. Formats browsers cannot render
    reliably (AVIF, HEIC, TIFF, BMP, ...) are converted to JPEG, so `.jfif`,
    `.avif` and friends all just work.

    The stored path always uses forward slashes so it is portable between
    Windows and POSIX hosts. Every skip path is logged.
    """
    log = current_app.logger

    f = req.files.get('photo')
    if f is None:
        log.info('[photo] emp=%s: no "photo" key in request.files (keys=%s). '
                 'Is the form enctype="multipart/form-data" and the input name="photo"?',
                 emp_id, list(req.files.keys()))
        return
    if not f.filename:
        log.info('[photo] emp=%s: "photo" field present but empty (no file chosen).', emp_id)
        return

    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext in BLOCKED_PHOTO_EXT:
        log.warning('[photo] emp=%s: rejected "%s" (blocked extension %r).',
                    emp_id, f.filename, ext)
        flash(_t(f'"{f.filename}" is not an image file.',
                 f'"{f.filename}" ليس ملف صورة.'), 'warning')
        return

    try:
        raw = f.read()
        if not raw:
            log.warning('[photo] emp=%s: "%s" is empty (0 bytes).', emp_id, f.filename)
            flash(_t('The selected image is empty.', 'الصورة المختارة فارغة.'), 'warning')
            return
        if len(raw) > MAX_PHOTO_BYTES:
            log.warning('[photo] emp=%s: "%s" too large (%d bytes).',
                        emp_id, f.filename, len(raw))
            flash(_t('The image is larger than 10 MB.',
                     'حجم الصورة أكبر من 10 ميغابايت.'), 'warning')
            return

        final_ext, data = _normalise_image(raw, emp_id, f.filename)
        if data is None:
            return  # _normalise_image already logged + flashed

        folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'employees', str(emp_id))
        os.makedirs(folder, exist_ok=True)
        fname = f'photo_{uuid.uuid4().hex}.{final_ext}'
        dest = os.path.join(folder, fname)
        with open(dest, 'wb') as out:
            out.write(data)

        if not os.path.exists(dest) or os.path.getsize(dest) == 0:
            log.error('[photo] emp=%s: file did not land at %s', emp_id, dest)
            flash(_t('The photo could not be written to disk.',
                     'تعذر حفظ الصورة على القرص.'), 'danger')
            return
    except Exception as exc:  # noqa: BLE001
        log.exception('[photo] emp=%s: save failed: %s', emp_id, exc)
        flash(_t('The photo could not be saved.', 'تعذر حفظ الصورة.'), 'danger')
        return

    emp = Employee.query.get(emp_id)
    if not emp:
        log.error('[photo] emp=%s: employee row not found after upload.', emp_id)
        return

    # Remove the previous photo file so old images don't pile up.
    if emp.photo_path:
        old = os.path.join(current_app.config['UPLOAD_FOLDER'],
                           *emp.photo_path.replace('\\', '/').split('/'))
        if os.path.exists(old):
            try:
                os.remove(old)
            except OSError:
                pass

    emp.photo_path = f'employees/{emp_id}/{fname}'   # always forward slashes
    log.info('[photo] emp=%s: saved -> %s (%d bytes)',
             emp_id, emp.photo_path, os.path.getsize(dest))


def _normalise_image(raw, emp_id, filename):
    """Validate image bytes and return ``(extension, bytes)`` ready to write.

    Decides purely on content. Browser-safe formats pass through untouched;
    everything else Pillow can decode is re-encoded as JPEG. Returns
    ``(None, None)`` when the bytes are not a readable image.
    """
    import io
    log = current_app.logger

    try:
        from PIL import Image
    except ImportError:
        log.error('[photo] emp=%s: Pillow is not installed; cannot validate images.', emp_id)
        flash(_t('Image support is not installed on the server.',
                 'دعم الصور غير مثبت على الخادم.'), 'danger')
        return None, None

    try:
        probe = Image.open(io.BytesIO(raw))
        probe.verify()                       # cheap integrity check
        img = Image.open(io.BytesIO(raw))    # re-open: verify() exhausts it
        fmt = (img.format or '').upper()
    except Exception as exc:  # noqa: BLE001
        log.warning('[photo] emp=%s: "%s" is not a readable image (%s).',
                    emp_id, filename, exc)
        flash(_t(f'"{filename}" is not a readable image file.',
                 f'"{filename}" ليس ملف صورة صالح.'), 'warning')
        return None, None

    # Already displayable in every browser -> store the original bytes.
    if fmt in BROWSER_SAFE_FORMATS:
        log.info('[photo] emp=%s: accepted %s (%s).', emp_id, filename, fmt)
        return FORMAT_EXT[fmt], raw

    # Anything else (AVIF, HEIC, TIFF, BMP, ICO, ...) -> convert to JPEG.
    try:
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=90, optimize=True)
        log.info('[photo] emp=%s: converted %s (%s) -> jpg', emp_id, filename, fmt or '?')
        return 'jpg', buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        log.warning('[photo] emp=%s: could not convert %s (%s) to JPEG: %s.',
                    emp_id, filename, fmt or '?', exc)
        flash(_t('This image could not be converted. Try a JPG or PNG.',
                 'تعذر تحويل الصورة. جرّب JPG أو PNG.'), 'warning')
        return None, None


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
    # professions are stored only in employee_professions (junction table)


TEXT_FIELDS = [
    'name', 'name_ar', 'kafeel_name', 'kafeel_name_ar', 'kafeel_reference', 'kafeel_reference_ar',
    'nationality', 'nationality_ar', 'passport_number', 'entry_number', 'iqama_number',
    'education', 'education_ar',
    'mobile', 'address', 'address_ar', 'email', 'home_city', 'home_city_ar',
    'employee_reference', 'employee_reference_ar',
    'po_number', 'salary_type', 'salary_category', 'kafalat_number',
    'work_status',
    'hostel_name', 'hostel_name_ar', 'room_number',
    'hostel_location', 'hostel_location_ar',
    'crn', 'crn_ar', 'insurance_company', 'insurance_company_ar', 'labour_office',
    'passport_location', 'document_type',
]
FLOAT_FIELDS = ['po_rate', 'basic_salary', 'working_hours', 'overtime_ratio']
DATE_FIELDS  = ['arrival_date', 'birth_date', 'passport_expiry', 'iqama_expiry',
                'joining_date', 'insurance_expiry', 'end_date_work']

def save_work_allocation(emp, f):
    """Create a NEW employee_work_allocation row on every save (a history).

    The employee form posts shift / location / location_ar and the department +
    buyer selections; everything else is copied from the employee record so each
    allocation row is a self-contained snapshot.
    """
    from models import EmployeeWorkAllocation, BuyerMaster

    shift = (f.get('shift') or 'day').strip().lower()
    if shift not in ('day', 'night'):
        shift = 'day'

    buyer = BuyerMaster.query.get(emp.buyer_id) if emp.buyer_id else None

    # department name comes from the hidden fields the cascade fills
    dept_en = (f.get('department') or '').strip()
    dept_ar = (f.get('department_ar') or '').strip()

    wa = EmployeeWorkAllocation(
        employee_id         = emp.id,
        kafeel              = emp.kafeel_name,
        name                = emp.name,
        nationality         = emp.nationality,
        profession          = _emp_profession_str(emp),
        iqama               = emp.iqama_number,
        month               = (f.get('work_month') or '').strip() or None,
        joining_date        = emp.joining_date,
        end_date            = emp.end_date_work,
        buyer_id            = emp.buyer_id,
        buyer_name          = buyer.buyer_name_en if buyer else '',
        buyer_name_ar       = (buyer.buyer_name_ar or '') if buyer else '',
        buyer_department    = dept_en,
        buyer_department_ar = dept_ar,
        location            = (f.get('location') or '').strip(),
        location_ar         = (f.get('location_ar') or '').strip(),
        shift               = shift,
        created_by          = current_user.id,
    )
    db.session.add(wa)
    return wa


def latest_work_allocation(emp_id):
    """The employee's most recent allocation row (for edit-mode display)."""
    from models import EmployeeWorkAllocation
    return (EmployeeWorkAllocation.query
            .filter_by(employee_id=emp_id)
            .order_by(EmployeeWorkAllocation.id.desc())
            .first())

def _wa_department(e, ar=False):
    """Department name for the grid, taken from the employee's latest allocation.

    The department columns were removed from `employees`; department/company/
    location now live on employee_work_allocation only.
    """
    wa = latest_work_allocation(e.id)
    if not wa:
        return ''
    return (wa.buyer_department_ar if ar and wa.buyer_department_ar
            else wa.buyer_department) or ''

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

    # Department/company/location now live only on employee_work_allocation.

    emp.overtime_rate = _calc_overtime_rate(emp)
    emp.net_salary = _to_decimal(emp.basic_salary) + _to_decimal(emp.total_allowances)


def _to_decimal(value):
    """Coerce a form float / DB Decimal / None into a Decimal.

    Form fields arrive as floats while columns already loaded from the DB are
    Decimals, and Python refuses to add the two. Normalising here keeps every
    money calculation on a single numeric type.
    """
    if value is None or value == '':
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _calc_overtime_rate(emp):
    """Overtime rate = (basic / 30 / 8) * overtime ratio.

    i.e. the hourly rate (monthly basic over 30 days, 8 hours a day)
    multiplied by the overtime ratio.
    """
    basic = float(emp.basic_salary or 0)
    ratio = float(emp.overtime_ratio or 0)
    if basic <= 0 or ratio <= 0:
        return 0
    return round(basic / 30 / 8 * ratio, 2)

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
    total = sum((_to_decimal(a.amount) for a in emp.allowance_rows.all()), Decimal('0'))
    emp.total_allowances = total
    emp.net_salary = _to_decimal(emp.basic_salary) + total


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
            'profession': _emp_profession_str(e, ar),
            'kafeel_name': (e.kafeel_name_ar if ar and e.kafeel_name_ar else e.kafeel_name) or '',
            'kafeel_reference': e.kafeel_reference or '',
            'nationality': (e.nationality_ar if ar and e.nationality_ar else e.nationality) or '',
            'birth_date': e.birth_date.strftime('%Y-%m-%d') if e.birth_date else '',
            'age': age,
            'iqama_number': e.iqama_number or '',
            'iqama_expiry': e.iqama_expiry.strftime('%Y-%m-%d') if e.iqama_expiry else '',
            'passport_number': e.passport_number or '',
            'department': _wa_department(e, ar),
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

    wa = latest_work_allocation(e.id)   # most recent allocation (may be None)
    return jsonify({
        'id': e.id, 'employee_code': e.employee_code, 'is_active': e.is_active, 'is_muslim': e.is_muslim,
        'name': g('name'), 'name_ar': g('name_ar'),
        'kafeel_name': g('kafeel_name'), 'kafeel_name_ar': g('kafeel_name_ar'),
        'kafeel_reference': g('kafeel_reference'), 'kafeel_reference_ar': g('kafeel_reference_ar'),
        'nationality': g('nationality'), 'nationality_ar': g('nationality_ar'),
        'arrival_date': d(e.arrival_date), 'birth_date': d(e.birth_date),
        'passport_number': g('passport_number'), 'passport_expiry': d(e.passport_expiry),
        'entry_number': g('entry_number'), 'iqama_number': g('iqama_number'), 'iqama_expiry': d(e.iqama_expiry),
        'profession': (profession_list[0]['name_en'] if profession_list else ''), 'profession_ar': (profession_list[0]['name_ar'] if profession_list else ''),
        'professions': profession_list,
        'profession_ids': profession_ids,
        'education': g('education'), 'education_ar': g('education_ar'),
        'mobile': g('mobile'), 'address': g('address'), 'address_ar': g('address_ar'), 'email': g('email'),
        'home_city': g('home_city'), 'home_city_ar': g('home_city_ar'),
        'employee_reference': g('employee_reference'), 'employee_reference_ar': g('employee_reference_ar'),
        'po_rate': float(e.po_rate or 0),
        'po_number': g('po_number'), 'kafalat_number': g('kafalat_number'),
        'salary_type': g('salary_type') or 'month',
        'salary_category': g('salary_category') or 'salary',
        'basic_salary': float(e.basic_salary or 0),
        'total_allowances': float(e.total_allowances or 0),
        'net_salary': float(e.net_salary or 0),
        'working_hours': float(e.working_hours or 8),
        'overtime_ratio': float(e.overtime_ratio or 1.5),
        'overtime_rate': float(e.overtime_rate or 0),
        'joining_date': d(e.joining_date), 'end_date_work': d(e.end_date_work),
        'work_status': g('work_status') or 'active',
        'hostel_name': g('hostel_name'), 'hostel_name_ar': g('hostel_name_ar'),
        'room_number': g('room_number'), 'hostel_location': g('hostel_location'), 'hostel_location_ar': g('hostel_location_ar'),
        'crn': g('crn'), 'crn_ar': g('crn_ar'),
        'insurance_company': g('insurance_company'), 'insurance_company_ar': g('insurance_company_ar'),
        'insurance_expiry': d(e.insurance_expiry), 'labour_office': g('labour_office'),
        'passport_location': g('passport_location') or 'IN',
        'document_type': g('document_type'), 'buyer_id': e.buyer_id or '',
        # department/company/location come from the latest allocation (wa_* below)
        'photo_path': e.photo_path or '',
        'photo_url': _photo_url(e),
        'allowances': allowance_rows,
        'banks': [b.to_dict() for b in e.banks.order_by(EmployeeBank.id).all()],
        'documents': [d.to_dict() for d in e.documents.order_by(EmployeeDocument.id).all()],
        # last work-allocation entry -> the form shows these in edit mode
        'wa_shift': (wa.shift if wa else 'day'),
        'company': (wa.buyer_name if wa else ''),
        'company_ar': (wa.buyer_name_ar if wa else ''),
        'department': (wa.buyer_department if wa else ''),
        'department_ar': (wa.buyer_department_ar if wa else ''),
        'work_month': (wa.month if wa else ''),
        'wa_location': (wa.location if wa else ''),
        'wa_location_ar': (wa.location_ar if wa else ''),
        'wa_month': (wa.month if wa else ''),
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
    save_work_allocation(emp, request.form)   # new history row
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
    save_work_allocation(emp, request.form)   # new history row on every save
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


# ─── COMPANY (BUYER) -> DEPARTMENT CASCADE ────────────────────────

@employees_bp.route('/employees/departments-by-buyer')
@login_required
def departments_by_buyer():
    """Departments belonging to the selected Company/HR (buyer).

    Returns [] when no buyer is supplied, so the Department dropdown can
    never offer a record from an unrelated company.
    """
    from models import BuyerDepartment
    buyer_id = request.args.get('buyer_id', type=int)
    if not buyer_id:
        return jsonify([])
    rows = (BuyerDepartment.query
            .filter_by(buyer_id=buyer_id)
            .order_by(BuyerDepartment.department_name).all())
    return jsonify([{
        'id': r.id,
        'name': r.department_name,
        'name_ar': r.department_name_ar or '',
        'label': r.department_name,
        'location_name': r.location_name or '',
        'location_name_ar': r.location_name_ar or '',
    } for r in rows])


@employees_bp.route('/employees/departments/add', methods=['POST'])
@login_required
def add_department_quick():
    """Create a department under the given Company/HR (buyer) from the
    Employee form's Department (+Add) button, then return it so the dropdown
    can refresh and pre-select it. Errors are returned as JSON messages."""
    from models import BuyerDepartment
    buyer_id = request.form.get('buyer_id', type=int)
    name = (request.form.get('department_name', '') or '').strip()
    name_ar = (request.form.get('department_name_ar', '') or '').strip()
    if not buyer_id:
        return jsonify({'ok': False, 'error': _t('Select a company first.',
                                                 'اختر الشركة أولاً.')}), 400
    if not name:
        return jsonify({'ok': False, 'error': _t('Department name is required.',
                                                 'اسم القسم مطلوب.')}), 400
    existing = (BuyerDepartment.query
                .filter_by(buyer_id=buyer_id, department_name=name).first())
    if existing:
        return jsonify({'ok': False, 'error': _t('This department already exists.',
                                                 'هذا القسم موجود بالفعل.')}), 400
    try:
        dep = BuyerDepartment(buyer_id=buyer_id, department_name=name,
                              department_name_ar=name_ar or None)
        db.session.add(dep)
        db.session.commit()
        return jsonify({'ok': True, 'id': dep.id, 'name': dep.department_name,
                        'name_ar': dep.department_name_ar or ''})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('[dept-add] failed: %s', e)
        return jsonify({'ok': False, 'error': _t('Could not save the department.',
                                                 'تعذّر حفظ القسم.')}), 500


# ─── EMPLOYEE PHOTO ───────────────────────────────────────────────

@employees_bp.route('/employees/<int:emp_id>/photo')
@login_required
def employee_photo(emp_id):
    """Serve the employee's photo. Missing/broken paths return 404 so the
    front-end can show its placeholder instead of a broken image."""
    from flask import send_file, abort
    e = Employee.query.get_or_404(emp_id)
    full = _photo_abs_path(e)
    if not full or not os.path.exists(full):
        abort(404)
    resp = send_file(full)
    # The URL is cache-busted by mtime, but never let a stale copy linger.
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


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
        w.writerow([e.employee_code, e.name, e.nationality or '', _emp_profession_str(e),
                    e.iqama_number or '', e.birth_date or '', e.mobile or '',
                    _wa_department(e), e.salary_type or '', e.basic_salary or '',
                    e.total_allowances or 0, e.net_salary or '',
                    'Active' if e.is_active else 'Inactive'])
    resp = make_response(out.getvalue())
    resp.headers['Content-Disposition'] = 'attachment; filename=employees.csv'
    resp.headers['Content-type'] = 'text/csv'
    return resp