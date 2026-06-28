import os, uuid
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app, send_from_directory, jsonify, session)

def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en
from flask_login import login_required, current_user
from models import db, Seller, SellerBank, SellerDocument, ActivityLog
from forms import SellerForm, BankForm, SearchForm
from functools import wraps

sellers_bp = Blueprint('sellers', __name__)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            flash(_t('Access denied. Admin privileges required.', 'الوصول مرفوض. يلزم صلاحيات المدير.'), 'danger')
            return redirect(url_for('sellers.list_sellers'))
        return f(*args, **kwargs)
    return decorated

def generate_seller_code():
    last = Seller.query.order_by(Seller.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f'SEL-{num:05d}'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_file(file, seller_id):
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(seller_id))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, unique_name)
    file.save(path)
    return os.path.join(str(seller_id), unique_name)

def log_activity(seller_id, action, description):
    db.session.add(ActivityLog(
        seller_id=seller_id, user_id=current_user.id,
        action=action, description=description
    ))


# ── List ──────────────────────────────────────────────────────────────
@sellers_bp.route('/sellers')
@login_required
def list_sellers():
    q = request.args.get('q', '').strip()
    query = Seller.query
    if q:
        query = query.filter(
            db.or_(
                Seller.name.ilike(f'%{q}%'),
                Seller.seller_code.ilike(f'%{q}%'),
                Seller.email.ilike(f'%{q}%'),
                Seller.crn.ilike(f'%{q}%'),
                Seller.vat_number.ilike(f'%{q}%'),
            )
        )
    sort = request.args.get('sort', 'created_at')
    direction = request.args.get('dir', 'desc')
    col = getattr(Seller, sort, Seller.created_at)
    query = query.order_by(col.desc() if direction == 'desc' else col.asc())
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 15)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    seller_form = SellerForm()
    bank_form = BankForm()
    return render_template('sellers/list.html',
                           sellers=pagination.items,
                           pagination=pagination,
                           seller_form=seller_form,
                           bank_form=bank_form,
                           q=q, sort=sort, direction=direction)


# ── Add ───────────────────────────────────────────────────────────────
@sellers_bp.route('/sellers/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_seller():
    form = SellerForm()
    if form.validate_on_submit():
        seller = Seller(seller_code=generate_seller_code(), created_by=current_user.id)
        seller.name = form.name.data
        seller.vat_number = form.vat_number.data
        seller.crn = form.crn.data
        seller.phone = form.phone.data
        seller.fax = form.fax.data
        seller.email = form.email.data
        seller.website = form.website.data
        seller.report_color = form.report_color.data or '#16a34a'
        seller.street_name = form.street_name.data
        seller.building_number = form.building_number.data
        seller.additional_number = form.additional_number.data
        seller.district = form.district.data
        seller.city = form.city.data
        seller.postal_code = form.postal_code.data
        seller.country = form.country.data
        # AR fields from form
        seller.name_ar = request.form.get('name_ar', '')
        seller.vat_number_ar = request.form.get('vat_number_ar', '')
        seller.crn_ar = request.form.get('crn_ar', '')
        seller.street_name_ar = request.form.get('street_name_ar', '')
        seller.building_number_ar = request.form.get('building_number_ar', '')
        seller.additional_number_ar = request.form.get('additional_number_ar', '')
        seller.district_ar = request.form.get('district_ar', '')
        seller.city_ar = request.form.get('city_ar', '')
        seller.postal_code_ar = request.form.get('postal_code_ar', '')
        seller.country_ar = request.form.get('country_ar', '')
        db.session.add(seller)
        db.session.flush()

        # Handle logo uploads
        logo = request.files.get('logo')
        if logo and logo.filename and allowed_file(logo.filename):
            seller.logo_path = save_file(logo, seller.id)

        bg_logo = request.files.get('bg_logo')
        if bg_logo and bg_logo.filename and allowed_file(bg_logo.filename):
            seller.bg_logo_path = save_file(bg_logo, seller.id)

        log_activity(seller.id, 'CREATE', f'Seller {seller.seller_code} created')
        db.session.commit()
        flash(_t(f'Seller {seller.seller_code} added successfully!', f'تم إضافة البائع {seller.seller_code} بنجاح'), 'success')
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f'{field}: {e}', 'danger')
    return redirect(url_for('sellers.list_sellers'))


