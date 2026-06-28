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
            flash(_t('Access denied. Admin privileges required.',
                     'الوصول مرفوض. يلزم صلاحيات المدير.'), 'danger')
            return redirect(url_for('sellers.list_sellers'))
        return f(*args, **kwargs)
    return decorated


def generate_seller_code():
    last = Seller.query.order_by(Seller.id.desc()).first()
    num  = (last.id + 1) if last else 1
    return f'SEL-{num:05d}'


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in \
           current_app.config.get('ALLOWED_EXTENSIONS',
                                   {'jpg', 'jpeg', 'png', 'pdf', 'docx', 'xlsx', 'doc'})


def save_file(file, seller_id):
    ext         = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    folder      = os.path.join(current_app.config['UPLOAD_FOLDER'], str(seller_id))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, unique_name)
    file.save(path)
    return os.path.join(str(seller_id), unique_name)


def log_activity(action, target, target_id, detail=''):
    try:
        db.session.add(ActivityLog(
            user_id    = current_user.id,
            action     = action,
            target     = target,
            target_id  = target_id,
            detail     = detail,
            ip_address = request.remote_addr,
        ))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# SERIALIZER
# ─────────────────────────────────────────────────────────────────────

def _doc_to_dict(doc):
    """Serialize a SellerDocument for the frontend.
    Returns both (document_type / doc_type) and (document_name / doc_name)
    aliases so the JS doesn't need to know which version the server used.
    issue_date is guarded with hasattr so missing columns don't crash.
    """
    uploader = None
    if doc.uploaded_by:
        from models import User
        uploader = User.query.get(doc.uploaded_by)
    return {
        'id':               doc.id,
        'seller_id':        doc.seller_id,
        # both aliases
        'document_type':    doc.document_type or '',
        'doc_type':         doc.document_type or '',
        'document_name':    doc.document_name or '',
        'doc_name':         doc.document_name or '',
        # issue_date may not exist in DB yet — safe fallback
        'issue_date':       str(getattr(doc, 'issue_date', '') or ''),
        'expiry_date':      str(doc.expiry_date or '') if doc.expiry_date else '',
        'uploaded_at':      doc.uploaded_at.strftime('%Y-%m-%d %H:%M') if doc.uploaded_at else '',
        'uploaded_by':      doc.uploaded_by,
        'uploaded_by_name': uploader.username if uploader else '',
        'file_path':        doc.file_path or '',
        'file_size_kb':     round((doc.file_size or 0) / 1024, 1),
    }


# ─────────────────────────────────────────────────────────────────────
# FORM HELPERS  (called by add_seller / edit_seller after flush)
# ─────────────────────────────────────────────────────────────────────

def _save_docs_from_form(seller_id):
    """
    Reads  docs[N][doc_type], docs[N][file] ...  from request.form/files
    and upserts SellerDocument rows.
    Also deletes any existing docs that are no longer in the submitted list.
    """
    from datetime import date as _date
    i = 0
    submitted_ids = set()

    while True:
        prefix   = f'docs[{i}]'
        doc_type = request.form.get(f'{prefix}[doc_type]', '').strip()
        doc_name = request.form.get(f'{prefix}[doc_name]', '').strip()
        if not doc_type and not doc_name:
            break

        db_id_str  = request.form.get(f'{prefix}[_db_id]', '').strip()
        issue_raw  = request.form.get(f'{prefix}[issue_date]',  '').strip()
        expiry_raw = request.form.get(f'{prefix}[expiry_date]', '').strip()
        file_obj   = request.files.get(f'{prefix}[file]')

        if db_id_str:
            submitted_ids.add(int(db_id_str))
            doc = SellerDocument.query.get(int(db_id_str))
            if doc and doc.seller_id == seller_id:
                doc.document_type = doc_type or doc.document_type
                doc.document_name = doc_name or doc.document_name
                if issue_raw:
                    try:   doc.issue_date = _date.fromisoformat(issue_raw)
                    except (ValueError, AttributeError): pass
                if expiry_raw:
                    try:   doc.expiry_date = _date.fromisoformat(expiry_raw)
                    except ValueError: pass
                if file_obj and file_obj.filename and allowed_file(file_obj.filename):
                    old = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
                    if os.path.exists(old): os.remove(old)
                    doc.file_path = save_file(file_obj, seller_id)
                    doc.file_size = os.path.getsize(
                        os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path))
                db.session.add(doc)
        else:
            # new document — needs at least doc_type and doc_name
            if not doc_type or not doc_name:
                i += 1; continue

            path      = ''
            file_size = 0
            if file_obj and file_obj.filename and allowed_file(file_obj.filename):
                path      = save_file(file_obj, seller_id)
                file_size = os.path.getsize(
                    os.path.join(current_app.config['UPLOAD_FOLDER'], path))

            doc = SellerDocument(
                seller_id     = seller_id,
                document_type = doc_type,
                document_name = doc_name,
                file_path     = path,
                file_size     = file_size,
                uploaded_by   = current_user.id,
                uploaded_at   = datetime.utcnow(),
            )
            if issue_raw:
                try:   doc.issue_date = _date.fromisoformat(issue_raw)
                except (ValueError, AttributeError): pass
            if expiry_raw:
                try:   doc.expiry_date = _date.fromisoformat(expiry_raw)
                except ValueError: pass
            db.session.add(doc)
        i += 1

    # Delete docs that were removed from the form
    if submitted_ids:
        existing_ids = {d.id for d in SellerDocument.query.filter_by(seller_id=seller_id).all()}
        to_delete    = existing_ids - submitted_ids
        if to_delete:
            for doc in SellerDocument.query.filter(
                    SellerDocument.id.in_(to_delete),
                    SellerDocument.seller_id == seller_id).all():
                if doc.file_path:
                    fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
                    if os.path.exists(fpath): os.remove(fpath)
                db.session.delete(doc)


