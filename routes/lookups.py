from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from models import db, ProfessionMaster, BuyerMaster, BuyerBank, Employee, EmployeeAllowance, AllowanceType
from functools import wraps

lookups_bp = Blueprint('lookups', __name__)

def admin_required(f):
    @wraps(f)
    def d(*a, **k):
        if not current_user.is_admin():
            flash('Access denied', 'danger')
            return redirect(request.referrer or url_for('dashboard.index'))
        return f(*a, **k)
    return d

def _t(en, ar): return ar if session.get('lang')=='ar' else en

# ── PROFESSIONS ──────────────────────────────────────────────────────
@lookups_bp.route('/professions')
@login_required
def list_professions():
    items = ProfessionMaster.query.order_by(ProfessionMaster.profession_en).all()
    return render_template('lookups/professions.html', items=items)

@lookups_bp.route('/professions/add', methods=['POST'])
@login_required
@admin_required
def add_profession():
    en = request.form.get('profession_en','').strip()
    ar = request.form.get('profession_ar','').strip()
    if not en:
        flash(_t('English name required','الاسم الإنجليزي مطلوب'),'danger')
        return redirect(url_for('lookups.list_professions'))
    if ProfessionMaster.query.filter_by(profession_en=en).first():
        flash(_t(f'"{en}" already exists.',f'"{en}" موجود بالفعل'),'warning')
        return redirect(url_for('lookups.list_professions'))
    db.session.add(ProfessionMaster(profession_en=en, profession_ar=ar))
    db.session.commit()
    flash(_t(f'Profession "{en}" added.',f'تم إضافة المهنة "{ar or en}"'),'success')
    return redirect(url_for('lookups.list_professions'))

