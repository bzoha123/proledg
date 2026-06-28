"""
seller_doc.py
─────────────────────────────────────────────────────────────────────
Blueprint: seller_doc_bp
Prefix:    (none — URLs are defined explicitly on each route)

All routes related to SellerDocument:
  Upload, View inline, Download, Delete, List JSON per seller,
  Standalone AG-Grid page, AG-Grid data feed, Edit metadata.

FILE PATH in your project:
  seller_ms/
  └── seller_doc.py          ← this file
       (same level as sellers.py, models.py, app.py)

Register in app.py (or __init__.py):
  from seller_doc import seller_doc_bp
  app.register_blueprint(seller_doc_bp)
─────────────────────────────────────────────────────────────────────
"""

import os
import uuid
from datetime import datetime, date as _date
from functools import wraps

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, current_app, send_from_directory, jsonify, session,
)
from flask_login import login_required, current_user

from models import db, Seller, SellerDocument, ActivityLog, User

seller_doc_bp = Blueprint('seller_doc', __name__)


# ─────────────────────────────────────────────────────────────────────
# PRIVATE HELPERS  (mirrors of the ones in sellers.py so this module
# is fully self-contained — no circular imports)
# ─────────────────────────────────────────────────────────────────────

def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en


def _admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            flash(_t('Access denied. Admin privileges required.',
                     'الوصول مرفوض. يلزم صلاحيات المدير.'), 'danger')
            return redirect(url_for('sellers.list_sellers'))
        return f(*args, **kwargs)
    return decorated


def _allowed_file(filename):
    allowed = current_app.config.get(
        'ALLOWED_EXTENSIONS', {'jpg', 'jpeg', 'png', 'pdf', 'docx', 'xlsx', 'doc'}
    )
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _save_file(file, seller_id):
    ext         = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    folder      = os.path.join(current_app.config['UPLOAD_FOLDER'], str(seller_id))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, unique_name)
    file.save(path)
    return os.path.join(str(seller_id), unique_name)


def _log(action, target_id, detail=''):
    try:
        db.session.add(ActivityLog(
            user_id    = current_user.id,
            action     = action,
            target     = 'seller_document',
            target_id  = target_id,
            detail     = detail,
            ip_address = request.remote_addr,
        ))
    except Exception:
        pass


def _doc_to_dict(doc):
    """Serialize a SellerDocument row to a plain dict (JSON-safe)."""
    uploader = User.query.get(doc.uploaded_by) if doc.uploaded_by else None
    seller   = Seller.query.get(doc.seller_id) if doc.seller_id else None
    return {
        'id':               doc.id,
        'seller_id':        doc.seller_id or '',
        'seller_name':      seller.name         if seller   else '',
        'seller_code':      seller.seller_code  if seller   else '',
        'document_type':    doc.document_type   or '',
        'document_name':    doc.document_name   or '',
        'issue_date':       str(getattr(doc, 'issue_date', '') or ''),
        'expiry_date':      str(doc.expiry_date or '') if doc.expiry_date else '',
        'uploaded_at':      doc.uploaded_at.strftime('%Y-%m-%d %H:%M') if doc.uploaded_at else '',
        'uploaded_by':      doc.uploaded_by,
        'uploaded_by_name': uploader.username   if uploader else '',
        'file_path':        doc.file_path       or '',
        'file_size_kb':     round((doc.file_size or 0) / 1024, 1),
    }


# ─────────────────────────────────────────────────────────────────────
# 1. UPLOAD  POST /sellers/<id>/documents/upload
#    Dual-mode: AJAX → JSON   |   plain form POST → flash + redirect
# ─────────────────────────────────────────────────────────────────────
@seller_doc_bp.route('/sellers/<int:seller_id>/documents/upload', methods=['POST'])
@login_required
def upload_document(seller_id):
    is_ajax = bool(
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or request.headers.get('X-CSRFToken')       # set by JS fetch()
    )

    Seller.query.get_or_404(seller_id)              # 404 guard
    file = request.files.get('file')

    def _fail(msg):
        if is_ajax:
            return jsonify({'ok': False, 'error': msg})
        flash(msg, 'danger')
        return redirect(url_for('sellers.view_seller', id=seller_id))

    if not file or not file.filename:
        return _fail(_t('No file selected.', 'لم يتم اختيار ملف'))
    if not _allowed_file(file.filename):
        return _fail(_t('File type not allowed.', 'نوع الملف غير مسموح به'))

    path = _save_file(file, seller_id)
    doc  = SellerDocument(
        seller_id     = seller_id,
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
    if hasattr(doc, 'issue_date') and raw_issue:
        try:   doc.issue_date = _date.fromisoformat(raw_issue)
        except ValueError: pass
    if raw_expiry:
        try:   doc.expiry_date = _date.fromisoformat(raw_expiry)
        except ValueError: pass

    db.session.add(doc)
    db.session.commit()
    _log('UPLOAD', doc.id, f'Uploaded "{doc.document_name}"')

    if is_ajax:
        return jsonify({'ok': True, 'doc': _doc_to_dict(doc)})
    flash(_t('Document uploaded successfully.', 'تم رفع المستند بنجاح'), 'success')
    return redirect(url_for('sellers.view_seller', id=seller_id))


# ─────────────────────────────────────────────────────────────────────
# 2. VIEW INLINE  GET /sellers/documents/<did>/view
# ─────────────────────────────────────────────────────────────────────
@seller_doc_bp.route('/sellers/documents/<int:did>/view')
@login_required
def view_document(did):
    doc    = SellerDocument.query.get_or_404(did)
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(doc.seller_id))
    fname  = doc.file_path.split(os.sep)[-1]
    return send_from_directory(folder, fname, as_attachment=False)


