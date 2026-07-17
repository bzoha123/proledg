from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, abort
from flask_login import login_required, current_user
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy import text
import os, re, uuid
from werkzeug.utils import secure_filename

# ✅ FIX: Complete imports - ItemMaster is in models.py
from models import (
    db, 
    VendorMaster, 
    VendorBank,
    VendorDocument,
    PurchaseRequest, 
    PurchaseQuotation, 
    PurchaseOrder, 
    GoodsReceiptNote,
    PurchaseInvoice, 
    GoodsReturnRequest, 
    PurchaseDebitMemo,
    PurchaseAttachment,
    PurchaseRequestLineItem, 
    PurchaseQuotationLineItem, 
    PurchaseOrderLineItem,
    GoodsReceiptLineItem, 
    PurchaseInvoiceLineItem, 
    GoodsReturnLineItem, 
    PurchaseDebitMemoLineItem,
    PurchaseTaxCode,
    SalesTaxCode,
    ItemMaster,           # ✅ Now properly imported
    ItemCategory,         # ✅ Now properly imported
    ItemSubCategory,      # ✅ Now properly imported
    TaxCategory,          # ✅ Now properly imported
    UnitOfMeasurement,    # ✅ Now properly imported
    ItemUOM,              # ✅ Now properly imported
)

pur_bp = Blueprint('purchase', __name__)


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
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

def _next_doc_no(doc_type, model):
    """Generate unique doc number per type. Format: PR-2026-0001, PQ-2026-0001, etc."""
    year = date.today().year
    prefix = doc_type
    like = f'{prefix}-{year}-%'
    
    # Determine primary key column
    pk_name = 'id'
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
    
    pk_column = getattr(model, pk_name)
    
    # Get all records for this year
    all_docs = db.session.query(model).filter(
        model.doc_no.like(like)
    ).all()
    
    max_num = 0
    for doc in all_docs:
        if doc.doc_no:
            try:
                parts = doc.doc_no.split('-')
                if len(parts) == 3:
                    num = int(parts[2])
                    if num > max_num:
                        max_num = num
            except (ValueError, IndexError):
                continue
    
    n = max_num + 1
    doc_no = f'{prefix}-{year}-{n:04d}'
    
    # Safety check - ensure uniqueness
    retries = 0
    while model.query.filter_by(doc_no=doc_no).first() and retries < 100:
        n += 1
        doc_no = f'{prefix}-{year}-{n:04d}'
        retries += 1
    
    if retries >= 100:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        doc_no = f'{prefix}-{year}-{timestamp}'
    
    return doc_no


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


def _get_tax_rate(tax_code, doc_type='purchase'):
    """Get tax rate from tax code (numeric only)."""
    try:
        if doc_type == 'purchase':
            tax = PurchaseTaxCode.query.filter_by(tax_code=tax_code, status='Active').first()
        else:
            tax = SalesTaxCode.query.filter_by(tax_code=tax_code, status='Active').first()
        
        if tax and hasattr(tax, 'tax_rate'):
            return Decimal(str(tax.tax_rate))
        
        # Fallback: try to parse tax_code as number
        try:
            return Decimal(tax_code)
        except:
            return Decimal('0')
    except Exception:
        return Decimal('0')