def _save_banks_from_form(seller_id):
    """
    Reads  banks[N][field] ...  from request.form and upserts SellerBank rows.
    Also deletes banks that were removed from the form.
    """
    i = 0
    submitted_ids = set()

    while True:
        prefix    = f'banks[{i}]'
        bank_name = request.form.get(f'{prefix}[bank_name]', '').strip()
        if not bank_name:
            break

        db_id_str      = request.form.get(f'{prefix}[_db_id]',        '').strip()
        is_primary     = request.form.get(f'{prefix}[is_primary]',    '0') == '1'
        bank_name_ar   = request.form.get(f'{prefix}[bank_name_ar]',  '').strip()
        branch         = request.form.get(f'{prefix}[branch]',         '').strip()
        branch_ar      = request.form.get(f'{prefix}[branch_ar]',      '').strip()
        account_number = request.form.get(f'{prefix}[account_number]', '').strip()
        swift_code     = request.form.get(f'{prefix}[swift_code]',     '').strip()
        iban           = request.form.get(f'{prefix}[iban]',           '').strip()

        if db_id_str:
            submitted_ids.add(int(db_id_str))
            bank = SellerBank.query.get(int(db_id_str))
            if bank and bank.seller_id == seller_id:
                if is_primary:
                    SellerBank.query.filter_by(seller_id=seller_id).update({'is_primary': False})
                bank.bank_name      = bank_name
                bank.account_number = account_number
                bank.branch         = branch
                bank.swift_code     = swift_code
                bank.iban           = iban
                bank.is_primary     = is_primary
                # optional bilingual columns
                if hasattr(bank, 'bank_name_ar'): bank.bank_name_ar = bank_name_ar
                if hasattr(bank, 'branch_ar'):    bank.branch_ar    = branch_ar
                db.session.add(bank)
        else:
            if is_primary:
                SellerBank.query.filter_by(seller_id=seller_id).update({'is_primary': False})
            bank = SellerBank(
                seller_id      = seller_id,
                bank_name      = bank_name,
                account_number = account_number,
                branch         = branch,
                swift_code     = swift_code,
                iban           = iban,
                is_primary     = is_primary,
            )
            if hasattr(bank, 'bank_name_ar'): bank.bank_name_ar = bank_name_ar
            if hasattr(bank, 'branch_ar'):    bank.branch_ar    = branch_ar
            db.session.add(bank)
        i += 1

    # Delete banks removed from form
    if submitted_ids:
        existing_ids = {b.id for b in SellerBank.query.filter_by(seller_id=seller_id).all()}
        to_delete    = existing_ids - submitted_ids
        if to_delete:
            SellerBank.query.filter(
                SellerBank.id.in_(to_delete),
                SellerBank.seller_id == seller_id,
            ).delete(synchronize_session='fetch')


# ═════════════════════════════════════════════════════════════════════
# SELLER ROUTES
# ═════════════════════════════════════════════════════════════════════

