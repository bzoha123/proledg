from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from decimal import Decimal
from datetime import datetime, date
from models import (
    db, VendorMaster, VendorBank, VendorDocument,
    PurchaseRequest, PurchaseQuotation, PurchaseOrder, GoodsReceiptNote,
    PurchaseInvoice, GoodsReturnRequest, PurchaseDebitMemo,
    PurchaseAttachment, Invoice,
    PurchaseRequestLineItem, PurchaseQuotationLineItem, PurchaseOrderLineItem,
    GoodsReceiptLineItem, PurchaseInvoiceLineItem, GoodsReturnLineItem, PurchaseDebitMemoLineItem,
)
import os, re
from werkzeug.utils import secure_filename

pur_bp = Blueprint('purchase', __name__)


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (ONCE ONLY)
# ══════════════════════════════════════════════════════════════════

def _t(en, ar): return ar if session.get('lang') == 'ar' else en

def pd(val):
    """Parse date string, return None if empty/invalid."""
    if not val:
        return None
    try:
        return datetime.strptime(str(val).strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError, AttributeError):
        return None

def _vendor_list():
    """Return list of vendors for dropdowns."""
    return [{'id':v.id,'name':v.vendor_name_en,'name_ar':v.vendor_name_ar or ''} 
            for v in VendorMaster.query.filter_by(is_active=True).order_by(VendorMaster.vendor_name_en).all()]

def _invoice_list():
    return [{'id':i.id,'invoice_no':i.invoice_no} for i in Invoice.query.order_by(Invoice.id.desc()).all()]

def _next_doc_no(doc_type, model):
    """Generate unique doc number per type. Format: PR-2026-0001, PQ-2026-0001, PO-2026-0001."""
    year = date.today().year
    prefix = doc_type
    like = f'{prefix}-{year}-%'
    
    pk_name = None
    if hasattr(model, 'purchase_request_id'):
        pk_name = 'purchase_request_id'
    elif hasattr(model, 'purchase_quotation_id'):
        pk_name = 'purchase_quotation_id'
    elif hasattr(model, 'purchase_order_id'):
        pk_name = 'purchase_order_id'
    elif hasattr(model, 'goods_receipt_note_id'):
        pk_name = 'goods_receipt_note_id'
    elif hasattr(model, 'purchase_invoice_id'):
        pk_name = 'purchase_invoice_id'
    elif hasattr(model, 'goods_return_request_id'):
        pk_name = 'goods_return_request_id'
    elif hasattr(model, 'purchase_debit_memo_id'):
        pk_name = 'purchase_debit_memo_id'
    else:
        pk_name = 'id'
    
    pk_column = getattr(model, pk_name)
    
    last = db.session.query(model).filter(
        model.doc_no.like(like)
    ).order_by(pk_column.desc()).first()
    
    if last and last.doc_no:
        try:
            n = int(last.doc_no.split('-')[-1]) + 1
        except:
            n = 1
    else:
        n = 1
    return f'{prefix}-{year}-{n:04d}'

def _save_attachments(doc_type, doc_id, files):
    """Save uploaded attachments."""
    upload_dir = os.path.join('static','uploads','purchase',doc_type,str(doc_id))
    os.makedirs(upload_dir, exist_ok=True)
    for f in files:
        if not f or not f.filename: continue
        fname = secure_filename(f.filename)
        fpath = os.path.join(upload_dir, fname)
        f.save(fpath)
        att = PurchaseAttachment(
            doc_type=doc_type, doc_id=doc_id,
            filename=fname, filepath=fpath,
            file_size=os.path.getsize(fpath),
            uploaded_by=current_user.id,
        )
        db.session.add(att)

def _save_doc_line_items(LIModel, fk_field, fk_value, f):
    """Generic save for any dedicated line item model."""
    LIModel.query.filter_by(**{fk_field: fk_value}).delete()

    codes    = f.getlist('li_item_code[]')
    descs    = f.getlist('li_item_desc[]')
    rdates   = f.getlist('li_required_date[]')
    whs      = f.getlist('li_warehouse[]')
    uoms     = f.getlist('li_uom[]')
    qtys     = f.getlist('li_qty[]')
    rates    = f.getlist('li_rate[]')
    discs    = f.getlist('li_discount[]')
    freights = f.getlist('li_freight[]')
    tcodes   = f.getlist('li_tax_code[]')

    total_bd = Decimal(0); total_disc = Decimal(0)
    total_fr = Decimal(0); total_vat  = Decimal(0)

    for i in range(len(qtys)):
        try:
            qty      = Decimal(qtys[i]     or '0')
            rate     = Decimal(rates[i]    if i < len(rates)    else '0')
            disc     = Decimal(discs[i]    if i < len(discs)    else '0')
            fr       = Decimal(freights[i] if i < len(freights) else '0')
            tax_code = tcodes[i] if i < len(tcodes) else 'VAT15'
            tax_rate = Decimal('15') if '15' in tax_code else Decimal('0')
            taxable  = max(Decimal('0'), (qty * rate - disc) + fr)
            tax_amt  = (taxable * tax_rate / 100).quantize(Decimal('0.01'))
            total    = taxable + tax_amt

            li = LIModel(**{
                fk_field:        fk_value,
                'line_number':   i + 1,
                'item_code':     codes[i]  if i < len(codes)  else '',
                'description':   descs[i]  if i < len(descs)  else '',
                'required_date': pd(rdates[i]) if i < len(rdates) and rdates[i] else None,
                'warehouse':     whs[i]    if i < len(whs)    else '',
                'uom':           uoms[i]   if i < len(uoms)   else 'unit',
                'quantity':      qty,
                'rate':          rate,
                'discount':      disc,
                'freight':       fr,
                'taxable':       taxable,
                'tax_code':      tax_code,
                'tax_amount':    tax_amt,
                'total':         total,
            })
            db.session.add(li)
            total_bd   += qty * rate
            total_disc += disc
            total_fr   += fr
            total_vat  += tax_amt
        except Exception as e:
            print(f"Error processing line item {i}: {str(e)}")
            import traceback
            traceback.print_exc()

    excl = (total_bd - total_disc) + total_fr
    return {
        'total_before_discount': total_bd,
        'total_discount':        total_disc,
        'total_freight':         total_fr,
        'total_excl_vat':        excl,
        'vat_amount':            total_vat,
        'total_incl_vat':        excl + total_vat,
    }