def _save_doc_line_items(LIModel, fk_field, fk_value, f, doc_type='purchase'):
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

    total_bd = Decimal(0)
    total_disc = Decimal(0)
    total_fr = Decimal(0)
    total_vat = Decimal(0)

    for i in range(len(qtys)):
        try:
            # ✅ FIX: Handle empty/None values safely
            qty_str = qtys[i] if i < len(qtys) and qtys[i] else '0'
            rate_str = rates[i] if i < len(rates) and rates[i] else '0'
            disc_str = discs[i] if i < len(discs) and discs[i] else '0'
            fr_str = freights[i] if i < len(freights) and freights[i] else '0'
            
            # Remove commas and clean
            qty_str = qty_str.replace(',', '').strip()
            rate_str = rate_str.replace(',', '').strip()
            disc_str = disc_str.replace(',', '').strip()
            fr_str = fr_str.replace(',', '').strip()
            
            # Parse with 4 decimal precision
            qty = Decimal(qty_str or '0').quantize(Decimal('0.0001'))
            rate = Decimal(rate_str or '0').quantize(Decimal('0.0001'))
            disc = Decimal(disc_str or '0').quantize(Decimal('0.0001'))
            fr = Decimal(fr_str or '0').quantize(Decimal('0.0001'))
            
            # Get tax rate from tax code (numeric only)
            tax_code = tcodes[i] if i < len(tcodes) and tcodes[i] else '0'
            tax_code = tax_code.strip()
            tax_rate = _get_tax_rate(tax_code, doc_type)
            
            # Calculate with proper precision
            taxable = max(Decimal('0'), (qty * rate - disc) + fr)
            tax_amt = (taxable * tax_rate / 100).quantize(Decimal('0.01'))  # 2 decimals
            total = (taxable + tax_amt).quantize(Decimal('0.01'))  # 2 decimals
            taxable_rounded = taxable.quantize(Decimal('0.01'))  # 2 decimals

            li = LIModel(**{
                fk_field:        fk_value,
                'line_number':   i + 1,
                'item_code':     codes[i]  if i < len(codes)  else '',
                'description':   descs[i]  if i < len(descs)  else '',
                'required_date': pd(rdates[i]) if i < len(rdates) and rdates[i] else None,
                'warehouse':     whs[i]    if i < len(whs)    else '',
                'uom':           uoms[i]   if i < len(uoms)   else 'unit',
                'quantity':      qty,  # 4 decimals
                'rate':          rate,  # 4 decimals
                'discount':      disc,  # 4 decimals
                'freight':       fr,    # 4 decimals
                'taxable':       taxable_rounded,  # 2 decimals
                'tax_code':      tax_code,
                'tax_amount':    tax_amt,  # 2 decimals
                'total':         total,  # 2 decimals
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
        'total_before_discount': total_bd.quantize(Decimal('0.01')),
        'total_discount':        total_disc.quantize(Decimal('0.01')),
        'total_freight':         total_fr.quantize(Decimal('0.01')),
        'total_excl_vat':        excl.quantize(Decimal('0.01')),
        'vat_amount':            total_vat.quantize(Decimal('0.01')),
        'total_incl_vat':        (excl + total_vat).quantize(Decimal('0.01')),
    }


def _validate_pr_pq_dates(valid_until, required_date):
    """valid_until must be >= today (document_date); required_date must be <= valid_until."""
    today = date.today()
    if valid_until and valid_until < today:
        return 'Valid Until must be on/after the document date'
    if required_date and valid_until and required_date > valid_until:
        return 'Required Date must be on/before Valid Until'
    return None


def _next_item_code():
    """Generate the next sequential item code. Format: ITM-0001, ITM-0002, ..."""
    prefix = 'ITM'
    like = f'{prefix}-%'
    last = db.session.query(ItemMaster).filter(
        ItemMaster.item_code.like(like)
    ).order_by(ItemMaster.id.desc()).first()

    n = 1
    if last and last.item_code:
        try:
            n = int(last.item_code.split('-')[-1]) + 1
        except (ValueError, IndexError):
            n = ItemMaster.query.count() + 1
    code = f'{prefix}-{n:04d}'
    while ItemMaster.query.filter_by(item_code=code).first():
        n += 1
        code = f'{prefix}-{n:04d}'
    return code


# ══════════════════════════════════════════════════════════════════
# UNIFIED NEXT-DOC-NO ENDPOINT
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/next-doc-no')
@login_required
def next_doc_no():
    """Return next document number for AJAX - works for all types."""
    doc_type = request.args.get('type', 'PO')
    force_new = request.args.get('force_new', 'false').lower() == 'true'
    
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
    
    doc_no = _next_doc_no(doc_type, model)
    
    return jsonify({
        'ok': True,
        'doc_no': doc_no,
        'force_new': force_new
    })

@pur_bp.route('/purchase/next-no')
@login_required
def purchase_next_no():
    """Legacy endpoint - redirects to next-doc-no."""
    doc_type = request.args.get('type', 'PR')
    model_map = {
        'PR': PurchaseRequest,
        'PQ': PurchaseQuotation,
        'PO': PurchaseOrder,
        'GRN': GoodsReceiptNote,
        'PINV': PurchaseInvoice,
        'GRR': GoodsReturnRequest,
        'PDM': PurchaseDebitMemo,
    }
    model = model_map.get(doc_type, PurchaseRequest)
    doc_no = _next_doc_no(doc_type, model)
    return jsonify({'doc_no': doc_no})


# ══════════════════════════════════════════════════════════════════
# VENDOR REGISTRATION
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/purchase/vendors')
@login_required
def vendor_list():
    return render_template('purchase/vendor_list.html')

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
    unique_name = f'{uuid.uuid4().hex}.{ext}'
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

# ─────────────────────────────────────────────────────────────
# PURCHASE ATTACHMENTS — view / download
# Attachments are saved by _save_attachments() under
#   static/uploads/purchase/<doc_type>/<doc_id>/<filename>
# and that relative path is stored in PurchaseAttachment.filepath.
# These routes serve them behind @login_required.
# ─────────────────────────────────────────────────────────────
def _attachment_dir_and_name(att):
    """Return (absolute_dir, filename) for a stored attachment."""
    rel = (att.filepath or '').replace('\\', '/')
    directory = os.path.abspath(os.path.dirname(rel))
    fname = os.path.basename(rel)
    return directory, fname


@pur_bp.route('/purchase/attachments/<int:att_id>/view')
@login_required
def purchase_attachment_view(att_id):
    """Open the attachment inline when the browser can show it."""
    from flask import send_from_directory
    import mimetypes
    att = PurchaseAttachment.query.get_or_404(att_id)
    directory, fname = _attachment_dir_and_name(att)
    full = os.path.join(directory, fname)
    if not os.path.exists(full):
        abort(404)
    mime = mimetypes.guess_type(fname)[0] or 'application/octet-stream'
    inline_ok = mime in ('application/pdf', 'text/plain', 'text/csv') or mime.startswith('image/')
    return send_from_directory(directory, fname, as_attachment=not inline_ok,
                               download_name=att.filename or fname, mimetype=mime)


@pur_bp.route('/purchase/attachments/<int:att_id>/download')
@login_required
def purchase_attachment_download(att_id):
    """Always download the attachment."""
    from flask import send_from_directory
    import mimetypes
    att = PurchaseAttachment.query.get_or_404(att_id)
    directory, fname = _attachment_dir_and_name(att)
    full = os.path.join(directory, fname)
    if not os.path.exists(full):
        abort(404)
    mime = mimetypes.guess_type(fname)[0] or 'application/octet-stream'
    return send_from_directory(directory, fname, as_attachment=True,
                               download_name=att.filename or fname, mimetype=mime)


@pur_bp.route('/purchase/attachments/<int:att_id>/delete', methods=['POST'])
@login_required
def purchase_attachment_delete(att_id):
    """Delete a single attachment: remove the file from disk, then the row."""
    att = PurchaseAttachment.query.get_or_404(att_id)
    try:
        directory, fname = _attachment_dir_and_name(att)
        full = os.path.join(directory, fname)
        if os.path.exists(full):
            os.remove(full)
        db.session.delete(att)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


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
# ITEM MASTER
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/items/next-code')
@login_required
def item_next_code():
    return jsonify({'item_code': _next_item_code()})

@pur_bp.route('/items/data')
@login_required
def item_data():
    rows = ItemMaster.query.filter_by(is_active=True).order_by(ItemMaster.item_code).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/items/all')
@login_required
def items_all():
    rows = ItemMaster.query.order_by(ItemMaster.item_code).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/items/<int:id>/json')
@login_required
def item_json(id):
    item = ItemMaster.query.get_or_404(id)
    return jsonify(item.to_dict())

@pur_bp.route('/items/add', methods=['POST'])
@login_required
def item_add():
    f = request.form
    try:
        item = ItemMaster(
            item_code=_next_item_code(),
            item_type=f.get('item_type','Product'),
            article_no=f.get('article_no','').strip() or None,
            name_en=f.get('name_en','').strip(),
            name_ar=f.get('name_ar','').strip() or None,
            print_name=f.get('print_name','').strip() or None,
            uom=f.get('uom','unit'),
            item_desc=f.get('item_desc','').strip() or None,
            category_id=int(f.get('category_id')) if f.get('category_id') else None,
            sub_category_id=int(f.get('sub_category_id')) if f.get('sub_category_id') else None,
            tax_category_id=int(f.get('tax_category_id')) if f.get('tax_category_id') else None,
            vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
            main_rate=Decimal(f.get('main_rate') or '0'),
            po_rate=Decimal(f.get('po_rate') or '0'),
            retail_rate=Decimal(f.get('retail_rate') or '0'),
            wholesale_rate=Decimal(f.get('wholesale_rate') or '0'),
            special_rate=Decimal(f.get('special_rate') or '0'),
            mrp=Decimal(f.get('mrp') or '0'),
            minimum_sp=Decimal(f.get('minimum_sp') or '0'),
            is_active=f.get('is_active') == '1',
            created_by=current_user.id,
        )
        db.session.add(item)
        db.session.flush()
        
        # Handle UOMs if provided
        uom_ids = f.getlist('uom_ids[]')
        for uom_id in uom_ids:
            if uom_id:
                item_uom = ItemUOM(
                    item_id=item.id,
                    uom_id=int(uom_id),
                    is_default=False
                )
                db.session.add(item_uom)
        
        db.session.commit()
        return jsonify({'ok': True, 'id': item.id, 'item_code': item.item_code})
    except Exception as e:
        db.session.rollback()
        print(f"Error adding item: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@pur_bp.route('/items/<int:id>/edit', methods=['POST'])
@login_required
def item_edit(id):
    item = ItemMaster.query.get_or_404(id)
    f = request.form
    try:
        item.item_type = f.get('item_type','Product')
        item.article_no = f.get('article_no','').strip() or None
        item.name_en = f.get('name_en','').strip()
        item.name_ar = f.get('name_ar','').strip() or None
        item.print_name = f.get('print_name','').strip() or None
        item.uom = f.get('uom','unit')
        item.item_desc = f.get('item_desc','').strip() or None
        item.category_id = int(f.get('category_id')) if f.get('category_id') else None
        item.sub_category_id = int(f.get('sub_category_id')) if f.get('sub_category_id') else None
        item.tax_category_id = int(f.get('tax_category_id')) if f.get('tax_category_id') else None
        item.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
        item.main_rate = Decimal(f.get('main_rate') or '0')
        item.po_rate = Decimal(f.get('po_rate') or '0')
        item.retail_rate = Decimal(f.get('retail_rate') or '0')
        item.wholesale_rate = Decimal(f.get('wholesale_rate') or '0')
        item.special_rate = Decimal(f.get('special_rate') or '0')
        item.mrp = Decimal(f.get('mrp') or '0')
        item.minimum_sp = Decimal(f.get('minimum_sp') or '0')
        item.is_active = f.get('is_active') == '1'
        item.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error editing item: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@pur_bp.route('/items/<int:id>/delete', methods=['POST'])
@login_required
def item_delete(id):
    item = ItemMaster.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════
# UNIT OF MEASUREMENT
# ══════════════════════════════════════════════════════════════════

@pur_bp.route('/items/uom/list')
@login_required
def uom_master_list():
    rows = UnitOfMeasurement.query.order_by(UnitOfMeasurement.unit_name).all()
    return jsonify([u.to_dict() for u in rows])

@pur_bp.route('/items/uom/add', methods=['POST'])
@login_required
def uom_master_add():
    f = request.form
    name = f.get('unit_name','').strip()
    if not name:
        return jsonify({'ok': False, 'error': 'Unit name is required'}), 400
    existing = UnitOfMeasurement.query.filter(db.func.lower(UnitOfMeasurement.unit_name) == name.lower()).first()
    if existing:
        return jsonify({'ok': True, 'unit': existing.to_dict()})
    unit = UnitOfMeasurement(unit_name=name, unit_name_ar=f.get('unit_name_ar','').strip() or None)
    db.session.add(unit)
    db.session.commit()
    return jsonify({'ok': True, 'unit': unit.to_dict()})

@pur_bp.route('/items/<int:item_id>/uoms')
@login_required
def item_uom_list(item_id):
    rows = ItemUOM.query.filter_by(item_id=item_id).order_by(ItemUOM.is_default.desc(), ItemUOM.id).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/items/<int:item_id>/uoms/add', methods=['POST'])
@login_required
def item_uom_add(item_id):
    item = ItemMaster.query.get_or_404(item_id)
    f = request.form
    uom_id = f.get('uom_id')
    if uom_id:
        unit = UnitOfMeasurement.query.get(int(uom_id))
        if not unit:
            return jsonify({'ok': False, 'error': 'Unit not found'}), 404
    else:
        name = f.get('unit_name','').strip()
        if not name:
            return jsonify({'ok': False, 'error': 'Select a unit or enter a new unit name'}), 400
        unit = UnitOfMeasurement.query.filter(db.func.lower(UnitOfMeasurement.unit_name) == name.lower()).first()
        if not unit:
            unit = UnitOfMeasurement(unit_name=name, unit_name_ar=f.get('unit_name_ar','').strip() or None)
            db.session.add(unit)
            db.session.flush()

    dup = ItemUOM.query.filter_by(item_id=item_id, uom_id=unit.id).first()
    if dup:
        return jsonify({'ok': False, 'error': 'This unit is already attached to the item'}), 400

    is_first = ItemUOM.query.filter_by(item_id=item_id).count() == 0
    link = ItemUOM(item_id=item_id, uom_id=unit.id, is_default=is_first)
    db.session.add(link)
    if is_first:
        item.uom = unit.unit_name
    db.session.commit()
    return jsonify({'ok': True, 'item_uom': link.to_dict()})

@pur_bp.route('/items/uoms/<int:item_uom_id>/delete', methods=['POST'])
@login_required
def item_uom_delete(item_uom_id):
    link = ItemUOM.query.get_or_404(item_uom_id)
    item_id = link.item_id
    was_default = link.is_default
    db.session.delete(link)
    db.session.flush()
    if was_default:
        nxt = ItemUOM.query.filter_by(item_id=item_id).order_by(ItemUOM.id).first()
        if nxt:
            nxt.is_default = True
            item = ItemMaster.query.get(item_id)
            if item:
                item.uom = nxt.uom.unit_name if nxt.uom else item.uom
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/items/uoms/<int:item_uom_id>/set-default', methods=['POST'])
@login_required
def item_uom_set_default(item_uom_id):
    link = ItemUOM.query.get_or_404(item_uom_id)
    ItemUOM.query.filter_by(item_id=link.item_id).update({'is_default': False})
    link.is_default = True
    item = ItemMaster.query.get(link.item_id)
    if item:
        item.uom = link.uom.unit_name if link.uom else item.uom
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
    d['attachments'] = [{'id':a.id,'filename':a.filename,'filepath':a.filepath} for a in
                        PurchaseAttachment.query.filter_by(doc_type='PR', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/requests/<int:id>/view')
@login_required
def pr_view(id):
    pr = PurchaseRequest.query.get_or_404(id)
    items = PurchaseRequestLineItem.query.filter_by(purchase_request_id=id).order_by(PurchaseRequestLineItem.line_number).all()
    attachments = PurchaseAttachment.query.filter_by(doc_type='PR', doc_id=id).all()
    return render_template('purchase/pr_view.html', pr=pr, items=items, attachments=attachments)

@pur_bp.route('/purchase/requests/<int:id>/summary')
@login_required
def pr_summary(id):
    pr = PurchaseRequest.query.get_or_404(id)
    d = pr.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseRequestLineItem.query.filter_by(purchase_request_id=id).order_by(PurchaseRequestLineItem.line_number).all()]
    return jsonify(d)

@pur_bp.route('/purchase/requests/add', methods=['POST'])
@login_required
def pr_add():
    f = request.form
    valid_until   = pd(f.get('valid_until'))
    required_date = pd(f.get('required_date'))
    err = _validate_pr_pq_dates(valid_until, required_date)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    pr = PurchaseRequest(
        doc_no=_next_doc_no('PR', PurchaseRequest),
        requester=current_user.username,
        requester_name=current_user.username,
        vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
        status=f.get('status','Open'),
        kind=f.get('kind','Goods'),
        posting_date=pd(f.get('posting_date')),
        valid_until=valid_until,
        document_date=date.today(),
        required_date=required_date,
        remarks=f.get('remarks','').strip(),
        approved_by=f.get('approved_by','').strip(),
        created_by=current_user.id,
    )
    db.session.add(pr); db.session.flush()
    tots = _save_doc_line_items(PurchaseRequestLineItem, 'purchase_request_id', pr.purchase_request_id, f, 'purchase')
    for k,v in tots.items(): setattr(pr, k, v)
    _save_attachments('PR', pr.purchase_request_id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True, 'id': pr.purchase_request_id, 'doc_no': pr.doc_no})

@pur_bp.route('/purchase/requests/<int:id>/edit', methods=['POST'])
@login_required
def pr_edit(id):
    pr = PurchaseRequest.query.get_or_404(id)
    f = request.form
    valid_until   = pd(f.get('valid_until'))
    required_date = pd(f.get('required_date'))
    err = _validate_pr_pq_dates(valid_until, required_date)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    for fld in ['status','remarks','approved_by']:
        setattr(pr, fld, f.get(fld,'').strip())
    pr.kind = f.get('kind','Goods')
    if not pr.requester:
        pr.requester = current_user.username
    if not pr.requester_name:
        pr.requester_name = current_user.username
    pr.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
    pr.posting_date  = pd(f.get('posting_date'))
    pr.valid_until    = valid_until
    pr.document_date  = date.today()
    pr.required_date  = required_date
    tots = _save_doc_line_items(PurchaseRequestLineItem, 'purchase_request_id', id, f, 'purchase')
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
    prs = [{'id':p.purchase_request_id,'doc_no':p.doc_no} for p in PurchaseRequest.query.filter_by(status='Approved').order_by(PurchaseRequest.purchase_request_id.desc()).all()]
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
    d['attachments'] = [{'id':a.id,'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='PQ', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/quotations/<int:id>/view')
@login_required
def pq_view(id):
    pq = PurchaseQuotation.query.get_or_404(id)
    items = PurchaseQuotationLineItem.query.filter_by(purchase_quotation_id=id).order_by(PurchaseQuotationLineItem.line_number).all()
    attachments = PurchaseAttachment.query.filter_by(doc_type='PQ', doc_id=id).all()
    return render_template('purchase/pq_view.html', doc=pq, items=items, attachments=attachments, doc_type='PQ')

@pur_bp.route('/purchase/quotations/<int:id>/summary')
@login_required
def pq_summary(id):
    pq = PurchaseQuotation.query.get_or_404(id)
    d = pq.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseQuotationLineItem.query.filter_by(purchase_quotation_id=id).order_by(PurchaseQuotationLineItem.line_number).all()]
    return jsonify(d)

@pur_bp.route('/purchase/quotations/add', methods=['POST'])
@login_required
def pq_add():
    f = request.form
    pr_id = int(f.get('pr_id')) if f.get('pr_id') else None
    pr = PurchaseRequest.query.get(pr_id) if pr_id else None
    if pr_id and (not pr or pr.status != 'Approved'):
        return jsonify({'ok': False, 'error': 'Selected Purchase Request is not Approved'}), 400

    valid_until   = pd(f.get('valid_until'))
    required_date = pd(f.get('required_date'))
    err = _validate_pr_pq_dates(valid_until, required_date)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    pq = PurchaseQuotation(
        doc_no=_next_doc_no('PQ', PurchaseQuotation),
        purchase_request_id=pr_id,
        requester=current_user.username,
        requester_name=current_user.username,
        vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
        vendor_ref_no=f.get('vendor_ref_no','').strip(),
        status=f.get('status','Open'),
        kind=f.get('kind','Goods'),
        posting_date=pd(f.get('posting_date')),
        valid_until=valid_until,
        document_date=date.today(),
        required_date=required_date,
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
        f,
        'purchase'
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
    valid_until   = pd(f.get('valid_until'))
    required_date = pd(f.get('required_date'))
    err = _validate_pr_pq_dates(valid_until, required_date)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    for fld in ['status','remarks','approved_by']:
        setattr(pq, fld, f.get(fld,'').strip())
    pq.kind = f.get('kind','Goods')
    if not pq.requester:
        pq.requester = current_user.username
    if not pq.requester_name:
        pq.requester_name = current_user.username

    pq.purchase_request_id = int(f.get('pr_id')) if f.get('pr_id') else None
    pq.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
    pq.vendor_ref_no = f.get('vendor_ref_no','').strip()
    pq.posting_date  = pd(f.get('posting_date'))
    pq.valid_until    = valid_until
    pq.document_date  = date.today()
    pq.required_date  = required_date

    tots = _save_doc_line_items(
        PurchaseQuotationLineItem,
        'purchase_quotation_id',
        id,
        f,
        'purchase'
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
           for p in PurchaseQuotation.query.filter_by(status='Approved').order_by(PurchaseQuotation.purchase_quotation_id.desc()).all()]
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
    d['attachments'] = [{'id': a.id, 'filename': a.filename} 
                        for a in PurchaseAttachment.query.filter_by(doc_type='PO', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/orders/<int:id>/summary')
@login_required
def po_summary(id):
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
        pq_id = int(f.get('pq_id')) if f.get('pq_id') else None
        pq = PurchaseQuotation.query.get(pq_id) if pq_id else None
        if pq_id and (not pq or pq.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Purchase Quotation is not Approved'}), 400

        vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else (pq.vendor_id if pq else None)

        po = PurchaseOrder(
            doc_no=_next_doc_no('PO', PurchaseOrder),
            purchase_quotation_id=pq_id,
            vendor_id=vendor_id,
            vendor_ref_no=f.get('vendor_ref_no', '').strip(),
            remarks=f.get('remarks', '').strip(),
            status=f.get('status', 'Open'),
            kind=f.get('kind','Goods'),
            posting_date=pd(f.get('posting_date')),
            delivery_date=pd(f.get('delivery_date')),
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(po)
        db.session.flush()

        tots = _save_doc_line_items(PurchaseOrderLineItem, 'purchase_order_id', po.purchase_order_id, f, 'purchase')
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
        pq_id = int(f.get('pq_id')) if f.get('pq_id') else None
        pq = PurchaseQuotation.query.get(pq_id) if pq_id else None

        po.purchase_quotation_id = pq_id
        po.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else (pq.vendor_id if pq else None)
        po.vendor_ref_no = f.get('vendor_ref_no', '').strip()
        po.remarks = f.get('remarks', '').strip()
        po.status = f.get('status', 'Open')
        po.kind = f.get('kind','Goods')
        po.posting_date  = pd(f.get('posting_date'))
        po.delivery_date = pd(f.get('delivery_date'))
        po.document_date = date.today()

        tots = _save_doc_line_items(PurchaseOrderLineItem, 'purchase_order_id', id, f, 'purchase')
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
    pos = [{'id':p.purchase_order_id,'doc_no':p.doc_no} for p in PurchaseOrder.query.filter_by(status='Approved').order_by(PurchaseOrder.purchase_order_id.desc()).all()]
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
    d['attachments'] = [{'id':a.id,'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='GRN', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/grn/<int:id>/view')
@login_required
def grn_view(id):
    doc = GoodsReceiptNote.query.get_or_404(id)
    return render_template('purchase/grn_view.html', doc=doc,
        items=GoodsReceiptLineItem.query.filter_by(goods_receipt_note_id=id).order_by(GoodsReceiptLineItem.line_number).all(),
        attachments=PurchaseAttachment.query.filter_by(doc_type='GRN', doc_id=id).all())

@pur_bp.route('/purchase/grn/<int:id>/summary')
@login_required
def grn_summary(id):
    doc = GoodsReceiptNote.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in GoodsReceiptLineItem.query
                  .filter_by(goods_receipt_note_id=id)
                  .order_by(GoodsReceiptLineItem.line_number).all()]
    return jsonify(d)

@pur_bp.route('/purchase/grn/add', methods=['POST'])
@login_required
def grn_add():
    try:
        f = request.form
        po_id = int(f.get('po_id')) if f.get('po_id') else None
        po = PurchaseOrder.query.get(po_id) if po_id else None
        if po_id and (not po or po.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Purchase Order is not Approved'}), 400

        doc = GoodsReceiptNote(
            doc_no=_next_doc_no('GRN', GoodsReceiptNote),
            purchase_order_id=po_id,
            vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
            contact_person=f.get('contact_person','').strip(),
            vendor_ref_no=f.get('vendor_ref_no','').strip(),
            status=f.get('status','Open'),
            kind=f.get('kind','Goods'),
            posting_date=pd(f.get('posting_date')),
            delivery_date=pd(f.get('delivery_date')),
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(doc); db.session.flush()
        tots = _save_doc_line_items(GoodsReceiptLineItem, 'goods_receipt_note_id', doc.goods_receipt_note_id, f, 'purchase')
        for k,v in tots.items(): setattr(doc, k, v)
        _save_attachments('GRN', doc.goods_receipt_note_id, request.files.getlist('attachments'))
        db.session.commit()
        return jsonify({'ok':True,'id':doc.goods_receipt_note_id,'doc_no':doc.doc_no})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in grn_add: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@pur_bp.route('/purchase/grn/<int:id>/edit', methods=['POST'])
@login_required
def grn_edit(id):
    try:
        doc = GoodsReceiptNote.query.get_or_404(id); f = request.form
        doc.purchase_order_id = int(f.get('po_id')) if f.get('po_id') else None
        doc.vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None
        doc.contact_person=f.get('contact_person','').strip()
        doc.vendor_ref_no=f.get('vendor_ref_no','').strip()
        doc.status=f.get('status','Open')
        doc.kind=f.get('kind','Goods')
        doc.posting_date  = pd(f.get('posting_date'))
        doc.delivery_date = pd(f.get('delivery_date'))
        doc.document_date = date.today()
        tots = _save_doc_line_items(GoodsReceiptLineItem, 'goods_receipt_note_id', id, f, 'purchase')
        for k,v in tots.items(): setattr(doc, k, v)
        _save_attachments('GRN', id, request.files.getlist('attachments'))
        db.session.commit(); return jsonify({'ok':True})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in grn_edit: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

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
    pos = [{'id':p.purchase_order_id,'doc_no':p.doc_no} for p in PurchaseOrder.query.filter_by(status='Approved').order_by(PurchaseOrder.purchase_order_id.desc()).all()]
    grns = [{'id':g.goods_receipt_note_id,'doc_no':g.doc_no,'purchase_order_id':g.purchase_order_id} 
            for g in GoodsReceiptNote.query.filter_by(status='Approved').order_by(GoodsReceiptNote.goods_receipt_note_id.desc()).all()]
    return render_template('purchase/pinv_list.html', vendors=_vendor_list(), pos=pos, grns=grns)

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
    d['attachments'] = [{'id':a.id,'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='PINV', doc_id=id).all()]
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
        po_id = int(f.get('po_id')) if f.get('po_id') else None
        po = PurchaseOrder.query.get(po_id) if po_id else None
        if po_id and (not po or po.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Purchase Order is not Approved'}), 400

        status = f.get('status','Open')
        posting_date = pd(f.get('posting_date'))
        if status != 'Open' and not posting_date:
            posting_date = date.today()

        doc = PurchaseInvoice(
            doc_no=_next_doc_no('PINV', PurchaseInvoice),
            purchase_order_id=po_id,
            goods_receipt_note_id=int(f.get('grn_id')) if f.get('grn_id') else None,
            vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else (po.vendor_id if po else None),
            vendor_ref_no=f.get('vendor_ref_no','').strip(),
            status=status,
            kind=f.get('kind','Goods'),
            payment_method=f.get('payment_method','Credit'),
            bank_account_id=int(f.get('bank_account_id')) if f.get('bank_account_id') else None,
            posting_date=posting_date,
            delivery_date=pd(f.get('delivery_date')),
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(doc)
        db.session.flush()

        tots = _save_doc_line_items(PurchaseInvoiceLineItem, 'purchase_invoice_id', doc.purchase_invoice_id, f, 'purchase')

        for k,v in tots.items():
            setattr(doc, k, v)
        _save_attachments('PINV', doc.purchase_invoice_id, request.files.getlist('attachments'))
        
        db.session.commit()
        
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
        
        status = f.get('status','Open')
        posting_date = pd(f.get('posting_date'))
        if status != 'Open' and not posting_date:
            posting_date = date.today()

        doc.purchase_order_id = int(f.get('po_id')) if f.get('po_id') else None
        doc.goods_receipt_note_id = int(f.get('grn_id')) if f.get('grn_id') else None
        doc.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
        doc.vendor_ref_no = f.get('vendor_ref_no','').strip()
        doc.status = status
        doc.kind = f.get('kind','Goods')
        doc.payment_method = f.get('payment_method','Credit')
        doc.bank_account_id = int(f.get('bank_account_id')) if f.get('bank_account_id') else None
        doc.posting_date  = posting_date
        doc.delivery_date = pd(f.get('delivery_date'))
        doc.document_date = date.today()
        
        tots = _save_doc_line_items(PurchaseInvoiceLineItem, 'purchase_invoice_id', id, f, 'purchase')
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
    pins = [{'id':p.purchase_invoice_id,'doc_no':p.doc_no} for p in PurchaseInvoice.query.filter_by(status='Approved').order_by(PurchaseInvoice.purchase_invoice_id.desc()).all()]
    return render_template('purchase/grr_list.html', vendors=_vendor_list(), pinvs=pins)

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
    d['attachments'] = [{'id':a.id,'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='GRR', doc_id=id).all()]
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

def _validate_grr_qty(f, purchase_invoice_id):
    if not purchase_invoice_id:
        return None
    src_lines = PurchaseInvoiceLineItem.query.filter_by(purchase_invoice_id=purchase_invoice_id).all()
    max_by_code = {}
    for li in src_lines:
        code = (li.item_code or '').strip()
        max_by_code[code] = max_by_code.get(code, Decimal(0)) + Decimal(li.quantity or 0)

    codes = f.getlist('li_item_code[]')
    qtys  = f.getlist('li_qty[]')
    for i in range(len(qtys)):
        code = (codes[i] if i < len(codes) else '').strip()
        try:
            qty = Decimal(qtys[i] or '0')
        except Exception:
            qty = Decimal(0)
        if qty <= 0:
            continue
        if code not in max_by_code:
            return f'Item "{code}" is not part of the selected Purchase Invoice'
        if qty > max_by_code[code]:
            return f'Return quantity for "{code}" ({qty}) exceeds invoiced quantity ({max_by_code[code]})'
    return None


@pur_bp.route('/purchase/returns/add', methods=['POST'])
@login_required
def grr_add():
    try:
        f = request.form
        pi_id = int(f.get('pi_id')) if f.get('pi_id') else None
        pinv = PurchaseInvoice.query.get(pi_id) if pi_id else None
        if pi_id and (not pinv or pinv.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Purchase Invoice is not Approved'}), 400

        err = _validate_grr_qty(f, pi_id)
        if err:
            return jsonify({'ok': False, 'error': err}), 400

        delivery_date = pd(f.get('delivery_date'))
        if delivery_date and delivery_date < date.today():
            return jsonify({'ok': False, 'error': 'Delivery date must be on/after the document date'}), 400

        doc = GoodsReturnRequest(
            doc_no=_next_doc_no('GRR', GoodsReturnRequest),
            purchase_invoice_id=pi_id,
            vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
            contact_person=f.get('contact_person','').strip(),
            vendor_ref_no=f.get('vendor_ref_no','').strip(),
            status=f.get('status','Open'),
            kind=f.get('kind','Goods'),
            posting_date=pd(f.get('posting_date')),
            delivery_date=delivery_date,
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(doc); db.session.flush()
        tots = _save_doc_line_items(GoodsReturnLineItem, 'goods_return_request_id', doc.goods_return_request_id, f, 'purchase')
        for k,v in tots.items(): setattr(doc, k, v)
        _save_attachments('GRR', doc.goods_return_request_id, request.files.getlist('attachments'))
        db.session.commit(); return jsonify({'ok':True,'id':doc.goods_return_request_id,'doc_no':doc.doc_no})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in grr_add: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@pur_bp.route('/purchase/returns/<int:id>/edit', methods=['POST'])
@login_required
def grr_edit(id):
    try:
        doc = GoodsReturnRequest.query.get_or_404(id); f = request.form
        pi_id = int(f.get('pi_id')) if f.get('pi_id') else None

        err = _validate_grr_qty(f, pi_id)
        if err:
            return jsonify({'ok': False, 'error': err}), 400

        delivery_date = pd(f.get('delivery_date'))
        if delivery_date and delivery_date < date.today():
            return jsonify({'ok': False, 'error': 'Delivery date must be on/after the document date'}), 400

        doc.purchase_invoice_id=pi_id
        doc.vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None
        doc.contact_person=f.get('contact_person','').strip()
        doc.vendor_ref_no=f.get('vendor_ref_no','').strip()
        doc.status=f.get('status','Open')
        doc.kind=f.get('kind','Goods')
        doc.posting_date  = pd(f.get('posting_date'))
        doc.delivery_date = delivery_date
        doc.document_date = date.today()
        tots = _save_doc_line_items(GoodsReturnLineItem, 'goods_return_request_id', id, f, 'purchase')
        for k,v in tots.items(): setattr(doc, k, v)
        _save_attachments('GRR', id, request.files.getlist('attachments'))
        db.session.commit(); return jsonify({'ok':True})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in grr_edit: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

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
    grrs = [{'id':p.goods_return_request_id,'doc_no':p.doc_no} for p in GoodsReturnRequest.query.filter_by(status='Approved').order_by(GoodsReturnRequest.goods_return_request_id.desc()).all()]
    return render_template('purchase/pdm_list.html', vendors=_vendor_list(), grrs=grrs)

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
    d['attachments'] = [{'id':a.id,'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='PDM', doc_id=id).all()]
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
    try:
        f = request.form
        grr_id = int(f.get('grr_id')) if f.get('grr_id') else None
        grr = GoodsReturnRequest.query.get(grr_id) if grr_id else None
        if grr_id and (not grr or grr.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Goods Return Request is not Approved'}), 400

        doc = PurchaseDebitMemo(
            doc_no=_next_doc_no('PDM', PurchaseDebitMemo),
            goods_return_request_id=grr_id,
            purchase_invoice_id=(grr.purchase_invoice_id if grr else None),
            vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
            contact_person=f.get('contact_person','').strip(),
            vendor_ref_no=f.get('vendor_ref_no','').strip(),
            status=f.get('status','Open'),
            kind=f.get('kind','Goods'),
            payment_method=f.get('payment_method','Credit'),
            bank_account_id=int(f.get('bank_account_id')) if f.get('bank_account_id') else None,
            posting_date=pd(f.get('posting_date')),
            delivery_date=pd(f.get('delivery_date')),
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(doc); db.session.flush()
        tots = _save_doc_line_items(PurchaseDebitMemoLineItem, 'purchase_debit_memo_id', doc.purchase_debit_memo_id, f, 'purchase')
        for k,v in tots.items(): setattr(doc, k, v)
        _save_attachments('PDM', doc.purchase_debit_memo_id, request.files.getlist('attachments'))
        db.session.commit(); return jsonify({'ok':True,'id':doc.purchase_debit_memo_id,'doc_no':doc.doc_no})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in pdm_add: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@pur_bp.route('/purchase/debit-memos/<int:id>/edit', methods=['POST'])
@login_required
def pdm_edit(id):
    try:
        doc = PurchaseDebitMemo.query.get_or_404(id); f = request.form
        grr_id = int(f.get('grr_id')) if f.get('grr_id') else None
        grr = GoodsReturnRequest.query.get(grr_id) if grr_id else None

        doc.goods_return_request_id = grr_id
        doc.purchase_invoice_id = (grr.purchase_invoice_id if grr else None)
        doc.vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None
        doc.contact_person=f.get('contact_person','').strip()
        doc.vendor_ref_no=f.get('vendor_ref_no','').strip()
        doc.status=f.get('status','Open')
        doc.kind=f.get('kind','Goods')
        doc.payment_method = f.get('payment_method','Credit')
        doc.bank_account_id = int(f.get('bank_account_id')) if f.get('bank_account_id') else None
        doc.posting_date  = pd(f.get('posting_date'))
        doc.delivery_date = pd(f.get('delivery_date'))
        doc.document_date = date.today()
        tots = _save_doc_line_items(PurchaseDebitMemoLineItem, 'purchase_debit_memo_id', id, f, 'purchase')
        for k,v in tots.items(): setattr(doc, k, v)
        _save_attachments('PDM', id, request.files.getlist('attachments'))
        db.session.commit(); return jsonify({'ok':True})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in pdm_edit: {str(e)}")
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@pur_bp.route('/purchase/debit-memos/<int:id>/delete', methods=['POST'])
@login_required
def pdm_delete(id):
    PurchaseDebitMemoLineItem.query.filter_by(purchase_debit_memo_id=id).delete()
    PurchaseAttachment.query.filter_by(doc_type='PDM', doc_id=id).delete()
    db.session.delete(PurchaseDebitMemo.query.get_or_404(id)); db.session.commit()
    return jsonify({'ok':True})