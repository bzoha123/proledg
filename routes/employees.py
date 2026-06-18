import os, uuid, json
from datetime import datetime, date
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app, jsonify, session)
from flask_login import login_required, current_user
from models import db, Employee, BankMaster, ProfessionMaster, BuyerMaster
from functools import wraps

employees_bp = Blueprint('employees', __name__)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            flash(_t('Access denied.','الوصول مرفوض'), 'danger')
            return redirect(url_for('employees.list_employees'))
        return f(*args, **kwargs)
    return decorated

def _t(en, ar): return ar if session.get('lang')=='ar' else en

def generate_code():
    last = Employee.query.order_by(Employee.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f'EMP-{num:02d}'

def parse_date(v):
    if not v: return None
    try: return datetime.strptime(v,'%Y-%m-%d').date()
    except: return None

def save_upload(file, emp_id, subfolder='employees'):
    if not file or not file.filename: return None
    ext = file.filename.rsplit('.',1)[-1].lower()
    if ext not in {'pdf','jpg','jpeg','png'}: return None
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, str(emp_id))
    os.makedirs(folder, exist_ok=True)
    fname = f'{uuid.uuid4().hex}.{ext}'
    file.save(os.path.join(folder, fname))
    return os.path.join(subfolder, str(emp_id), fname)

def bind_employee(emp, f, files=None):
    text_fields = [
        'name','name_ar','kafeel_name','kafeel_name_ar','kafeel_reference','kafeel_reference_ar',
        'nationality','nationality_ar','passport_number','entry_number','iqama_number',
        'profession','profession_ar','employee_type','education','education_ar',
        'mobile','address','address_ar','email','home_city','home_city_ar',
        'employee_reference','employee_reference_ar',
        'po_number','salary_type','department','department_ar','shift_type',
        'forman','forman_ar','hostel_name','hostel_name_ar','room_number',
        'hostel_location','hostel_location_ar','bank_name','bank_name_ar',
        'bank_branch','bank_branch_ar','swift_code','account_number','iban',
        'crn','crn_ar','insurance_company','insurance_company_ar','labour_office',
        'passport_location','document_type',
    ]
    for field in text_fields:
        setattr(emp, field, f.get(field,'') or '')

    float_fields = ['rate','po_rate','food_allowance','rent','basic_salary','net_salary','working_hours','overtime_rate']
    for field in float_fields:
        try: setattr(emp, field, float(f.get(field,0) or 0))
        except: setattr(emp, field, 0)

    date_fields = ['arrival_date','birth_date','passport_expiry','iqama_expiry','joining_date','insurance_expiry']
    for field in date_fields:
        setattr(emp, field, parse_date(f.get(field)))

    emp.is_active  = f.get('is_active') == 'on'
    emp.is_muslim  = f.get('is_muslim') == 'on'
    emp.auto_code  = f.get('auto_code') == 'on'

    # Buyer
    buyer_id = f.get('buyer_id')
    emp.buyer_id = int(buyer_id) if buyer_id else None

    # Allowances JSON
    allowance_names  = f.getlist('allowance_name[]')
    allowance_amounts= f.getlist('allowance_amount[]')
    allowances = [{'name':n,'amount':float(a or 0)} for n,a in zip(allowance_names,allowance_amounts) if n]
    emp.allowances = json.dumps(allowances) if allowances else None

    # Auto-calc net salary
    basic = emp.basic_salary or 0
    total_allow = sum(a['amount'] for a in allowances)
    food = emp.food_allowance or 0
    rent = emp.rent or 0
    emp.net_salary = basic + total_allow + food + rent

@employees_bp.route('/employees')
@login_required
def list_employees():
    return render_template('employees/list.html')

@employees_bp.route('/employees/data')
@login_required
def employees_data():
    lang = session.get('lang','en')
    ar = lang=='ar'
    emps = Employee.query.order_by(Employee.created_at.desc()).all()
    rows = []
    for e in emps:
        age = ''
        if e.birth_date:
            today = date.today()
            y = today.year - e.birth_date.year - ((today.month,today.day)<(e.birth_date.month,e.birth_date.day))
            days_in_year = (today - e.birth_date).days % 365
            age = f'{y} {"سنة" if ar else "Yrs"} {days_in_year//30} {"يوم" if ar else "Days"}'
        rows.append({
            'id':e.id, 'employee_code':e.employee_code,
            'name': e.name_ar if ar and e.name_ar else e.name,
            'name_en':e.name, 'name_ar':e.name_ar or '',
            'profession':(e.profession_ar if ar and e.profession_ar else e.profession) or '',
            'kafeel_name':(e.kafeel_name_ar if ar and e.kafeel_name_ar else e.kafeel_name) or '',
            'kafeel_reference':e.kafeel_reference or '',
            'nationality':(e.nationality_ar if ar and e.nationality_ar else e.nationality) or '',
            'birth_date':e.birth_date.strftime('%Y-%m-%d') if e.birth_date else '',
            'age':age,
            'iqama_number':e.iqama_number or '',
            'iqama_expiry':e.iqama_expiry.strftime('%Y-%m-%d') if e.iqama_expiry else '',
            'passport_number':e.passport_number or '',
            'department':(e.department_ar if ar and e.department_ar else e.department) or '',
            'salary_type':e.salary_type or '',
            'basic_salary':e.basic_salary or 0,
            'is_active':e.is_active, 'employee_type':e.employee_type or '',
        })
    return jsonify(rows)

