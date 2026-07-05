from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from models import db, InvoiceBank, Invoice, InvoiceLineItem, InvoicePayment, Seller, BuyerMaster, Employee
from datetime import datetime
from decimal import Decimal

inv_bp = Blueprint('invoices', __name__)

# ── Invoice number prefixes ──────────────────────────────────────
PREFIXES = {
    'STDINV': 'STDINV',   # Standard Invoice
    'STDDR':  'STDDR',    # Standard Debit
    'STDCR':  'STDCR',    # Standard Credit
    'SIMINV': 'SIMINV',   # Simplified Invoice
    'SIMDR':  'SIMDR',    # Simplified Debit
    'SIMCR':  'SIMCR',    # Simplified Credit
}

def next_invoice_no(dr_cr_type):
    prefix = PREFIXES.get(dr_cr_type, 'STDCR')
    like = f'{prefix}-%'
    last = Invoice.query.filter(Invoice.invoice_no.like(like))                        .order_by(Invoice.id.desc()).first()
    if last:
        try:
            num = int(last.invoice_no.split('-')[-1]) + 1
        except:
            num = 1
    else:
        num = 1
    return f'{prefix}-{num:05d}'

def parse_date(val, is_hijri=False):
    if not val: return None
    if is_hijri:
        try:
            from hijridate import Hijri
            parts = val.replace('/','-').split('-')
            if len(parts) == 3:
                h = Hijri(int(parts[0]), int(parts[1]), int(parts[2]))
                return h.to_gregorian().date()
        except:
            pass
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
        try: return datetime.strptime(val, fmt).date()
        except: pass
    return None

def gregorian_to_hijri_str(d):
    if not d: return ''
    try:
        from hijridate import Gregorian
        h = Gregorian(d.year, d.month, d.day).to_hijri()
        return f'{h.year:04d}-{h.month:02d}-{h.day:02d}'
    except:
        return str(d)

def _t(en, ar): return ar if session.get('lang') == 'ar' else en

# ── List page ────────────────────────────────────────────────────
@inv_bp.route('/invoices')
@login_required
def list_invoices():
    sellers = Seller.query.filter_by(status='active').all()
    buyers  = BuyerMaster.query.filter_by(is_active=True).all()
    return render_template('invoices/list.html', sellers=sellers, buyers=buyers)

@inv_bp.route('/invoices/data')
@login_required
def invoices_data():
    rows = Invoice.query.order_by(Invoice.id.desc()).all()
    return jsonify([r.to_dict() for r in rows])

@inv_bp.route('/invoices/next-no')
@login_required
def next_no():
    t = request.args.get('type', 'S')
    return jsonify({'invoice_no': next_invoice_no(t)})

@inv_bp.route('/invoices/<int:id>/json')
@login_required
def invoice_json(id):
    inv = Invoice.query.get_or_404(id)
    return jsonify(inv.to_dict())