@sellers_bp.route('/sellers')
@login_required
def list_sellers():
    seller_form = SellerForm()
    bank_form   = BankForm()
    return render_template('sellers/list.html',
                           seller_form=seller_form, bank_form=bank_form)


@sellers_bp.route('/sellers/add', methods=['POST'])
@login_required
@admin_required
def add_seller():
    seller = Seller(
        seller_code          = generate_seller_code(),
        created_by           = current_user.id,
        name                 = request.form.get('name',             '').strip(),
        name_ar              = request.form.get('name_ar',          '').strip(),
        vat_number           = request.form.get('vat_number',       '').strip(),
        crn                  = request.form.get('crn',              '').strip(),
        phone                = request.form.get('phone',            '').strip(),
        fax                  = request.form.get('fax',              '').strip(),
        email                = request.form.get('email',            '').strip(),
        website              = request.form.get('website',          '').strip(),
        report_color         = request.form.get('report_color', '#16a34a').strip(),
        status               = request.form.get('status',      'active').strip(),
        street_name          = request.form.get('street_name',      '').strip(),
        street_name_ar       = request.form.get('street_name_ar',   '').strip(),
        building_number      = request.form.get('building_number',  '').strip(),
        building_number_ar   = request.form.get('building_number_ar', '').strip(),
        additional_number    = request.form.get('additional_number',  '').strip(),
        additional_number_ar = request.form.get('additional_number_ar', '').strip(),
        district             = request.form.get('district',         '').strip(),
        district_ar          = request.form.get('district_ar',      '').strip(),
        city                 = request.form.get('city',             '').strip(),
        city_ar              = request.form.get('city_ar',          '').strip(),
        postal_code          = request.form.get('postal_code',      '').strip(),
        postal_code_ar       = request.form.get('postal_code_ar',   '').strip(),
        country              = request.form.get('country', 'Saudi Arabia').strip(),
        country_ar           = request.form.get('country_ar',       '').strip(),
    )

    errors = []
    if not seller.name:  errors.append('Name is required')
    if not seller.email: errors.append('Email is required')
    if errors:
        for e in errors: flash(e, 'danger')
        return redirect(url_for('sellers.list_sellers'))

    db.session.add(seller)
    db.session.flush()

    logo    = request.files.get('logo')
    bg_logo = request.files.get('bg_logo')
    if logo    and logo.filename    and allowed_file(logo.filename):
        seller.logo_path    = save_file(logo,    seller.id)
    if bg_logo and bg_logo.filename and allowed_file(bg_logo.filename):
        seller.bg_logo_path = save_file(bg_logo, seller.id)

    log_activity('CREATE', 'seller', seller.id, f'Seller {seller.seller_code} created')
    _save_banks_from_form(seller.id)
    _save_docs_from_form(seller.id)
    db.session.commit()
    flash(_t(f'Seller {seller.seller_code} added successfully!',
             f'تم إضافة البائع {seller.seller_code} بنجاح'), 'success')
    return redirect(url_for('sellers.list_sellers'))


@sellers_bp.route('/sellers/<int:id>/json')
@login_required
def seller_json(id):
    s = Seller.query.get_or_404(id)
    g = lambda f: getattr(s, f, None) or ''
    try:
        banks_data = [
            {**b.to_dict(),
             'bank_name_ar': getattr(b, 'bank_name_ar', '') or '',
             'branch_ar':    getattr(b, 'branch_ar',    '') or ''}
            for b in s.banks
        ]
    except Exception:
        banks_data = []
    try:
        docs_data = [_doc_to_dict(d) for d in s.documents]
    except Exception:
        docs_data = []
    return jsonify({
        'id':                    s.id,
        'seller_code':           g('seller_code'),
        'name':                  g('name'),             'name_ar':              g('name_ar'),
        'vat_number':            g('vat_number'),       'crn':                  g('crn'),
        'phone':                 g('phone'),             'fax':                  g('fax'),
        'email':                 g('email'),             'website':              g('website'),
        'report_color':          g('report_color') or '#16a34a',
        'street_name':           g('street_name'),      'street_name_ar':       g('street_name_ar'),
        'building_number':       g('building_number'),  'building_number_ar':   g('building_number_ar'),
        'additional_number':     g('additional_number'),'additional_number_ar': g('additional_number_ar'),
        'district':              g('district'),          'district_ar':          g('district_ar'),
        'city':                  g('city'),              'city_ar':              g('city_ar'),
        'postal_code':           g('postal_code'),       'postal_code_ar':       g('postal_code_ar'),
        'country':               g('country'),           'country_ar':           g('country_ar'),
        'status':                g('status'),
        'banks':                 banks_data,
        'documents':             docs_data,
    })


