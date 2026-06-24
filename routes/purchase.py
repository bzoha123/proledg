from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from models import db, VendorMaster, PurchaseRequest, PurchaseQuotation, PurchaseOrder, \
    PurchaseLineItem, PurchaseAttachment, Invoice
from datetime import datetime, date
from decimal import Decimal
import os, re
from werkzeug.utils import secure_filename

pur_bp = Blueprint('purchase', __name__)

# ── Helpers ────────────────────────────────────────────────────
def pd(val):
    if not val: return None
    for fmt in ['%Y-%m-%d','%d/%m/%Y','%d-%m-%Y']:
        try: return datetime.strptime(val, fmt).date()
        except: pass
    return None

def _t(en, ar): return ar if session.get('lang') == 'ar' else en

def _next_doc_no(doc_type, model):
    """Generate unique doc number per type. Format: PR-2026-0001, PQ-2026-0001, PO-2026-0001."""
    year = date.today().year
    prefix = doc_type   # PR / PQ / PO
    like = f'{prefix}-{year}-%'
    last = db.session.query(model).filter(
        model.doc_no.like(like)
    ).order_by(model.id.desc()).first()
    if last and last.doc_no:
        try:
            n = int(last.doc_no.split('-')[-1]) + 1
        except:
            n = 1
    else:
        n = 1
    return f'{prefix}-{year}-{n:04d}'

def _save_line_items(doc_type, doc_id, f):
    PurchaseLineItem.query.filter_by(doc_type=doc_type, doc_id=doc_id).delete()
    codes  = f.getlist('li_item_code[]')
    descs  = f.getlist('li_item_desc[]')
    rdates = f.getlist('li_required_date[]')
    whs    = f.getlist('li_warehouse[]')
    uoms   = f.getlist('li_uom[]')
    qtys   = f.getlist('li_qty[]')
    rates  = f.getlist('li_rate[]')
    discs  = f.getlist('li_discount[]')
    freights = f.getlist('li_freight[]')
    tcodes = f.getlist('li_tax_code[]')

    total_bd=Decimal(0); total_disc=Decimal(0); total_fr=Decimal(0)
    total_vat=Decimal(0)

    for i in range(len(qtys)):
        try:
            qty  = Decimal(qtys[i] or '0')
            rate = Decimal(rates[i] if i<len(rates) else '0')
            disc = Decimal(discs[i] if i<len(discs) else '0')
            fr   = Decimal(freights[i] if i<len(freights) else '0')
            tax_code = tcodes[i] if i<len(tcodes) else 'VAT15'
            tax_rate = Decimal('15') if '15' in tax_code else Decimal('0')
            taxable  = qty * rate
            subtotal = taxable - disc
            tax_amt  = (subtotal * tax_rate / 100).quantize(Decimal('0.01'))
            total    = subtotal + fr + tax_amt
            li = PurchaseLineItem(
                doc_type=doc_type, doc_id=doc_id,
                item_code=codes[i] if i<len(codes) else '',
                item_desc=descs[i] if i<len(descs) else '',
                required_date=pd(rdates[i]) if i<len(rdates) else None,
                warehouse=whs[i] if i<len(whs) else '',
                uom=uoms[i] if i<len(uoms) else 'unit',
                quantity=qty, rate=rate, discount=disc, freight=fr,
                taxable=taxable, tax_code=tax_code,
                tax_amount=tax_amt, total=total,
            )
            db.session.add(li)
            total_bd   += qty*rate
            total_disc += disc
            total_fr   += fr
            total_vat  += tax_amt
        except: pass

    excl = total_bd - total_disc
    return {
        'total_before_discount': total_bd,
        'total_discount': total_disc,
        'total_freight': total_fr,
        'total_excl_vat': excl,
        'vat_amount': total_vat,
        'total_incl_vat': excl + total_fr + total_vat,
    }

def _save_attachments(doc_type, doc_id, files):
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