# ── Add ──────────────────────────────────────────────────────────
@inv_bp.route('/invoices/add', methods=['POST'])
@login_required
def add_invoice():
    f = request.form
    dr_cr_type = f.get('dr_cr_type', 'S')
    is_ar = session.get('lang') == 'ar'
    inv = Invoice(
        invoice_no        = next_invoice_no(dr_cr_type),
        custom_invoice_no = f.get('custom_invoice_no', '').strip() or None,
        dr_cr_type        = dr_cr_type,
        payment_type      = f.get('payment_type', 'credit'),
        invoice_date      = parse_date(f.get('invoice_date'), is_hijri=is_ar),
        month             = f.get('month', '').strip(),
        po_number         = f.get('po_number', '').strip() or None,
        project_reference = f.get('project_reference', '').strip() or None,
        due_date          = parse_date(f.get('due_date'), is_hijri=is_ar),
        period_start      = parse_date(f.get('period_start')),
        period_end        = parse_date(f.get('period_end')),
        invoice_type      = f.get('invoice_type', '').strip() or None,
        invoice_department= f.get('invoice_department', '').strip() or None,
        seller_id         = int(f.get('seller_id', 0)),
        buyer_id          = int(f.get('buyer_id', 0)),
        retention_pct     = Decimal(f.get('retention_pct', '0') or '0'),
        status            = 'active',
        created_by        = current_user.id,
    )
    db.session.add(inv)
    db.session.flush()  # get inv.id

    # Line items
    gross = Decimal('0')
    discount_total = Decimal('0')
    vat_total = Decimal('0')
    items = _parse_line_items(f)
    for item in items:
        li = InvoiceLineItem(
            invoice_id  = inv.id,
            employee_id = item.get('employee_id'),
            uom         = item.get('uom', 'hour'),
            quantity    = item['qty'],
            rate        = item['rate'],
            discount    = item['discount'],
            taxable     = item['taxable'],
            tax_rate    = item['tax_rate'],
            tax_amount  = item['tax_amount'],
            total       = item['total'],
        )
        db.session.add(li)
        gross += item['qty'] * item['rate']
        discount_total += item['discount']
        vat_total += item['tax_amount']

    subtotal = gross - discount_total
    total = subtotal + vat_total
    retention = (total * inv.retention_pct / 100).quantize(Decimal('0.01'))
    balance = total - retention

    inv.gross_total = gross
    inv.total_discount = discount_total
    inv.vat_amount = vat_total
    inv.total_amount = total
    inv.retention_amount = retention
    inv.balance_due = balance
    db.session.commit()
    flash(_t('Invoice added successfully.', 'تم إضافة الفاتورة بنجاح.'), 'success')
    return redirect(url_for('invoices.list_invoices'))

# ── Edit ─────────────────────────────────────────────────────────
@inv_bp.route('/invoices/<int:id>/edit', methods=['POST'])
@login_required
def edit_invoice(id):
    inv = Invoice.query.get_or_404(id)
    f = request.form
    inv.custom_invoice_no = f.get('custom_invoice_no', '').strip() or None
    inv.dr_cr_type        = f.get('dr_cr_type', inv.dr_cr_type)
    inv.payment_type      = f.get('payment_type', inv.payment_type)
    inv.invoice_date      = parse_date(f.get('invoice_date')) or inv.invoice_date
    inv.month             = f.get('month', inv.month or '').strip()
    inv.po_number         = f.get('po_number', '').strip() or None
    inv.project_reference = f.get('project_reference', '').strip() or None
    inv.due_date          = parse_date(f.get('due_date'))
    inv.period_start      = parse_date(f.get('period_start'))
    inv.period_end        = parse_date(f.get('period_end'))
    inv.invoice_type      = f.get('invoice_type', '').strip() or None
    inv.invoice_department= f.get('invoice_department', '').strip() or None
    inv.seller_id         = int(f.get('seller_id', inv.seller_id))
    inv.buyer_id          = int(f.get('buyer_id', inv.buyer_id))
    inv.retention_pct     = Decimal(f.get('retention_pct', '0') or '0')

    # Replace line items
    InvoiceLineItem.query.filter_by(invoice_id=id).delete()
    gross = Decimal('0'); discount_total = Decimal('0'); vat_total = Decimal('0')
    for item in _parse_line_items(f):
        li = InvoiceLineItem(invoice_id=id, employee_id=item.get('employee_id'),
                             uom=item.get('uom','hour'), quantity=item['qty'], rate=item['rate'],
                             discount=item['discount'], taxable=item['taxable'],
                             tax_rate=item['tax_rate'], tax_amount=item['tax_amount'], total=item['total'])
        db.session.add(li)
        gross += item['qty'] * item['rate']
        discount_total += item['discount']; vat_total += item['tax_amount']

    subtotal = gross - discount_total; total = subtotal + vat_total
    retention = (total * inv.retention_pct / 100).quantize(Decimal('0.01'))
    inv.gross_total = gross; inv.total_discount = discount_total
    inv.vat_amount = vat_total; inv.total_amount = total
    inv.retention_amount = retention; inv.balance_due = total - retention
    db.session.commit()
    flash(_t('Invoice updated.', 'تم تحديث الفاتورة.'), 'success')
    return redirect(url_for('invoices.list_invoices'))