@sellers_bp.route('/sellers/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_seller(id):
    seller = Seller.query.get_or_404(id)

    seller.name                 = request.form.get('name',             '').strip() or seller.name
    seller.name_ar              = request.form.get('name_ar',          '').strip()
    seller.vat_number           = request.form.get('vat_number',       '').strip()
    seller.crn                  = request.form.get('crn',              '').strip()
    seller.phone                = request.form.get('phone',            '').strip()
    seller.fax                  = request.form.get('fax',              '').strip()
    seller.email                = request.form.get('email',            '').strip() or seller.email
    seller.website              = request.form.get('website',          '').strip()
    seller.report_color         = request.form.get('report_color', '#16a34a').strip()
    seller.status               = request.form.get('status',      'active').strip()
    seller.street_name          = request.form.get('street_name',      '').strip()
    seller.street_name_ar       = request.form.get('street_name_ar',   '').strip()
    seller.building_number      = request.form.get('building_number',  '').strip()
    seller.building_number_ar   = request.form.get('building_number_ar',  '').strip()
    seller.additional_number    = request.form.get('additional_number',   '').strip()
    seller.additional_number_ar = request.form.get('additional_number_ar','').strip()
    seller.district             = request.form.get('district',         '').strip()
    seller.district_ar          = request.form.get('district_ar',      '').strip()
    seller.city                 = request.form.get('city',             '').strip()
    seller.city_ar              = request.form.get('city_ar',          '').strip()
    seller.postal_code          = request.form.get('postal_code',      '').strip()
    seller.postal_code_ar       = request.form.get('postal_code_ar',   '').strip()
    seller.country              = request.form.get('country',          '').strip()
    seller.country_ar           = request.form.get('country_ar',       '').strip()
    seller.updated_at           = datetime.utcnow()

    logo    = request.files.get('logo')
    bg_logo = request.files.get('bg_logo')
    if logo    and logo.filename    and allowed_file(logo.filename):
        seller.logo_path    = save_file(logo,    seller.id)
    if bg_logo and bg_logo.filename and allowed_file(bg_logo.filename):
        seller.bg_logo_path = save_file(bg_logo, seller.id)

    log_activity('EDIT', 'seller', seller.id, f'Seller {seller.seller_code} updated')
    _save_banks_from_form(seller.id)
    _save_docs_from_form(seller.id)
    db.session.commit()
    flash(_t('Seller updated successfully!', 'تم تحديث البائع بنجاح'), 'success')
    return redirect(url_for('sellers.list_sellers'))


@sellers_bp.route('/sellers/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_seller(id):
    seller = Seller.query.get_or_404(id)
    for doc in seller.documents:
        fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
        if doc.file_path and os.path.exists(fpath):
            os.remove(fpath)
    code = seller.seller_code
    db.session.delete(seller)
    db.session.commit()
    flash(_t(f'Seller {code} deleted.', f'تم حذف البائع {code}'), 'success')
    return redirect(url_for('sellers.list_sellers'))


@sellers_bp.route('/sellers/<int:id>/view')
@login_required
def view_seller(id):
    seller    = Seller.query.get_or_404(id)
    documents = (SellerDocument.query.filter_by(seller_id=id)
                 .order_by(SellerDocument.id.desc()).all())
    banks     = (SellerBank.query.filter_by(seller_id=id)
                 .order_by(SellerBank.id).all())
    activity  = (ActivityLog.query
                 .filter_by(target='seller', target_id=id)
                 .order_by(ActivityLog.created_at.desc())
                 .limit(50).all())
    return render_template('sellers/view.html',
                           seller=seller, documents=documents,
                           banks=banks, activity=activity)


# ═════════════════════════════════════════════════════════════════════
# BANK ROUTES
# ═════════════════════════════════════════════════════════════════════

@sellers_bp.route('/sellers/<int:id>/banks')
@login_required
def list_seller_banks(id):
    banks = SellerBank.query.filter_by(seller_id=id).order_by(SellerBank.id).all()
    return jsonify([b.to_dict() for b in banks])


@sellers_bp.route('/sellers/banks/<int:bid>/json')
@login_required
def seller_bank_json(bid):
    bank = SellerBank.query.get_or_404(bid)
    return jsonify(bank.to_dict())


@sellers_bp.route('/sellers/<int:id>/banks/add', methods=['POST'])
@login_required
def add_bank(id):
    Seller.query.get_or_404(id)
    data = request.get_json() or {}
    if data.get('is_primary') in [True, 'true', '1', 'on']:
        SellerBank.query.filter_by(seller_id=id).update({'is_primary': False})
    bank = SellerBank(
        seller_id      = id,
        bank_name      = data.get('bank_name',      ''),
        account_number = data.get('account_number', ''),
        branch         = data.get('branch',         ''),
        swift_code     = data.get('swift_code',     ''),
        iban           = data.get('iban',           ''),
        is_primary     = data.get('is_primary') in [True, 'true', '1', 'on'],
    )
    db.session.add(bank)
    db.session.commit()
    return jsonify({'ok': True, 'id': bank.id, 'bank': bank.to_dict()})


@sellers_bp.route('/sellers/banks/<int:bid>/edit', methods=['POST'])
@login_required
def edit_seller_bank(bid):
    b    = SellerBank.query.get_or_404(bid)
    data = request.get_json() or {}
    if data.get('is_primary') in [True, 'true', '1', 'on']:
        SellerBank.query.filter_by(seller_id=b.seller_id).update({'is_primary': False})
    b.bank_name      = data.get('bank_name',      b.bank_name)
    b.account_number = data.get('account_number', b.account_number or '')
    b.branch         = data.get('branch',         b.branch         or '')
    b.swift_code     = data.get('swift_code',     b.swift_code     or '')
    b.iban           = data.get('iban',            b.iban          or '')
    b.is_primary     = data.get('is_primary') in [True, 'true', '1', 'on']
    if hasattr(b, 'bank_name_ar'): b.bank_name_ar = data.get('bank_name_ar', getattr(b, 'bank_name_ar', '') or '')
    if hasattr(b, 'branch_ar'):    b.branch_ar    = data.get('branch_ar',    getattr(b, 'branch_ar',    '') or '')
    db.session.commit()
    return jsonify({'ok': True, 'bank': b.to_dict()})


@sellers_bp.route('/sellers/banks/<int:bid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_bank(bid):
    bank = SellerBank.query.get_or_404(bid)
    db.session.delete(bank)
    db.session.commit()
    return jsonify({'ok': True})


# ═════════════════════════════════════════════════════════════════════
# DOCUMENT ROUTES
# ═════════════════════════════════════════════════════════════════════

@sellers_bp.route('/sellers/<int:id>/documents/upload', methods=['POST'])
@login_required
def upload_document(id):
    """
    Dual-mode:
    • AJAX (X-CSRFToken header set by fetch())  → JSON {ok, doc}
    • Plain form POST from view.html            → flash + redirect to view
    """
    is_ajax = bool(
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or request.headers.get('X-CSRFToken')
    )

    def _fail(msg):
        if is_ajax:
            return jsonify({'ok': False, 'error': msg})
        flash(msg, 'danger')
        return redirect(url_for('sellers.view_seller', id=id))

    Seller.query.get_or_404(id)
    file = request.files.get('file')
    if not file or not file.filename:
        return _fail(_t('No file selected.', 'لم يتم اختيار ملف'))
    if not allowed_file(file.filename):
        return _fail(_t('File type not allowed.', 'نوع الملف غير مسموح به'))

    from datetime import date as _date
    path = save_file(file, id)
    doc  = SellerDocument(
        seller_id     = id,
        document_type = request.form.get('document_type', 'Other'),
        document_name = request.form.get('document_name', file.filename),
        file_path     = path,
        file_size     = os.path.getsize(
            os.path.join(current_app.config['UPLOAD_FOLDER'], path)),
        uploaded_by   = current_user.id,
        uploaded_at   = datetime.utcnow(),
    )
    raw_issue  = request.form.get('issue_date',  '')
    raw_expiry = request.form.get('expiry_date', '')
    if raw_issue:
        try:   doc.issue_date = _date.fromisoformat(raw_issue)
        except (ValueError, AttributeError): pass
    if raw_expiry:
        try:   doc.expiry_date = _date.fromisoformat(raw_expiry)
        except ValueError: pass

    db.session.add(doc)
    db.session.commit()
    log_activity('UPLOAD', 'seller', id, f'Document "{doc.document_name}" uploaded')

    if is_ajax:
        return jsonify({'ok': True, 'doc': _doc_to_dict(doc)})
    flash(_t('Document uploaded successfully.', 'تم رفع المستند بنجاح'), 'success')
    return redirect(url_for('sellers.view_seller', id=id))


@sellers_bp.route('/sellers/<int:id>/documents/json')
@login_required
def list_seller_documents(id):
    """Return all documents for a seller (used by the edit modal docs tab)."""
    docs = (SellerDocument.query.filter_by(seller_id=id)
            .order_by(SellerDocument.id).all())
    return jsonify([_doc_to_dict(d) for d in docs])


def _resolve_doc_path(doc):
    """
    Safely resolve the absolute filesystem path and filename for a document.
    file_path is stored as  "seller_id/uuid.ext"  (forward slash on all OS).
    Returns (abs_folder, filename, abs_filepath).
    """
    # Normalise: replace any backslash with forward slash, then split
    rel = (doc.file_path or '').replace('\\', '/')
    parts = rel.split('/')
    filename = parts[-1]                          # uuid.ext
    abs_folder = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        *parts[:-1]                               # seller_id (and any sub-dirs)
    )
    abs_filepath = os.path.join(abs_folder, filename)
    return abs_folder, filename, abs_filepath


@sellers_bp.route('/sellers/documents/<int:did>/view')
@login_required
def view_document(did):
    """
    View a document inline.
    • PDF / images  → served inline (browser renders natively)
    • Excel (.xlsx/.xls/.xlsm/.ods) → SheetJS HTML viewer
    • Word / other  → force-download (browsers cannot render these)
    """
    doc = SellerDocument.query.get_or_404(did)
    abs_folder, fname, abs_filepath = _resolve_doc_path(doc)

    if not os.path.exists(abs_filepath):
        from flask import abort
        abort(404, description=f'File not found on server: {abs_filepath}')

    ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''

    # ── Excel → SheetJS viewer ──────────────────────────────────────
    if ext in ('xlsx', 'xls', 'xlsm', 'xlsb', 'ods'):
        file_url  = url_for('sellers.download_document_alt', did=did, _external=True)
        friendly  = _friendly_name(doc, fname)
        html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>{friendly}</title>
<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Segoe UI',sans-serif;background:#f1f5f9;}}
  header{{background:#1e3a5f;color:#fff;padding:12px 20px;display:flex;align-items:center;gap:12px;}}
  header h1{{font-size:15px;font-weight:700;margin:0;flex:1;}}
  header a{{background:#16a34a;color:#fff;padding:6px 16px;border-radius:8px;text-decoration:none;font-size:12px;font-weight:600;}}
  #sheet-tabs{{background:#fff;border-bottom:1px solid #e2e8f0;padding:8px 16px;display:flex;gap:6px;overflow-x:auto;}}
  .tab{{padding:5px 14px;border-radius:6px;border:1.5px solid #d1d5db;font-size:12px;cursor:pointer;background:#f8fafc;}}
  .tab.active{{background:#2563eb;color:#fff;border-color:#2563eb;}}
  #tbl-wrap{{overflow:auto;padding:16px;max-height:calc(100vh - 110px);}}
  table{{border-collapse:collapse;font-size:12.5px;background:#fff;width:100%;}}
  th{{background:#1e3a5f;color:#fff;padding:8px 12px;text-align:left;white-space:nowrap;font-size:11px;text-transform:uppercase;}}
  td{{padding:7px 12px;border-bottom:1px solid #f1f5f9;white-space:nowrap;}}
  tr:hover td{{background:#eff6ff;}}
  #loading{{text-align:center;padding:60px;color:#6b7280;font-size:14px;}}
</style>
</head><body>
<header>
  <h1>&#128196; {friendly}</h1>
  <a href="{file_url}" download="{friendly}">&#8595; Download</a>
</header>
<div id="sheet-tabs"></div>
<div id="tbl-wrap"><div id="loading">&#9203; Loading spreadsheet...</div></div>
<script>
fetch("{file_url}")
  .then(r=>r.arrayBuffer())
  .then(buf=>{{
    const wb = XLSX.read(new Uint8Array(buf),{{type:'array'}});
    const tabs = document.getElementById('sheet-tabs');
    wb.SheetNames.forEach((name,i)=>{{
      const btn=document.createElement('button');
      btn.className='tab'+(i===0?' active':'');
      btn.textContent=name;
      btn.onclick=()=>{{document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));btn.classList.add('active');render(wb,name);}};
      tabs.appendChild(btn);
    }});
    render(wb, wb.SheetNames[0]);
  }})
  .catch(e=>{{document.getElementById('loading').textContent='Error loading file: '+e;}});

function render(wb,name){{
  const ws=wb.Sheets[name];
  document.getElementById('tbl-wrap').innerHTML=XLSX.utils.sheet_to_html(ws,{{header:'',editable:false}});
}}
</script>
</body></html>"""
        from flask import Response
        return Response(html, mimetype='text/html')

    # ── PDF / images → inline ───────────────────────────────────────
    mime_map = {
        'pdf':'application/pdf',
        'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png',
        'gif':'image/gif','webp':'image/webp','svg':'image/svg+xml','bmp':'image/bmp',
    }
    if ext in mime_map:
        from flask import Response as _Resp
        with open(abs_filepath, 'rb') as f:
            data = f.read()
        resp = _Resp(data, mimetype=mime_map[ext])
        resp.headers['Content-Disposition'] = (
            f'inline; filename="{_friendly_name(doc, fname)}"'
        )
        return resp

    # ── Everything else → force-download ───────────────────────────
    return send_from_directory(abs_folder, fname, as_attachment=True,
                               download_name=_friendly_name(doc, fname))


def _friendly_name(doc, raw_fname):
    """
    "Trade License 2025" + "abc123.pdf"  →  "Trade License 2025.pdf"
    Preserves the original file extension so the OS knows how to open it.
    """
    ext  = raw_fname.rsplit('.', 1)[-1].lower() if '.' in raw_fname else ''
    base = (doc.document_name or '').strip()
    if not base:
        return raw_fname
    if ext and base.lower().endswith('.' + ext):
        return base
    return f'{base}.{ext}' if ext else base


@sellers_bp.route('/sellers/documents/<int:did>/download')
@login_required
def download_document_alt(did):
    """Force-download — preserves original extension in the saved filename."""
    doc = SellerDocument.query.get_or_404(did)
    abs_folder, fname, abs_filepath = _resolve_doc_path(doc)
    if not os.path.exists(abs_filepath):
        from flask import abort
        abort(404, description='File not found on server')
    return send_from_directory(abs_folder, fname,
                               as_attachment=True,
                               download_name=_friendly_name(doc, fname))


@sellers_bp.route('/documents/<int:did>/download')
@login_required
def download_document(did):
    """Legacy URL alias — keeps old links working."""
    return download_document_alt(did)


@sellers_bp.route('/documents/<int:did>/delete', methods=['POST'])
@login_required
@admin_required
def delete_document(did):
    doc = SellerDocument.query.get_or_404(did)
    _, _, abs_filepath = _resolve_doc_path(doc)
    if os.path.exists(abs_filepath):
        os.remove(abs_filepath)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'ok': True})


# ═════════════════════════════════════════════════════════════════════
# SELLER DOCUMENTS — STANDALONE AG-GRID PAGE
# path: /seller-documents
# ═════════════════════════════════════════════════════════════════════

@sellers_bp.route('/seller-documents')
@login_required
def list_seller_documents_page():
    """Standalone AG-Grid page showing ALL documents across all sellers."""
    return render_template('seller_documents/list.html')


@sellers_bp.route('/seller-documents/data')
@login_required
def seller_documents_data():
    """JSON feed for the standalone seller-documents AG-Grid."""
    docs = SellerDocument.query.order_by(SellerDocument.id.desc()).all()
    rows = []
    for d in docs:
        from models import User
        seller   = Seller.query.get(d.seller_id) if d.seller_id else None
        uploader = User.query.get(d.uploaded_by)  if d.uploaded_by else None
        rows.append({
            'id':               d.id,
            'seller_id':        d.seller_id or '',
            'seller_name':      seller.name        if seller   else '',
            'seller_code':      seller.seller_code if seller   else '',
            'document_type':    d.document_type    or '',
            'doc_type':         d.document_type    or '',
            'document_name':    d.document_name    or '',
            'doc_name':         d.document_name    or '',
            'issue_date':       str(getattr(d, 'issue_date', '') or ''),
            'expiry_date':      str(d.expiry_date) if d.expiry_date else '',
            'uploaded_at':      d.uploaded_at.strftime('%Y-%m-%d %H:%M') if d.uploaded_at else '',
            'uploaded_by_name': uploader.username  if uploader else '',
            'file_size_kb':     round((d.file_size or 0) / 1024, 1),
            'file_path':        d.file_path        or '',
        })
    return jsonify(rows)


@sellers_bp.route('/seller-documents/<int:did>/json')
@login_required
def seller_document_json(did):
    """Single document JSON — used by the edit modal on the standalone grid."""
    doc = SellerDocument.query.get_or_404(did)
    return jsonify(_doc_to_dict(doc))


@sellers_bp.route('/seller-documents/<int:did>/edit', methods=['POST'])
@login_required
@admin_required
def edit_seller_document(did):
    """Edit document metadata only (type, name, issue_date, expiry_date).
    File replacement is NOT done here — upload a new doc instead."""
    from datetime import date as _date
    doc  = SellerDocument.query.get_or_404(did)
    data = request.get_json() or {}

    doc.document_type = data.get('document_type', doc.document_type) or doc.document_type
    doc.document_name = data.get('document_name', doc.document_name) or doc.document_name

    raw_issue  = data.get('issue_date',  '')
    raw_expiry = data.get('expiry_date', '')
    if raw_issue:
        try:   doc.issue_date = _date.fromisoformat(raw_issue)
        except (ValueError, AttributeError): pass
    try:       doc.expiry_date = _date.fromisoformat(raw_expiry) if raw_expiry else None
    except ValueError: pass

    db.session.commit()
    log_activity('EDIT', 'seller_document', did, f'Edited "{doc.document_name}"')
    return jsonify({'ok': True, 'doc': _doc_to_dict(doc)})


# ═════════════════════════════════════════════════════════════════════
# AG-GRID SELLERS DATA  /  EXPORT  /  TRANSLATE
# ═════════════════════════════════════════════════════════════════════

@sellers_bp.route('/sellers/data')
@login_required
def sellers_data():
    sellers = Seller.query.order_by(Seller.created_at.desc()).all()
    rows = []
    for s in sellers:
        rows.append({
            'id':                s.id,
            'seller_code':       s.seller_code       or '',
            'name':              s.name               or '',
            'name_ar':           getattr(s,'name_ar','') or '',
            'vat_number':        s.vat_number         or '',
            'crn':               s.crn                or '',
            'phone':             s.phone              or '',
            'fax':               s.fax                or '',
            'email':             s.email              or '',
            'website':           s.website            or '',
            'city':              s.city               or '',
            'country':           s.country            or '',
            'report_color':      s.report_color       or '#16a34a',
            'status':            s.status             or '',
            'created_at':        s.created_at.strftime('%Y-%m-%d') if s.created_at else '',
        })
    return jsonify(rows)


@sellers_bp.route('/sellers/export')
@login_required
def export_sellers():
    import csv, io
    from flask import make_response
    sellers = Seller.query.all()
    output  = io.StringIO()
    writer  = csv.writer(output)
    writer.writerow(['Code','Name','VAT Number','CRN','Phone','Fax',
                     'Email','Website','City','Country','Status','Created'])
    for s in sellers:
        writer.writerow([s.seller_code, s.name, s.vat_number or '', s.crn or '',
                         s.phone or '', s.fax or '', s.email or '', s.website or '',
                         s.city or '', s.country or '', s.status,
                         s.created_at.strftime('%Y-%m-%d') if s.created_at else ''])
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=sellers_export.csv'
    response.headers['Content-type'] = 'text/csv'
    return response


@sellers_bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    import urllib.request, urllib.parse, json as _json
    data      = request.get_json() or {}
    text      = (data.get('text') or '').strip()
    direction = data.get('direction', 'en|ar')
    if not text:
        return jsonify({'translated': ''})
    src, tgt = direction.split('|')
    # Google Translate (unofficial, no key)
    try:
        params = urllib.parse.urlencode({'client':'gtx','sl':src,'tl':tgt,'dt':'t','q':text})
        url    = f'https://translate.googleapis.com/translate_a/single?{params}'
        req    = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as r:
            result = _json.loads(r.read().decode('utf-8'))
        translated = ''.join(chunk[0] for chunk in result[0] if chunk[0])
        if translated:
            return jsonify({'translated': translated.strip()})
    except Exception:
        pass
    # Fallback: MyMemory
    try:
        q   = urllib.parse.quote(text)
        url = f'https://api.mymemory.translated.net/get?q={q}&langpair={direction}'
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            result = _json.loads(r.read().decode())
        return jsonify({'translated': result.get('responseData',{}).get('translatedText','')})
    except Exception as e:
        return jsonify({'translated': '', 'error': str(e)})