def _vendor_list():
    return [{'id':v.id,'name':v.vendor_name_en,'name_ar':v.vendor_name_ar or ''} for v in VendorMaster.query.filter_by(is_active=True).order_by(VendorMaster.vendor_name_en).all()]

def _invoice_list():
    return [{'id':i.id,'invoice_no':i.invoice_no} for i in Invoice.query.order_by(Invoice.id.desc()).all()]

# ══════════════════════════════════════════════════════════════════
# VENDOR REGISTRATION
# ══════════════════════════════════════════════════════════════════
@pur_bp.route('/purchase/next-no')
@login_required
def purchase_next_no():
    doc_type = request.args.get('type','PR')
    models_map = {'PR': PurchaseRequest, 'PQ': PurchaseQuotation, 'PO': PurchaseOrder}
    model = models_map.get(doc_type, PurchaseRequest)
    return jsonify({'doc_no': _next_doc_no(doc_type, model)})


@pur_bp.route('/purchase/next-doc-no')
@login_required  
def next_doc_no():
    doc_type = request.args.get('type', 'PR')
    model_map = {'PR': PurchaseRequest, 'PQ': PurchaseQuotation, 'PO': PurchaseOrder}
    model = model_map.get(doc_type, PurchaseRequest)
    return jsonify({'doc_no': _next_doc_no(doc_type, model)})

@pur_bp.route('/purchase/requests/<int:id>/view')
@login_required
def pr_view(id):
    pr = PurchaseRequest.query.get_or_404(id)
    items = PurchaseLineItem.query.filter_by(doc_type='PR', doc_id=id).all()
    attachments = PurchaseAttachment.query.filter_by(doc_type='PR', doc_id=id).all()
    return render_template('purchase/pr_view.html', pr=pr, items=items, attachments=attachments)

@pur_bp.route('/purchase/quotations/<int:id>/view')
@login_required
def pq_view(id):
    pq = PurchaseQuotation.query.get_or_404(id)
    items = PurchaseLineItem.query.filter_by(doc_type='PQ', doc_id=id).all()
    attachments = PurchaseAttachment.query.filter_by(doc_type='PQ', doc_id=id).all()
    return render_template('purchase/pq_view.html', doc=pq, items=items, attachments=attachments, doc_type='PQ')

@pur_bp.route('/purchase/orders/<int:id>/view')
@login_required
def po_view(id):
    po = PurchaseOrder.query.get_or_404(id)
    items = PurchaseLineItem.query.filter_by(doc_type='PO', doc_id=id).all()
    attachments = PurchaseAttachment.query.filter_by(doc_type='PO', doc_id=id).all()
    return render_template('purchase/po_view.html', doc=po, items=items, attachments=attachments, doc_type='PO')

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
    # Add full fields
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
        bank_name=f.get('bank_name','').strip() or None,
        bank_branch=f.get('bank_branch','').strip() or None,
        swift_code=f.get('swift_code','').strip() or None,
        account_number=f.get('account_number','').strip() or None,
        iban=f.get('iban','').strip() or None,
        invoice_id=int(f.get('invoice_id')) if f.get('invoice_id') else None,
        status='active', is_active=True, created_by=current_user.id,
    )
    db.session.add(v); db.session.commit()
    return jsonify({'ok': True, 'id': v.id, 'vendor_code': v.vendor_code})

@pur_bp.route('/purchase/vendors/<int:id>/edit', methods=['POST'])
@login_required
def vendor_edit(id):
    v = VendorMaster.query.get_or_404(id)
    f = request.form
    for fld in ['vendor_name_en','vendor_name_ar','vat_number','crn','phone','fax','email',
                'website','contact_person','street_name','street_name_ar','building_number',
                'additional_number','postal_code','country','country_ar','city','city_ar',
                'district','district_ar','bank_name','bank_branch','swift_code',
                'account_number','iban']:
        setattr(v, fld, f.get(fld,'').strip() or None)
    v.invoice_id = int(f.get('invoice_id')) if f.get('invoice_id') else None
    v.status = f.get('status','active')
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/purchase/vendors/<int:id>/delete', methods=['POST'])
@login_required
def vendor_delete(id):
    v = VendorMaster.query.get_or_404(id)
    db.session.delete(v); db.session.commit()
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════════════
# PURCHASE REQUEST
# ══════════════════════════════════════════════════════════════════
@pur_bp.route('/purchase/requests')
@login_required
def pr_list():
    return render_template('purchase/pr_list.html',
                           vendors=_vendor_list())

