from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from models import db, ProfessionMaster, BuyerMaster
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
    items = BuyerMaster.query.order_by(BuyerMaster.buyer_name_en).all()
    return render_template('lookups/buyers.html', items=items)

@lookups_bp.route('/buyers/add', methods=['POST'])
@login_required
@admin_required
def add_buyer():
    en = request.form.get('buyer_name_en','').strip()
    ar = request.form.get('buyer_name_ar','').strip()
    if not en:
        flash(_t('English name required','الاسم الإنجليزي مطلوب'),'danger')
        return redirect(url_for('lookups.list_buyers'))
    db.session.add(BuyerMaster(buyer_name_en=en, buyer_name_ar=ar))
    db.session.commit()
    flash(_t(f'Buyer "{en}" added.',f'تم إضافة المشتري "{ar or en}"'),'success')
    return redirect(url_for('lookups.list_buyers'))

@lookups_bp.route('/buyers/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_buyer(id):
    b = BuyerMaster.query.get_or_404(id)
    b.buyer_name_en = request.form.get('buyer_name_en', b.buyer_name_en).strip()
    b.buyer_name_ar = request.form.get('buyer_name_ar', b.buyer_name_ar or '').strip()
    b.is_active = request.form.get('is_active') == 'on'
    db.session.commit()
    flash(_t('Updated.','تم التحديث'),'success')
    return redirect(url_for('lookups.list_buyers'))

@lookups_bp.route('/buyers/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_buyer(id):
    db.session.delete(BuyerMaster.query.get_or_404(id))
    db.session.commit()
    flash(_t('Deleted.','تم الحذف'),'success')
    return redirect(url_for('lookups.list_buyers'))

@lookups_bp.route('/buyers/data')
@login_required
def buyers_data():
    lang = session.get('lang','en')
    items = BuyerMaster.query.filter_by(is_active=True).order_by(BuyerMaster.buyer_name_en).all()
    return jsonify([{'id':b.id,'en':b.buyer_name_en,'ar':b.buyer_name_ar or b.buyer_name_en,
                     'label':b.buyer_name_ar if lang=='ar' else b.buyer_name_en} for b in items])