# ── Edit (GET shows modal data via JSON, POST saves) ──────────────────
@sellers_bp.route('/sellers/<int:id>/json')
@login_required
def seller_json(id):
    s = Seller.query.get_or_404(id)
    def g(f): return getattr(s, f, None) or ''
    return jsonify({
        'id': s.id,
        'name': g('name'), 'vat_number': g('vat_number'), 'crn': g('crn'),
        'phone': g('phone'), 'fax': g('fax'), 'email': g('email'),
        'website': g('website'), 'report_color': g('report_color') or '#16a34a',
        'street_name': g('street_name'), 'building_number': g('building_number'),
        'additional_number': g('additional_number'), 'district': g('district'),
        'city': g('city'), 'postal_code': g('postal_code'), 'country': g('country'),
        'name_ar': g('name_ar'), 'vat_number_ar': g('vat_number_ar'), 'crn_ar': g('crn_ar'),
        'street_name_ar': g('street_name_ar'), 'building_number_ar': g('building_number_ar'),
        'additional_number_ar': g('additional_number_ar'), 'district_ar': g('district_ar'),
        'city_ar': g('city_ar'), 'postal_code_ar': g('postal_code_ar'), 'country_ar': g('country_ar'),
        'banks': [{'id': b.id, 'bank_name': b.bank_name, 'account_number': b.account_number or '',
                   'branch': b.branch or '', 'swift_code': b.swift_code or '',
                   'iban': b.iban or '', 'is_primary': b.is_primary} for b in s.banks]
    })