@pur_bp.route('/purchase/requests/data')
@login_required
def pr_data():
    rows = PurchaseRequest.query.order_by(PurchaseRequest.id.desc()).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/purchase/requests/<int:id>/json')
@login_required
def pr_json(id):
    pr = PurchaseRequest.query.get_or_404(id)
    d = pr.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseLineItem.query.filter_by(doc_type='PR', doc_id=id).all()]
    d['attachments'] = [{'filename':a.filename,'filepath':a.filepath} for a in
                        PurchaseAttachment.query.filter_by(doc_type='PR', doc_id=id).all()]
    return jsonify(d)

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
    tots = _save_line_items('PR', pr.id, f)
    for k,v in tots.items(): setattr(pr, k, v)
    _save_attachments('PR', pr.id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True, 'id': pr.id, 'doc_no': pr.doc_no})

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
    tots = _save_line_items('PR', id, f)
    for k,v in tots.items(): setattr(pr, k, v)
    _save_attachments('PR', id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/purchase/requests/<int:id>/delete', methods=['POST'])
@login_required
def pr_delete(id):
    pr = PurchaseRequest.query.get_or_404(id)
    PurchaseLineItem.query.filter_by(doc_type='PR', doc_id=id).delete()
    PurchaseAttachment.query.filter_by(doc_type='PR', doc_id=id).delete()
    db.session.delete(pr); db.session.commit()
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════════════
# PURCHASE QUOTATION
# ══════════════════════════════════════════════════════════════════
@pur_bp.route('/purchase/quotations')
@login_required
def pq_list():
    prs = [{'id':p.id,'doc_no':p.doc_no} for p in PurchaseRequest.query.order_by(PurchaseRequest.id.desc()).all()]
    return render_template('purchase/pq_list.html', vendors=_vendor_list(), prs=prs)

@pur_bp.route('/purchase/quotations/data')
@login_required
def pq_data():
    rows = PurchaseQuotation.query.order_by(PurchaseQuotation.id.desc()).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/purchase/quotations/<int:id>/json')
@login_required
def pq_json(id):
    pq = PurchaseQuotation.query.get_or_404(id)
    d = pq.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseLineItem.query.filter_by(doc_type='PQ', doc_id=id).all()]
    d['attachments'] = [{'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='PQ', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/quotations/add', methods=['POST'])
@login_required
def pq_add():
    f = request.form
    pq = PurchaseQuotation(
        doc_no=_next_doc_no('PQ', PurchaseQuotation),
        pr_id=int(f.get('pr_id')) if f.get('pr_id') else None,
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
    db.session.add(pq); db.session.flush()
    tots = _save_line_items('PQ', pq.id, f)
    for k,v in tots.items(): setattr(pq, k, v)
    _save_attachments('PQ', pq.id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True, 'id': pq.id, 'doc_no': pq.doc_no})

@pur_bp.route('/purchase/quotations/<int:id>/edit', methods=['POST'])
@login_required
def pq_edit(id):
    pq = PurchaseQuotation.query.get_or_404(id)
    f = request.form
    for fld in ['requester','requester_name','status','remarks','approved_by']:
        setattr(pq, fld, f.get(fld,'').strip())
    pq.pr_id = int(f.get('pr_id')) if f.get('pr_id') else None
    pq.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
    for df in ['posting_date','valid_until','document_date','required_date']:
        setattr(pq, df, pd(f.get(df)))
    tots = _save_line_items('PQ', id, f)
    for k,v in tots.items(): setattr(pq, k, v)
    _save_attachments('PQ', id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/purchase/quotations/<int:id>/delete', methods=['POST'])
@login_required
def pq_delete(id):
    PurchaseLineItem.query.filter_by(doc_type='PQ', doc_id=id).delete()
    PurchaseAttachment.query.filter_by(doc_type='PQ', doc_id=id).delete()
    pq = PurchaseQuotation.query.get_or_404(id)
    db.session.delete(pq); db.session.commit()
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════════════
# PURCHASE ORDER
# ══════════════════════════════════════════════════════════════════
@pur_bp.route('/purchase/orders')
@login_required
def po_list():
    pqs = [{'id':p.id,'doc_no':p.doc_no} for p in PurchaseQuotation.query.order_by(PurchaseQuotation.id.desc()).all()]
    return render_template('purchase/po_list.html', vendors=_vendor_list(), pqs=pqs)

@pur_bp.route('/purchase/orders/data')
@login_required
def po_data():
    rows = PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).all()
    return jsonify([r.to_dict() for r in rows])

@pur_bp.route('/purchase/orders/<int:id>/json')
@login_required
def po_json(id):
    po = PurchaseOrder.query.get_or_404(id)
    d = po.to_dict()
    d['items'] = [i.to_dict() for i in PurchaseLineItem.query.filter_by(doc_type='PO', doc_id=id).all()]
    d['attachments'] = [{'filename':a.filename} for a in PurchaseAttachment.query.filter_by(doc_type='PO', doc_id=id).all()]
    return jsonify(d)

@pur_bp.route('/purchase/orders/add', methods=['POST'])
@login_required
def po_add():
    f = request.form
    po = PurchaseOrder(
        doc_no=_next_doc_no('PO', PurchaseOrder),
        pq_id=int(f.get('pq_id')) if f.get('pq_id') else None,
        vendor_id=int(f.get('vendor_id')) if f.get('vendor_id') else None,
        vendor_ref_no=f.get('vendor_ref_no','').strip(),
        status=f.get('status','Open'),
        posting_date=pd(f.get('posting_date')),
        delivery_date=pd(f.get('delivery_date')),
        document_date=pd(f.get('document_date')),
        created_by=current_user.id,
    )
    db.session.add(po); db.session.flush()
    tots = _save_line_items('PO', po.id, f)
    for k,v in tots.items(): setattr(po, k, v)
    _save_attachments('PO', po.id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True, 'id': po.id, 'doc_no': po.doc_no})

@pur_bp.route('/purchase/orders/<int:id>/edit', methods=['POST'])
@login_required
def po_edit(id):
    po = PurchaseOrder.query.get_or_404(id)
    f = request.form
    po.pq_id = int(f.get('pq_id')) if f.get('pq_id') else None
    po.vendor_id = int(f.get('vendor_id')) if f.get('vendor_id') else None
    po.vendor_ref_no = f.get('vendor_ref_no','').strip()
    po.status = f.get('status','Open')
    for df in ['posting_date','delivery_date','document_date']:
        setattr(po, df, pd(f.get(df)))
    tots = _save_line_items('PO', id, f)
    for k,v in tots.items(): setattr(po, k, v)
    _save_attachments('PO', id, request.files.getlist('attachments'))
    db.session.commit()
    return jsonify({'ok': True})

@pur_bp.route('/purchase/orders/<int:id>/delete', methods=['POST'])
@login_required
def po_delete(id):
    PurchaseLineItem.query.filter_by(doc_type='PO', doc_id=id).delete()
    PurchaseAttachment.query.filter_by(doc_type='PO', doc_id=id).delete()
    po = PurchaseOrder.query.get_or_404(id)
    db.session.delete(po); db.session.commit()
    return jsonify({'ok': True})