# ══════════════════════════════════════════════════════════════════
# UNIFIED NEXT-DOC-NO ENDPOINT (ONCE ONLY)
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/next-doc-no')
@login_required
def next_doc_no():
    """Return next document number for AJAX - works for all types."""
    doc_type = request.args.get('type', 'PO')
    model_map = {
        'PR': PurchaseRequest,
        'PQ': PurchaseQuotation,
        'PO': PurchaseOrder,
        'GRN': GoodsReceiptNote,
        'PINV': PurchaseInvoice,
        'GRR': GoodsReturnRequest,
        'PDM': PurchaseDebitMemo,
    }
    model = model_map.get(doc_type, PurchaseOrder)
    return jsonify({'doc_no': _next_doc_no(doc_type, model)})

@pur_bp.route('/purchase/next-no')
@login_required
def purchase_next_no():
    """Legacy endpoint - redirects to next-doc-no."""
    doc_type = request.args.get('type','PR')
    return jsonify({'doc_no': _next_doc_no(doc_type, PurchaseRequest)})


# ══════════════════════════════════════════════════════════════════
# VENDOR REGISTRATION
# ══════════════════════════════════════════════════════════════════
@pur_bp.route('/purchase/vendors')
@login_required
def vendor_list():
    invoices = Invoice.query.order_by(Invoice.id.desc()).all()
    return render_template('purchase/vendor_list.html', invoices=invoices)

@pur_bp.route('/purchase/vendors/<int:id>')
@login_required
def vendor_view(id):
    v = VendorMaster.query.get_or_404(id)
    return render_template('purchase/vendor_view.html', vendor=v)

@pur_bp.route('/purchase/vendors/data')
@login_required
def vendor_data():
    rows = VendorMaster.query.order_by(VendorMaster.id.desc()).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/purchase/vendors/<int:id>/json')
@login_required
def vendor_json(id):
    v = VendorMaster.query.get_or_404(id)
    d = v.to_dict()
    for fld in ['vendor_name_ar','vat_number','crn','phone','fax','email','website',
                'contact_person','street_name','street_name_ar','building_number',
                'additional_number','postal_code','country','country_ar','city','city_ar',
                'district','district_ar','bank_name','bank_branch','swift_code',
                'account_number','iban','invoice_id']:
        d[fld] = getattr(v, fld, '') or ''
    return jsonify(d)

@pur_bp.route('/purchase/vendors/add', methods=['POST'])
@login_required
def vendor_add():
    f = request.form
    last = VendorMaster.query.order_by(VendorMaster.id.desc()).first()
    n = (last.id + 1) if last else 1
    v = VendorMaster(
        vendor_code=f'VND-{n:05d}',
        vendor_name_en=f.get('vendor_name_en','').strip(),
        vendor_name_ar=f.get('vendor_name_ar','').strip() or None,
        vat_number=f.get('vat_number','').strip() or None,
        crn=f.get('crn','').strip() or None,
        phone=f.get('phone','').strip() or None,
        fax=f.get('fax','').strip() or None,
        email=f.get('email','').strip() or None,
        website=f.get('website','').strip() or None,
        contact_person=f.get('contact_person','').strip() or None,
        street_name=f.get('street_name','').strip() or None,
        street_name_ar=f.get('street_name_ar','').strip() or None,
        building_number=f.get('building_number','').strip() or None,
        additional_number=f.get('additional_number','').strip() or None,
        postal_code=f.get('postal_code','').strip() or None,
        country=f.get('country','Saudi Arabia').strip(),
        country_ar=f.get('country_ar','المملكة العربية السعودية').strip(),
        city=f.get('city','').strip() or None,
        city_ar=f.get('city_ar','').strip() or None,
        district=f.get('district','').strip() or None,
        district_ar=f.get('district_ar','').strip() or None,
        status='active', is_active=True, created_by=current_user.id,
    )
    db.session.add(v); db.session.flush()
    
    bank_names_en = f.getlist('bank_name_en[]')
    bank_names_ar = f.getlist('bank_name_ar[]')
    bank_accounts = f.getlist('bank_account_number[]')
    bank_branches_en = f.getlist('bank_branch_en[]')
    bank_branches_ar = f.getlist('bank_branch_ar[]')
    bank_swifts = f.getlist('bank_swift[]')
    bank_ibans = f.getlist('bank_iban[]')
    bank_primaries = f.getlist('bank_is_primary[]')
    
    for i in range(len(bank_names_en)):
        if not bank_names_en[i].strip():
            continue
        is_primary = bank_primaries[i] == '1' if i < len(bank_primaries) else False
        if is_primary:
            VendorBank.query.filter_by(vendor_id=v.id, is_primary=True).update({'is_primary': False})
        bank = VendorBank(
            vendor_id=v.id,
            bank_name_en=bank_names_en[i].strip(),
            bank_name_ar=bank_names_ar[i].strip() if i < len(bank_names_ar) and bank_names_ar[i].strip() else None,
            account_number=bank_accounts[i].strip() if i < len(bank_accounts) and bank_accounts[i].strip() else None,
            branch_en=bank_branches_en[i].strip() if i < len(bank_branches_en) and bank_branches_en[i].strip() else None,
            branch_ar=bank_branches_ar[i].strip() if i < len(bank_branches_ar) and bank_branches_ar[i].strip() else None,
            swift_code=bank_swifts[i].strip() if i < len(bank_swifts) and bank_swifts[i].strip() else None,
            iban=bank_ibans[i].strip() if i < len(bank_ibans) and bank_ibans[i].strip() else None,
            is_primary=is_primary,
        )
        db.session.add(bank)
    
    db.session.commit()
    return jsonify({'ok': True, 'id': v.id, 'vendor_code': v.vendor_code})