# ── Delete ───────────────────────────────────────────────────────
@inv_bp.route('/invoices/<int:id>/delete', methods=['POST'])
@login_required
def delete_invoice(id):
    inv = Invoice.query.get_or_404(id)
    db.session.delete(inv)
    db.session.commit()
    flash(_t('Invoice deleted.', 'تم حذف الفاتورة.'), 'success')
    return redirect(url_for('invoices.list_invoices'))

# ── Add Payment ──────────────────────────────────────────────────
@inv_bp.route('/invoices/<int:id>/payment', methods=['POST'])
@login_required
def add_payment(id):
    inv = Invoice.query.get_or_404(id)
    f = request.form
    pmt = InvoicePayment(
        invoice_id   = id,
        payment_date = parse_date(f.get('payment_date')) or datetime.today().date(),
        amount       = Decimal(f.get('amount', '0') or '0'),
        method       = f.get('method', '').strip(),
        reference    = f.get('reference', '').strip(),
        created_by   = current_user.id,
    )
    db.session.add(pmt)
    # Recalculate balance
    paid = sum(p.amount for p in inv.payments) + pmt.amount
    inv.balance_due = max(Decimal('0'), inv.total_amount - paid)
    db.session.commit()
    return jsonify({'ok': True, 'balance_due': float(inv.balance_due)})

@inv_bp.route('/invoices/<int:id>/payments')
@login_required
def get_payments(id):
    pmts = InvoicePayment.query.filter_by(invoice_id=id).order_by(InvoicePayment.payment_date).all()
    return jsonify([{
        'id': p.id, 'date': p.payment_date.strftime('%d/%m/%Y'),
        'amount': float(p.amount), 'method': p.method, 'reference': p.reference
    } for p in pmts])

# ── Employees for line items ─────────────────────────────────────
@inv_bp.route('/invoices/employees')
@login_required
def inv_employees():
    emps = Employee.query.filter_by(is_active=True).order_by(Employee.employee_code).all()
    return jsonify([{
        'id': e.id, 'employee_code': e.employee_code,
        'name': e.name, 'name_ar': e.name_ar or '',
        'display': f"{e.employee_code} - {e.name}",
        'po_rate': float(e.po_rate) if e.po_rate else 0,
    } for e in emps])


@inv_bp.route('/invoices/<int:id>/view')
@login_required
def view_invoice(id):
    inv = Invoice.query.get_or_404(id)
    sellers = Seller.query.filter_by(status='active').all()
    buyers  = BuyerMaster.query.filter_by(is_active=True).all()
    return render_template('invoices/view.html', inv=inv)

@inv_bp.route('/invoices/<int:id>/print')
@login_required
def print_invoice(id):
    inv = Invoice.query.get_or_404(id)
    return render_template('invoices/print.html', inv=inv)

@inv_bp.route('/invoices/<int:id>/upload', methods=['POST'])
@login_required
def upload_invoice(id):
    inv = Invoice.query.get_or_404(id)
    import os
    from werkzeug.utils import secure_filename
    f = request.files.get('file')
    if not f or f.filename == '':
        return jsonify({'ok': False, 'error': 'No file'}), 400
    fname = secure_filename(f.filename)
    upload_dir = os.path.join('static', 'uploads', 'invoices', str(id))
    os.makedirs(upload_dir, exist_ok=True)
    f.save(os.path.join(upload_dir, fname))
    return jsonify({'ok': True, 'filename': fname})