# ─────────────────────────────────────────────────────────────────────
# 3. DOWNLOAD  GET /sellers/documents/<did>/download
#              GET /documents/<did>/download  (legacy alias)
# ─────────────────────────────────────────────────────────────────────
@seller_doc_bp.route('/sellers/documents/<int:did>/download')
@login_required
def download_document(did):
    doc    = SellerDocument.query.get_or_404(did)
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(doc.seller_id))
    fname  = doc.file_path.split(os.sep)[-1]
    return send_from_directory(
        folder, fname,
        as_attachment=True,
        download_name=doc.document_name or fname,
    )


@seller_doc_bp.route('/documents/<int:did>/download')
@login_required
def download_document_legacy(did):
    """Legacy URL kept so existing links don't break."""
    return download_document(did)


# ─────────────────────────────────────────────────────────────────────
# 4. DELETE  POST /documents/<did>/delete
# ─────────────────────────────────────────────────────────────────────
@seller_doc_bp.route('/documents/<int:did>/delete', methods=['POST'])
@login_required
@_admin_required
def delete_document(did):
    doc   = SellerDocument.query.get_or_404(did)
    fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
    if os.path.exists(fpath):
        os.remove(fpath)
    _log('DELETE', did, f'Deleted "{doc.document_name}"')
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'ok': True})


# ─────────────────────────────────────────────────────────────────────
# 5. LIST JSON per seller  GET /sellers/<id>/documents/json
#    Used by the seller edit modal to reload the documents tab
# ─────────────────────────────────────────────────────────────────────
@seller_doc_bp.route('/sellers/<int:seller_id>/documents/json')
@login_required
def list_seller_documents(seller_id):
    docs = (SellerDocument.query
            .filter_by(seller_id=seller_id)
            .order_by(SellerDocument.id)
            .all())
    return jsonify([_doc_to_dict(d) for d in docs])


# ─────────────────────────────────────────────────────────────────────
# 6. SINGLE JSON  GET /seller-documents/<did>/json
#    Used by the edit modal on the standalone grid page
# ─────────────────────────────────────────────────────────────────────
@seller_doc_bp.route('/seller-documents/<int:did>/json')
@login_required
def seller_document_json(did):
    doc = SellerDocument.query.get_or_404(did)
    return jsonify(_doc_to_dict(doc))


# ─────────────────────────────────────────────────────────────────────
# 7. EDIT METADATA  POST /seller-documents/<did>/edit
#    Updates document_type, document_name, issue_date, expiry_date.
#    File replacement is NOT done here (upload a new doc instead).
# ─────────────────────────────────────────────────────────────────────
@seller_doc_bp.route('/seller-documents/<int:did>/edit', methods=['POST'])
@login_required
@_admin_required
def edit_seller_document(did):
    doc  = SellerDocument.query.get_or_404(did)
    data = request.get_json() or {}

    doc.document_type = data.get('document_type', doc.document_type) or doc.document_type
    doc.document_name = data.get('document_name', doc.document_name) or doc.document_name

    raw_issue  = data.get('issue_date',  '')
    raw_expiry = data.get('expiry_date', '')

    if hasattr(doc, 'issue_date'):
        try:
            doc.issue_date = _date.fromisoformat(raw_issue) if raw_issue \
                             else getattr(doc, 'issue_date', None)
        except ValueError:
            pass

    try:
        doc.expiry_date = _date.fromisoformat(raw_expiry) if raw_expiry else None
    except ValueError:
        pass

    db.session.commit()
    _log('EDIT', did, f'Edited "{doc.document_name}"')
    return jsonify({'ok': True, 'doc': _doc_to_dict(doc)})


# ─────────────────────────────────────────────────────────────────────
# 8. STANDALONE GRID PAGE  GET /seller-documents
# ─────────────────────────────────────────────────────────────────────
@seller_doc_bp.route('/seller-documents')
@login_required
def list_seller_documents_page():
    """Renders the full standalone AG-Grid page for all seller documents."""
    return render_template('seller_documents/list.html')


# ─────────────────────────────────────────────────────────────────────
# 9. AG-GRID DATA FEED  GET /seller-documents/data
#    Returns every SellerDocument row enriched with seller + uploader info
# ─────────────────────────────────────────────────────────────────────
@seller_doc_bp.route('/seller-documents/data')
@login_required
def seller_documents_data():
    docs = SellerDocument.query.order_by(SellerDocument.id.desc()).all()
    return jsonify([_doc_to_dict(d) for d in docs])