@sellers_bp.route('/sellers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_seller(id):
    seller = Seller.query.get_or_404(id)
    form = SellerForm()
    if form.validate_on_submit():
        seller.name = form.name.data
        seller.vat_number = form.vat_number.data
        seller.crn = form.crn.data
        seller.phone = form.phone.data
        seller.fax = form.fax.data
        seller.email = form.email.data
        seller.website = form.website.data
        seller.report_color = form.report_color.data or '#16a34a'
        seller.street_name = form.street_name.data
        seller.building_number = form.building_number.data
        seller.additional_number = form.additional_number.data
        seller.district = form.district.data
        seller.city = form.city.data
        seller.postal_code = form.postal_code.data
        seller.country = form.country.data
        seller.name_ar = request.form.get('name_ar', '')
        seller.vat_number_ar = request.form.get('vat_number_ar', '')
        seller.crn_ar = request.form.get('crn_ar', '')
        seller.street_name_ar = request.form.get('street_name_ar', '')
        seller.building_number_ar = request.form.get('building_number_ar', '')
        seller.additional_number_ar = request.form.get('additional_number_ar', '')
        seller.district_ar = request.form.get('district_ar', '')
        seller.city_ar = request.form.get('city_ar', '')
        seller.postal_code_ar = request.form.get('postal_code_ar', '')
        seller.country_ar = request.form.get('country_ar', '')
        seller.updated_at = datetime.utcnow()

        logo = request.files.get('logo')
        if logo and logo.filename and allowed_file(logo.filename):
            seller.logo_path = save_file(logo, seller.id)
        bg_logo = request.files.get('bg_logo')
        if bg_logo and bg_logo.filename and allowed_file(bg_logo.filename):
            seller.bg_logo_path = save_file(bg_logo, seller.id)

        log_activity(seller.id, 'EDIT', f'Seller {seller.seller_code} updated')
        db.session.commit()
        flash(_t('Seller updated successfully!', 'تم تحديث البائع بنجاح'), 'success')
    else:
        for field, errors in form.errors.items():
            for e in errors:
                flash(f'{field}: {e}', 'danger')
    return redirect(url_for('sellers.list_sellers'))


# ── Delete ────────────────────────────────────────────────────────────
@sellers_bp.route('/sellers/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_seller(id):
    seller = Seller.query.get_or_404(id)
    for doc in seller.documents:
        fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
        if os.path.exists(fpath):
            os.remove(fpath)
    db.session.delete(seller)
    db.session.commit()
    flash(_t(f'Seller {seller.seller_code} deleted.', f'تم حذف البائع {seller.seller_code}'), 'success')
    return redirect(url_for('sellers.list_sellers'))


# ── Bank CRUD (AJAX) ──────────────────────────────────────────────────
@sellers_bp.route('/sellers/<int:id>/banks/add', methods=['POST'])
@login_required
def add_bank(id):
    seller = Seller.query.get_or_404(id)
    data = request.get_json() or request.form
    if data.get('is_primary') in [True, 'true', '1', 'on']:
        SellerBank.query.filter_by(seller_id=id).update({'is_primary': False})
    bank = SellerBank(
        seller_id=id,
        bank_name=data.get('bank_name', ''),
        account_number=data.get('account_number', ''),
        branch=data.get('branch', ''),
        swift_code=data.get('swift_code', ''),
        iban=data.get('iban', ''),
        is_primary=data.get('is_primary') in [True, 'true', '1', 'on']
    )
    db.session.add(bank)
    db.session.commit()
    return jsonify({'ok': True, 'id': bank.id, 'bank': bank.to_dict()})


@sellers_bp.route('/sellers/banks/<int:bid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_bank(bid):
    bank = SellerBank.query.get_or_404(bid)
    db.session.delete(bank)
    db.session.commit()
    return jsonify({'success': True})


# ── Documents ─────────────────────────────────────────────────────────


@sellers_bp.route('/sellers/<int:id>/banks')
@login_required
def list_seller_banks(id):
    banks = SellerBank.query.filter_by(seller_id=id).order_by(SellerBank.id).all()
    return jsonify([b.to_dict() for b in banks])

@sellers_bp.route('/sellers/banks/<int:bid>/edit', methods=['POST'])
@login_required
def edit_seller_bank(bid):
    b    = SellerBank.query.get_or_404(bid)
    data = request.get_json() or request.form
    if data.get('is_primary') in [True,'true','1','on']:
        SellerBank.query.filter_by(seller_id=b.seller_id).update({'is_primary':False})
    b.bank_name      = data.get('bank_name',      b.bank_name)
    b.account_number = data.get('account_number', b.account_number or '')
    b.branch         = data.get('branch',         b.branch or '')
    b.swift_code     = data.get('swift_code',     b.swift_code or '')
    b.iban           = data.get('iban',            b.iban or '')
    b.is_primary     = data.get('is_primary') in [True,'true','1','on']
    db.session.commit()
    return jsonify({'ok': True, 'bank': b.to_dict()})

@sellers_bp.route('/sellers/<int:id>/documents/upload', methods=['POST'])
@login_required
def upload_document(id):
    file = request.files.get('file')
    if not file or not file.filename:
        flash(_t('No file selected.', 'لم يتم اختيار ملف'), 'danger')
        return redirect(url_for('sellers.list_sellers'))
    if not allowed_file(file.filename):
        flash(_t('File type not allowed.', 'نوع الملف غير مسموح'), 'danger')
        return redirect(url_for('sellers.list_sellers'))
    path = save_file(file, id)
    doc = SellerDocument(
        seller_id=id,
        document_type=request.form.get('document_type', 'other'),
        document_name=request.form.get('document_name', file.filename),
        file_path=path,
        file_size=os.path.getsize(os.path.join(current_app.config['UPLOAD_FOLDER'], path)),
        uploaded_by=current_user.id
    )
    db.session.add(doc)
    db.session.commit()
    flash('Document uploaded.', 'success')
    return redirect(url_for('sellers.list_sellers'))


@sellers_bp.route('/documents/<int:did>/download')
@login_required
def download_document(did):
    doc = SellerDocument.query.get_or_404(did)
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(doc.seller_id))
    filename = doc.file_path.split(os.sep)[-1]
    return send_from_directory(folder, filename, as_attachment=True)


@sellers_bp.route('/documents/<int:did>/delete', methods=['POST'])
@login_required
@admin_required
def delete_document(did):
    doc = SellerDocument.query.get_or_404(did)
    fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
    if os.path.exists(fpath):
        os.remove(fpath)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'success': True})


