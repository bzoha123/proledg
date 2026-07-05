import os
import uuid
import mimetypes
from datetime import datetime, date as _date
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
    send_from_directory,
    jsonify,
    session,
    abort,
)
from flask_login import login_required, current_user

from models import db, ActivityLog, User, VendorMaster, VendorDocument

vendor_doc_bp = Blueprint('vendor_doc', __name__)

mimetypes.add_type('application/msword', '.doc')
mimetypes.add_type('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx')
mimetypes.add_type('application/vnd.ms-excel', '.xls')
mimetypes.add_type('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx')
mimetypes.add_type('application/vnd.ms-powerpoint', '.ppt')
mimetypes.add_type('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx')

ALLOWED_MIMETYPES = {
    'application/pdf',
    'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp', 'image/tiff',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain', 'text/csv',
    'application/rtf',
    'application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed',
}

ALLOWED_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'tif',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'csv', 'rtf', 'zip', 'rar', '7z',
}

INLINE_MIMETYPES = {
    'application/pdf',
    'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp', 'image/tiff',
    'text/plain', 'text/csv',
}

# Map document types to categories
DOC_TYPE_CATEGORY = {
    'CR': 'registration',
    'VAT': 'registration',
    'Chamber': 'registration',
    'Zakat': 'registration',
    'Contract': 'legal',
    'Agreement': 'legal',
    'NDA': 'legal',
    'Invoice': 'financial',
    'Bank Statement': 'financial',
    'Insurance': 'financial',
    'Specification': 'technical',
    'Certificate': 'technical',
    'Other': 'other',
}


def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en


def _admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            flash(_t('Access denied. Admin privileges required.', 'الوصول مرفوض. يلزم صلاحيات المدير.'), 'danger')
            return redirect(url_for('purchase.vendor_list'))
        return f(*args, **kwargs)
    return decorated


def _allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and mime_type in ALLOWED_MIMETYPES:
        return True
    if ext in ALLOWED_EXTENSIONS:
        return True
    generic_mimes = {'application/octet-stream', 'application/x-msdownload', 'binary/octet-stream'}
    return mime_type in generic_mimes and ext in ALLOWED_EXTENSIONS


def _allowed_file_size(file_storage, max_size_mb=16):
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    return (size <= max_size_mb * 1024 * 1024), size


def _save_file(file_storage, vendor_id):
    ext = file_storage.filename.rsplit('.', 1)[1].lower() if '.' in file_storage.filename else 'bin'
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'vendor_documents', str(vendor_id))
    os.makedirs(folder, exist_ok=True)
    full_path = os.path.join(folder, unique_name)
    file_storage.save(full_path)
    # Always store with forward slashes for cross-platform compatibility
    return f'vendor_documents/{vendor_id}/{unique_name}'


def _log(action, target_id, detail=''):
    try:
        db.session.add(ActivityLog(
            user_id=current_user.id,
            action=action,
            target='vendor_document',
            target_id=target_id,
            detail=detail,
            ip_address=request.remote_addr,
        ))
    except Exception:
        pass


def _doc_to_dict(doc):
    uploader = User.query.get(doc.uploaded_by) if doc.uploaded_by else None
    vendor = VendorMaster.query.get(doc.vendor_id) if doc.vendor_id else None

    # Derive file extension from stored path
    file_path = doc.file_path or ''
    file_ext = file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else ''

    # Derive category from document_type (fall back to model field if it exists)
    doc_type = doc.document_type or 'Other'
    category = DOC_TYPE_CATEGORY.get(doc_type, 'other')
    # If the model has its own document_category column, prefer it
    if hasattr(doc, 'document_category') and doc.document_category:
        category = doc.document_category

    return {
        'id': doc.id,
        'vendor_id': doc.vendor_id or '',
        'vendor_name': vendor.vendor_name_en if vendor else '',
        'vendor_code': vendor.vendor_code if vendor else '',
        'document_type': doc_type,
        'document_category': category,          # ← was missing, caused JS badge render to fail
        'file_extension': file_ext,             # ← was missing, caused JS icon render to fail
        'document_name': doc.document_name or '',
        'issue_date': str(doc.issue_date) if doc.issue_date else '',
        'expiry_date': str(doc.expiry_date) if doc.expiry_date else '',
        'uploaded_at': doc.uploaded_at.strftime('%Y-%m-%d %H:%M') if doc.uploaded_at else '',
        'uploaded_by': doc.uploaded_by,
        'uploaded_by_name': uploader.username if uploader else '',
        'file_path': file_path,
        'file_size_kb': round((doc.file_size or 0) / 1024, 1),
    }


def _get_mime_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or 'application/octet-stream'


def _can_display_inline(mime_type):
    return mime_type in INLINE_MIMETYPES


def _resolve_path(doc):
    """
    Returns (directory, filename, full_path).
    Handles both flat filenames and relative paths like
    'vendor_documents/42/abcdef.pdf'.
    """
    rel_path = (doc.file_path or '').replace('\\', '/')
    upload_root = current_app.config['UPLOAD_FOLDER']

    if '/' in rel_path:
        # Relative path stored — split into dir + file
        dir_part = os.path.dirname(rel_path)          # e.g. "vendor_documents/42"
        filename = os.path.basename(rel_path)          # e.g. "abcdef.pdf"
        folder = os.path.join(upload_root, dir_part)  # absolute dir
    else:
        # Flat filename stored directly in upload root
        filename = rel_path
        folder = upload_root

    full_path = os.path.join(folder, filename)
    return folder, filename, full_path


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@vendor_doc_bp.route('/vendor-documents')
@login_required
def list_vendor_documents_page():
    return render_template('vendor_documents/list.html')


