from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from models import db, WorkAllocation, Employee
from datetime import datetime, date
import calendar

wa_bp = Blueprint('work_allocations', __name__)

def _t(en, ar): return ar if session.get('lang') == 'ar' else en
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def dec(*a, **kw):
        if not current_user.is_admin():
            flash(_t('Admin access required.','مطلوب صلاحية مدير.'),'danger')
            return redirect(url_for('work_allocations.list_wa'))
        return f(*a, **kw)
    return dec

@wa_bp.route('/work-allocations')
@login_required
def list_wa():
    return render_template('work_allocations/list.html')

@wa_bp.route('/work-allocations/data')
@login_required
def wa_data():
    lang = session.get('lang', 'en')
    rows = WorkAllocation.query.order_by(WorkAllocation.id.desc()).all()
    return jsonify([r.to_dict() for r in rows])

@wa_bp.route('/work-allocations/employees')
@login_required
def wa_employees():
    """Return active employees for dropdown"""
    lang = session.get('lang', 'en')
    emps = Employee.query.filter_by(is_active=True).order_by(Employee.employee_code).all()
    return jsonify([{
        'id': e.id,
        'employee_code': e.employee_code,
        'name': e.name,
        'name_ar': e.name_ar or '',
        'nationality': e.nationality or '',
        'passport_number': e.passport_number or '',
        'iqama_number': e.iqama_number or '',
        'profession': e.profession or '',
        'kafeel_name': e.kafeel_name or '',
        'kafeel_name_ar': e.kafeel_name_ar or '',
        'joining_date': e.joining_date.strftime('%Y-%m-%d') if e.joining_date else '',
        'department': e.department or '',
        'department_ar': e.department_ar or '',
        'label': f"{e.employee_code} — {e.name_ar if lang=='ar' and e.name_ar else e.name}",
    } for e in emps])

@wa_bp.route('/work-allocations/add', methods=['POST'])
@login_required
@admin_required
def add_wa():
    f = request.form
    # Support multiple employee IDs
    employee_ids = f.getlist('employee_id[]') or ([f.get('employee_id')] if f.get('employee_id') else [])
    employee_ids = [int(x) for x in employee_ids if x and str(x).isdigit()]
    if not employee_ids:
        flash(_t('At least one employee required.','مطلوب موظف واحد على الأقل.'),'danger')
        return redirect(url_for('work_allocations.list_wa'))
    def parse_date(val):
        if not val: return None
        try: return datetime.strptime(val, '%Y-%m-%d').date()
        except: return None
    added = 0
    for emp_id in employee_ids:
        wa = WorkAllocation(
            employee_id=emp_id,
            buyer_id=f.get('buyer_id', type=int),
            status=f.get('status','active'),
            month=f.get('month','').strip(),
            company=f.get('company','').strip(),
            company_ar=f.get('company_ar','').strip(),
            department=f.get('department','').strip(),
            department_ar=f.get('department_ar','').strip(),
            section=f.get('section','').strip(),
            section_ar=f.get('section_ar','').strip(),
            shift_type=f.get('shift_type','').strip(),
            joining_date=parse_date(f.get('joining_date')),
            end_date=parse_date(f.get('end_date')),
            created_by=current_user.id,
        )
        db.session.add(wa)
        added += 1
    db.session.commit()
    flash(_t(f'{added} work allocation(s) added.',f'تم إضافة {added} توزيع/توزيعات عمل.'),'success')
    return redirect(url_for('work_allocations.list_wa'))

@wa_bp.route('/work-allocations/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_wa(id):
    wa = WorkAllocation.query.get_or_404(id)
    f = request.form
    def parse_date(val):
        if not val: return None
        try: return datetime.strptime(val, '%Y-%m-%d').date()
        except: return None
    wa.status      = f.get('status', wa.status)
    wa.month       = f.get('month', wa.month or '').strip()
    wa.company     = f.get('company', wa.company or '').strip()
    wa.company_ar  = f.get('company_ar', wa.company_ar or '').strip()
    wa.department  = f.get('department', wa.department or '').strip()
    wa.department_ar = f.get('department_ar', wa.department_ar or '').strip()
    wa.section     = f.get('section', wa.section or '').strip()
    wa.section_ar  = f.get('section_ar', wa.section_ar or '').strip()
    wa.shift_type  = f.get('shift_type', wa.shift_type or '').strip()
    wa.joining_date= parse_date(f.get('joining_date'))
    wa.end_date    = parse_date(f.get('end_date'))
    buyer_id = f.get('buyer_id', type=int)
    if buyer_id: wa.buyer_id = buyer_id
    # Batch edit extra employees with same details
    extra_ids = [int(x) for x in f.getlist('extra_employee_id[]') if x and str(x).isdigit()]
    for eid in extra_ids:
        extra = WorkAllocation(
            employee_id=eid,
            buyer_id=buyer_id,
            status=wa.status, month=wa.month,
            company=wa.company, company_ar=wa.company_ar,
            department=wa.department, department_ar=wa.department_ar,
            section=wa.section, section_ar=wa.section_ar,
            shift_type=wa.shift_type,
            joining_date=wa.joining_date, end_date=wa.end_date,
            created_by=current_user.id,
        )
        db.session.add(extra)
    db.session.commit()
    flash(_t('Work allocation updated.','تم تحديث توزيع العمل.'),'success')
    return redirect(url_for('work_allocations.list_wa'))

@wa_bp.route('/work-allocations/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_wa(id):
    wa = WorkAllocation.query.get_or_404(id)
    db.session.delete(wa)
    db.session.commit()
    flash(_t('Work allocation deleted.','تم حذف توزيع العمل.'),'success')
    return redirect(url_for('work_allocations.list_wa'))

@wa_bp.route('/work-allocations/<int:id>/json')
@login_required
def wa_json(id):
    wa = WorkAllocation.query.get_or_404(id)
    return jsonify(wa.to_dict())