@pur_bp.route('/purchase/vendors/<int:id>/edit', methods=['POST'])
@login_required
def vendor_edit(id):
    v = VendorMaster.query.get_or_404(id)
    f = request.form
    for fld in ['vendor_name_en','vendor_name_ar','vat_number','crn','phone','fax','email',
                'website','contact_person','street_name','street_name_ar','building_number',
                'additional_number','postal_code','country','country_ar','city','city_ar',
                'district','district_ar']:
        setattr(v, fld, f.get(fld,'').strip() or None)
    v.status = f.get('status','active')
    
    VendorBank.query.filter_by(vendor_id=id).delete()
    
    bank_names_en = f.getlist('bank_name_en[]')
    bank_names_ar = f.getlist('bank_name_ar[]')
    bank_accounts = f.getlist('bank_account_number[]')
    bank_branches_en = f.getlist('bank_branch_en[]')
    bank_branches_ar = f.getlist('bank_branch_ar[]')
    bank_swifts = f.getlist('bank_swift[]')
    bank_ibans = f.getlist('bank_iban[]')
    bank_primaries = f.getlist('bank_is_primary[]')
    
    for i in range(len(bank_names_en)):
        if not bank_names_en[i].strip():
            continue
        is_primary = bank_primaries[i] == '1' if i < len(bank_primaries) else False
        bank = VendorBank(
            vendor_id=id,
            bank_name_en=bank_names_en[i].strip(),
            bank_name_ar=bank_names_ar[i].strip() if i < len(bank_names_ar) and bank_names_ar[i].strip() else None,
            account_number=bank_accounts[i].strip() if i < len(bank_accounts) and bank_accounts[i].strip() else None,
            branch_en=bank_branches_en[i].strip() if i < len(bank_branches_en) and bank_branches_en[i].strip() else None,
            branch_ar=bank_branches_ar[i].strip() if i < len(bank_branches_ar) and bank_branches_ar[i].strip() else None,
            swift_code=bank_swifts[i].strip() if i < len(bank_swifts) and bank_swifts[i].strip() else None,
            iban=bank_ibans[i].strip() if i < len(bank_ibans) and bank_ibans[i].strip() else None,
            is_primary=is_primary,
        )
        db.session.add(bank)
    
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/purchase/vendors/<int:id>/delete', methods=['POST'])
@login_required
def vendor_delete(id):
    v = VendorMaster.query.get_or_404(id)
    db.session.delete(v); db.session.commit()
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════════════
# VENDOR BANKS
# ══════════════════════════════════════════════════════════════════
@pur_bp.route('/purchase/vendors/<int:vendor_id>/banks')
@login_required
def vendor_banks(vendor_id):
    banks = VendorBank.query.filter_by(vendor_id=vendor_id).order_by(VendorBank.is_primary.desc()).all()
    return jsonify([b.to_dict() for b in banks])

@pur_bp.route('/purchase/vendors/<int:vendor_id>/banks/add', methods=['POST'])
@login_required
def vendor_bank_add(vendor_id):
    f = request.form
    if f.get('is_primary') == '1':
        VendorBank.query.filter_by(vendor_id=vendor_id, is_primary=True).update({'is_primary': False})
    bank = VendorBank(
        vendor_id      = vendor_id,
        bank_name_en   = f.get('bank_name_en','').strip(),
        bank_name_ar   = f.get('bank_name_ar','').strip() or None,
        account_number = f.get('account_number','').strip() or None,
        branch_en      = f.get('branch_en','').strip() or None,
        branch_ar      = f.get('branch_ar','').strip() or None,
        swift_code     = f.get('swift_code','').strip() or None,
        iban           = f.get('iban','').strip() or None,
        is_primary     = f.get('is_primary') == '1',
    )
    db.session.add(bank)
    db.session.commit()
    return jsonify({'ok': True, 'id': bank.id})

@pur_bp.route('/purchase/vendors/banks/<int:bank_id>/edit', methods=['POST'])
@login_required
def vendor_bank_edit(bank_id):
    bank = VendorBank.query.get_or_404(bank_id)
    f = request.form
    if f.get('is_primary') == '1':
        VendorBank.query.filter_by(vendor_id=bank.vendor_id, is_primary=True).update({'is_primary': False})
    bank.bank_name_en   = f.get('bank_name_en','').strip()
    bank.bank_name_ar   = f.get('bank_name_ar','').strip() or None
    bank.account_number = f.get('account_number','').strip() or None
    bank.branch_en      = f.get('branch_en','').strip() or None
    bank.branch_ar      = f.get('branch_ar','').strip() or None
    bank.swift_code     = f.get('swift_code','').strip() or None
    bank.iban           = f.get('iban','').strip() or None
    bank.is_primary     = f.get('is_primary') == '1'
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/purchase/vendors/banks/<int:bank_id>/delete', methods=['POST'])
@login_required
def vendor_bank_delete(bank_id):
    bank = VendorBank.query.get_or_404(bank_id)
    db.session.delete(bank)
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/purchase/vendors/banks/<int:bank_id>/set-primary', methods=['POST'])
@login_required
def vendor_bank_set_primary(bank_id):
    bank = VendorBank.query.get_or_404(bank_id)
    VendorBank.query.filter_by(vendor_id=bank.vendor_id, is_primary=True).update({'is_primary': False})
    bank.is_primary = True
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════
# VENDOR DOCUMENTS
# ══════════════════════════════════════════════════════════════════
from werkzeug.utils import secure_filename as _sf
import uuid as _uuid

VENDOR_DOC_TYPES = [
    'CR / سجل تجاري', 'VAT Certificate / شهادة ضريبة', 'ID / هوية',
    'Contract / عقد', 'License / رخصة', 'Insurance / تأمين',
    'Bank Letter / خطاب بنكي', 'Other / أخرى',
]
VENDOR_ALLOWED_EXT = {'pdf','doc','docx','xls','xlsx','jpg','jpeg','png','gif','txt'}

@pur_bp.route('/purchase/vendors/<int:vendor_id>/documents')
@login_required
def vendor_documents(vendor_id):
    docs = VendorDocument.query.filter_by(vendor_id=vendor_id).order_by(VendorDocument.uploaded_at.desc()).all()
    return jsonify([d.to_dict() for d in docs])