@vendor_doc_bp.route('/vendor-documents/vendors-list')
@login_required
def vendors_list():
    vendors = VendorMaster.query.order_by(VendorMaster.vendor_name_en.asc()).all()
    data = [
        {
            'id': v.id,
            'name': v.vendor_name_en or v.vendor_name_ar or '',
            'vendor_code': v.vendor_code or '',
        }
        for v in vendors
    ]
    return jsonify(data)


@vendor_doc_bp.route('/vendor-documents/data')
@login_required
def vendor_documents_data():
    try:
        documents = VendorDocument.query.order_by(VendorDocument.uploaded_at.desc()).all()
        return jsonify([_doc_to_dict(doc) for doc in documents])
    except Exception as e:
        current_app.logger.error(f'vendor_documents_data error: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@vendor_doc_bp.route('/vendor-documents/upload', methods=['POST'])
@login_required
def upload_documents():
    try:
        vendor_id = request.form.get('vendor_id', '').strip()
        if not vendor_id:
            return jsonify({'ok': False, 'error': 'Vendor is required'})

        vendor = VendorMaster.query.get(int(vendor_id))
        if not vendor:
            return jsonify({'ok': False, 'error': 'Vendor not found'})

        files = request.files.getlist('files')
        if not files or all(not fs.filename for fs in files):
            return jsonify({'ok': False, 'error': 'No files selected'})

        uploaded = []
        errors = []

        for index, file_storage in enumerate(files):
            if not file_storage or not file_storage.filename:
                continue

            if not _allowed_file(file_storage.filename):
                errors.append({'filename': file_storage.filename, 'error': 'File type not allowed'})
                continue

            ok, size = _allowed_file_size(file_storage)
            if not ok:
                size_mb = size / (1024 * 1024)
                errors.append({'filename': file_storage.filename,
                               'error': f'File too large ({size_mb:.1f} MB). Max 16 MB.'})
                continue

            relative_path = _save_file(file_storage, vendor.id)

            doc_type = request.form.get(f'document_types[{index}]', 'Other')
            category = DOC_TYPE_CATEGORY.get(doc_type, 'other')

            doc = VendorDocument(
                vendor_id=vendor.id,
                document_type=doc_type,
                document_name=(
                    request.form.get(f'document_names[{index}]', '').strip()
                    or file_storage.filename
                ),
                issue_date=(
                    _date.fromisoformat(request.form.get(f'issue_dates[{index}]', ''))
                    if request.form.get(f'issue_dates[{index}]') else None
                ),
                expiry_date=(
                    _date.fromisoformat(request.form.get(f'expiry_dates[{index}]', ''))
                    if request.form.get(f'expiry_dates[{index}]') else None
                ),
                file_path=relative_path,
                file_size=os.path.getsize(
                    os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)
                ),
                uploaded_by=current_user.id,
                uploaded_at=datetime.utcnow(),
            )

            # Set category if the model column exists
            if hasattr(doc, 'document_category'):
                doc.document_category = category

            db.session.add(doc)
            uploaded.append(doc)

        if uploaded:
            db.session.commit()
            for doc in uploaded:
                _log('UPLOAD', doc.id, f'Uploaded "{doc.document_name}" for vendor {vendor.vendor_code}')

        return jsonify({
            'ok': True,
            'message': f'Successfully uploaded {len(uploaded)} file(s).' if not errors
                       else f'Uploaded {len(uploaded)} file(s) with {len(errors)} error(s).',
            'uploaded': [doc.id for doc in uploaded],
            'errors': errors,
        })

    except Exception as e:
        current_app.logger.error(f'upload_documents error: {e}', exc_info=True)
        db.session.rollback()
        return jsonify({'ok': False, 'error': f'Server error: {str(e)}'}), 500


@vendor_doc_bp.route('/vendors/documents/<int:doc_id>/view')
@login_required
def view_document(doc_id):
    doc = VendorDocument.query.get_or_404(doc_id)
    folder, filename, full_path = _resolve_path(doc)
    if not os.path.exists(full_path):
        abort(404)
    mime_type = _get_mime_type(full_path)
    if _can_display_inline(mime_type):
        return send_from_directory(folder, filename, as_attachment=False, mimetype=mime_type)
    return send_from_directory(folder, filename, as_attachment=True,
                               download_name=doc.document_name or filename, mimetype=mime_type)


@vendor_doc_bp.route('/vendors/documents/<int:doc_id>/download')
@login_required
def download_document(doc_id):
    doc = VendorDocument.query.get_or_404(doc_id)
    folder, filename, full_path = _resolve_path(doc)
    if not os.path.exists(full_path):
        abort(404)
    mime_type = _get_mime_type(full_path)
    return send_from_directory(folder, filename, as_attachment=True,
                               download_name=doc.document_name or filename, mimetype=mime_type)


@vendor_doc_bp.route('/vendor-documents/<int:doc_id>/delete', methods=['POST'])
@login_required
@_admin_required
def delete_document(doc_id):
    try:
        doc = VendorDocument.query.get_or_404(doc_id)
        folder, filename, full_path = _resolve_path(doc)
        doc_name = doc.document_name or filename
        if os.path.exists(full_path):
            os.remove(full_path)
        _log('DELETE', doc.id, f'Deleted "{doc_name}"')
        db.session.delete(doc)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        current_app.logger.error(f'delete_document error: {e}', exc_info=True)
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500