@lookups_bp.route('/professions/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_profession(id):
    p = ProfessionMaster.query.get_or_404(id)
    p.profession_en = request.form.get('profession_en', p.profession_en).strip()
    p.profession_ar = request.form.get('profession_ar', p.profession_ar or '').strip()
    p.is_active = request.form.get('is_active') == 'on'
    db.session.commit()
    flash(_t('Updated.','تم التحديث'),'success')
    return redirect(url_for('lookups.list_professions'))

@lookups_bp.route('/professions/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_profession(id):
    db.session.delete(ProfessionMaster.query.get_or_404(id))
    db.session.commit()
    flash(_t('Deleted.','تم الحذف'),'success')
    return redirect(url_for('lookups.list_professions'))

@lookups_bp.route('/professions/data')
@login_required
def professions_data():
    lang = session.get('lang','en')
    items = ProfessionMaster.query.filter_by(is_active=True).order_by(ProfessionMaster.profession_en).all()
    return jsonify([{'id':p.id,'en':p.profession_en,'ar':p.profession_ar or p.profession_en,
                     'label':p.profession_ar if lang=='ar' else p.profession_en} for p in items])
# ── BUYERS ───────────────────────────────────────────────────────────
@lookups_bp.route('/buyers')
@login_required
def list_buyers():
    buyers = BuyerMaster.query.order_by(BuyerMaster.buyer_name_en).all()
    return render_template('lookups/buyers.html', buyers=buyers)

@lookups_bp.route('/buyers/add', methods=['POST'])
@login_required
@admin_required
def add_buyer():
    from datetime import datetime as dt
    
    # Debug: print all form data
    print("=" * 50)
    print("ADD BUYER - Form Data Received:")
    for key in request.form:
        print(f"  {key} = {request.form[key]}")
    print("=" * 50)
    
    en = request.form.get('buyer_name_en','').strip()
    if not en:
        flash(_t('Buyer name is required.','اسم المشتري مطلوب.'),'danger')
        return redirect(url_for('lookups.list_buyers'))
    
    # Generate code
    last = BuyerMaster.query.order_by(BuyerMaster.id.desc()).first()
    num  = (last.id + 1) if last else 1
    code = f'BUY-{num:04d}'
    
    b = BuyerMaster(
        buyer_code=code,
        buyer_name_en=en,
        buyer_name_ar=request.form.get('buyer_name_ar','').strip(),
        vat_number=request.form.get('vat_number','').strip(),
        crn=request.form.get('crn','').strip(),
        phone=request.form.get('phone','').strip(),
        fax=request.form.get('fax','').strip(),
        email=request.form.get('email','').strip(),
        website=request.form.get('website','').strip(),
        report_color=request.form.get('report_color','#2563eb').strip(),
        street_name=request.form.get('street_name','').strip(),
        street_name_ar=request.form.get('street_name_ar','').strip(),
        building_number=request.form.get('building_number','').strip(),
        building_number_ar=request.form.get('building_number_ar','').strip(),
        additional_number=request.form.get('additional_number','').strip(),
        additional_number_ar=request.form.get('additional_number_ar','').strip(),
        postal_code=request.form.get('postal_code','').strip(),
        postal_code_ar=request.form.get('postal_code_ar','').strip(),
        country=request.form.get('country','Saudi Arabia').strip(),
        country_ar=request.form.get('country_ar','').strip(),
        city=request.form.get('city','').strip(),
        city_ar=request.form.get('city_ar','').strip(),
        district=request.form.get('district','').strip(),
        district_ar=request.form.get('district_ar','').strip(),
        status=request.form.get('status','active').strip(),
        is_active=request.form.get('status','active')=='active',
        created_by=current_user.id,
    )
    db.session.add(b)
    db.session.flush()  # Get b.id without committing
    
    # ── Save banks from form ──
    print(f"Calling _save_banks_from_form for buyer_id={b.id}")
    _save_banks_from_form(b.id)
    
    db.session.commit()
    flash(_t(f'Buyer {code} added.', f'تم إضافة المشتري {code}.'),'success')
    return redirect(url_for('lookups.list_buyers'))

@lookups_bp.route('/buyers/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_buyer(id):
    b = BuyerMaster.query.get_or_404(id)
    
    # Debug: print all form data
    print("=" * 50)
    print(f"EDIT BUYER {id} - Form Data Received:")
    for key in request.form:
        print(f"  {key} = {request.form[key]}")
    print("=" * 50)
    
    b.buyer_name_en  = request.form.get('buyer_name_en', b.buyer_name_en).strip()
    b.buyer_name_ar  = request.form.get('buyer_name_ar', b.buyer_name_ar or '').strip()
    b.vat_number     = request.form.get('vat_number','').strip()
    b.crn            = request.form.get('crn','').strip()
    b.phone          = request.form.get('phone','').strip()
    b.fax            = request.form.get('fax','').strip()
    b.email          = request.form.get('email','').strip()
    b.website        = request.form.get('website','').strip()
    b.report_color   = request.form.get('report_color','#2563eb').strip()
    b.street_name    = request.form.get('street_name','').strip()
    b.street_name_ar = request.form.get('street_name_ar','').strip()
    b.building_number= request.form.get('building_number','').strip()
    b.building_number_ar= request.form.get('building_number_ar','').strip()
    b.additional_number = request.form.get('additional_number','').strip()
    b.additional_number_ar = request.form.get('additional_number_ar','').strip()
    b.postal_code    = request.form.get('postal_code','').strip()
    b.postal_code_ar = request.form.get('postal_code_ar','').strip()
    b.country        = request.form.get('country','Saudi Arabia').strip()
    b.country_ar     = request.form.get('country_ar','').strip()
    b.city           = request.form.get('city','').strip()
    b.city_ar        = request.form.get('city_ar','').strip()
    b.district       = request.form.get('district','').strip()
    b.district_ar    = request.form.get('district_ar','').strip()
    b.status         = request.form.get('status','active').strip()
    b.is_active      = b.status == 'active'
    
    # ── Save banks from form ──
    print(f"Calling _save_banks_from_form for buyer_id={id}")
    _save_banks_from_form(id)
    
    db.session.commit()
    flash(_t('Buyer updated.','تم تحديث المشتري.'),'success')
    return redirect(url_for('lookups.list_buyers'))


def _save_banks_from_form(buyer_id):
    """Process banks[] hidden fields from form submission.
    
    Expected format:
    banks[0][bank_name] = Al Rajhi
    banks[0][bank_name_ar] = الراجحي
    banks[0][account_number] = 12345
    banks[0][branch] = Main
    banks[0][branch_ar] = الرئيسي
    banks[0][swift_code] = RJHI
    banks[0][iban] = SA123
    banks[0][is_primary] = true
    banks[0][_dbId] = 5   (or empty for new)
    """
    submitted_ids = set()
    
    # Parse all form keys matching banks[index][field]
    banks_data = {}
    for key in request.form:
        if key.startswith('banks['):
            # Parse: banks[0][bank_name]
            rest = key[6:]  # Remove 'banks['
            close_bracket = rest.index(']')
            idx = rest[:close_bracket]
            field = rest[close_bracket+2:-1]  # Remove '][' and trailing ']'
            
            if idx not in banks_data:
                banks_data[idx] = {}
            banks_data[idx][field] = request.form[key]
    
    print(f"\n=== _save_banks_from_form (buyer_id={buyer_id}) ===")
    print(f"Parsed banks_data: {banks_data}")
    
    # Process each bank entry
    for idx, data in banks_data.items():
        bank_name = data.get('bank_name', '').strip()
        if not bank_name:
            print(f"  Skipping index {idx} - no bank_name")
            continue
        
        db_id = data.get('_dbId', '').strip()
        print(f"  Processing bank: name={bank_name}, _dbId={db_id}")
        
        if db_id:
            # Update existing bank
            bank = BuyerBank.query.get(int(db_id))
            if bank and bank.buyer_id == buyer_id:
                print(f"    Updating existing bank id={db_id}")
                bank.bank_name      = bank_name
                bank.bank_name_ar   = data.get('bank_name_ar', '').strip()
                bank.account_number = data.get('account_number', '').strip()
                bank.branch         = data.get('branch', '').strip()
                bank.branch_ar      = data.get('branch_ar', '').strip()
                bank.swift_code     = data.get('swift_code', '').strip()
                bank.iban           = data.get('iban', '').strip()
                bank.is_primary     = data.get('is_primary', 'false').lower() == 'true'
                submitted_ids.add(int(db_id))
            else:
                print(f"    Bank id={db_id} not found or wrong buyer, creating new")
                db_id = ''  # Force create new
        
        if not db_id:
            # Create new bank
            print(f"    Creating new bank")
            bank = BuyerBank(
                buyer_id=buyer_id,
                bank_name=bank_name,
                bank_name_ar=data.get('bank_name_ar', '').strip(),
                account_number=data.get('account_number', '').strip(),
                branch=data.get('branch', '').strip(),
                branch_ar=data.get('branch_ar', '').strip(),
                swift_code=data.get('swift_code', '').strip(),
                iban=data.get('iban', '').strip(),
                is_primary=data.get('is_primary', 'false').lower() == 'true',
            )
            db.session.add(bank)
            db.session.flush()
            submitted_ids.add(bank.id)
            print(f"    Created bank id={bank.id}")
    
    # Delete banks that were removed from the array
    existing_banks = BuyerBank.query.filter_by(buyer_id=buyer_id).all()
    for bank in existing_banks:
        if bank.id not in submitted_ids:
            print(f"  Deleting bank id={bank.id} (not in submitted_ids)")
            db.session.delete(bank)
    
    # Enforce single-primary rule
    primary_banks = BuyerBank.query.filter_by(buyer_id=buyer_id, is_primary=True).all()
    if len(primary_banks) > 1:
        print(f"  Fixing {len(primary_banks)} primary banks - keeping only last one")
        for b in primary_banks[:-1]:
            b.is_primary = False
    
    print(f"  submitted_ids: {submitted_ids}")
    print(f"=== _save_banks_from_form complete ===\n")


@lookups_bp.route('/buyers/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_buyer(id):
    b = BuyerMaster.query.get_or_404(id)
    db.session.delete(b)
    db.session.commit()
    flash(_t('Buyer deleted.','تم حذف المشتري.'),'success')
    return redirect(url_for('lookups.list_buyers'))

@lookups_bp.route('/buyers/<int:id>/json')
@login_required
def buyer_json(id):
    b = BuyerMaster.query.get_or_404(id)
    def g(f): return getattr(b,f,None) or ''
    return jsonify({
        'id':b.id,'buyer_code':b.buyer_code or '',
        'buyer_name_en':g('buyer_name_en'),'buyer_name_ar':g('buyer_name_ar'),
        'vat_number':g('vat_number'),'crn':g('crn'),
        'phone':g('phone'),'fax':g('fax'),'email':g('email'),'website':g('website'),
        'report_color':g('report_color') or '#2563eb',
        'street_name':g('street_name'),'street_name_ar':g('street_name_ar'),
        'building_number':g('building_number'),'building_number_ar':g('building_number_ar'),
        'additional_number':g('additional_number'),'additional_number_ar':g('additional_number_ar'),
        'postal_code':g('postal_code'),'postal_code_ar':g('postal_code_ar'),
        'country':g('country') or 'Saudi Arabia','country_ar':g('country_ar'),
        'city':g('city'),'city_ar':g('city_ar'),
        'district':g('district'),'district_ar':g('district_ar'),
        'status':g('status') or 'active',
    })

@lookups_bp.route('/buyers/data')
@login_required
def buyers_data():
    lang  = session.get('lang','en')
    items = BuyerMaster.query.order_by(BuyerMaster.buyer_name_en).all()
    return jsonify([{
        'id':       b.id,
        'buyer_code': b.buyer_code or '',
        'en':       b.buyer_name_en,
        'ar':       b.buyer_name_ar or b.buyer_name_en,
        'label':    b.buyer_name_ar if lang=='ar' and b.buyer_name_ar else b.buyer_name_en,
        'vat_number': b.vat_number or '',
        'crn':      b.crn or '',
        'phone':    b.phone or '',
        'email':    b.email or '',
        'status':   b.status or 'active',
        'is_active':b.is_active,
        'report_color': b.report_color or '#2563eb',
    } for b in items])

# ── BUYER BANKS API (for loading banks on edit) ──
@lookups_bp.route('/buyers/<int:buyer_id>/banks')
@login_required
def buyer_banks(buyer_id):
    """Returns banks for loading into JS array on edit"""
    banks = BuyerBank.query.filter_by(buyer_id=buyer_id).order_by(BuyerBank.id).all()
    return jsonify([b.to_dict() for b in banks])

# Legacy API endpoints kept for backward compatibility
@lookups_bp.route('/buyers/<int:buyer_id>/banks/add', methods=['POST'])
@login_required
@admin_required
def add_buyer_bank(buyer_id):
    BuyerMaster.query.get_or_404(buyer_id)
    data = request.get_json() or {}
    b = BuyerBank(
        buyer_id=buyer_id,
        bank_name=data.get('bank_name','').strip(),
        bank_name_ar=data.get('bank_name_ar','').strip(),
        account_number=data.get('account_number','').strip(),
        branch=data.get('branch','').strip(),
        branch_ar=data.get('branch_ar','').strip(),
        swift_code=data.get('swift_code','').strip(),
        iban=data.get('iban','').strip(),
        is_primary=bool(data.get('is_primary',False)),
    )
    if b.is_primary:
        BuyerBank.query.filter_by(buyer_id=buyer_id, is_primary=True).update({'is_primary':False})
    db.session.add(b)
    db.session.commit()
    return jsonify({'ok':True, 'bank':b.to_dict()})

@lookups_bp.route('/buyers/banks/<int:bank_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_buyer_bank(bank_id):
    b = BuyerBank.query.get_or_404(bank_id)
    data = request.get_json() or {}
    b.bank_name     = data.get('bank_name', b.bank_name).strip()
    b.bank_name_ar  = data.get('bank_name_ar', b.bank_name_ar or '').strip()
    b.account_number= data.get('account_number', b.account_number or '').strip()
    b.branch        = data.get('branch', b.branch or '').strip()
    b.branch_ar     = data.get('branch_ar', b.branch_ar or '').strip()
    b.swift_code    = data.get('swift_code', b.swift_code or '').strip()
    b.iban          = data.get('iban', b.iban or '').strip()
    b.is_primary    = bool(data.get('is_primary', b.is_primary))
    if b.is_primary:
        BuyerBank.query.filter_by(buyer_id=b.buyer_id, is_primary=True).update({'is_primary':False})
        b.is_primary = True
    db.session.commit()
    return jsonify({'ok':True, 'bank':b.to_dict()})

@lookups_bp.route('/buyers/banks/<int:bank_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_buyer_bank(bank_id):
    b = BuyerBank.query.get_or_404(bank_id)
    db.session.delete(b)
    db.session.commit()
    return jsonify({'ok':True})
# ── ALLOWANCE TYPES MASTER ────────────────────────────────────────────
@lookups_bp.route('/allowance-types')
@login_required
def list_allowance_types():
    types = AllowanceType.query.order_by(AllowanceType.allowance_code).all()
    return render_template('lookups/allowance_types.html', types=types)

@lookups_bp.route('/allowance-types/add', methods=['POST'])
@login_required
@admin_required
def add_allowance_type():
    code = request.form.get('allowance_code','').strip().upper()
    en   = request.form.get('allowance_name_en','').strip()
    ar_n = request.form.get('allowance_name_ar','').strip()
    desc = request.form.get('description','').strip()
    active = request.form.get('is_active') == 'on'
    if not code or not en:
        flash(_t('Code and English name are required.','الكود والاسم الإنجليزي مطلوبان.'),'danger')
        return redirect(url_for('lookups.list_allowance_types'))
    if AllowanceType.query.filter_by(allowance_code=code).first():
        flash(_t(f'Code {code} already exists.', f'الكود {code} موجود مسبقاً.'),'danger')
        return redirect(url_for('lookups.list_allowance_types'))
    db.session.add(AllowanceType(allowance_code=code,allowance_name_en=en,allowance_name_ar=ar_n,description=desc,is_active=active))
    db.session.commit()
    flash(_t(f'Allowance type "{en}" added.',f'تم إضافة نوع البدل "{ar_n or en}".'),'success')
    return redirect(url_for('lookups.list_allowance_types'))

@lookups_bp.route('/allowance-types/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_allowance_type(id):
    t = AllowanceType.query.get_or_404(id)
    t.allowance_code    = request.form.get('allowance_code', t.allowance_code).strip().upper()
    t.allowance_name_en = request.form.get('allowance_name_en', t.allowance_name_en).strip()
    t.allowance_name_ar = request.form.get('allowance_name_ar', t.allowance_name_ar or '').strip()
    t.description       = request.form.get('description', t.description or '').strip()
    t.is_active         = request.form.get('is_active') == 'on'
    db.session.commit()
    flash(_t('Allowance type updated.','تم تحديث نوع البدل.'),'success')
    return redirect(url_for('lookups.list_allowance_types'))

@lookups_bp.route('/allowance-types/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_allowance_type(id):
    t = AllowanceType.query.get_or_404(id)
    if t.employee_allowances:
        flash(_t('Cannot delete: this type is used in employee allowances.',
                 'لا يمكن الحذف: هذا النوع مستخدم في بدلات الموظفين.'),'danger')
        return redirect(url_for('lookups.list_allowance_types'))
    db.session.delete(t)
    db.session.commit()
    flash(_t('Allowance type deleted.','تم حذف نوع البدل.'),'success')
    return redirect(url_for('lookups.list_allowance_types'))

@lookups_bp.route('/allowance-types/data')
@login_required
def allowance_types_data():
    lang = session.get('lang','en')
    types = AllowanceType.query.filter_by(is_active=True).order_by(AllowanceType.allowance_code).all()
    return jsonify([{
        'id':   t.id,
        'code': t.allowance_code,
        'en':   t.allowance_name_en,
        'ar':   t.allowance_name_ar or t.allowance_name_en,
        'label': t.allowance_name_ar if lang=='ar' and t.allowance_name_ar else t.allowance_name_en,
    } for t in types])

# ── EMPLOYEE ALLOWANCES ──────────────────────────────────────────────
@lookups_bp.route('/allowances')
@login_required
def list_allowances():
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    # Build allowances with employee names
    rows = []
    for emp in employees:
        for a in emp.allowance_rows.order_by(EmployeeAllowance.id).all():
            rows.append({'allowance': a, 'employee': emp})
    return render_template('lookups/allowances.html', rows=rows, employees=employees)

@lookups_bp.route('/allowances/add', methods=['POST'])
@login_required
@admin_required
def add_allowance():
    emp_id           = request.form.get('employee_id','').strip()
    allowance_type_id= request.form.get('allowance_type_id','').strip()
    amount           = request.form.get('amount','0').strip()
    if not emp_id or not allowance_type_id:
        flash(_t('Employee and allowance type are required.',
                 'الموظف ونوع البدل مطلوبان.'),'danger')
        return redirect(url_for('lookups.list_allowances'))
    emp = Employee.query.get_or_404(int(emp_id))
    atype = AllowanceType.query.get_or_404(int(allowance_type_id))
    # Unique check
    existing = EmployeeAllowance.query.filter_by(employee_id=emp.id, allowance_type_id=atype.id).first()
    if existing:
        flash(_t(f'Allowance type "{atype.allowance_name_en}" already exists for this employee.',
                 f'نوع البدل "{atype.allowance_name_ar or atype.allowance_name_en}" موجود مسبقاً لهذا الموظف.'),'danger')
        return redirect(url_for('lookups.list_allowances'))
    try: amount = float(amount)
    except: amount = 0.0
    db.session.add(EmployeeAllowance(employee_id=emp.id, allowance_type_id=atype.id,
                                     name=atype.allowance_name_en, name_ar=atype.allowance_name_ar, amount=amount))
    _recalc(emp)
    db.session.commit()
    flash(_t(f'Allowance "{atype.allowance_name_en}" added.',
             f'تم إضافة البدل "{atype.allowance_name_ar or atype.allowance_name_en}".'),'success')
    return redirect(url_for('lookups.list_allowances'))

@lookups_bp.route('/allowances/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_allowance(id):
    a = EmployeeAllowance.query.get_or_404(id)
    a.name    = request.form.get('name', a.name).strip()
    a.name_ar = request.form.get('name_ar', a.name_ar or '').strip()
    try: a.amount = float(request.form.get('amount', a.amount))
    except: pass
    _recalc(a.employee)
    db.session.commit()
    flash(_t('Allowance updated.','تم تحديث البدل.'),'success')
    return redirect(url_for('lookups.list_allowances'))

@lookups_bp.route('/allowances/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_allowance(id):
    a = EmployeeAllowance.query.get_or_404(id)
    emp = a.employee
    db.session.delete(a)
    _recalc(emp)
    db.session.commit()
    flash(_t('Allowance deleted.','تم حذف البدل.'),'success')
    return redirect(url_for('lookups.list_allowances'))

@lookups_bp.route('/allowances/data')
@login_required
def allowances_data():
    lang = session.get('lang','en')
    rows = EmployeeAllowance.query.join(Employee).order_by(Employee.name, EmployeeAllowance.id).all()
    return jsonify([{
        'id': a.id,
        'employee_id': a.employee_id,
        'employee_name': (a.employee.name_ar if lang=='ar' and a.employee.name_ar else a.employee.name),
        'employee_code': a.employee.employee_code,
        'name': a.name_ar if lang=='ar' and a.name_ar else a.name,
        'name_en': a.name,
        'name_ar': a.name_ar or '',
        'amount': a.amount,
    } for a in rows])

def _recalc(emp):
    """Recalculate total_allowances and net_salary for an employee."""
    total = sum(a.amount for a in emp.allowance_rows.all())
    emp.total_allowances = total
    emp.net_salary = (emp.basic_salary or 0) + total


@lookups_bp.route('/professions/add-quick', methods=['POST'])
@login_required
def add_profession_quick():
    from flask import request as req
    data = req.get_json() or {}
    en = (data.get('profession_en') or '').strip()
    ar = (data.get('profession_ar') or '').strip()
    if not en:
        return jsonify({'ok': False, 'error': 'Name required'})
    # Check duplicate
    existing = ProfessionMaster.query.filter_by(profession_en=en).first()
    if existing:
        return jsonify({'ok': True, 'id': existing.id, 'exists': True})
    p = ProfessionMaster(profession_en=en, profession_ar=ar or en)
    db.session.add(p)
    db.session.commit()
    return jsonify({'ok': True, 'id': p.id, 'profession_en': p.profession_en, 'profession_ar': p.profession_ar})


@lookups_bp.route('/allowance-types/add-quick', methods=['POST'])
@login_required
def add_allowance_type_quick():
    from flask import request as req
    data = req.get_json() or {}
    code = (data.get('allowance_code') or '').strip().upper()
    en   = (data.get('allowance_name_en') or '').strip()
    ar   = (data.get('allowance_name_ar') or '').strip()
    if not code or not en:
        return jsonify({'ok': False, 'error': 'Code and Name required'})
    existing = AllowanceType.query.filter_by(allowance_code=code).first()
    if existing:
        return jsonify({'ok': True, 'id': existing.id, 'exists': True})
    at = AllowanceType(allowance_code=code, allowance_name_en=en, allowance_name_ar=ar or en, is_active=True)
    db.session.add(at)
    db.session.commit()
    return jsonify({'ok': True, 'id': at.id})


# ══════════════════════════════════════════════════════════════════
# ITEM MASTER
# ══════════════════════════════════════════════════════════════════
import urllib.request, urllib.parse, json as _json
from models import ItemMaster, ItemCategory, ItemSubCategory, TaxCategory, VendorMaster

@lookups_bp.route('/items')
@login_required
def items_list():
    cats    = ItemCategory.query.order_by(ItemCategory.name_en).all()
    subcats = ItemSubCategory.query.order_by(ItemSubCategory.name_en).all()
    taxcats = TaxCategory.query.order_by(TaxCategory.name_en).all()
    vendors = VendorMaster.query.order_by(VendorMaster.vendor_name_en).all()
    uoms    = ['unit','hour','day','month','kg','gram','meter','liter','box','piece','set','pair','dozen']
    return render_template('lookups/items.html',
        cats=cats, subcats=subcats, taxcats=taxcats, vendors=vendors, uoms=uoms)

@lookups_bp.route('/items/data')
@login_required
def items_data():
    return jsonify([i.to_dict() for i in ItemMaster.query.order_by(ItemMaster.id.desc()).all()])

@lookups_bp.route('/items/<int:id>/json')
@login_required
def item_json(id):
    return jsonify(ItemMaster.query.get_or_404(id).to_dict())

@lookups_bp.route('/items/add', methods=['POST'])
@login_required
def item_add():
    f = request.form
    item = ItemMaster(
        item_code   = f.get('item_code','').strip(),
        article_no  = f.get('article_no','').strip(),
        name_en     = f.get('name_en','').strip(),
        name_ar     = f.get('name_ar','').strip(),
        print_name  = f.get('print_name','').strip(),
        uom         = f.get('uom','unit'),
        item_desc   = f.get('item_desc','').strip(),
        category_id     = int(f['category_id'])     if f.get('category_id')     else None,
        sub_category_id = int(f['sub_category_id']) if f.get('sub_category_id') else None,
        tax_category_id = int(f['tax_category_id']) if f.get('tax_category_id') else None,
        vendor_id       = int(f['vendor_id'])        if f.get('vendor_id')       else None,
        main_rate       = float(f.get('main_rate','0') or 0),
        last_purchase_rate = float(f.get('last_purchase_rate','0') or 0),
        retail_rate     = float(f.get('retail_rate','0') or 0),
        wholesale_rate  = float(f.get('wholesale_rate','0') or 0),
        special_rate    = float(f.get('special_rate','0') or 0),
        mrp             = float(f.get('mrp','0') or 0),
        minimum_sp      = float(f.get('minimum_sp','0') or 0),
        is_active       = f.get('is_active','1') == '1',
        created_by      = current_user.id,
    )
    db.session.add(item); db.session.commit()
    return jsonify({'ok': True, 'id': item.id})

@lookups_bp.route('/items/<int:id>/edit', methods=['POST'])
@login_required
def item_edit(id):
    item = ItemMaster.query.get_or_404(id)
    f = request.form
    item.item_code   = f.get('item_code','').strip()
    item.article_no  = f.get('article_no','').strip()
    item.name_en     = f.get('name_en','').strip()
    item.name_ar     = f.get('name_ar','').strip()
    item.print_name  = f.get('print_name','').strip()
    item.uom         = f.get('uom','unit')
    item.item_desc   = f.get('item_desc','').strip()
    item.category_id     = int(f['category_id'])     if f.get('category_id')     else None
    item.sub_category_id = int(f['sub_category_id']) if f.get('sub_category_id') else None
    item.tax_category_id = int(f['tax_category_id']) if f.get('tax_category_id') else None
    item.vendor_id       = int(f['vendor_id'])        if f.get('vendor_id')       else None
    item.main_rate       = float(f.get('main_rate','0') or 0)
    item.last_purchase_rate = float(f.get('last_purchase_rate','0') or 0)
    item.retail_rate     = float(f.get('retail_rate','0') or 0)
    item.wholesale_rate  = float(f.get('wholesale_rate','0') or 0)
    item.special_rate    = float(f.get('special_rate','0') or 0)
    item.mrp             = float(f.get('mrp','0') or 0)
    item.minimum_sp      = float(f.get('minimum_sp','0') or 0)
    item.is_active       = f.get('is_active','1') == '1'
    db.session.commit()
    return jsonify({'ok': True})

@lookups_bp.route('/items/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def item_delete(id):
    db.session.delete(ItemMaster.query.get_or_404(id))
    db.session.commit()
    return jsonify({'ok': True})

@lookups_bp.route('/items/categories/data')
@login_required
def item_cats_data():
    return jsonify([c.to_dict() for c in ItemCategory.query.order_by(ItemCategory.name_en).all()])

@lookups_bp.route('/items/categories/add', methods=['POST'])
@login_required
def item_category_add():
    """Quick-add a category from the Item Master form popup."""
    f = request.form
    name_en = f.get('name_en', '').strip()
    if not name_en:
        return jsonify({'ok': False, 'error': 'Category name (EN) is required'}), 400
    cat = ItemCategory(name_en=name_en, name_ar=f.get('name_ar', '').strip() or None)
    db.session.add(cat)
    db.session.commit()
    return jsonify({'ok': True, 'category': cat.to_dict()})

@lookups_bp.route('/items/sub-categories/<int:cat_id>')
@login_required
def item_subcats(cat_id):
    return jsonify([s.to_dict() for s in ItemSubCategory.query.filter_by(category_id=cat_id).all()])

@lookups_bp.route('/items/sub-categories/add', methods=['POST'])
@login_required
def item_subcategory_add():
    """Quick-add a sub-category from the Item Master form popup."""
    f = request.form
    category_id = f.get('category_id')
    name_en = f.get('name_en', '').strip()
    if not category_id:
        return jsonify({'ok': False, 'error': 'Category is required'}), 400
    if not name_en:
        return jsonify({'ok': False, 'error': 'Sub-category name (EN) is required'}), 400
    sub = ItemSubCategory(
        category_id=int(category_id),
        name_en=name_en,
        name_ar=f.get('name_ar', '').strip() or None,
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({'ok': True, 'sub_category': sub.to_dict()})

@lookups_bp.route('/items/tax-categories/data')
@login_required
def item_tax_cats_data():
    return jsonify([t.to_dict() for t in TaxCategory.query.order_by(TaxCategory.name_en).all()])

@lookups_bp.route('/items/tax-categories/add', methods=['POST'])
@login_required
def item_tax_category_add():
    """Quick-add a tax category from the Item Master form popup."""
    f = request.form
    name_en = f.get('name_en', '').strip()
    if not name_en:
        return jsonify({'ok': False, 'error': 'Tax category name (EN) is required'}), 400
    rate_raw = f.get('rate', '0').strip()
    try:
        rate = float(rate_raw) if rate_raw else 0
    except ValueError:
        return jsonify({'ok': False, 'error': 'Tax rate must be a number'}), 400
    tax = TaxCategory(name_en=name_en, name_ar=f.get('name_ar', '').strip() or None, rate=rate)
    db.session.add(tax)
    db.session.commit()
    return jsonify({'ok': True, 'tax_category': tax.to_dict()})


# ── Translation API ─────────────────────────────────────────────────
# Uses the free unofficial Google Translate web endpoint (same pattern
# as sellers.py's translate_text route) — no external package needed,
# no API key, no GoogleTranslator import that was previously missing.
@lookups_bp.route('/items/translate', methods=['POST'])
@login_required
def item_translate():
    data      = request.get_json(silent=True) or {}
    text      = (data.get('text') or request.args.get('text') or '').strip()
    direction = data.get('dir') or request.args.get('dir', 'en2ar')

    if not text:
        return jsonify({'ok': True, 'translated': ''})

    src, tgt = ('en', 'ar') if direction == 'en2ar' else ('ar', 'en')

    # Primary: unofficial Google Translate endpoint
    try:
        params = urllib.parse.urlencode({'client': 'gtx', 'sl': src, 'tl': tgt, 'dt': 't', 'q': text})
        url    = f'https://translate.googleapis.com/translate_a/single?{params}'
        req    = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as r:
            result = _json.loads(r.read().decode('utf-8'))
        translated = ''.join(chunk[0] for chunk in result[0] if chunk[0])
        if translated:
            return jsonify({'ok': True, 'translated': translated.strip()})
    except Exception:
        pass

    # Fallback: MyMemory (also free, no key)
    try:
        q   = urllib.parse.quote(text)
        url = f'https://api.mymemory.translated.net/get?q={q}&langpair={src}|{tgt}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            result = _json.loads(r.read().decode())
        translated = result.get('responseData', {}).get('translatedText', '')
        return jsonify({'ok': True, 'translated': translated})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'translated': ''}), 502