# ── Helpers ──────────────────────────────────────────────────────
def _parse_line_items(f):
    items = []
    emp_ids   = f.getlist('li_employee[]')
    uoms      = f.getlist('li_uom[]')
    qtys      = f.getlist('li_qty[]')
    rates     = f.getlist('li_rate[]')
    discounts = f.getlist('li_discount[]')
    taxables  = f.getlist('li_taxable[]')
    tax_rates = f.getlist('li_tax_rate[]')
    for i in range(len(qtys)):
        try:
            qty      = Decimal(qtys[i] or '0')
            rate     = Decimal(rates[i] if i < len(rates) else '0')
            discount = Decimal(discounts[i] if i < len(discounts) else '0')
            taxable  = (taxables[i] if i < len(taxables) else 'true').lower() in ('true','1','on','yes')
            tax_rate = Decimal(tax_rates[i] if i < len(tax_rates) else '15')
            subtotal = qty * rate - discount
            tax_amt  = (subtotal * tax_rate / 100).quantize(Decimal('0.01')) if taxable else Decimal('0')
            total    = subtotal + tax_amt
            emp_id   = int(emp_ids[i]) if i < len(emp_ids) and emp_ids[i] else None
            uom      = uoms[i] if i < len(uoms) else 'hour'
            items.append({'employee_id': emp_id, 'uom': uom, 'qty': qty, 'rate': rate,
                          'discount': discount, 'taxable': taxable,
                          'tax_rate': tax_rate, 'tax_amount': tax_amt, 'total': total})
        except Exception as e:
            pass
    return items


# ══════════════════════════════════════════════════════════════════
# INVOICE BANK ROUTES  →  invoice_banks table
# ══════════════════════════════════════════════════════════════════
@inv_bp.route('/invoices/<int:invoice_id>/banks')
@login_required
def invoice_banks(invoice_id):
    banks = InvoiceBank.query.filter_by(invoice_id=invoice_id).order_by(InvoiceBank.id).all()
    return jsonify([b.to_dict() for b in banks])

@inv_bp.route('/invoices/<int:invoice_id>/banks/add', methods=['POST'])
@login_required
def add_invoice_bank(invoice_id):
    data = request.get_json() or {}
    if not data.get('bank_name','').strip():
        return jsonify({'ok': False, 'error': 'Bank name required'}), 400
    if data.get('is_primary'):
        InvoiceBank.query.filter_by(invoice_id=invoice_id, is_primary=True).update({'is_primary': False})
    b = InvoiceBank(
        invoice_id     = invoice_id,
        bank_name      = data.get('bank_name','').strip(),
        account_number = data.get('account_number','').strip(),
        branch         = data.get('branch','').strip(),
        swift_code     = data.get('swift_code','').strip(),
        iban           = data.get('iban','').strip(),
        is_primary     = bool(data.get('is_primary', False)),
    )
    db.session.add(b)
    db.session.commit()
    return jsonify({'ok': True, 'id': b.id, 'bank': b.to_dict()})

@inv_bp.route('/invoices/banks/<int:bank_id>/edit', methods=['POST'])
@login_required
def edit_invoice_bank(bank_id):
    b    = InvoiceBank.query.get_or_404(bank_id)
    data = request.get_json() or {}
    if data.get('is_primary'):
        InvoiceBank.query.filter_by(invoice_id=b.invoice_id, is_primary=True).update({'is_primary': False})
    b.bank_name      = data.get('bank_name', b.bank_name).strip()
    b.account_number = data.get('account_number', b.account_number or '').strip()
    b.branch         = data.get('branch', b.branch or '').strip()
    b.swift_code     = data.get('swift_code', b.swift_code or '').strip()
    b.iban           = data.get('iban', b.iban or '').strip()
    b.is_primary     = bool(data.get('is_primary', b.is_primary))
    db.session.commit()
    return jsonify({'ok': True, 'bank': b.to_dict()})

@inv_bp.route('/invoices/banks/<int:bank_id>/delete', methods=['POST'])
@login_required
def delete_invoice_bank(bank_id):
    b = InvoiceBank.query.get_or_404(bank_id)
    db.session.delete(b)
    db.session.commit()
    return jsonify({'ok': True})