# ── Export ────────────────────────────────────────────────────────────
@sellers_bp.route('/sellers/export')
@login_required
def export_sellers():
    import csv, io
    from flask import make_response
    sellers = Seller.query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Code', 'Name', 'VAT Number', 'CRN', 'Phone', 'Fax',
                     'Email', 'Website', 'City', 'Country', 'Status', 'Created'])
    for s in sellers:
        writer.writerow([s.seller_code, s.name, s.vat_number or '', s.crn or '',
                         s.phone or '', s.fax or '', s.email or '', s.website or '',
                         s.city or '', s.country or '', s.status,
                         s.created_at.strftime('%Y-%m-%d')])
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=sellers_export.csv'
    response.headers['Content-type'] = 'text/csv'
    return response


# ── Translation API ────────────────────────────────────────────────────
# Uses Google Translate unofficial endpoint — accurate, free, no key needed
@sellers_bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    import urllib.request, urllib.parse, json as _json
    data     = request.get_json()
    text     = (data.get('text') or '').strip()
    direction = data.get('direction', 'en|ar')   # 'en|ar' or 'ar|en'
    if not text:
        return jsonify({'translated': ''})

    src, tgt = direction.split('|')

    # ── Try Google Translate (unofficial, accurate) ──
    try:
        params = urllib.parse.urlencode({
            'client': 'gtx',
            'sl':     src,
            'tl':     tgt,
            'dt':     't',
            'q':      text,
        })
        url = f'https://translate.googleapis.com/translate_a/single?{params}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=6) as r:
            result = _json.loads(r.read().decode('utf-8'))
        # result[0] is a list of [translated_chunk, original_chunk, ...]
        translated = ''.join(
            chunk[0] for chunk in result[0] if chunk[0]
        )
        if translated:
            return jsonify({'translated': translated.strip()})
    except Exception:
        pass

    # ── Fallback: MyMemory ──
    try:
        q   = urllib.parse.quote(text)
        url = f'https://api.mymemory.translated.net/get?q={q}&langpair={direction}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            result = _json.loads(r.read().decode())
        translated = result.get('responseData', {}).get('translatedText', '')
        return jsonify({'translated': translated})
    except Exception as e:
        return jsonify({'translated': '', 'error': str(e)})


# ── AG-Grid data endpoint ─────────────────────────────────────────────
@sellers_bp.route('/sellers/data')
@login_required
def sellers_data():
    sellers = Seller.query.order_by(Seller.created_at.desc()).all()
    rows = []
    for s in sellers:
        rows.append({
            'id': s.id,
            'seller_code': s.seller_code or '',
            'name': s.name or '',
            'name_ar': getattr(s,'name_ar','') or '',
            'vat_number': s.vat_number or '',
            'crn': s.crn or '',
            'phone': s.phone or '',
            'fax': s.fax or '',
            'email': s.email or '',
            'website': s.website or '',
            'street_name': s.street_name or '',
            'building_number': s.building_number or '',
            'additional_number': s.additional_number or '',
            'district': s.district or '',
            'district_ar': getattr(s,'district_ar','') or '',
            'city': s.city or '',
            'city_ar': getattr(s,'city_ar','') or '',
            'postal_code': s.postal_code or '',
            'country': s.country or '',
            'country_ar': getattr(s,'country_ar','') or '',
            'report_color': s.report_color or '#16a34a',
            'status': s.status or '',
            'created_at': s.created_at.strftime('%Y-%m-%d') if s.created_at else '',
        })
    return jsonify(rows)