from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
from models import db, PurchaseTaxCode, SalesTaxCode
import re

tax_bp = Blueprint('tax_codes', __name__)


def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en


# Small helper to DRY up the two identical masters.
def _model(kind):
    return PurchaseTaxCode if kind == 'purchase' else SalesTaxCode


# ── Pages ───────────────────────────────────────────────────────
@tax_bp.route('/purchase-tax-codes')
@login_required
def purchase_tax_page():
    return render_template('tax_codes/tax_list.html',
                           kind='purchase', title_en='Purchase Tax Codes',
                           title_ar='رموز ضريبة الشراء')


@tax_bp.route('/sales-tax-codes')
@login_required
def sales_tax_page():
    return render_template('tax_codes/tax_list.html',
                           kind='sales', title_en='Sales Tax Codes',
                           title_ar='رموز ضريبة البيع')


# ── Data ────────────────────────────────────────────────────────
@tax_bp.route('/<kind>-tax-codes/data')
@login_required
def tax_data(kind):
    if kind not in ('purchase', 'sales'):
        return jsonify([]), 404
    rows = _model(kind).query.order_by(_model(kind).tax_code).all()
    return jsonify([r.to_dict() for r in rows])


# ── Create ──────────────────────────────────────────────────────
@tax_bp.route('/<kind>-tax-codes/add', methods=['POST'])
@login_required
def tax_add(kind):
    if kind not in ('purchase', 'sales'):
        return jsonify({'ok': False, 'error': 'bad kind'}), 404
    M = _model(kind)
    f = request.form
    account_code = f.get('account_code', '').strip()
    tax_code     = f.get('tax_code', '').strip()
    section      = f.get('section', '').strip()
    status       = f.get('status', 'Active')
    if status not in ('Active', 'Inactive'):
        status = 'Active'

    # Validation
    if not account_code or not tax_code or not section:
        return jsonify({'ok': False, 'error': _t('Account Code, Tax Code and Section are required.',
                                                  'رمز الحساب والرمز الضريبي والوصف مطلوبة')}), 400
    
    # Store the account code as a percentage. The edit route does the same,
    # so append % rather than rejecting a value that arrives without it.
    if account_code and not account_code.endswith('%'):
        account_code = account_code + '%'
    
    # Tax code must be alphanumeric
    if not re.match(r'^[A-Za-z0-9]+$', tax_code):
        return jsonify({'ok': False, 'error': _t('Tax Code must contain only letters and numbers (e.g., P1)',
                                                  'الرمز الضريبي يجب أن يحتوي على حروف وأرقام فقط (مثال: P1)')}), 400
    
    if M.query.filter_by(tax_code=tax_code).first():
        return jsonify({'ok': False, 'error': _t(f'Tax Code "{tax_code}" already exists.',
                                                  f'الرمز الضريبي "{tax_code}" موجود بالفعل')}), 400
    try:
        db.session.add(M(account_code=account_code, tax_code=tax_code,
                         section=section, status=status))
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Update (account_code, section, status; tax_code stays fixed) ─
@tax_bp.route('/<kind>-tax-codes/<int:id>/edit', methods=['POST'])
@login_required
def tax_edit(kind, id):
    if kind not in ('purchase', 'sales'):
        return jsonify({'ok': False, 'error': 'bad kind'}), 404
    row = _model(kind).query.get_or_404(id)
    f = request.form
    account_code = f.get('account_code', '').strip()
    section      = f.get('section', '').strip()
    status = f.get('status', row.status)
    
    # Account code must end with %
    if account_code and not account_code.endswith('%'):
        account_code = account_code + '%'
    
    row.account_code = account_code
    row.section      = section
    row.status = status if status in ('Active', 'Inactive') else row.status
    try:
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Delete ──────────────────────────────────────────────────────
@tax_bp.route('/<kind>-tax-codes/<int:id>/delete', methods=['POST'])
@login_required
def tax_delete(kind, id):
    if kind not in ('purchase', 'sales'):
        return jsonify({'ok': False, 'error': 'bad kind'}), 404
    row = _model(kind).query.get_or_404(id)
    try:
        db.session.delete(row)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500