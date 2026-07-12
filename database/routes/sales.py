from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy import text
import os
import random
import re
from werkzeug.utils import secure_filename

from models import (
    db, BuyerMaster,
    Seller, SellerBank,
    SalesRequest, SalesQuotation, SalesOrder, DeliveryNote,
    SalesInvoice, SalesReturnRequest, SalesCreditMemo,
    SalesAttachment,
    SalesRequestLineItem, SalesQuotationLineItem, SalesOrderLineItem,
    DeliveryLineItem, SalesInvoiceLineItem, SalesReturnLineItem, SalesCreditMemoLineItem,
    PurchaseTaxCode, SalesTaxCode,
)

sale_bp = Blueprint('sales', __name__)


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def pd(val):
    """Parse date string, return None if empty/invalid."""
    if not val:
        return None
    try:
        return datetime.strptime(str(val).strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError, AttributeError):
        return None


def _buyer_list():
    """Return list of buyers for dropdowns (sales counterpart of vendors)."""
    return [{'id': b.id, 'name': b.buyer_name_en, 'name_ar': b.buyer_name_ar or ''}
            for b in BuyerMaster.query.filter_by(is_active=True).order_by(BuyerMaster.buyer_name_en).all()]


@sale_bp.route('/sales/sellers/<int:seller_id>/banks')
@login_required
def seller_banks(seller_id):
    """Active bank accounts for a seller, for the invoice/credit-memo bank dropdown."""
    banks = SellerBank.query.filter_by(seller_id=seller_id).order_by(SellerBank.is_primary.desc()).all()
    return jsonify([b.to_dict() for b in banks])


def _validate_sr_sq_dates(valid_until, required_date):
    """valid_until must be >= today (document_date); required_date must be <= valid_until."""
    today = date.today()
    if valid_until and valid_until < today:
        return 'Valid Until must be on/after the document date'
    if required_date and valid_until and required_date > valid_until:
        return 'Required Date must be on/before Valid Until'
    return None


