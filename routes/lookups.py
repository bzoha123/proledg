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
    db.session.flush()
    # Save pending bank details
    names = request.form.getlist('bank_bank_name[]')
    accts = request.form.getlist('bank_account_number[]')
    brchs = request.form.getlist('bank_branch[]')
    swfts = request.form.getlist('bank_swift_code[]')
    ibans = request.form.getlist('bank_iban[]')
    prims = request.form.getlist('bank_is_primary[]')
    for i,bn in enumerate(names):
        if not bn.strip(): continue
        db.session.add(BuyerBank(
            buyer_id=b.id,
            bank_name=bn.strip(),
            account_number=accts[i].strip() if i<len(accts) else '',
            branch=brchs[i].strip() if i<len(brchs) else '',
            swift_code=swfts[i].strip() if i<len(swfts) else '',
            iban=ibans[i].strip() if i<len(ibans) else '',
            is_primary=prims[i]=='1' if i<len(prims) else False,
        ))
    db.session.commit()
    flash(_t(f'Buyer {code} added.', f'تم إضافة المشتري {code}.'),'success')
    return redirect(url_for('lookups.list_buyers'))

@lookups_bp.route('/buyers/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_buyer(id):
    b = BuyerMaster.query.get_or_404(id)
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
    db.session.commit()
    flash(_t('Buyer updated.','تم تحديث المشتري.'),'success')
    return redirect(url_for('lookups.list_buyers'))

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
        'street_name':g('street_name'),'building_number':g('building_number'),
        'additional_number':g('additional_number'),
        'postal_code':g('postal_code'),
        'country':g('country') or 'Saudi Arabia',
        'city':g('city'),'district':g('district'),
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

# ── BUYER BANKS API ──────────────────────────────────────────────────
@lookups_bp.route('/buyers/<int:buyer_id>/banks')
@login_required
def buyer_banks(buyer_id):
    banks = BuyerBank.query.filter_by(buyer_id=buyer_id).order_by(BuyerBank.id).all()
    return jsonify([b.to_dict() for b in banks])

@lookups_bp.route('/buyers/<int:buyer_id>/banks/add', methods=['POST'])
@login_required
@admin_required
def add_buyer_bank(buyer_id):
    BuyerMaster.query.get_or_404(buyer_id)
    data = request.get_json() or {}
    b = BuyerBank(
        buyer_id=buyer_id,
        bank_name=data.get('bank_name','').strip(),
        account_number=data.get('account_number','').strip(),
        branch=data.get('branch','').strip(),
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
    b.account_number= data.get('account_number', b.account_number or '').strip()
    b.branch        = data.get('branch', b.branch or '').strip()
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

@lookups_bp.route('/items/sub-categories/<int:cat_id>')
@login_required
def item_subcats(cat_id):
    return jsonify([s.to_dict() for s in ItemSubCategory.query.filter_by(category_id=cat_id).all()])