@employees_bp.route('/employees/<int:id>/json')
@login_required
def employee_json(id):
    e = Employee.query.get_or_404(id)
    def d(v): return v.strftime('%Y-%m-%d') if v else ''
    def g(f): return getattr(e,f,None) or ''
    allowances = json.loads(e.allowances) if e.allowances else []
    return jsonify({
        'id':e.id,'employee_code':e.employee_code,'is_active':e.is_active,'is_muslim':e.is_muslim,
        'auto_code':e.auto_code if hasattr(e,'auto_code') else True,
        'name':g('name'),'name_ar':g('name_ar'),
        'kafeel_name':g('kafeel_name'),'kafeel_name_ar':g('kafeel_name_ar'),
        'kafeel_reference':g('kafeel_reference'),'kafeel_reference_ar':g('kafeel_reference_ar'),
        'nationality':g('nationality'),'nationality_ar':g('nationality_ar'),
        'arrival_date':d(e.arrival_date),'birth_date':d(e.birth_date),
        'passport_number':g('passport_number'),'passport_expiry':d(e.passport_expiry),
        'entry_number':g('entry_number'),'iqama_number':g('iqama_number'),'iqama_expiry':d(e.iqama_expiry),
        'profession':g('profession'),'profession_ar':g('profession_ar'),
        'employee_type':g('employee_type'),'education':g('education'),'education_ar':g('education_ar'),
        'mobile':g('mobile'),'address':g('address'),'address_ar':g('address_ar'),'email':g('email'),
        'home_city':g('home_city'),'home_city_ar':g('home_city_ar'),
        'employee_reference':g('employee_reference'),'employee_reference_ar':g('employee_reference_ar'),
        'rate':e.rate or 0,'po_rate':e.po_rate or 0,'po_number':g('po_number'),
        'salary_type':g('salary_type'),'food_allowance':e.food_allowance or 0,'rent':e.rent or 0,
        'basic_salary':e.basic_salary or 0,'net_salary':e.net_salary or 0,
        'working_hours':e.working_hours or 8,'overtime_rate':e.overtime_rate or 0,
        'joining_date':d(e.joining_date),'department':g('department'),'department_ar':g('department_ar'),
        'shift_type':g('shift_type') or 'day','forman':g('forman'),'forman_ar':g('forman_ar'),
        'hostel_name':g('hostel_name'),'hostel_name_ar':g('hostel_name_ar'),
        'room_number':g('room_number'),'hostel_location':g('hostel_location'),'hostel_location_ar':g('hostel_location_ar'),
        'bank_name':g('bank_name'),'bank_name_ar':g('bank_name_ar'),
        'bank_branch':g('bank_branch'),'bank_branch_ar':g('bank_branch_ar'),
        'swift_code':g('swift_code'),'account_number':g('account_number'),'iban':g('iban'),
        'crn':g('crn'),'crn_ar':g('crn_ar'),
        'insurance_company':g('insurance_company'),'insurance_company_ar':g('insurance_company_ar'),
        'insurance_expiry':d(e.insurance_expiry),'labour_office':g('labour_office'),
        'passport_location':g('passport_location') or 'IN',
        'document_type':g('document_type'),'buyer_id':e.buyer_id or '',
        'allowances': allowances,
    })

@employees_bp.route('/employees/add', methods=['GET','POST'])
@login_required
@admin_required
def add_employee():
    if request.method=='POST':
        auto = request.form.get('auto_code')=='on'
        manual_code = request.form.get('manual_code','').strip()
        emp = Employee(created_by=current_user.id)
        emp.employee_code = generate_code() if auto else (manual_code or generate_code())
        bind_employee(emp, request.form)
        db.session.add(emp)
        db.session.flush()
        doc = request.files.get('document')
        if doc and doc.filename: emp.document_path = save_upload(doc, emp.id)
        db.session.commit()
        flash(_t(f'Employee {emp.employee_code} added.',f'تم إضافة الموظف {emp.employee_code}'),'success')
    return redirect(url_for('employees.list_employees'))

@employees_bp.route('/employees/<int:id>/edit', methods=['GET','POST'])
@login_required
@admin_required
def edit_employee(id):
    emp = Employee.query.get_or_404(id)
    if request.method=='POST':
        auto = request.form.get('auto_code')=='on'
        manual_code = request.form.get('manual_code','').strip()
        if not auto and manual_code: emp.employee_code = manual_code
        bind_employee(emp, request.form)
        emp.updated_at = datetime.utcnow()
        doc = request.files.get('document')
        if doc and doc.filename: emp.document_path = save_upload(doc, emp.id)
        db.session.commit()
        flash(_t('Employee updated.','تم تحديث الموظف'),'success')
    return redirect(url_for('employees.list_employees'))

@employees_bp.route('/employees/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_employee(id):
    db.session.delete(Employee.query.get_or_404(id))
    db.session.commit()
    flash(_t('Employee deleted.','تم حذف الموظف'),'success')
    return redirect(url_for('employees.list_employees'))

@employees_bp.route('/employees/export')
@login_required
def export_employees():
    import csv, io
    from flask import make_response
    emps = Employee.query.all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Code','Name','Nationality','Profession','Iqama','Birth Date','Mobile','Dept','Salary Type','Basic','Net Salary','Status'])
    for e in emps:
        w.writerow([e.employee_code,e.name,e.nationality or '',e.profession or '',
                    e.iqama_number or '',e.birth_date or '',e.mobile or '',
                    e.department or '',e.salary_type or '',e.basic_salary or '',e.net_salary or '',
                    'Active' if e.is_active else 'Inactive'])
    resp = make_response(out.getvalue())
    resp.headers['Content-Disposition']='attachment; filename=employees.csv'
    resp.headers['Content-type']='text/csv'
    return resp