def _ensure_doc_counters_table():
    """Ensure the doc_counters table exists."""
    try:
        table_exists = db.session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='doc_counters'")
        ).fetchone()
        
        if not table_exists:
            db.session.execute(text("""
                CREATE TABLE doc_counters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_type TEXT NOT NULL UNIQUE,
                    counter_value INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.commit()
            
            doc_types = ['SR', 'SQ', 'SO', 'DN', 'SINV', 'SRR', 'SCM']
            for dt in doc_types:
                db.session.execute(
                    text("INSERT OR IGNORE INTO doc_counters (doc_type, counter_value) VALUES (:dt, 0)"),
                    {'dt': dt}
                )
            db.session.commit()
        return True
    except Exception as e:
        print(f"Error creating doc_counters table: {e}")
        return False


def _next_doc_no(doc_type, model):
    """Generate unique doc number per type with atomic counter."""
    year = date.today().year
    prefix = doc_type
    
    _ensure_doc_counters_table()
    
    try:
        db.session.execute(text("BEGIN"))
        
        row = db.session.execute(
            text("SELECT counter_value FROM doc_counters WHERE doc_type = :dt"),
            {'dt': doc_type}
        ).fetchone()
        
        if row:
            counter = row[0] + 1
            db.session.execute(
                text("UPDATE doc_counters SET counter_value = :val, last_updated = CURRENT_TIMESTAMP WHERE doc_type = :dt"),
                {'val': counter, 'dt': doc_type}
            )
        else:
            counter = 1
            db.session.execute(
                text("INSERT INTO doc_counters (doc_type, counter_value) VALUES (:dt, :val)"),
                {'dt': doc_type, 'val': counter}
            )
        
        db.session.commit()
        
        doc_no = f'{prefix}-{year}-{counter:04d}'
        
        existing = model.query.filter_by(doc_no=doc_no).first()
        if existing:
            db.session.execute(text("BEGIN"))
            db.session.execute(
                text("UPDATE doc_counters SET counter_value = counter_value + 1, last_updated = CURRENT_TIMESTAMP WHERE doc_type = :dt"),
                {'dt': doc_type}
            )
            db.session.commit()
            
            row = db.session.execute(
                text("SELECT counter_value FROM doc_counters WHERE doc_type = :dt"),
                {'dt': doc_type}
            ).fetchone()
            
            if row:
                counter = row[0]
                doc_no = f'{prefix}-{year}-{counter:04d}'
                
                if model.query.filter_by(doc_no=doc_no).first():
                    timestamp = datetime.now().strftime("%H%M%S")
                    doc_no = f'{prefix}-{year}-{counter:04d}-{timestamp}'
        
        return doc_no
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in atomic counter: {e}")
        return _fallback_next_doc_no(doc_type, model)


def _fallback_next_doc_no(doc_type, model):
    """Fallback method if atomic counter fails."""
    year = date.today().year
    prefix = doc_type
    
    pk_name = 'id'
    if hasattr(model, 'sales_request_id'):
        pk_name = 'sales_request_id'
    elif hasattr(model, 'sales_quotation_id'):
        pk_name = 'sales_quotation_id'
    elif hasattr(model, 'sales_order_id'):
        pk_name = 'sales_order_id'
    elif hasattr(model, 'delivery_note_id'):
        pk_name = 'delivery_note_id'
    elif hasattr(model, 'sales_invoice_id'):
        pk_name = 'sales_invoice_id'
    elif hasattr(model, 'sales_return_request_id'):
        pk_name = 'sales_return_request_id'
    elif hasattr(model, 'sales_credit_memo_id'):
        pk_name = 'sales_credit_memo_id'
    
    pk_column = getattr(model, pk_name)
    like = f'{prefix}-{year}-%'
    
    last = db.session.query(model).filter(model.doc_no.like(like)).order_by(pk_column.desc()).first()
    
    if last and last.doc_no:
        try:
            parts = last.doc_no.split('-')
            if len(parts) >= 3:
                n = int(parts[-1]) + 1
            else:
                n = 1
        except Exception:
            n = 1
    else:
        n = 1
    
    doc_no = f'{prefix}-{year}-{n:04d}'
    
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
    """Save uploaded attachments under static/uploads/sales/<doc_type>/<doc_id>/."""
    upload_dir = os.path.join('static', 'uploads', 'sales', doc_type, str(doc_id))
    os.makedirs(upload_dir, exist_ok=True)
    for f in files:
        if not f or not f.filename:
            continue
        fname = secure_filename(f.filename)
        fpath = os.path.join(upload_dir, fname)
        f.save(fpath)
        att = SalesAttachment(
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
        
        if tax and hasattr(tax, 'tax_rate') and tax.tax_rate is not None:
            return Decimal(str(tax.tax_rate))
        
        # Fallback: try to parse tax_code as number
        try:
            return Decimal(tax_code)
        except:
            return Decimal('0')
    except Exception:
        return Decimal('0')


def _save_doc_line_items(LIModel, fk_field, fk_value, f, doc_type='purchase'):
    """Generic save for any dedicated line item model with improved decimal precision."""
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
            # Handle empty/None values safely
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


@sale_bp.route('/sales/next-doc-no')
@login_required
def next_doc_no():
    """Preview the next document number for a given sales doc type."""
    t = (request.args.get('type') or 'SR').upper()
    force_new = request.args.get('force_new', 'false').lower() == 'true'
    
    model_map = {
        'SR': SalesRequest, 'SQ': SalesQuotation, 'SO': SalesOrder,
        'DN': DeliveryNote, 'SINV': SalesInvoice,
        'SRR': SalesReturnRequest, 'SCM': SalesCreditMemo,
    }
    model = model_map.get(t, SalesRequest)
    try:
        doc_no = _next_doc_no(t, model)
        return jsonify({'doc_no': doc_no, 'force_new': force_new})
    except Exception as e:
        print(f"Error generating doc number: {e}")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return jsonify({'doc_no': f'{t}-{timestamp}', 'force_new': force_new})


# ══════════════════════════════════════════════════════════════════
# SALES REQUESTS (SR)
# ══════════════════════════════════════════════════════════════════

@sale_bp.route('/sales/requests')
@login_required
def sr_list():
    return render_template('sales/sr_list.html', buyers=_buyer_list())


@sale_bp.route('/sales/requests/data')
@login_required
def sr_data():
    rows = SalesRequest.query.order_by(SalesRequest.sales_request_id.desc()).all()
    return jsonify([r.to_dict() for r in rows])


@sale_bp.route('/sales/requests/<int:id>/json')
@login_required
def sr_json(id):
    sr = SalesRequest.query.get_or_404(id)
    d = sr.to_dict()
    d['items'] = [i.to_dict() for i in SalesRequestLineItem.query.filter_by(sales_request_id=id).order_by(SalesRequestLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename,'filepath':a.filepath} for a in
                        SalesAttachment.query.filter_by(doc_type='SR', doc_id=id).all()]
    return jsonify(d)


@sale_bp.route('/sales/requests/<int:id>/view')
@login_required
def sr_view(id):
    sr = SalesRequest.query.get_or_404(id)
    items = SalesRequestLineItem.query.filter_by(sales_request_id=id).order_by(SalesRequestLineItem.line_number).all()
    attachments = SalesAttachment.query.filter_by(doc_type='SR', doc_id=id).all()
    return render_template('sales/sr_view.html', pr=sr, items=items, attachments=attachments)


@sale_bp.route('/sales/requests/<int:id>/summary')
@login_required
def sr_summary(id):
    """Lightweight PR data for auto-filling Sales Quotation form."""
    sr = SalesRequest.query.get_or_404(id)
    d = sr.to_dict()
    d['items'] = [i.to_dict() for i in SalesRequestLineItem.query.filter_by(sales_request_id=id).order_by(SalesRequestLineItem.line_number).all()]
    return jsonify(d)


@sale_bp.route('/sales/requests/add', methods=['POST'])
@login_required
def sr_add():
    f = request.form
    valid_until   = pd(f.get('valid_until'))
    required_date = pd(f.get('required_date'))
    err = _validate_sr_sq_dates(valid_until, required_date)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    sr = SalesRequest(
        doc_no=_next_doc_no('SR', SalesRequest),
        requester=current_user.username,
        requester_name=current_user.username,
        buyer_id=int(f.get('buyer_id')) if f.get('buyer_id') else None,
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
    db.session.add(sr)
    db.session.flush()
    tots = _save_doc_line_items(SalesRequestLineItem, 'sales_request_id', sr.sales_request_id, f, 'purchase')
    for k,v in tots.items(): 
        setattr(sr, k, float(v) if isinstance(v, Decimal) else v)
    _save_attachments('SR', sr.sales_request_id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True, 'id': sr.sales_request_id, 'doc_no': sr.doc_no})


@sale_bp.route('/sales/requests/<int:id>/edit', methods=['POST'])
@login_required
def sr_edit(id):
    sr = SalesRequest.query.get_or_404(id)
    f = request.form
    valid_until   = pd(f.get('valid_until'))
    required_date = pd(f.get('required_date'))
    err = _validate_sr_sq_dates(valid_until, required_date)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    for fld in ['status','remarks','approved_by']:
        setattr(sr, fld, f.get(fld,'').strip())
    sr.kind = f.get('kind','Goods')
    if not sr.requester:
        sr.requester = current_user.username
    if not sr.requester_name:
        sr.requester_name = current_user.username
    sr.buyer_id = int(f.get('buyer_id')) if f.get('buyer_id') else None
    sr.posting_date  = pd(f.get('posting_date'))
    sr.valid_until    = valid_until
    sr.document_date  = date.today()
    sr.required_date  = required_date
    tots = _save_doc_line_items(SalesRequestLineItem, 'sales_request_id', id, f, 'purchase')
    for k,v in tots.items(): 
        setattr(sr, k, float(v) if isinstance(v, Decimal) else v)
    _save_attachments('SR', id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True})


@sale_bp.route('/sales/requests/<int:id>/delete', methods=['POST'])
@login_required
def sr_delete(id):
    sr = SalesRequest.query.get_or_404(id)
    SalesRequestLineItem.query.filter_by(sales_request_id=id).delete()
    SalesAttachment.query.filter_by(doc_type='SR', doc_id=id).delete()
    db.session.delete(sr)
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════
# SALES QUOTATIONS (SQ)
# ══════════════════════════════════════════════════════════════════

@sale_bp.route('/sales/quotations')
@login_required
def sq_list():
    srs = [{'id':p.sales_request_id,'doc_no':p.doc_no} for p in SalesRequest.query.filter_by(status='Approved').order_by(SalesRequest.sales_request_id.desc()).all()]
    return render_template('sales/sq_list.html', buyers=_buyer_list(), srs=srs)


@sale_bp.route('/sales/quotations/data')
@login_required
def sq_data():
    rows = SalesQuotation.query.order_by(SalesQuotation.sales_quotation_id.desc()).all()
    return jsonify([r.to_dict() for r in rows])


@sale_bp.route('/sales/quotations/<int:id>/json')
@login_required
def sq_json(id):
    sq = SalesQuotation.query.get_or_404(id)
    d = sq.to_dict()
    d['items'] = [i.to_dict() for i in SalesQuotationLineItem.query.filter_by(sales_quotation_id=id).order_by(SalesQuotationLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in SalesAttachment.query.filter_by(doc_type='SQ', doc_id=id).all()]
    return jsonify(d)


@sale_bp.route('/sales/quotations/<int:id>/view')
@login_required
def sq_view(id):
    sq = SalesQuotation.query.get_or_404(id)
    items = SalesQuotationLineItem.query.filter_by(sales_quotation_id=id).order_by(SalesQuotationLineItem.line_number).all()
    attachments = SalesAttachment.query.filter_by(doc_type='SQ', doc_id=id).all()
    return render_template('sales/sq_view.html', doc=sq, items=items, attachments=attachments, doc_type='SQ')


@sale_bp.route('/sales/quotations/<int:id>/summary')
@login_required
def sq_summary(id):
    """Lightweight PQ data for auto-filling Sales Order form."""
    sq = SalesQuotation.query.get_or_404(id)
    d = sq.to_dict()
    d['items'] = [i.to_dict() for i in SalesQuotationLineItem.query.filter_by(sales_quotation_id=id).order_by(SalesQuotationLineItem.line_number).all()]
    return jsonify(d)


@sale_bp.route('/sales/quotations/add', methods=['POST'])
@login_required
def sq_add():
    f = request.form
    sr_id = int(f.get('sr_id')) if f.get('sr_id') else None
    sr = SalesRequest.query.get(sr_id) if sr_id else None
    if sr_id and (not sr or sr.status != 'Approved'):
        return jsonify({'ok': False, 'error': 'Selected Sales Request is not Approved'}), 400

    valid_until   = pd(f.get('valid_until'))
    required_date = pd(f.get('required_date'))
    err = _validate_sr_sq_dates(valid_until, required_date)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    sq = SalesQuotation(
        doc_no=_next_doc_no('SQ', SalesQuotation),
        sales_request_id=sr_id,
        requester=current_user.username,
        requester_name=current_user.username,
        buyer_id=int(f.get('buyer_id')) if f.get('buyer_id') else None,
        buyer_ref_no=f.get('buyer_ref_no','').strip(),
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
    db.session.add(sq)
    db.session.flush()

    tots = _save_doc_line_items(SalesQuotationLineItem, 'sales_quotation_id', sq.sales_quotation_id, f, 'sales')
    for k, v in tots.items():
        setattr(sq, k, float(v) if isinstance(v, Decimal) else v)

    _save_attachments('SQ', sq.sales_quotation_id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True, 'id': sq.sales_quotation_id, 'doc_no': sq.doc_no})


@sale_bp.route('/sales/quotations/<int:id>/edit', methods=['POST'])
@login_required
def sq_edit(id):
    sq = SalesQuotation.query.get_or_404(id)
    f = request.form
    valid_until   = pd(f.get('valid_until'))
    required_date = pd(f.get('required_date'))
    err = _validate_sr_sq_dates(valid_until, required_date)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    for fld in ['status','remarks','approved_by']:
        setattr(sq, fld, f.get(fld,'').strip())
    sq.kind = f.get('kind','Goods')
    if not sq.requester:
        sq.requester = current_user.username
    if not sq.requester_name:
        sq.requester_name = current_user.username

    sq.sales_request_id = int(f.get('sr_id')) if f.get('sr_id') else None
    sq.buyer_id = int(f.get('buyer_id')) if f.get('buyer_id') else None
    sq.buyer_ref_no = f.get('buyer_ref_no','').strip()
    sq.posting_date  = pd(f.get('posting_date'))
    sq.valid_until    = valid_until
    sq.document_date  = date.today()
    sq.required_date  = required_date

    tots = _save_doc_line_items(SalesQuotationLineItem, 'sales_quotation_id', id, f, 'sales')
    for k, v in tots.items():
        setattr(sq, k, float(v) if isinstance(v, Decimal) else v)

    _save_attachments('SQ', id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True})


@sale_bp.route('/sales/quotations/<int:id>/delete', methods=['POST'])
@login_required
def sq_delete(id):
    SalesQuotationLineItem.query.filter_by(sales_quotation_id=id).delete()
    SalesAttachment.query.filter_by(doc_type='SQ', doc_id=id).delete()
    sq = SalesQuotation.query.get_or_404(id)
    db.session.delete(sq)
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════
# SALES ORDERS (SO)
# ══════════════════════════════════════════════════════════════════

@sale_bp.route('/sales/orders')
@login_required
def so_list():
    sqs = [{'id': p.sales_quotation_id, 'doc_no': p.doc_no}
           for p in SalesQuotation.query.filter_by(status='Approved').order_by(SalesQuotation.sales_quotation_id.desc()).all()]
    return render_template('sales/so_list.html', buyers=_buyer_list(), sqs=sqs)


@sale_bp.route('/sales/orders/data')
@login_required
def so_data():
    rows = SalesOrder.query.order_by(SalesOrder.sales_order_id.desc()).all()
    return jsonify([r.to_dict() for r in rows])


@sale_bp.route('/sales/orders/<int:id>/json')
@login_required
def so_json(id):
    so = SalesOrder.query.get_or_404(id)
    d = so.to_dict()
    d['items'] = [i.to_dict() for i in SalesOrderLineItem.query
                  .filter_by(sales_order_id=id)
                  .order_by(SalesOrderLineItem.line_number).all()]
    d['attachments'] = [{'filename': a.filename} 
                        for a in SalesAttachment.query.filter_by(doc_type='SO', doc_id=id).all()]
    return jsonify(d)


@sale_bp.route('/sales/orders/<int:id>/summary')
@login_required
def so_summary(id):
    """Lightweight PO data for auto-filling Sales Invoice form."""
    so = SalesOrder.query.get_or_404(id)
    d = so.to_dict()
    d['items'] = [i.to_dict() for i in SalesOrderLineItem.query
                  .filter_by(sales_order_id=id)
                  .order_by(SalesOrderLineItem.line_number).all()]
    return jsonify(d)


@sale_bp.route('/sales/orders/<int:id>/view')
@login_required
def so_view(id):
    so = SalesOrder.query.get_or_404(id)
    items = SalesOrderLineItem.query.filter_by(sales_order_id=id).order_by(SalesOrderLineItem.line_number).all()
    attachments = SalesAttachment.query.filter_by(doc_type='SO', doc_id=id).all()
    return render_template('sales/so_view.html', doc=so, items=items, attachments=attachments, doc_type='SO')


@sale_bp.route('/sales/orders/add', methods=['POST'])
@login_required
def so_add():
    try:
        f = request.form
        sq_id = int(f.get('sq_id')) if f.get('sq_id') else None
        sq = SalesQuotation.query.get(sq_id) if sq_id else None
        if sq_id and (not sq or sq.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Sales Quotation is not Approved'}), 400

        buyer_id = int(f.get('buyer_id')) if f.get('buyer_id') else (sq.buyer_id if sq else None)

        doc_no = _next_doc_no('SO', SalesOrder)
        print(f"Generated doc_no: {doc_no}")

        so = SalesOrder(
            doc_no=doc_no,
            sales_quotation_id=sq_id,
            buyer_id=buyer_id,
            buyer_ref_no=f.get('buyer_ref_no', '').strip(),
            remarks=f.get('remarks', '').strip(),
            status=f.get('status', 'Open'),
            kind=f.get('kind','Goods'),
            posting_date=pd(f.get('posting_date')),
            delivery_date=pd(f.get('delivery_date')),
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(so)
        db.session.flush()

        tots = _save_doc_line_items(SalesOrderLineItem, 'sales_order_id', so.sales_order_id, f, 'sales')
        for k, v in tots.items():
            setattr(so, k, float(v) if isinstance(v, Decimal) else v)

        _save_attachments('SO', so.sales_order_id, request.files.getlist('attachments'))
        
        db.session.commit()
        return jsonify({'ok': True, 'id': so.sales_order_id, 'doc_no': so.doc_no})
    
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"ERROR in so_add: {error_msg}")
        import traceback
        traceback.print_exc()
        
        if 'UNIQUE constraint failed' in error_msg or 'IntegrityError' in error_msg:
            try:
                timestamp = datetime.now().strftime("%H%M%S")
                fallback_doc_no = f'SO-{date.today().year}-{timestamp}'
                
                existing = SalesOrder.query.filter_by(doc_no=fallback_doc_no).first()
                if existing:
                    fallback_doc_no = f'SO-{date.today().year}-{timestamp}-{random.randint(100,999)}'
                
                so.doc_no = fallback_doc_no
                db.session.commit()
                return jsonify({'ok': True, 'id': so.sales_order_id, 'doc_no': so.doc_no, 'retry': True})
                
            except Exception as retry_error:
                db.session.rollback()
                print(f"Retry failed: {retry_error}")
                return jsonify({'ok': False, 'error': 'Duplicate document number. Please try again.'}), 500
        
        return jsonify({'ok': False, 'error': error_msg}), 500


@sale_bp.route('/sales/orders/<int:id>/edit', methods=['POST'])
@login_required
def so_edit(id):
    try:
        so = SalesOrder.query.get_or_404(id)
        f = request.form
        sq_id = int(f.get('sq_id')) if f.get('sq_id') else None
        sq = SalesQuotation.query.get(sq_id) if sq_id else None

        so.sales_quotation_id = sq_id
        so.buyer_id = int(f.get('buyer_id')) if f.get('buyer_id') else (sq.buyer_id if sq else None)
        so.buyer_ref_no = f.get('buyer_ref_no', '').strip()
        so.remarks = f.get('remarks', '').strip()
        so.status = f.get('status', 'Open')
        so.kind = f.get('kind','Goods')
        so.posting_date  = pd(f.get('posting_date'))
        so.delivery_date = pd(f.get('delivery_date'))
        so.document_date = date.today()

        tots = _save_doc_line_items(SalesOrderLineItem, 'sales_order_id', id, f, 'sales')
        for k, v in tots.items():
            setattr(so, k, float(v) if isinstance(v, Decimal) else v)

        _save_attachments('SO', id, request.files.getlist('attachments'))
        
        db.session.commit()
        return jsonify({'ok': True})
    
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in so_edit: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@sale_bp.route('/sales/orders/<int:id>/delete', methods=['POST'])
@login_required
def so_delete(id):
    try:
        SalesOrderLineItem.query.filter_by(sales_order_id=id).delete()
        SalesAttachment.query.filter_by(doc_type='SO', doc_id=id).delete()
        so = SalesOrder.query.get_or_404(id)
        db.session.delete(so)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# DELIVERY NOTES (DN)
# ══════════════════════════════════════════════════════════════════

@sale_bp.route('/sales/delivery')
@login_required
def dn_list():
    sos = [{'id':p.sales_order_id,'doc_no':p.doc_no} for p in SalesOrder.query.filter_by(status='Approved').order_by(SalesOrder.sales_order_id.desc()).all()]
    return render_template('sales/dn_list.html', buyers=_buyer_list(), sos=sos)


@sale_bp.route('/sales/delivery/data')
@login_required
def dn_data():
    return jsonify([r.to_dict() for r in DeliveryNote.query.order_by(DeliveryNote.delivery_note_id.desc()).all()])


@sale_bp.route('/sales/delivery/<int:id>/json')
@login_required
def dn_json(id):
    doc = DeliveryNote.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in DeliveryLineItem.query.filter_by(delivery_note_id=id).order_by(DeliveryLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in SalesAttachment.query.filter_by(doc_type='DN', doc_id=id).all()]
    return jsonify(d)


@sale_bp.route('/sales/delivery/<int:id>/view')
@login_required
def dn_view(id):
    doc = DeliveryNote.query.get_or_404(id)
    return render_template('sales/dn_view.html', doc=doc,
        items=DeliveryLineItem.query.filter_by(delivery_note_id=id).order_by(DeliveryLineItem.line_number).all(),
        attachments=SalesAttachment.query.filter_by(doc_type='DN', doc_id=id).all())


@sale_bp.route('/sales/delivery/<int:id>/summary')
@login_required
def dn_summary(id):
    """Lightweight GRN data for auto-filling Sales Invoice form."""
    doc = DeliveryNote.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in DeliveryLineItem.query
                  .filter_by(delivery_note_id=id)
                  .order_by(DeliveryLineItem.line_number).all()]
    return jsonify(d)


@sale_bp.route('/sales/delivery/add', methods=['POST'])
@login_required
def dn_add():
    try:
        f = request.form
        so_id = int(f.get('so_id')) if f.get('so_id') else None
        so = SalesOrder.query.get(so_id) if so_id else None
        if so_id and (not so or so.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Sales Order is not Approved'}), 400

        doc = DeliveryNote(
            doc_no=_next_doc_no('DN', DeliveryNote),
            sales_order_id=so_id,
            buyer_id=int(f.get('buyer_id')) if f.get('buyer_id') else None,
            contact_person=f.get('contact_person','').strip(),
            buyer_ref_no=f.get('buyer_ref_no','').strip(),
            status=f.get('status','Open'),
            kind=f.get('kind','Goods'),
            posting_date=pd(f.get('posting_date')),
            delivery_date=pd(f.get('delivery_date')),
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(doc)
        db.session.flush()
        tots = _save_doc_line_items(DeliveryLineItem, 'delivery_note_id', doc.delivery_note_id, f, 'sales')
        for k,v in tots.items(): 
            setattr(doc, k, float(v) if isinstance(v, Decimal) else v)
        _save_attachments('DN', doc.delivery_note_id, request.files.getlist('attachments'))
        db.session.commit()
        return jsonify({'ok':True,'id':doc.delivery_note_id,'doc_no':doc.doc_no})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in dn_add: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@sale_bp.route('/sales/delivery/<int:id>/edit', methods=['POST'])
@login_required
def dn_edit(id):
    try:
        doc = DeliveryNote.query.get_or_404(id)
        f = request.form
        doc.sales_order_id = int(f.get('so_id')) if f.get('so_id') else None
        doc.buyer_id=int(f.get('buyer_id')) if f.get('buyer_id') else None
        doc.contact_person=f.get('contact_person','').strip()
        doc.buyer_ref_no=f.get('buyer_ref_no','').strip()
        doc.status=f.get('status','Open')
        doc.kind=f.get('kind','Goods')
        doc.posting_date  = pd(f.get('posting_date'))
        doc.delivery_date = pd(f.get('delivery_date'))
        doc.document_date = date.today()
        tots = _save_doc_line_items(DeliveryLineItem, 'delivery_note_id', id, f, 'sales')
        for k,v in tots.items(): 
            setattr(doc, k, float(v) if isinstance(v, Decimal) else v)
        _save_attachments('DN', id, request.files.getlist('attachments'))
        db.session.commit()
        return jsonify({'ok':True})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in dn_edit: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@sale_bp.route('/sales/delivery/<int:id>/delete', methods=['POST'])
@login_required
def dn_delete(id):
    DeliveryLineItem.query.filter_by(delivery_note_id=id).delete()
    SalesAttachment.query.filter_by(doc_type='DN', doc_id=id).delete()
    db.session.delete(DeliveryNote.query.get_or_404(id))
    db.session.commit()
    return jsonify({'ok':True})


# ══════════════════════════════════════════════════════════════════
# SALES INVOICES (SINV)
# ══════════════════════════════════════════════════════════════════

@sale_bp.route('/sales/invoices')
@login_required
def sinv_list():
    sos = [{'id':p.sales_order_id,'doc_no':p.doc_no} for p in SalesOrder.query.filter_by(status='Approved').order_by(SalesOrder.sales_order_id.desc()).all()]
    dns = [{'id':g.delivery_note_id,'doc_no':g.doc_no,'sales_order_id':g.sales_order_id} for g in DeliveryNote.query.order_by(DeliveryNote.delivery_note_id.desc()).all()]
    return render_template('sales/sinv_list.html', buyers=_buyer_list(), sos=sos, dns=dns, sellers=Seller.query.order_by(Seller.name).all())


@sale_bp.route('/sales/invoices/data')
@login_required
def sinv_data():
    return jsonify([r.to_dict() for r in SalesInvoice.query.order_by(SalesInvoice.sales_invoice_id.desc()).all()])


@sale_bp.route('/sales/invoices/reference-list')
@login_required
def sinv_reference_list():
    """Previously-saved invoices for the reference-invoice picker."""
    category = (request.args.get('category') or '').strip().lower()
    exclude  = request.args.get('exclude', type=int)
    q = SalesInvoice.query
    if category in ('standard', 'simplified'):
        q = q.filter(SalesInvoice.invoice_category == category)
    if exclude:
        q = q.filter(SalesInvoice.sales_invoice_id != exclude)
    rows = q.order_by(SalesInvoice.sales_invoice_id.desc()).all()
    return jsonify([{
        'id': r.sales_invoice_id,
        'doc_no': r.doc_no or '',
        'buyer_name': r.buyer.buyer_name_en if r.buyer else '',
        'invoice_category': r.invoice_category or '',
        'transaction_type': r.transaction_type or '',
        'document_date': str(r.document_date) if r.document_date else '',
        'total_incl_vat': float(r.total_incl_vat or 0),
    } for r in rows])


@sale_bp.route('/sales/invoices/<int:id>/json')
@login_required
def sinv_json(id):
    doc = SalesInvoice.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in SalesInvoiceLineItem.query.filter_by(sales_invoice_id=id).order_by(SalesInvoiceLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in SalesAttachment.query.filter_by(doc_type='SINV', doc_id=id).all()]
    return jsonify(d)


@sale_bp.route('/sales/invoices/<int:id>/view')
@login_required
def sinv_view(id):
    doc = SalesInvoice.query.get_or_404(id)
    return render_template('sales/sinv_view.html', doc=doc,
        items=SalesInvoiceLineItem.query.filter_by(sales_invoice_id=id).order_by(SalesInvoiceLineItem.line_number).all(),
        attachments=SalesAttachment.query.filter_by(doc_type='SINV', doc_id=id).all())


@sale_bp.route('/sales/invoices/<int:id>/summary')
@login_required
def sinv_summary(id):
    doc = SalesInvoice.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in SalesInvoiceLineItem.query.filter_by(sales_invoice_id=id).order_by(SalesInvoiceLineItem.line_number).all()]
    return jsonify(d)


@sale_bp.route('/sales/invoices/add', methods=['POST'])
@login_required
def sinv_add():
    try:
        f = request.form
        so_id = int(f.get('so_id')) if f.get('so_id') else None
        so = SalesOrder.query.get(so_id) if so_id else None
        if so_id and (not so or so.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Sales Order is not Approved'}), 400

        status = f.get('status','Open')
        posting_date = pd(f.get('posting_date'))
        if status != 'Open' and not posting_date:
            posting_date = date.today()

        doc = SalesInvoice(
            doc_no=_next_doc_no('SINV', SalesInvoice),
            sales_order_id=so_id,
            delivery_note_id=int(f.get('dn_id')) if f.get('dn_id') else None,
            buyer_id=int(f.get('buyer_id')) if f.get('buyer_id') else (so.buyer_id if so else None),
            buyer_ref_no=f.get('buyer_ref_no','').strip(),
            transaction_type=f.get('transaction_type','').strip() or None,
            invoice_category=f.get('invoice_category','').strip() or None,
            reference_invoices=f.get('reference_invoices','').strip() or None,
            status=status,
            kind=f.get('kind','Goods'),
            payment_method=f.get('payment_method','Credit'),
            seller_id=int(f.get('seller_id')) if f.get('seller_id') else None,
            bank_account_id=int(f.get('bank_account_id')) if f.get('bank_account_id') else None,
            posting_date=posting_date,
            delivery_date=pd(f.get('delivery_date')),
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(doc)
        db.session.flush()

        tots = _save_doc_line_items(SalesInvoiceLineItem, 'sales_invoice_id', doc.sales_invoice_id, f, 'sales')
        for k,v in tots.items():
            setattr(doc, k, float(v) if isinstance(v, Decimal) else v)
        _save_attachments('SINV', doc.sales_invoice_id, request.files.getlist('attachments'))
        
        db.session.commit()
        return jsonify({'ok':True,'id':doc.sales_invoice_id,'doc_no':doc.doc_no})
    
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in sinv_add: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@sale_bp.route('/sales/invoices/<int:id>/edit', methods=['POST'])
@login_required
def sinv_edit(id):
    try:
        doc = SalesInvoice.query.get_or_404(id)
        f = request.form
        
        status = f.get('status','Open')
        posting_date = pd(f.get('posting_date'))
        if status != 'Open' and not posting_date:
            posting_date = date.today()

        doc.sales_order_id = int(f.get('so_id')) if f.get('so_id') else None
        doc.delivery_note_id = int(f.get('dn_id')) if f.get('dn_id') else None
        doc.buyer_id = int(f.get('buyer_id')) if f.get('buyer_id') else None
        doc.buyer_ref_no = f.get('buyer_ref_no','').strip()
        doc.transaction_type = f.get('transaction_type','').strip() or None
        doc.invoice_category = f.get('invoice_category','').strip() or None
        doc.reference_invoices = f.get('reference_invoices','').strip() or None
        doc.status = status
        doc.kind = f.get('kind','Goods')
        doc.payment_method = f.get('payment_method','Credit')
        doc.seller_id = int(f.get('seller_id')) if f.get('seller_id') else None
        doc.bank_account_id = int(f.get('bank_account_id')) if f.get('bank_account_id') else None
        doc.posting_date  = posting_date
        doc.delivery_date = pd(f.get('delivery_date'))
        doc.document_date = date.today()
        
        tots = _save_doc_line_items(SalesInvoiceLineItem, 'sales_invoice_id', id, f, 'sales')
        for k,v in tots.items(): 
            setattr(doc, k, float(v) if isinstance(v, Decimal) else v)
        _save_attachments('SINV', id, request.files.getlist('attachments'))
        
        db.session.commit()
        return jsonify({'ok':True})
    
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in sinv_edit: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@sale_bp.route('/sales/invoices/<int:id>/delete', methods=['POST'])
@login_required
def sinv_delete(id):
    try:
        SalesInvoiceLineItem.query.filter_by(sales_invoice_id=id).delete()
        SalesAttachment.query.filter_by(doc_type='SINV', doc_id=id).delete()
        db.session.delete(SalesInvoice.query.get_or_404(id))
        db.session.commit()
        return jsonify({'ok':True})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in sinv_delete: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# SALES RETURN REQUESTS (SRR)
# ══════════════════════════════════════════════════════════════════

@sale_bp.route('/sales/returns')
@login_required
def srr_list():
    sins = [{'id':p.sales_invoice_id,'doc_no':p.doc_no} for p in SalesInvoice.query.filter_by(status='Approved').order_by(SalesInvoice.sales_invoice_id.desc()).all()]
    return render_template('sales/srr_list.html', buyers=_buyer_list(), sinvs=sins)


@sale_bp.route('/sales/returns/data')
@login_required
def srr_data():
    return jsonify([r.to_dict() for r in SalesReturnRequest.query.order_by(SalesReturnRequest.sales_return_request_id.desc()).all()])


@sale_bp.route('/sales/returns/<int:id>/json')
@login_required
def srr_json(id):
    doc = SalesReturnRequest.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in SalesReturnLineItem.query.filter_by(sales_return_request_id=id).order_by(SalesReturnLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in SalesAttachment.query.filter_by(doc_type='SRR', doc_id=id).all()]
    return jsonify(d)


@sale_bp.route('/sales/returns/<int:id>/view')
@login_required
def srr_view(id):
    doc = SalesReturnRequest.query.get_or_404(id)
    return render_template('sales/srr_view.html', doc=doc,
        items=SalesReturnLineItem.query.filter_by(sales_return_request_id=id).order_by(SalesReturnLineItem.line_number).all(),
        attachments=SalesAttachment.query.filter_by(doc_type='SRR', doc_id=id).all())


@sale_bp.route('/sales/returns/<int:id>/summary')
@login_required
def srr_summary(id):
    doc = SalesReturnRequest.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in SalesReturnLineItem.query.filter_by(sales_return_request_id=id).order_by(SalesReturnLineItem.line_number).all()]
    return jsonify(d)


def _validate_srr_qty(f, sales_invoice_id):
    """SRR line quantities must not exceed the original Sales Invoice line quantity for that item."""
    if not sales_invoice_id:
        return None
    src_lines = SalesInvoiceLineItem.query.filter_by(sales_invoice_id=sales_invoice_id).all()
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
            return f'Item "{code}" is not part of the selected Sales Invoice'
        if qty > max_by_code[code]:
            return f'Return quantity for "{code}" ({qty}) exceeds invoiced quantity ({max_by_code[code]})'
    return None


@sale_bp.route('/sales/returns/add', methods=['POST'])
@login_required
def srr_add():
    try:
        f = request.form
        si_id = int(f.get('si_id')) if f.get('si_id') else None
        sinv = SalesInvoice.query.get(si_id) if si_id else None
        if si_id and (not sinv or sinv.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Sales Invoice is not Approved'}), 400

        err = _validate_srr_qty(f, si_id)
        if err:
            return jsonify({'ok': False, 'error': err}), 400

        delivery_date = pd(f.get('delivery_date'))
        if delivery_date and delivery_date < date.today():
            return jsonify({'ok': False, 'error': 'Delivery date must be on/after the document date'}), 400

        doc = SalesReturnRequest(
            doc_no=_next_doc_no('SRR', SalesReturnRequest),
            sales_invoice_id=si_id,
            buyer_id=int(f.get('buyer_id')) if f.get('buyer_id') else None,
            contact_person=f.get('contact_person','').strip(),
            buyer_ref_no=f.get('buyer_ref_no','').strip(),
            status=f.get('status','Open'),
            kind=f.get('kind','Goods'),
            posting_date=pd(f.get('posting_date')),
            delivery_date=delivery_date,
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(doc)
        db.session.flush()
        tots = _save_doc_line_items(SalesReturnLineItem, 'sales_return_request_id', doc.sales_return_request_id, f, 'sales')
        for k,v in tots.items(): 
            setattr(doc, k, float(v) if isinstance(v, Decimal) else v)
        _save_attachments('SRR', doc.sales_return_request_id, request.files.getlist('attachments'))
        db.session.commit()
        return jsonify({'ok':True,'id':doc.sales_return_request_id,'doc_no':doc.doc_no})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in srr_add: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@sale_bp.route('/sales/returns/<int:id>/edit', methods=['POST'])
@login_required
def srr_edit(id):
    try:
        doc = SalesReturnRequest.query.get_or_404(id)
        f = request.form
        si_id = int(f.get('si_id')) if f.get('si_id') else None

        err = _validate_srr_qty(f, si_id)
        if err:
            return jsonify({'ok': False, 'error': err}), 400

        delivery_date = pd(f.get('delivery_date'))
        if delivery_date and delivery_date < date.today():
            return jsonify({'ok': False, 'error': 'Delivery date must be on/after the document date'}), 400

        doc.sales_invoice_id=si_id
        doc.buyer_id=int(f.get('buyer_id')) if f.get('buyer_id') else None
        doc.contact_person=f.get('contact_person','').strip()
        doc.buyer_ref_no=f.get('buyer_ref_no','').strip()
        doc.status=f.get('status','Open')
        doc.kind=f.get('kind','Goods')
        doc.posting_date  = pd(f.get('posting_date'))
        doc.delivery_date = delivery_date
        doc.document_date = date.today()
        tots = _save_doc_line_items(SalesReturnLineItem, 'sales_return_request_id', id, f, 'sales')
        for k,v in tots.items(): 
            setattr(doc, k, float(v) if isinstance(v, Decimal) else v)
        _save_attachments('SRR', id, request.files.getlist('attachments'))
        db.session.commit()
        return jsonify({'ok':True})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in srr_edit: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@sale_bp.route('/sales/returns/<int:id>/delete', methods=['POST'])
@login_required
def srr_delete(id):
    SalesReturnLineItem.query.filter_by(sales_return_request_id=id).delete()
    SalesAttachment.query.filter_by(doc_type='SRR', doc_id=id).delete()
    db.session.delete(SalesReturnRequest.query.get_or_404(id))
    db.session.commit()
    return jsonify({'ok':True})


# ══════════════════════════════════════════════════════════════════
# SALES CREDIT MEMOS (SCM)
# ══════════════════════════════════════════════════════════════════

@sale_bp.route('/sales/credit-memos')
@login_required
def scm_list():
    srrs = [{'id':p.sales_return_request_id,'doc_no':p.doc_no} for p in SalesReturnRequest.query.filter_by(status='Approved').order_by(SalesReturnRequest.sales_return_request_id.desc()).all()]
    return render_template('sales/scm_list.html', buyers=_buyer_list(), srrs=srrs, sellers=Seller.query.order_by(Seller.name).all())


@sale_bp.route('/sales/credit-memos/data')
@login_required
def scm_data():
    return jsonify([r.to_dict() for r in SalesCreditMemo.query.order_by(SalesCreditMemo.sales_credit_memo_id.desc()).all()])


@sale_bp.route('/sales/credit-memos/<int:id>/json')
@login_required
def scm_json(id):
    doc = SalesCreditMemo.query.get_or_404(id)
    d = doc.to_dict()
    d['items'] = [i.to_dict() for i in SalesCreditMemoLineItem.query.filter_by(sales_credit_memo_id=id).order_by(SalesCreditMemoLineItem.line_number).all()]
    d['attachments'] = [{'filename':a.filename} for a in SalesAttachment.query.filter_by(doc_type='SCM', doc_id=id).all()]
    return jsonify(d)


@sale_bp.route('/sales/credit-memos/<int:id>/view')
@login_required
def scm_view(id):
    doc = SalesCreditMemo.query.get_or_404(id)
    return render_template('sales/scm_view.html', doc=doc,
        items=SalesCreditMemoLineItem.query.filter_by(sales_credit_memo_id=id).order_by(SalesCreditMemoLineItem.line_number).all(),
        attachments=SalesAttachment.query.filter_by(doc_type='SCM', doc_id=id).all())


@sale_bp.route('/sales/credit-memos/add', methods=['POST'])
@login_required
def scm_add():
    try:
        f = request.form
        srr_id = int(f.get('srr_id')) if f.get('srr_id') else None
        srr = SalesReturnRequest.query.get(srr_id) if srr_id else None
        if srr_id and (not srr or srr.status != 'Approved'):
            return jsonify({'ok': False, 'error': 'Selected Sales Return Request is not Approved'}), 400

        doc = SalesCreditMemo(
            doc_no=_next_doc_no('SCM', SalesCreditMemo),
            sales_return_request_id=srr_id,
            sales_invoice_id=(srr.sales_invoice_id if srr else None),
            buyer_id=int(f.get('buyer_id')) if f.get('buyer_id') else None,
            contact_person=f.get('contact_person','').strip(),
            buyer_ref_no=f.get('buyer_ref_no','').strip(),
            status=f.get('status','Open'),
            kind=f.get('kind','Goods'),
            payment_method=f.get('payment_method','Credit'),
            seller_id=int(f.get('seller_id')) if f.get('seller_id') else None,
            bank_account_id=int(f.get('bank_account_id')) if f.get('bank_account_id') else None,
            posting_date=pd(f.get('posting_date')),
            delivery_date=pd(f.get('delivery_date')),
            document_date=date.today(),
            created_by=current_user.id,
        )
        db.session.add(doc)
        db.session.flush()
        tots = _save_doc_line_items(SalesCreditMemoLineItem, 'sales_credit_memo_id', doc.sales_credit_memo_id, f, 'sales')
        for k,v in tots.items(): 
            setattr(doc, k, float(v) if isinstance(v, Decimal) else v)
        _save_attachments('SCM', doc.sales_credit_memo_id, request.files.getlist('attachments'))
        db.session.commit()
        return jsonify({'ok':True,'id':doc.sales_credit_memo_id,'doc_no':doc.doc_no})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in scm_add: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@sale_bp.route('/sales/credit-memos/<int:id>/edit', methods=['POST'])
@login_required
def scm_edit(id):
    try:
        doc = SalesCreditMemo.query.get_or_404(id)
        f = request.form
        srr_id = int(f.get('srr_id')) if f.get('srr_id') else None
        srr = SalesReturnRequest.query.get(srr_id) if srr_id else None

        doc.sales_return_request_id = srr_id
        doc.sales_invoice_id = (srr.sales_invoice_id if srr else None)
        doc.buyer_id=int(f.get('buyer_id')) if f.get('buyer_id') else None
        doc.contact_person=f.get('contact_person','').strip()
        doc.buyer_ref_no=f.get('buyer_ref_no','').strip()
        doc.status=f.get('status','Open')
        doc.kind=f.get('kind','Goods')
        doc.payment_method = f.get('payment_method','Credit')
        doc.seller_id = int(f.get('seller_id')) if f.get('seller_id') else None
        doc.bank_account_id = int(f.get('bank_account_id')) if f.get('bank_account_id') else None
        doc.posting_date  = pd(f.get('posting_date'))
        doc.delivery_date = pd(f.get('delivery_date'))
        doc.document_date = date.today()
        tots = _save_doc_line_items(SalesCreditMemoLineItem, 'sales_credit_memo_id', id, f, 'sales')
        for k,v in tots.items(): 
            setattr(doc, k, float(v) if isinstance(v, Decimal) else v)
        _save_attachments('SCM', id, request.files.getlist('attachments'))
        db.session.commit()
        return jsonify({'ok':True})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR in scm_edit: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@sale_bp.route('/sales/credit-memos/<int:id>/delete', methods=['POST'])
@login_required
def scm_delete(id):
    SalesCreditMemoLineItem.query.filter_by(sales_credit_memo_id=id).delete()
    SalesAttachment.query.filter_by(doc_type='SCM', doc_id=id).delete()
    db.session.delete(SalesCreditMemo.query.get_or_404(id))
    db.session.commit()
    return jsonify({'ok':True})


# ══════════════════════════════════════════════════════════════════
# PURCHASE TAX CODES
# ══════════════════════════════════════════════════════════════════

@sale_bp.route('/purchase-tax-codes')
@login_required
def purchase_tax_list():
    return render_template('tax_codes/tax_list.html', 
                         kind='purchase',
                         title_en='Purchase Tax Codes',
                         title_ar='رموز الضرائب للمشتريات',
                         doc_type='purchase')


@sale_bp.route('/purchase-tax-codes/data')
@login_required
def purchase_tax_data():
    rows = PurchaseTaxCode.query.order_by(PurchaseTaxCode.id.desc()).all()
    return jsonify([{
        'id': r.id,
        'account_code': r.account_code,
        'tax_code': r.tax_code,
        'tax_rate': float(r.tax_rate) if r.tax_rate else 0,
        'section': r.section,
        'status': r.status
    } for r in rows])


@sale_bp.route('/purchase-tax-codes/add', methods=['POST'])
@login_required
def purchase_tax_add():
    f = request.form
    tax_code = f.get('tax_code', '').strip()
    account_code = f.get('account_code', '').strip()
    section = f.get('section', '').strip()
    
    # Validate: tax_code must be numeric only
    if not tax_code or not re.match(r'^[\d.]+$', tax_code):
        return jsonify({'ok': False, 'error': 'Tax Code must contain only numbers'}), 400
    
    # Validate tax rate
    try:
        tax_rate = Decimal(f.get('tax_rate', '0'))
    except:
        return jsonify({'ok': False, 'error': 'Invalid tax rate'}), 400
    
    if not account_code or not section:
        return jsonify({'ok': False, 'error': 'Account Code and Section are required'}), 400
    
    # Check for duplicate
    existing = PurchaseTaxCode.query.filter_by(tax_code=tax_code).first()
    if existing:
        return jsonify({'ok': False, 'error': 'Tax Code already exists'}), 400
    
    tax = PurchaseTaxCode(
        account_code=account_code,
        tax_code=tax_code,
        tax_rate=tax_rate,
        section=section,
        status=f.get('status', 'Active'),
    )
    db.session.add(tax)
    db.session.commit()
    return jsonify({'ok': True})


@sale_bp.route('/purchase-tax-codes/<int:id>/edit', methods=['POST'])
@login_required
def purchase_tax_edit(id):
    tax = PurchaseTaxCode.query.get_or_404(id)
    f = request.form
    
    # If tax_code is being changed, validate it's numeric
    new_tax_code = f.get('tax_code', '').strip()
    if new_tax_code != tax.tax_code:
        if not new_tax_code or not re.match(r'^[\d.]+$', new_tax_code):
            return jsonify({'ok': False, 'error': 'Tax Code must contain only numbers'}), 400
        # Check for duplicate
        existing = PurchaseTaxCode.query.filter_by(tax_code=new_tax_code).first()
        if existing:
            return jsonify({'ok': False, 'error': 'Tax Code already exists'}), 400
        tax.tax_code = new_tax_code
    
    # Validate tax rate
    try:
        tax.tax_rate = Decimal(f.get('tax_rate', '0'))
    except:
        return jsonify({'ok': False, 'error': 'Invalid tax rate'}), 400
    
    tax.account_code = f.get('account_code', '').strip()
    tax.section = f.get('section', '').strip()
    tax.status = f.get('status', 'Active')
    tax.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'ok': True})


@sale_bp.route('/purchase-tax-codes/<int:id>/delete', methods=['POST'])
@login_required
def purchase_tax_delete(id):
    tax = PurchaseTaxCode.query.get_or_404(id)
    db.session.delete(tax)
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════
# SALES TAX CODES
# ══════════════════════════════════════════════════════════════════

@sale_bp.route('/sales-tax-codes')
@login_required
def sales_tax_list():
    return render_template('tax_codes/tax_list.html', 
                         kind='sales',
                         title_en='Sales Tax Codes',
                         title_ar='رموز الضرائب للمبيعات',
                         doc_type='sales')


@sale_bp.route('/sales-tax-codes/data')
@login_required
def sales_tax_data():
    rows = SalesTaxCode.query.order_by(SalesTaxCode.id.desc()).all()
    return jsonify([{
        'id': r.id,
        'account_code': r.account_code,
        'tax_code': r.tax_code,
        'tax_rate': float(r.tax_rate) if r.tax_rate else 0,
        'section': r.section,
        'status': r.status
    } for r in rows])


@sale_bp.route('/sales-tax-codes/add', methods=['POST'])
@login_required
def sales_tax_add():
    f = request.form
    tax_code = f.get('tax_code', '').strip()
    account_code = f.get('account_code', '').strip()
    section = f.get('section', '').strip()
    
    # Validate: tax_code must be numeric only
    if not tax_code or not re.match(r'^[\d.]+$', tax_code):
        return jsonify({'ok': False, 'error': 'Tax Code must contain only numbers'}), 400
    
    # Validate tax rate
    try:
        tax_rate = Decimal(f.get('tax_rate', '0'))
    except:
        return jsonify({'ok': False, 'error': 'Invalid tax rate'}), 400
    
    if not account_code or not section:
        return jsonify({'ok': False, 'error': 'Account Code and Section are required'}), 400
    
    # Check for duplicate
    existing = SalesTaxCode.query.filter_by(tax_code=tax_code).first()
    if existing:
        return jsonify({'ok': False, 'error': 'Tax Code already exists'}), 400
    
    tax = SalesTaxCode(
        account_code=account_code,
        tax_code=tax_code,
        tax_rate=tax_rate,
        section=section,
        status=f.get('status', 'Active'),
    )
    db.session.add(tax)
    db.session.commit()
    return jsonify({'ok': True})


@sale_bp.route('/sales-tax-codes/<int:id>/edit', methods=['POST'])
@login_required
def sales_tax_edit(id):
    tax = SalesTaxCode.query.get_or_404(id)
    f = request.form
    
    # If tax_code is being changed, validate it's numeric
    new_tax_code = f.get('tax_code', '').strip()
    if new_tax_code != tax.tax_code:
        if not new_tax_code or not re.match(r'^[\d.]+$', new_tax_code):
            return jsonify({'ok': False, 'error': 'Tax Code must contain only numbers'}), 400
        # Check for duplicate
        existing = SalesTaxCode.query.filter_by(tax_code=new_tax_code).first()
        if existing:
            return jsonify({'ok': False, 'error': 'Tax Code already exists'}), 400
        tax.tax_code = new_tax_code
    
    # Validate tax rate
    try:
        tax.tax_rate = Decimal(f.get('tax_rate', '0'))
    except:
        return jsonify({'ok': False, 'error': 'Invalid tax rate'}), 400
    
    tax.account_code = f.get('account_code', '').strip()
    tax.section = f.get('section', '').strip()
    tax.status = f.get('status', 'Active')
    tax.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'ok': True})


@sale_bp.route('/sales-tax-codes/<int:id>/delete', methods=['POST'])
@login_required
def sales_tax_delete(id):
    tax = SalesTaxCode.query.get_or_404(id)
    db.session.delete(tax)
    db.session.commit()
    return jsonify({'ok': True})