@pur_bp.route('/purchase/vendors/<int:vendor_id>/documents/upload', methods=['POST'])
@login_required
def vendor_doc_upload(vendor_id):
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'ok': False, 'error': 'No file selected'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in VENDOR_ALLOWED_EXT:
        return jsonify({'ok': False, 'error': f'File type .{ext} not allowed'}), 400
    unique_name = f'{_uuid.uuid4().hex}.{ext}'
    folder = os.path.join('uploads', 'vendors', str(vendor_id))
    os.makedirs(folder, exist_ok=True)
    full_path = os.path.join(folder, unique_name)
    file.save(full_path)
    rel_path = os.path.join('vendors', str(vendor_id), unique_name)
    doc = VendorDocument(
        vendor_id     = vendor_id,
        document_type = request.form.get('document_type', 'Other / أخرى'),
        document_name = request.form.get('document_name', file.filename).strip() or file.filename,
        file_path     = rel_path,
        file_size     = os.path.getsize(full_path),
        expiry_date   = datetime.strptime(request.form['expiry_date'], '%Y-%m-%d').date() if request.form.get('expiry_date') else None,
        uploaded_by   = current_user.id,
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify({'ok': True, 'id': doc.id, 'doc': doc.to_dict()})

@pur_bp.route('/purchase/vendors/documents/<int:doc_id>/download')
@login_required
def vendor_doc_download(doc_id):
    from flask import send_from_directory
    doc    = VendorDocument.query.get_or_404(doc_id)
    folder = os.path.join('uploads', os.path.dirname(doc.file_path))
    fname  = os.path.basename(doc.file_path)
    return send_from_directory(os.path.abspath(folder), fname, as_attachment=True, download_name=doc.document_name)

@pur_bp.route('/purchase/vendors/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
def vendor_doc_delete(doc_id):
    doc = VendorDocument.query.get_or_404(doc_id)
    full = os.path.join('uploads', doc.file_path)
    if os.path.exists(full):
        os.remove(full)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════
# PURCHASE REQUEST (PR)
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/requests')
@login_required
def pr_list():
    return render_template('purchase/pr_list.html', vendors=_vendor_list())

@pur_bp.route('/purchase/requests/data')
@login_required
def pr_data():
    rows = PurchaseRequest.query.order_by(PurchaseRequest.purchase_request_id.desc()).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/purchase/requests/<int:id>/json')
@login_required
def pr_json(id):
    pr = PurchaseRequest.query.get_or_404(id)
    d = pr.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseRequestLineItem.query.filter_by(purchase_request_id=id).order_by(PurchaseRequestLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename,'filepath':a.filepath} for a in
                        PurchaseAttachment.query.filter_by(doc_type='PR', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/requests/<int:id>/view')
@login_required
def pr_view(id):
    pr = PurchaseRequest.query.get_or_404(id)
    items = PurchaseRequestLineItem.query.filter_by(purchase_request_id=id).order_by(PurchaseRequestLineItem.line_number).all()
    attachments = PurchaseAttachment.query.filter_by(doc_type='PR', doc_id=id).all()
    return render_template('purchase/pr_view.html', pr=pr, items=items, attachments=attachments)

@pur_bp.route('/purchase/requests/add', methods=['POST'])
@login_required
def pr_add():
    f = request.form
    pr = PurchaseRequest(
        doc_no=_next_doc_no('PR', PurchaseRequest),
        requester=f.get('requester','').strip(),
        requester_name=f.get('requester_name','').strip(),
        vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
        status=f.get('status','Open'),
        posting_date=pd(f.get('posting_date')),
        valid_until=pd(f.get('valid_until')),
        document_date=pd(f.get('document_date')),
        required_date=pd(f.get('required_date')),
        remarks=f.get('remarks','').strip(),
        approved_by=f.get('approved_by','').strip(),
        created_by=current_user.id,
    )
    db.session.add(pr); db.session.flush()
    tots = _save_doc_line_items(PurchaseRequestLineItem, 'purchase_request_id', pr.purchase_request_id, f)
    for k,v in tots.items(): setattr(pr, k, v)
    _save_attachments('PR', pr.purchase_request_id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True, 'id': pr.purchase_request_id, 'doc_no': pr.doc_no})

@pur_bp.route('/purchase/requests/<int:id>/edit', methods=['POST'])
@login_required
def pr_edit(id):
    pr = PurchaseRequest.query.get_or_404(id)
    f = request.form
    for fld in ['requester','requester_name','status','remarks','approved_by']:
        setattr(pr, fld, f.get(fld,'').strip())
    pr.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
    for df in ['posting_date','valid_until','document_date','required_date']:
        setattr(pr, df, pd(f.get(df)))
    tots = _save_doc_line_items(PurchaseRequestLineItem, 'purchase_request_id', id, f)
    for k,v in tots.items(): setattr(pr, k, v)
    _save_attachments('PR', id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/purchase/requests/<int:id>/delete', methods=['POST'])
@login_required
def pr_delete(id):
    pr = PurchaseRequest.query.get_or_404(id)
    PurchaseRequestLineItem.query.filter_by(purchase_request_id=id).delete()
    PurchaseAttachment.query.filter_by(doc_type='PR', doc_id=id).delete()
    db.session.delete(pr); db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════
# PURCHASE QUOTATION (PQ)
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/quotations')
@login_required
def pq_list():
    prs = [{'id':p.purchase_request_id,'doc_no':p.doc_no} for p in PurchaseRequest.query.order_by(PurchaseRequest.purchase_request_id.desc()).all()]
    return render_template('purchase/pq_list.html', vendors=_vendor_list(), prs=prs)

@pur_bp.route('/purchase/quotations/data')
@login_required
def pq_data():
    rows = PurchaseQuotation.query.order_by(PurchaseQuotation.purchase_quotation_id.desc()).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/purchase/quotations/<int:id>/json')
@login_required
def pq_json(id):
    pq = PurchaseQuotation.query.get_or_404(id)
    d = pq.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseQuotationLineItem.query.filter_by(purchase_quotation_id=id).order_by(PurchaseQuotationLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='PQ', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/quotations/<int:id>/view')
@login_required
def pq_view(id):
    pq = PurchaseQuotation.query.get_or_404(id)
    items = PurchaseQuotationLineItem.query.filter_by(purchase_quotation_id=id).order_by(PurchaseQuotationLineItem.line_number).all()
    attachments = PurchaseAttachment.query.filter_by(doc_type='PQ', doc_id=id).all()
    return render_template('purchase/pq_view.html', doc=pq, items=items, attachments=attachments, doc_type='PQ')

@pur_bp.route('/purchase/quotations/add', methods=['POST'])
@login_required
def pq_add():
    f = request.form
    pq = PurchaseQuotation(
        doc_no=_next_doc_no('PQ', PurchaseQuotation),
        purchase_request_id=int(f.get('pr_id')) if f.get('pr_id') else None,
        requester=f.get('requester','').strip(),
        requester_name=f.get('requester_name','').strip(),
        vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
        status=f.get('status','Open'),
        posting_date=pd(f.get('posting_date')),
        valid_until=pd(f.get('valid_until')),
        document_date=pd(f.get('document_date')),
        required_date=pd(f.get('required_date')),
        remarks=f.get('remarks','').strip(),
        approved_by=f.get('approved_by','').strip(),
        created_by=current_user.id,
    )
    db.session.add(pq)
    db.session.flush()
    
    tots = _save_doc_line_items(
        PurchaseQuotationLineItem, 
        'purchase_quotation_id', 
        pq.purchase_quotation_id, 
        f
    )
    
    for k, v in tots.items():
        setattr(pq, k, float(v) if isinstance(v, Decimal) else v)
    
    _save_attachments('PQ', pq.purchase_quotation_id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True, 'id': pq.purchase_quotation_id, 'doc_no': pq.doc_no})

@pur_bp.route('/purchase/quotations/<int:id>/edit', methods=['POST'])
@login_required
def pq_edit(id):
    pq = PurchaseQuotation.query.get_or_404(id)
    f = request.form
    for fld in ['requester','requester_name','status','remarks','approved_by']:
        setattr(pq, fld, f.get(fld,'').strip())
    
    pq.purchase_request_id = int(f.get('pr_id')) if f.get('pr_id') else None  
    pq.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
    
    for df in ['posting_date','valid_until','document_date','required_date']:
        setattr(pq, df, pd(f.get(df)))
    
    tots = _save_doc_line_items(
        PurchaseQuotationLineItem, 
        'purchase_quotation_id', 
        id, 
        f
    )
    
    for k, v in tots.items():
        setattr(pq, k, float(v) if isinstance(v, Decimal) else v)
    
    _save_attachments('PQ', id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/purchase/quotations/<int:id>/delete', methods=['POST'])
@login_required
def pq_delete(id):
    PurchaseQuotationLineItem.query.filter_by(purchase_quotation_id=id).delete()
    PurchaseAttachment.query.filter_by(doc_type='PQ', doc_id=id).delete()
    pq = PurchaseQuotation.query.get_or_404(id)
    db.session.delete(pq); db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════
# PURCHASE ORDER (PO)
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/orders')
@login_required
def po_list():
    pqs = [{'id': p.purchase_quotation_id, 'doc_no': p.doc_no} 
           for p in PurchaseQuotation.query.order_by(PurchaseQuotation.purchase_quotation_id.desc()).all()]
    return render_template('purchase/po_list.html', vendors=_vendor_list(), pqs=pqs)

@pur_bp.route('/purchase/orders/data')
@login_required
def po_data():
    rows = PurchaseOrder.query.order_by(PurchaseOrder.purchase_order_id.desc()).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/purchase/orders/<int:id>/json')
@login_required
def po_json(id):
    po = PurchaseOrder.query.get_or_404(id)
    d = po.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseOrderLineItem.query
                  .filter_by(purchase_order_id=id)
                  .order_by(PurchaseOrderLineItem.line_number).all()]
    d['attachments'] = [{'filename': a.filename} 
                        for a in PurchaseAttachment.query.filter_by(doc_type='PO', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/orders/<int:id>/summary')
@login_required
def po_summary(id):
    """Lightweight PO data for auto-filling Purchase Invoice form."""
    po = PurchaseOrder.query.get_or_404(id)
    d = po.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseOrderLineItem.query
                  .filter_by(purchase_order_id=id)
                  .order_by(PurchaseOrderLineItem.line_number).all()]
    return jsonify(d)

@pur_bp.route('/purchase/orders/<int:id>/view')
@login_required
def po_view(id):
    po = PurchaseOrder.query.get_or_404(id)
    items = PurchaseOrderLineItem.query.filter_by(purchase_order_id=id).order_by(PurchaseOrderLineItem.line_number).all()
    attachments = PurchaseAttachment.query.filter_by(doc_type='PO', doc_id=id).all()
    return render_template('purchase/po_view.html', doc=po, items=items, attachments=attachments, doc_type='PO')

@pur_bp.route('/purchase/orders/add', methods=['POST'])
@login_required
def po_add():
    try:
        f = request.form
        po = PurchaseOrder(
            doc_no=_next_doc_no('PO', PurchaseOrder),
            purchase_quotation_id=int(f.get('pq_id')) if f.get('pq_id') else None,
            vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
            vendor_ref_no=f.get('vendor_ref_no', '').strip(),
            remarks=f.get('remarks', '').strip(),
            status=f.get('status', 'Open'),
            posting_date=pd(f.get('posting_date')),
            delivery_date=pd(f.get('delivery_date')),
            document_date=pd(f.get('document_date')),
            created_by=current_user.id,
        )
        db.session.add(po)
        db.session.flush()

        tots = _save_doc_line_items(PurchaseOrderLineItem, 'purchase_order_id', po.purchase_order_id, f)
        for k, v in tots.items():
            setattr(po, k, v)

        _save_attachments('PO', po.purchase_order_id, request.files.getlist('attachments'))
        
        db.session.commit()
        return jsonify({'ok': True, 'id': po.purchase_order_id, 'doc_no': po.doc_no})
    
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in po_add: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@pur_bp.route('/purchase/orders/<int:id>/edit', methods=['POST'])
@login_required
def po_edit(id):
    try:
        po = PurchaseOrder.query.get_or_404(id)
        f = request.form
        
        po.purchase_quotation_id = int(f.get('pq_id')) if f.get('pq_id') else None
        po.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
        po.vendor_ref_no = f.get('vendor_ref_no', '').strip()
        po.remarks = f.get('remarks', '').strip()
        po.status = f.get('status', 'Open')
        
        for df in ['posting_date', 'delivery_date', 'document_date']:
            setattr(po, df, pd(f.get(df)))

        tots = _save_doc_line_items(PurchaseOrderLineItem, 'purchase_order_id', id, f)
        for k, v in tots.items():
            setattr(po, k, v)

        _save_attachments('PO', id, request.files.getlist('attachments'))
        
        db.session.commit()
        return jsonify({'ok': True})
    
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in po_edit: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@pur_bp.route('/purchase/orders/<int:id>/delete', methods=['POST'])
@login_required
def po_delete(id):
    try:
        PurchaseOrderLineItem.query.filter_by(purchase_order_id=id).delete()
        PurchaseAttachment.query.filter_by(doc_type='PO', doc_id=id).delete()
        po = PurchaseOrder.query.get_or_404(id)
        db.session.delete(po)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# GOODS RECEIPT NOTE (GRN)
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/grn')
@login_required
def grn_list():
    pos = [{'id':p.purchase_order_id,'doc_no':p.doc_no} for p in PurchaseOrder.query.order_by(PurchaseOrder.purchase_order_id.desc()).all()]
    return render_template('purchase/grn_list.html', vendors=_vendor_list(), pos=pos)

@pur_bp.route('/purchase/grn/data')
@login_required
def grn_data():
    return jsonify([r.to_dict() for r in GoodsReceiptNote.query.order_by(GoodsReceiptNote.goods_receipt_note_id.desc()).all()])

@pur_bp.route('/purchase/grn/<int:id>/json')
@login_required
def grn_json(id):
    doc = GoodsReceiptNote.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in GoodsReceiptLineItem.query.filter_by(goods_receipt_note_id=id).order_by(GoodsReceiptLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='GRN', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/grn/<int:id>/view')
@login_required
def grn_view(id):
    doc = GoodsReceiptNote.query.get_or_404(id)
    return render_template('purchase/grn_view.html', doc=doc,
        items=GoodsReceiptLineItem.query.filter_by(goods_receipt_note_id=id).order_by(GoodsReceiptLineItem.line_number).all(),
        attachments=PurchaseAttachment.query.filter_by(doc_type='GRN', doc_id=id).all())

@pur_bp.route('/purchase/grn/add', methods=['POST'])
@login_required
def grn_add():
    f = request.form
    doc = GoodsReceiptNote(
        doc_no=_next_doc_no('GRN', GoodsReceiptNote),
        po_id=int(f.get('po_id')) if f.get('po_id') else None,
        vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
        contact_person=f.get('contact_person','').strip(),
        vendor_ref_no=f.get('vendor_ref_no','').strip(),
        status=f.get('status','Open'),
        posting_date=pd(f.get('posting_date')), delivery_date=pd(f.get('delivery_date')),
        document_date=pd(f.get('document_date')), created_by=current_user.id,
    )
    db.session.add(doc); db.session.flush()
    tots = _save_doc_line_items(GoodsReceiptLineItem, 'goods_receipt_note_id', doc.goods_receipt_note_id, f)
    for k,v in tots.items(): setattr(doc, k, v)
    _save_attachments('GRN', doc.goods_receipt_note_id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok':True,'id':doc.goods_receipt_note_id,'doc_no':doc.doc_no})

@pur_bp.route('/purchase/grn/<int:id>/edit', methods=['POST'])
@login_required
def grn_edit(id):
    doc = GoodsReceiptNote.query.get_or_404(id); f = request.form
    doc.po_id=int(f.get('po_id')) if f.get('po_id') else None
    doc.vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None
    doc.contact_person=f.get('contact_person','').strip()
    doc.vendor_ref_no=f.get('vendor_ref_no','').strip()
    doc.status=f.get('status','Open')
    for df in ['posting_date','delivery_date','document_date']: setattr(doc, df, pd(f.get(df)))
    tots = _save_doc_line_items(GoodsReceiptLineItem, 'goods_receipt_note_id', id, f)
    for k,v in tots.items(): setattr(doc, k, v)
    _save_attachments('GRN', id, request.files.getlist('attachments'))
    db.session.commit(); return jsonify({'ok':True})

@pur_bp.route('/purchase/grn/<int:id>/delete', methods=['POST'])
@login_required
def grn_delete(id):
    GoodsReceiptLineItem.query.filter_by(goods_receipt_note_id=id).delete()
    PurchaseAttachment.query.filter_by(doc_type='GRN', doc_id=id).delete()
    db.session.delete(GoodsReceiptNote.query.get_or_404(id)); db.session.commit()
    return jsonify({'ok':True})


# ══════════════════════════════════════════════════════════════════
# PURCHASE INVOICE (PINV)
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/invoices')
@login_required
def pinv_list():
    pos = [{'id':p.purchase_order_id,'doc_no':p.doc_no} for p in PurchaseOrder.query.order_by(PurchaseOrder.purchase_order_id.desc()).all()]
    return render_template('purchase/pinv_list.html', vendors=_vendor_list(), pos=pos)

@pur_bp.route('/purchase/invoices/data')
@login_required
def pinv_data():
    return jsonify([r.to_dict() for r in PurchaseInvoice.query.order_by(PurchaseInvoice.purchase_invoice_id.desc()).all()])

@pur_bp.route('/purchase/invoices/<int:id>/json')
@login_required
def pinv_json(id):
    doc = PurchaseInvoice.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseInvoiceLineItem.query.filter_by(purchase_invoice_id=id).order_by(PurchaseInvoiceLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='PINV', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/invoices/<int:id>/view')
@login_required
def pinv_view(id):
    doc = PurchaseInvoice.query.get_or_404(id)
    return render_template('purchase/pinv_view.html', doc=doc,
        items=PurchaseInvoiceLineItem.query.filter_by(purchase_invoice_id=id).order_by(PurchaseInvoiceLineItem.line_number).all(),
        attachments=PurchaseAttachment.query.filter_by(doc_type='PINV', doc_id=id).all())

@pur_bp.route('/purchase/invoices/<int:id>/summary')
@login_required
def pinv_summary(id):
    doc = PurchaseInvoice.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseInvoiceLineItem.query.filter_by(purchase_invoice_id=id).order_by(PurchaseInvoiceLineItem.line_number).all()]
    return jsonify(d)

@pur_bp.route('/purchase/invoices/add', methods=['POST'])
@login_required
def pinv_add():
    try:
        f = request.form
        
        print("=== PINV ADD ===")
        print("Form keys:", list(f.keys()))
        print("PO ID:", f.get('po_id'))
        print("Item codes count:", len(f.getlist('li_item_code[]')))
        
        doc = PurchaseInvoice(
            doc_no=_next_doc_no('PINV', PurchaseInvoice),
            purchase_order_id=int(f.get('po_id')) if f.get('po_id') else None,
            vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
            vendor_ref_no=f.get('vendor_ref_no','').strip(),
            status=f.get('status','Open'),
            posting_date=pd(f.get('posting_date')), 
            delivery_date=pd(f.get('delivery_date')),
            document_date=pd(f.get('document_date')), 
            created_by=current_user.id,
        )
        db.session.add(doc)
        db.session.flush()
        
        print(f"Created invoice ID: {doc.purchase_invoice_id}")
        
        tots = _save_doc_line_items(PurchaseInvoiceLineItem, 'purchase_invoice_id', doc.purchase_invoice_id, f)
        
        print("Totals:", tots)
        
        for k,v in tots.items(): 
            setattr(doc, k, v)
        _save_attachments('PINV', doc.purchase_invoice_id, request.files.getlist('attachments'))
        
        db.session.commit()
        print("Invoice saved successfully")
        
        return jsonify({'ok':True,'id':doc.purchase_invoice_id,'doc_no':doc.doc_no})
    
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in pinv_add: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@pur_bp.route('/purchase/invoices/<int:id>/edit', methods=['POST'])
@login_required
def pinv_edit(id):
    try:
        doc = PurchaseInvoice.query.get_or_404(id)
        f = request.form
        
        doc.purchase_order_id = int(f.get('po_id')) if f.get('po_id') else None
        doc.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
        doc.vendor_ref_no = f.get('vendor_ref_no','').strip()
        doc.status = f.get('status','Open')
        for df in ['posting_date','delivery_date','document_date']: 
            setattr(doc, df, pd(f.get(df)))
        
        tots = _save_doc_line_items(PurchaseInvoiceLineItem, 'purchase_invoice_id', id, f)
        for k,v in tots.items(): 
            setattr(doc, k, v)
        _save_attachments('PINV', id, request.files.getlist('attachments'))
        
        db.session.commit()
        return jsonify({'ok':True})
    
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in pinv_edit: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@pur_bp.route('/purchase/invoices/<int:id>/delete', methods=['POST'])
@login_required
def pinv_delete(id):
    try:
        PurchaseInvoiceLineItem.query.filter_by(purchase_invoice_id=id).delete()
        PurchaseAttachment.query.filter_by(doc_type='PINV', doc_id=id).delete()
        db.session.delete(PurchaseInvoice.query.get_or_404(id))
        db.session.commit()
        return jsonify({'ok':True})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in pinv_delete: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# GOODS RETURN REQUEST (GRR)
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/returns')
@login_required
def grr_list():
    pos  = [{'id':p.purchase_order_id,'doc_no':p.doc_no} for p in PurchaseOrder.query.order_by(PurchaseOrder.purchase_order_id.desc()).all()]
    pins = [{'id':p.purchase_invoice_id,'doc_no':p.doc_no} for p in PurchaseInvoice.query.order_by(PurchaseInvoice.purchase_invoice_id.desc()).all()]
    return render_template('purchase/grr_list.html', vendors=_vendor_list(), pos=pos, pinvs=pins)

@pur_bp.route('/purchase/returns/data')
@login_required
def grr_data():
    return jsonify([r.to_dict() for r in GoodsReturnRequest.query.order_by(GoodsReturnRequest.goods_return_request_id.desc()).all()])

@pur_bp.route('/purchase/returns/<int:id>/json')
@login_required
def grr_json(id):
    doc = GoodsReturnRequest.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in GoodsReturnLineItem.query.filter_by(goods_return_request_id=id).order_by(GoodsReturnLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='GRR', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/returns/<int:id>/view')
@login_required
def grr_view(id):
    doc = GoodsReturnRequest.query.get_or_404(id)
    return render_template('purchase/grr_view.html', doc=doc,
        items=GoodsReturnLineItem.query.filter_by(goods_return_request_id=id).order_by(GoodsReturnLineItem.line_number).all(),
        attachments=PurchaseAttachment.query.filter_by(doc_type='GRR', doc_id=id).all())

@pur_bp.route('/purchase/returns/<int:id>/summary')
@login_required
def grr_summary(id):
    doc = GoodsReturnRequest.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in GoodsReturnLineItem.query.filter_by(goods_return_request_id=id).order_by(GoodsReturnLineItem.line_number).all()]
    return jsonify(d)

@pur_bp.route('/purchase/returns/add', methods=['POST'])
@login_required
def grr_add():
    f = request.form
    doc = GoodsReturnRequest(
        doc_no=_next_doc_no('GRR', GoodsReturnRequest),
        pi_id=int(f.get('pi_id')) if f.get('pi_id') else None,
        po_id=int(f.get('po_id')) if f.get('po_id') else None,
        vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
        contact_person=f.get('contact_person','').strip(),
        vendor_ref_no=f.get('vendor_ref_no','').strip(),
        status=f.get('status','Open'),
        posting_date=pd(f.get('posting_date')), delivery_date=pd(f.get('delivery_date')),
        document_date=pd(f.get('document_date')), created_by=current_user.id,
    )
    db.session.add(doc); db.session.flush()
    tots = _save_doc_line_items(GoodsReturnLineItem, 'goods_return_request_id', doc.goods_return_request_id, f)
    for k,v in tots.items(): setattr(doc, k, v)
    _save_attachments('GRR', doc.goods_return_request_id, request.files.getlist('attachments'))
    db.session.commit(); return jsonify({'ok':True,'id':doc.goods_return_request_id,'doc_no':doc.doc_no})

@pur_bp.route('/purchase/returns/<int:id>/edit', methods=['POST'])
@login_required
def grr_edit(id):
    doc = GoodsReturnRequest.query.get_or_404(id); f = request.form
    doc.pi_id=int(f.get('pi_id')) if f.get('pi_id') else None
    doc.po_id=int(f.get('po_id')) if f.get('po_id') else None
    doc.vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None
    doc.contact_person=f.get('contact_person','').strip()
    doc.vendor_ref_no=f.get('vendor_ref_no','').strip()
    doc.status=f.get('status','Open')
    for df in ['posting_date','delivery_date','document_date']: setattr(doc, df, pd(f.get(df)))
    tots = _save_doc_line_items(GoodsReturnLineItem, 'goods_return_request_id', id, f)
    for k,v in tots.items(): setattr(doc, k, v)
    _save_attachments('GRR', id, request.files.getlist('attachments'))
    db.session.commit(); return jsonify({'ok':True})

@pur_bp.route('/purchase/returns/<int:id>/delete', methods=['POST'])
@login_required
def grr_delete(id):
    GoodsReturnLineItem.query.filter_by(goods_return_request_id=id).delete()
    PurchaseAttachment.query.filter_by(doc_type='GRR', doc_id=id).delete()
    db.session.delete(GoodsReturnRequest.query.get_or_404(id)); db.session.commit()
    return jsonify({'ok':True})


# ══════════════════════════════════════════════════════════════════
# PURCHASE DEBIT MEMO (PDM)
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/debit-memos')
@login_required
def pdm_list():
    pos  = [{'id':p.purchase_order_id,'doc_no':p.doc_no} for p in PurchaseOrder.query.order_by(PurchaseOrder.purchase_order_id.desc()).all()]
    grrs = [{'id':p.goods_return_request_id,'doc_no':p.doc_no} for p in GoodsReturnRequest.query.order_by(GoodsReturnRequest.goods_return_request_id.desc()).all()]
    return render_template('purchase/pdm_list.html', vendors=_vendor_list(), pos=pos, grrs=grrs)

@pur_bp.route('/purchase/debit-memos/data')
@login_required
def pdm_data():
    return jsonify([r.to_dict() for r in PurchaseDebitMemo.query.order_by(PurchaseDebitMemo.purchase_debit_memo_id.desc()).all()])

@pur_bp.route('/purchase/debit-memos/<int:id>/json')
@login_required
def pdm_json(id):
    doc = PurchaseDebitMemo.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseDebitMemoLineItem.query.filter_by(purchase_debit_memo_id=id).order_by(PurchaseDebitMemoLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='PDM', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/debit-memos/<int:id>/view')
@login_required
def pdm_view(id):
    doc = PurchaseDebitMemo.query.get_or_404(id)
    return render_template('purchase/pdm_view.html', doc=doc,
        items=PurchaseDebitMemoLineItem.query.filter_by(purchase_debit_memo_id=id).order_by(PurchaseDebitMemoLineItem.line_number).all(),
        attachments=PurchaseAttachment.query.filter_by(doc_type='PDM', doc_id=id).all())

@pur_bp.route('/purchase/debit-memos/add', methods=['POST'])
@login_required
def pdm_add():
    f = request.form
    doc = PurchaseDebitMemo(
        doc_no=_next_doc_no('PDM', PurchaseDebitMemo),
        po_id=int(f.get('po_id')) if f.get('po_id') else None,
        grr_id=int(f.get('grr_id')) if f.get('grr_id') else None,
        vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
        contact_person=f.get('contact_person','').strip(),
        vendor_ref_no=f.get('vendor_ref_no','').strip(),
        status=f.get('status','Open'),
        posting_date=pd(f.get('posting_date')), delivery_date=pd(f.get('delivery_date')),
        document_date=pd(f.get('document_date')), created_by=current_user.id,
    )
    db.session.add(doc); db.session.flush()
    tots = _save_doc_line_items(PurchaseDebitMemoLineItem, 'purchase_debit_memo_id', doc.purchase_debit_memo_id, f)
    for k,v in tots.items(): setattr(doc, k, v)
    _save_attachments('PDM', doc.purchase_debit_memo_id, request.files.getlist('attachments'))
    db.session.commit(); return jsonify({'ok':True,'id':doc.purchase_debit_memo_id,'doc_no':doc.doc_no})

@pur_bp.route('/purchase/debit-memos/<int:id>/edit', methods=['POST'])
@login_required
def pdm_edit(id):
    doc = PurchaseDebitMemo.query.get_or_404(id); f = request.form
    doc.po_id=int(f.get('po_id')) if f.get('po_id') else None
    doc.grr_id=int(f.get('grr_id')) if f.get('grr_id') else None
    doc.vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None
    doc.contact_person=f.get('contact_person','').strip()
    doc.vendor_ref_no=f.get('vendor_ref_no','').strip()
    doc.status=f.get('status','Open')
    for df in ['posting_date','delivery_date','document_date']: setattr(doc, df, pd(f.get(df)))
    tots = _save_doc_line_items(PurchaseDebitMemoLineItem, 'purchase_debit_memo_id', id, f)
    for k,v in tots.items(): setattr(doc, k, v)
    _save_attachments('PDM', id, request.files.getlist('attachments'))
    db.session.commit(); return jsonify({'ok':True})

@pur_bp.route('/purchase/debit-memos/<int:id>/delete', methods=['POST'])
@login_required
def pdm_delete(id):
    PurchaseDebitMemoLineItem.query.filter_by(purchase_debit_memo_id=id).delete()
    PurchaseAttachment.query.filter_by(doc_type='PDM', doc_id=id).delete()
    db.session.delete(PurchaseDebitMemo.query.get_or_404(id)); db.session.commit()
    return jsonify({'ok':True})