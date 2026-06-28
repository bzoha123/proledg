from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

# ─────────────────────────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), default='user')
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):   self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)
    def is_admin(self):           return self.role == 'admin'

    def to_dict(self):
        return {'id': self.id, 'username': self.username, 'email': self.email,
                'role': self.role, 'is_active': self.is_active}


# ─────────────────────────────────────────────────────────────────
# SELLER
# ─────────────────────────────────────────────────────────────────
class Seller(db.Model):
    __tablename__ = 'sellers'
    id                  = db.Column(db.Integer, primary_key=True)
    seller_code         = db.Column(db.String(20), unique=True)
    name                = db.Column(db.String(200), nullable=False)
    name_ar             = db.Column(db.String(200))
    vat_number          = db.Column(db.String(50))
    crn                 = db.Column(db.String(50))
    phone               = db.Column(db.String(30))
    fax                 = db.Column(db.String(30))
    email               = db.Column(db.String(120))
    website             = db.Column(db.String(200))
    report_color        = db.Column(db.String(10), default='#2563eb')
    logo_path           = db.Column(db.String(500))
    bg_logo_path        = db.Column(db.String(500))
    street_name         = db.Column(db.String(200))
    building_number     = db.Column(db.String(50))
    additional_number   = db.Column(db.String(50))
    district            = db.Column(db.String(100))
    city                = db.Column(db.String(100))
    postal_code         = db.Column(db.String(20))
    country             = db.Column(db.String(100), default='Saudi Arabia')
    street_name_ar      = db.Column(db.String(200))
    building_number_ar  = db.Column(db.String(50))
    additional_number_ar= db.Column(db.String(50))
    district_ar         = db.Column(db.String(100))
    city_ar             = db.Column(db.String(100))
    postal_code_ar      = db.Column(db.String(20))
    country_ar          = db.Column(db.String(100))
    status              = db.Column(db.String(20), default='active')
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow)
    created_by          = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    banks = db.relationship('SellerBank', backref='seller', lazy='dynamic',
                            foreign_keys='SellerBank.seller_id',
                            cascade='all, delete-orphan')
    documents = db.relationship('SellerDocument', backref='seller', lazy='dynamic',
                                foreign_keys='SellerDocument.seller_id',
                                cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by], lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'seller_code': self.seller_code or '',
            'name': self.name, 'name_ar': self.name_ar or '',
            'vat_number': self.vat_number or '', 'crn': self.crn or '',
            'phone': self.phone or '', 'email': self.email or '',
            'city': self.city or '', 'status': self.status,
            'report_color': self.report_color or '#2563eb',
        }


# ─────────────────────────────────────────────────────────────────
# SELLER BANK   (stored in seller_banks)
# ─────────────────────────────────────────────────────────────────
class SellerBank(db.Model):
    __tablename__ = 'seller_banks'
    id             = db.Column(db.Integer, primary_key=True)
    seller_id      = db.Column(db.Integer, db.ForeignKey('sellers.id'), nullable=False)
    bank_name      = db.Column(db.String(150), nullable=False)
    bank_name_ar   = db.Column(db.String(150))
    account_number = db.Column(db.String(50))
    branch         = db.Column(db.String(100))
    branch_ar      = db.Column(db.String(100))
    swift_code     = db.Column(db.String(20))
    iban           = db.Column(db.String(50))
    is_primary     = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'seller_id': self.seller_id,
            'bank_name': self.bank_name,
            'bank_name_ar': self.bank_name_ar or '',
            'account_number': self.account_number or '',
            'branch': self.branch or '',
            'branch_ar': self.branch_ar or '',
            'swift_code': self.swift_code or '',
            'iban': self.iban or '', 'is_primary': self.is_primary,
        }


# ─────────────────────────────────────────────────────────────────
# SELLER DOCUMENT
# ─────────────────────────────────────────────────────────────────
class SellerDocument(db.Model):
    __tablename__ = 'seller_documents'
    id            = db.Column(db.Integer, primary_key=True)
    seller_id     = db.Column(db.Integer, db.ForeignKey('sellers.id'), nullable=False)
    document_type = db.Column(db.String(100), nullable=False)
    document_name = db.Column(db.String(200), nullable=False)
    file_path     = db.Column(db.String(500), nullable=False)
    file_size     = db.Column(db.Integer)
    issue_date    = db.Column(db.Date)
    expiry_date   = db.Column(db.Date)
    uploaded_at   = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by   = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationship to User who uploaded
    uploader = db.relationship('User', foreign_keys=[uploaded_by], lazy=True)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action     = db.Column(db.String(50), nullable=False)
    target     = db.Column(db.String(50))
    target_id  = db.Column(db.Integer)
    detail     = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# BUYER MASTER
# ─────────────────────────────────────────────────────────────────
class BuyerMaster(db.Model):
    __tablename__ = 'buyers'
    id                   = db.Column(db.Integer, primary_key=True)
    buyer_code           = db.Column(db.String(20), unique=True)
    buyer_name_en        = db.Column(db.String(200), nullable=False)
    buyer_name_ar        = db.Column(db.String(200))
    vat_number           = db.Column(db.String(50))
    crn                  = db.Column(db.String(50))
    phone                = db.Column(db.String(30))
    fax                  = db.Column(db.String(30))
    email                = db.Column(db.String(120))
    website              = db.Column(db.String(200))
    report_color         = db.Column(db.String(10), default='#2563eb')
    street_name          = db.Column(db.String(200))
    street_name_ar       = db.Column(db.String(200))
    building_number      = db.Column(db.String(50))
    building_number_ar   = db.Column(db.String(50))
    additional_number    = db.Column(db.String(50))
    additional_number_ar = db.Column(db.String(50))
    postal_code          = db.Column(db.String(20))
    postal_code_ar       = db.Column(db.String(20))
    country              = db.Column(db.String(100), default='Saudi Arabia')
    country_ar           = db.Column(db.String(100))
    city                 = db.Column(db.String(100))
    city_ar              = db.Column(db.String(100))
    district             = db.Column(db.String(100))
    district_ar          = db.Column(db.String(100))
    status               = db.Column(db.String(20), default='active')
    is_active            = db.Column(db.Boolean, default=True)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at           = db.Column(db.DateTime, default=datetime.utcnow)
    created_by           = db.Column(db.Integer, db.ForeignKey('users.id'))

    def to_dict(self):
        return {
            'id': self.id, 'buyer_code': self.buyer_code or '',
            'buyer_name_en': self.buyer_name_en, 'buyer_name_ar': self.buyer_name_ar or '',
            'vat_number': self.vat_number or '', 'crn': self.crn or '',
            'phone': self.phone or '', 'email': self.email or '',
            'city': self.city or '', 'is_active': self.is_active,
        }


# ─────────────────────────────────────────────────────────────────
# BUYER BANK   (stored in buyer_banks)
# ─────────────────────────────────────────────────────────────────
class BuyerBank(db.Model):
    __tablename__ = 'buyer_banks'
    id             = db.Column(db.Integer, primary_key=True)
    buyer_id       = db.Column(db.Integer, db.ForeignKey('buyers.id', ondelete='CASCADE'), nullable=False)
    bank_name      = db.Column(db.String(150), nullable=False)
    account_number = db.Column(db.String(50))
    branch         = db.Column(db.String(100))
    swift_code     = db.Column(db.String(20))
    iban           = db.Column(db.String(50))
    is_primary     = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    buyer = db.relationship('BuyerMaster', backref=db.backref('banks', cascade='all,delete-orphan', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'buyer_id': self.buyer_id,
            'bank_name': self.bank_name, 'account_number': self.account_number or '',
            'branch': self.branch or '', 'swift_code': self.swift_code or '',
            'iban': self.iban or '', 'is_primary': self.is_primary,
        }


# ─────────────────────────────────────────────────────────────────
# PROFESSION MASTER
# ─────────────────────────────────────────────────────────────────
class ProfessionMaster(db.Model):
    __tablename__ = 'profession_master'
    id        = db.Column(db.Integer, primary_key=True)
    name_en   = db.Column(db.String(150), nullable=False)
    name_ar   = db.Column(db.String(150))
    is_active = db.Column(db.Boolean, default=True)
    created_at= db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'name_en': self.name_en,
                'name_ar': self.name_ar or '', 'is_active': self.is_active}


# ─────────────────────────────────────────────────────────────────
# EMPLOYEE
# ─────────────────────────────────────────────────────────────────
class Employee(db.Model):
    __tablename__ = 'employees'
    id               = db.Column(db.Integer, primary_key=True)
    employee_code    = db.Column(db.String(20), unique=True, nullable=False)
    is_active        = db.Column(db.Boolean, default=True)
    is_muslim        = db.Column(db.Boolean, default=False)
    name_en          = db.Column(db.String(200), nullable=False)
    name_ar          = db.Column(db.String(200))
    profession_id    = db.Column(db.Integer, db.ForeignKey('profession_master.id'))
    nationality      = db.Column(db.String(100))
    date_of_birth    = db.Column(db.Date)
    date_of_joining  = db.Column(db.Date)
    iqama_number     = db.Column(db.String(50))
    iqama_expiry     = db.Column(db.Date)
    passport_number  = db.Column(db.String(50))
    passport_expiry  = db.Column(db.Date)
    basic_salary     = db.Column(db.Numeric(12, 2), default=0)
    phone            = db.Column(db.String(30))
    email            = db.Column(db.String(120))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'))

    profession = db.relationship('ProfessionMaster', backref=db.backref('employees', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'employee_code': self.employee_code,
            'name_en': self.name_en, 'name_ar': self.name_ar or '',
            'nationality': self.nationality or '',
            'profession_id': self.profession_id,
            'profession_name': self.profession.name_en if self.profession else '',
            'basic_salary': float(self.basic_salary or 0),
            'phone': self.phone or '', 'email': self.email or '',
            'is_active': self.is_active,
        }



# ─────────────────────────────────────────────────────────────────
# EMPLOYEE BANK   (stored in employee_banks)
# ─────────────────────────────────────────────────────────────────
class EmployeeBank(db.Model):
    __tablename__ = 'employee_banks'
    id             = db.Column(db.Integer, primary_key=True)
    employee_id    = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    bank_name      = db.Column(db.String(150), nullable=False)
    account_number = db.Column(db.String(50))
    branch         = db.Column(db.String(100))
    swift_code     = db.Column(db.String(20))
    iban           = db.Column(db.String(50))
    is_primary     = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee', backref=db.backref('banks', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id, 'employee_id': self.employee_id,
            'bank_name': self.bank_name, 'account_number': self.account_number or '',
            'branch': self.branch or '', 'swift_code': self.swift_code or '',
            'iban': self.iban or '', 'is_primary': self.is_primary,
        }

# ─────────────────────────────────────────────────────────────────
# ALLOWANCE TYPE
# ─────────────────────────────────────────────────────────────────
class AllowanceType(db.Model):
    __tablename__ = 'allowance_types'
    id        = db.Column(db.Integer, primary_key=True)
    name_en   = db.Column(db.String(150), nullable=False)
    name_ar   = db.Column(db.String(150))
    is_active = db.Column(db.Boolean, default=True)
    created_at= db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'name_en': self.name_en,
                'name_ar': self.name_ar or '', 'is_active': self.is_active}


# ─────────────────────────────────────────────────────────────────
# EMPLOYEE ALLOWANCE
# ─────────────────────────────────────────────────────────────────
class EmployeeAllowance(db.Model):
    __tablename__ = 'employee_allowances'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    allowance_type_id = db.Column(db.Integer, db.ForeignKey('allowance_types.id'), nullable=False)
    amount            = db.Column(db.Numeric(12, 2), default=0)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    employee       = db.relationship('Employee',      backref=db.backref('allowances', lazy=True))
    allowance_type = db.relationship('AllowanceType', backref=db.backref('employee_allowances', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'employee_id': self.employee_id,
            'allowance_type_id': self.allowance_type_id,
            'allowance_name': self.allowance_type.name_en if self.allowance_type else '',
            'amount': float(self.amount or 0),
        }


# ─────────────────────────────────────────────────────────────────
# WORK ALLOCATION
# ─────────────────────────────────────────────────────────────────
class WorkAllocation(db.Model):
    __tablename__ = 'work_allocations'
    id          = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    seller_id   = db.Column(db.Integer, db.ForeignKey('sellers.id'),   nullable=False)
    start_date  = db.Column(db.Date)
    end_date    = db.Column(db.Date)
    notes       = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'))

    employee = db.relationship('Employee', backref=db.backref('allocations', lazy=True))
    seller   = db.relationship('Seller',   backref=db.backref('allocations', lazy=True))

    def to_dict(self):
        e = self.employee
        return {
            'id': self.id, 'employee_id': self.employee_id,
            'employee_name': e.name_en if e else '',
            'employee_code': e.employee_code if e else '',
            'seller_id': self.seller_id,
            'seller_name': self.seller.name if self.seller else '',
            'start_date': str(self.start_date) if self.start_date else '',
            'end_date':   str(self.end_date)   if self.end_date   else '',
            'notes': self.notes or '',
        }


# ─────────────────────────────────────────────────────────────────
# INVOICE
# ─────────────────────────────────────────────────────────────────
class Invoice(db.Model):
    __tablename__ = 'invoices'
    id                 = db.Column(db.Integer, primary_key=True)
    invoice_no         = db.Column(db.String(30), unique=True)
    custom_invoice_no  = db.Column(db.String(30))
    dr_cr_type         = db.Column(db.String(10))
    payment_type       = db.Column(db.String(20))
    invoice_date       = db.Column(db.Date)
    month              = db.Column(db.String(20))
    po_number          = db.Column(db.String(50))
    project_reference  = db.Column(db.String(100))
    due_date           = db.Column(db.Date)
    period_start       = db.Column(db.Date)
    period_end         = db.Column(db.Date)
    invoice_type       = db.Column(db.String(30))
    invoice_department = db.Column(db.String(100))
    seller_id          = db.Column(db.Integer, db.ForeignKey('sellers.id'))
    buyer_id           = db.Column(db.Integer, db.ForeignKey('buyers.id'))
    gross_total        = db.Column(db.Numeric(14, 2), default=0)
    total_discount     = db.Column(db.Numeric(14, 2), default=0)
    vat_amount         = db.Column(db.Numeric(14, 2), default=0)
    total_amount       = db.Column(db.Numeric(14, 2), default=0)
    retention_pct      = db.Column(db.Numeric(5,  2), default=0)
    retention_amount   = db.Column(db.Numeric(14, 2), default=0)
    balance_due        = db.Column(db.Numeric(14, 2), default=0)
    status             = db.Column(db.String(20), default='draft')
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    created_by         = db.Column(db.Integer, db.ForeignKey('users.id'))

    seller = db.relationship('Seller',      backref=db.backref('invoices', lazy=True))
    buyer  = db.relationship('BuyerMaster', backref=db.backref('invoices', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'invoice_no': self.invoice_no or '',
            'seller_id': self.seller_id, 'buyer_id': self.buyer_id,
            'invoice_date': str(self.invoice_date) if self.invoice_date else '',
            'due_date': str(self.due_date) if self.due_date else '',
            'status': self.status,
            'gross_total':  float(self.gross_total  or 0),
            'vat_amount':   float(self.vat_amount   or 0),
            'total_amount': float(self.total_amount or 0),
            'balance_due':  float(self.balance_due  or 0),
        }



# ─────────────────────────────────────────────────────────────────
# INVOICE BANK   (stored in invoice_banks)
# ─────────────────────────────────────────────────────────────────
class InvoiceBank(db.Model):
    __tablename__ = 'invoice_banks'
    id             = db.Column(db.Integer, primary_key=True)
    invoice_id     = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    bank_name      = db.Column(db.String(150), nullable=False)
    account_number = db.Column(db.String(50))
    branch         = db.Column(db.String(100))
    swift_code     = db.Column(db.String(20))
    iban           = db.Column(db.String(50))
    is_primary     = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    invoice = db.relationship('Invoice', backref=db.backref('banks', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id, 'invoice_id': self.invoice_id,
            'bank_name': self.bank_name, 'account_number': self.account_number or '',
            'branch': self.branch or '', 'swift_code': self.swift_code or '',
            'iban': self.iban or '', 'is_primary': self.is_primary,
        }

# ─────────────────────────────────────────────────────────────────
# INVOICE LINE ITEM
# ─────────────────────────────────────────────────────────────────
class InvoiceLineItem(db.Model):
    __tablename__ = 'invoice_line_items'
    id          = db.Column(db.Integer, primary_key=True)
    invoice_id  = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    uom         = db.Column(db.String(20), default='unit')
    quantity    = db.Column(db.Numeric(12, 4), default=0)
    rate        = db.Column(db.Numeric(12, 4), default=0)
    discount    = db.Column(db.Numeric(12, 2), default=0)
    taxable     = db.Column(db.Numeric(14, 2), default=0)
    tax_rate    = db.Column(db.Numeric(5,  2), default=15)
    tax_amount  = db.Column(db.Numeric(14, 2), default=0)
    total       = db.Column(db.Numeric(14, 2), default=0)

    invoice  = db.relationship('Invoice',  backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))
    employee = db.relationship('Employee', backref=db.backref('invoice_lines', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'invoice_id': self.invoice_id,
            'employee_id': self.employee_id,
            'uom': self.uom or 'unit',
            'quantity': float(self.quantity or 0), 'rate': float(self.rate or 0),
            'discount': float(self.discount or 0), 'taxable': float(self.taxable or 0),
            'tax_rate': float(self.tax_rate or 15), 'tax_amount': float(self.tax_amount or 0),
            'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────────────────────────
# INVOICE PAYMENT
# ─────────────────────────────────────────────────────────────────
class InvoicePayment(db.Model):
    __tablename__ = 'invoice_payments'
    id           = db.Column(db.Integer, primary_key=True)
    invoice_id   = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    payment_date = db.Column(db.Date)
    amount       = db.Column(db.Numeric(14, 2), default=0)
    method       = db.Column(db.String(50))
    reference    = db.Column(db.String(100))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'))

    invoice = db.relationship('Invoice', backref=db.backref('payments', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'invoice_id': self.invoice_id,
            'payment_date': str(self.payment_date) if self.payment_date else '',
            'amount': float(self.amount or 0),
            'method': self.method or '', 'reference': self.reference or '',
        }


# ─────────────────────────────────────────────────────────────────
# VENDOR REGISTRATION
# ─────────────────────────────────────────────────────────────────
class VendorMaster(db.Model):
    __tablename__ = 'vendors'
    id                = db.Column(db.Integer, primary_key=True)
    vendor_code       = db.Column(db.String(20), unique=True)
    vendor_name_en    = db.Column(db.String(200), nullable=False)
    vendor_name_ar    = db.Column(db.String(200))
    vat_number        = db.Column(db.String(50))
    crn               = db.Column(db.String(50))
    phone             = db.Column(db.String(30))
    fax               = db.Column(db.String(30))
    email             = db.Column(db.String(120))
    website           = db.Column(db.String(200))
    contact_person    = db.Column(db.String(150))
    street_name       = db.Column(db.String(200))
    street_name_ar    = db.Column(db.String(200))
    building_number   = db.Column(db.String(50))
    additional_number = db.Column(db.String(50))
    postal_code       = db.Column(db.String(20))
    country           = db.Column(db.String(100), default='Saudi Arabia')
    country_ar        = db.Column(db.String(100))
    city              = db.Column(db.String(100))
    city_ar           = db.Column(db.String(100))
    district          = db.Column(db.String(100))
    district_ar       = db.Column(db.String(100))
    status            = db.Column(db.String(20), default='active')
    is_active         = db.Column(db.Boolean, default=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    created_by        = db.Column(db.Integer, db.ForeignKey('users.id'))

    def to_dict(self):
        return {
            'id': self.id, 'vendor_code': self.vendor_code or '',
            'vendor_name_en': self.vendor_name_en, 'vendor_name_ar': self.vendor_name_ar or '',
            'vat_number': self.vat_number or '', 'crn': self.crn or '',
            'phone': self.phone or '', 'email': self.email or '',
            'city': self.city or '', 'status': self.status,
            'contact_person': self.contact_person or '', 'is_active': self.is_active,
        }


# ─────────────────────────────────────────────────────────────────
# VENDOR BANK   (stored in vendor_banks)
# ─────────────────────────────────────────────────────────────────
class VendorBank(db.Model):
    __tablename__ = 'vendor_banks'
    id             = db.Column(db.Integer, primary_key=True)
    vendor_id      = db.Column(db.Integer, db.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False)
    bank_name_en   = db.Column(db.String(150), nullable=False)
    bank_name_ar   = db.Column(db.String(150))
    account_number = db.Column(db.String(50))
    branch_en      = db.Column(db.String(100))
    branch_ar      = db.Column(db.String(100))
    swift_code     = db.Column(db.String(20))
    iban           = db.Column(db.String(50))
    is_primary     = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    vendor = db.relationship('VendorMaster', backref=db.backref('banks', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id, 'vendor_id': self.vendor_id,
            'bank_name_en': self.bank_name_en, 'bank_name_ar': self.bank_name_ar or '',
            'account_number': self.account_number or '',
            'branch_en': self.branch_en or '', 'branch_ar': self.branch_ar or '',
            'swift_code': self.swift_code or '', 'iban': self.iban or '',
            'is_primary': self.is_primary,
        }


# ─────────────────────────────────────────────────────────────────
# VENDOR DOCUMENT
# ─────────────────────────────────────────────────────────────────
class VendorDocument(db.Model):
    __tablename__ = 'vendor_documents'
    id            = db.Column(db.Integer, primary_key=True)
    vendor_id     = db.Column(db.Integer, db.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False)
    document_type = db.Column(db.String(100), nullable=False)
    document_name = db.Column(db.String(200), nullable=False)
    file_path     = db.Column(db.String(500), nullable=False)
    file_size     = db.Column(db.Integer)
    expiry_date   = db.Column(db.Date)
    uploaded_at   = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by   = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('documents', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id, 'vendor_id': self.vendor_id,
            'document_type': self.document_type, 'document_name': self.document_name,
            'file_path': self.file_path,
            'file_size_kb': round((self.file_size or 0) / 1024, 1),
            'expiry_date': str(self.expiry_date) if self.expiry_date else '',
            'uploaded_at': self.uploaded_at.strftime('%Y-%m-%d %H:%M') if self.uploaded_at else '',
        }


# ═══════════════════════════════════════════════════════════════════
# PURCHASE MODULE
# Flow: PR(1) → PQ(2) → PO(3) → GRN(4) → PINV(5)
#                                        ↓
#                               GRR(6) → PDM(7)
# ═══════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────
# 1. PURCHASE REQUEST
# ─────────────────────────────────────────────────────────────────
class PurchaseRequest(db.Model):
    __tablename__ = 'purchase_requests'
    purchase_request_id   = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    requester             = db.Column(db.String(150))
    requester_name        = db.Column(db.String(200))
    vendor_id             = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    status                = db.Column(db.String(20), default='Open')
    posting_date          = db.Column(db.Date)
    valid_until           = db.Column(db.Date)
    document_date         = db.Column(db.Date)
    required_date         = db.Column(db.Date)
    remarks               = db.Column(db.Text)
    approved_by           = db.Column(db.String(150))
    total_before_discount = db.Column(db.Numeric(14, 2), default=0)
    total_discount        = db.Column(db.Numeric(14, 2), default=0)
    total_freight         = db.Column(db.Numeric(14, 2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14, 2), default=0)
    vat_amount            = db.Column(db.Numeric(14, 2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14, 2), default=0)
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)
    created_by            = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('purchase_requests', lazy=True))

    def to_dict(self):
        return {
            'id': self.purchase_request_id,
            'purchase_request_id': self.purchase_request_id,
            'doc_no': self.doc_no or '', 'requester': self.requester or '',
            'requester_name': self.requester_name or '', 'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'status': self.status,
            'posting_date':  str(self.posting_date)  if self.posting_date  else '',
            'valid_until':   str(self.valid_until)   if self.valid_until   else '',
            'document_date': str(self.document_date) if self.document_date else '',
            'required_date': str(self.required_date) if self.required_date else '',
            'remarks': self.remarks or '', 'approved_by': self.approved_by or '',
            'total_before_discount': float(self.total_before_discount or 0),
            'total_discount': float(self.total_discount or 0),
            'total_freight':  float(self.total_freight  or 0),
            'total_excl_vat': float(self.total_excl_vat or 0),
            'vat_amount':     float(self.vat_amount     or 0),
            'total_incl_vat': float(self.total_incl_vat or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 1L. PURCHASE REQUEST LINE ITEMS
#      PK: purchase_request_line_item_id
#      FK: purchase_request_id → purchase_requests
# ─────────────────────────────────────────────────────────────────
class PurchaseRequestLineItem(db.Model):
    __tablename__ = 'purchase_request_line_items'
    purchase_request_line_item_id = db.Column(db.Integer, primary_key=True)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_requests.purchase_request_id', ondelete='CASCADE'), nullable=False)
    line_number   = db.Column(db.Integer, nullable=False, default=1)
    item_code     = db.Column(db.String(50))
    description   = db.Column(db.String(500))
    required_date = db.Column(db.Date)
    warehouse     = db.Column(db.String(150))
    uom           = db.Column(db.String(20),    nullable=False, default='unit')
    quantity      = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    rate          = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    discount      = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    freight       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    taxable       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tax_code      = db.Column(db.String(20),    nullable=False, default='VAT15')
    tax_amount    = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total         = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    purchase_request = db.relationship('PurchaseRequest', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.purchase_request_line_item_id,
            'purchase_request_line_item_id': self.purchase_request_line_item_id,
            'purchase_request_id': self.purchase_request_id,
            'line_number': self.line_number,
            'item_code': self.item_code or '', 'item_desc': self.description or '',
            'description': self.description or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '', 'uom': self.uom,
            'quantity': float(self.quantity or 0), 'rate': float(self.rate or 0),
            'discount': float(self.discount or 0), 'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0), 'tax_code': self.tax_code,
            'tax_amount': float(self.tax_amount or 0), 'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 2. PURCHASE QUOTATION
#      FK: purchase_request_id → purchase_requests
# ─────────────────────────────────────────────────────────────────
class PurchaseQuotation(db.Model):
    __tablename__ = 'purchase_quotations'
    purchase_quotation_id = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    purchase_request_id   = db.Column(db.Integer, db.ForeignKey('purchase_requests.purchase_request_id'))
    requester             = db.Column(db.String(150))
    requester_name        = db.Column(db.String(200))
    vendor_id             = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    status                = db.Column(db.String(20), default='Open')
    posting_date          = db.Column(db.Date)
    valid_until           = db.Column(db.Date)
    document_date         = db.Column(db.Date)
    required_date         = db.Column(db.Date)
    remarks               = db.Column(db.Text)
    approved_by           = db.Column(db.String(150))
    total_before_discount = db.Column(db.Numeric(14, 2), default=0)
    total_discount        = db.Column(db.Numeric(14, 2), default=0)
    total_freight         = db.Column(db.Numeric(14, 2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14, 2), default=0)
    vat_amount            = db.Column(db.Numeric(14, 2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14, 2), default=0)
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)
    created_by            = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('purchase_quotations', lazy=True))

    def to_dict(self):
        return {
            'id': self.purchase_quotation_id,
            'purchase_quotation_id': self.purchase_quotation_id,
            'doc_no': self.doc_no or '',
            'purchase_request_id': self.purchase_request_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'status': self.status,
            'posting_date':  str(self.posting_date)  if self.posting_date  else '',
            'valid_until':   str(self.valid_until)   if self.valid_until   else '',
            'document_date': str(self.document_date) if self.document_date else '',
            'required_date': str(self.required_date) if self.required_date else '',
            'remarks': self.remarks or '', 'approved_by': self.approved_by or '',
            'total_before_discount': float(self.total_before_discount or 0),
            'total_discount': float(self.total_discount or 0),
            'total_freight':  float(self.total_freight  or 0),
            'total_excl_vat': float(self.total_excl_vat or 0),
            'vat_amount':     float(self.vat_amount     or 0),
            'total_incl_vat': float(self.total_incl_vat or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 2L. PURCHASE QUOTATION LINE ITEMS
#      PK: purchase_quotation_line_item_id
#      FK: purchase_quotation_id → purchase_quotations
# ─────────────────────────────────────────────────────────────────
class PurchaseQuotationLineItem(db.Model):
    __tablename__ = 'purchase_quotation_line_items'
    purchase_quotation_line_item_id = db.Column(db.Integer, primary_key=True)
    purchase_quotation_id = db.Column(db.Integer, db.ForeignKey('purchase_quotations.purchase_quotation_id', ondelete='CASCADE'), nullable=False)
    line_number   = db.Column(db.Integer, nullable=False, default=1)
    item_code     = db.Column(db.String(50))
    description   = db.Column(db.String(500))
    required_date = db.Column(db.Date)
    warehouse     = db.Column(db.String(150))
    uom           = db.Column(db.String(20),    nullable=False, default='unit')
    quantity      = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    rate          = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    discount      = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    freight       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    taxable       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tax_code      = db.Column(db.String(20),    nullable=False, default='VAT15')
    tax_amount    = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total         = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    purchase_quotation = db.relationship('PurchaseQuotation', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.purchase_quotation_line_item_id,
            'purchase_quotation_line_item_id': self.purchase_quotation_line_item_id,
            'purchase_quotation_id': self.purchase_quotation_id,
            'line_number': self.line_number,
            'item_code': self.item_code or '', 'item_desc': self.description or '',
            'description': self.description or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '', 'uom': self.uom,
            'quantity': float(self.quantity or 0), 'rate': float(self.rate or 0),
            'discount': float(self.discount or 0), 'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0), 'tax_code': self.tax_code,
            'tax_amount': float(self.tax_amount or 0), 'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 3. PURCHASE ORDER
#      FK: purchase_quotation_id → purchase_quotations
# ─────────────────────────────────────────────────────────────────
class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    purchase_order_id     = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    purchase_quotation_id = db.Column(db.Integer, db.ForeignKey('purchase_quotations.purchase_quotation_id'))
    vendor_id             = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    vendor_ref_no         = db.Column(db.String(100))
    status                = db.Column(db.String(20), default='Open')
    posting_date          = db.Column(db.Date)
    delivery_date         = db.Column(db.Date)
    document_date         = db.Column(db.Date)
    total_before_discount = db.Column(db.Numeric(14, 2), default=0)
    total_discount        = db.Column(db.Numeric(14, 2), default=0)
    total_freight         = db.Column(db.Numeric(14, 2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14, 2), default=0)
    vat_amount            = db.Column(db.Numeric(14, 2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14, 2), default=0)
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)
    created_by            = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('purchase_orders', lazy=True))

    def to_dict(self):
        return {
            'id': self.purchase_order_id,
            'purchase_order_id': self.purchase_order_id,
            'doc_no': self.doc_no or '',
            'purchase_quotation_id': self.purchase_quotation_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'vendor_ref_no': self.vendor_ref_no or '', 'status': self.status,
            'posting_date':  str(self.posting_date)  if self.posting_date  else '',
            'delivery_date': str(self.delivery_date) if self.delivery_date else '',
            'document_date': str(self.document_date) if self.document_date else '',
            'total_before_discount': float(self.total_before_discount or 0),
            'total_discount': float(self.total_discount or 0),
            'total_freight':  float(self.total_freight  or 0),
            'total_excl_vat': float(self.total_excl_vat or 0),
            'vat_amount':     float(self.vat_amount     or 0),
            'total_incl_vat': float(self.total_incl_vat or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 3L. PURCHASE ORDER LINE ITEMS
#      PK: purchase_order_line_item_id
#      FK: purchase_order_id → purchase_orders
# ─────────────────────────────────────────────────────────────────
class PurchaseOrderLineItem(db.Model):
    __tablename__ = 'purchase_order_line_items'
    purchase_order_line_item_id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.purchase_order_id', ondelete='CASCADE'), nullable=False)
    line_number   = db.Column(db.Integer, nullable=False, default=1)
    item_code     = db.Column(db.String(50))
    description   = db.Column(db.String(500))
    required_date = db.Column(db.Date)
    warehouse     = db.Column(db.String(150))
    uom           = db.Column(db.String(20),    nullable=False, default='unit')
    quantity      = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    rate          = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    discount      = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    freight       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    taxable       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tax_code      = db.Column(db.String(20),    nullable=False, default='VAT15')
    tax_amount    = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total         = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    purchase_order = db.relationship('PurchaseOrder', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.purchase_order_line_item_id,
            'purchase_order_line_item_id': self.purchase_order_line_item_id,
            'purchase_order_id': self.purchase_order_id,
            'line_number': self.line_number,
            'item_code': self.item_code or '', 'item_desc': self.description or '',
            'description': self.description or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '', 'uom': self.uom,
            'quantity': float(self.quantity or 0), 'rate': float(self.rate or 0),
            'discount': float(self.discount or 0), 'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0), 'tax_code': self.tax_code,
            'tax_amount': float(self.tax_amount or 0), 'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 4. GOODS RECEIPT NOTE
#      FK: purchase_order_id → purchase_orders
# ─────────────────────────────────────────────────────────────────
class GoodsReceiptNote(db.Model):
    __tablename__ = 'goods_receipt_notes'
    goods_receipt_note_id = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    purchase_order_id     = db.Column(db.Integer, db.ForeignKey('purchase_orders.purchase_order_id'))
    vendor_id             = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    contact_person        = db.Column(db.String(150))
    vendor_ref_no         = db.Column(db.String(100))
    status                = db.Column(db.String(20), default='Open')
    posting_date          = db.Column(db.Date)
    delivery_date         = db.Column(db.Date)
    document_date         = db.Column(db.Date)
    total_before_discount = db.Column(db.Numeric(14, 2), default=0)
    total_discount        = db.Column(db.Numeric(14, 2), default=0)
    total_freight         = db.Column(db.Numeric(14, 2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14, 2), default=0)
    vat_amount            = db.Column(db.Numeric(14, 2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14, 2), default=0)
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)
    created_by            = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('grns', lazy=True))

    def to_dict(self):
        return {
            'id': self.goods_receipt_note_id,
            'goods_receipt_note_id': self.goods_receipt_note_id,
            'doc_no': self.doc_no or '',
            'purchase_order_id': self.purchase_order_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'vendor_ref_no': self.vendor_ref_no or '',
            'contact_person': self.contact_person or '', 'status': self.status,
            'posting_date':  str(self.posting_date)  if self.posting_date  else '',
            'delivery_date': str(self.delivery_date) if self.delivery_date else '',
            'document_date': str(self.document_date) if self.document_date else '',
            'total_before_discount': float(self.total_before_discount or 0),
            'total_discount': float(self.total_discount or 0),
            'total_freight':  float(self.total_freight  or 0),
            'total_excl_vat': float(self.total_excl_vat or 0),
            'vat_amount':     float(self.vat_amount     or 0),
            'total_incl_vat': float(self.total_incl_vat or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 4L. GOODS RECEIPT LINE ITEMS
#      PK: goods_receipt_line_item_id
#      FK: goods_receipt_note_id → goods_receipt_notes
# ─────────────────────────────────────────────────────────────────
class GoodsReceiptLineItem(db.Model):
    __tablename__ = 'goods_receipt_line_items'
    goods_receipt_line_item_id = db.Column(db.Integer, primary_key=True)
    goods_receipt_note_id = db.Column(db.Integer, db.ForeignKey('goods_receipt_notes.goods_receipt_note_id', ondelete='CASCADE'), nullable=False)
    line_number   = db.Column(db.Integer, nullable=False, default=1)
    item_code     = db.Column(db.String(50))
    description   = db.Column(db.String(500))
    required_date = db.Column(db.Date)
    warehouse     = db.Column(db.String(150))
    uom           = db.Column(db.String(20),    nullable=False, default='unit')
    quantity      = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    rate          = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    discount      = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    freight       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    taxable       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tax_code      = db.Column(db.String(20),    nullable=False, default='VAT15')
    tax_amount    = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total         = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    goods_receipt_note = db.relationship('GoodsReceiptNote', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.goods_receipt_line_item_id,
            'goods_receipt_line_item_id': self.goods_receipt_line_item_id,
            'goods_receipt_note_id': self.goods_receipt_note_id,
            'line_number': self.line_number,
            'item_code': self.item_code or '', 'item_desc': self.description or '',
            'description': self.description or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '', 'uom': self.uom,
            'quantity': float(self.quantity or 0), 'rate': float(self.rate or 0),
            'discount': float(self.discount or 0), 'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0), 'tax_code': self.tax_code,
            'tax_amount': float(self.tax_amount or 0), 'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 5. PURCHASE INVOICE
#      FK: purchase_order_id → purchase_orders
#      FK: goods_receipt_note_id → goods_receipt_notes
# ─────────────────────────────────────────────────────────────────
class PurchaseInvoice(db.Model):
    __tablename__ = 'purchase_invoices'
    purchase_invoice_id   = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    purchase_order_id     = db.Column(db.Integer, db.ForeignKey('purchase_orders.purchase_order_id'))
    goods_receipt_note_id = db.Column(db.Integer, db.ForeignKey('goods_receipt_notes.goods_receipt_note_id'))
    vendor_id             = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    vendor_ref_no         = db.Column(db.String(100))
    status                = db.Column(db.String(20), default='Open')
    posting_date          = db.Column(db.Date)
    delivery_date         = db.Column(db.Date)
    document_date         = db.Column(db.Date)
    total_before_discount = db.Column(db.Numeric(14, 2), default=0)
    total_discount        = db.Column(db.Numeric(14, 2), default=0)
    total_freight         = db.Column(db.Numeric(14, 2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14, 2), default=0)
    vat_amount            = db.Column(db.Numeric(14, 2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14, 2), default=0)
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)
    created_by            = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('purchase_invoices', lazy=True))

    def to_dict(self):
        return {
            'id': self.purchase_invoice_id,
            'purchase_invoice_id': self.purchase_invoice_id,
            'doc_no': self.doc_no or '',
            'purchase_order_id': self.purchase_order_id,
            'goods_receipt_note_id': self.goods_receipt_note_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'vendor_ref_no': self.vendor_ref_no or '', 'status': self.status,
            'posting_date':  str(self.posting_date)  if self.posting_date  else '',
            'delivery_date': str(self.delivery_date) if self.delivery_date else '',
            'document_date': str(self.document_date) if self.document_date else '',
            'total_before_discount': float(self.total_before_discount or 0),
            'total_discount': float(self.total_discount or 0),
            'total_freight':  float(self.total_freight  or 0),
            'total_excl_vat': float(self.total_excl_vat or 0),
            'vat_amount':     float(self.vat_amount     or 0),
            'total_incl_vat': float(self.total_incl_vat or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 5L. PURCHASE INVOICE LINE ITEMS
#      PK: purchase_invoice_line_item_id
#      FK: purchase_invoice_id → purchase_invoices
# ─────────────────────────────────────────────────────────────────
class PurchaseInvoiceLineItem(db.Model):
    __tablename__ = 'purchase_invoice_line_items'
    purchase_invoice_line_item_id = db.Column(db.Integer, primary_key=True)
    purchase_invoice_id = db.Column(db.Integer, db.ForeignKey('purchase_invoices.purchase_invoice_id', ondelete='CASCADE'), nullable=False)
    line_number   = db.Column(db.Integer, nullable=False, default=1)
    item_code     = db.Column(db.String(50))
    description   = db.Column(db.String(500))
    required_date = db.Column(db.Date)
    warehouse     = db.Column(db.String(150))
    uom           = db.Column(db.String(20),    nullable=False, default='unit')
    quantity      = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    rate          = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    discount      = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    freight       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    taxable       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tax_code      = db.Column(db.String(20),    nullable=False, default='VAT15')
    tax_amount    = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total         = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    purchase_invoice = db.relationship('PurchaseInvoice', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.purchase_invoice_line_item_id,
            'purchase_invoice_line_item_id': self.purchase_invoice_line_item_id,
            'purchase_invoice_id': self.purchase_invoice_id,
            'line_number': self.line_number,
            'item_code': self.item_code or '', 'item_desc': self.description or '',
            'description': self.description or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '', 'uom': self.uom,
            'quantity': float(self.quantity or 0), 'rate': float(self.rate or 0),
            'discount': float(self.discount or 0), 'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0), 'tax_code': self.tax_code,
            'tax_amount': float(self.tax_amount or 0), 'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 6. GOODS RETURN REQUEST
#      FK: purchase_invoice_id → purchase_invoices
# ─────────────────────────────────────────────────────────────────
class GoodsReturnRequest(db.Model):
    __tablename__ = 'goods_return_requests'
    goods_return_request_id = db.Column(db.Integer, primary_key=True)
    doc_no                  = db.Column(db.String(20), unique=True)
    purchase_invoice_id     = db.Column(db.Integer, db.ForeignKey('purchase_invoices.purchase_invoice_id'))
    vendor_id               = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    contact_person          = db.Column(db.String(150))
    vendor_ref_no           = db.Column(db.String(100))
    status                  = db.Column(db.String(20), default='Open')
    posting_date            = db.Column(db.Date)
    delivery_date           = db.Column(db.Date)
    document_date           = db.Column(db.Date)
    total_before_discount   = db.Column(db.Numeric(14, 2), default=0)
    total_discount          = db.Column(db.Numeric(14, 2), default=0)
    total_freight           = db.Column(db.Numeric(14, 2), default=0)
    total_excl_vat          = db.Column(db.Numeric(14, 2), default=0)
    vat_amount              = db.Column(db.Numeric(14, 2), default=0)
    total_incl_vat          = db.Column(db.Numeric(14, 2), default=0)
    created_at              = db.Column(db.DateTime, default=datetime.utcnow)
    created_by              = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('grrs', lazy=True))

    def to_dict(self):
        return {
            'id': self.goods_return_request_id,
            'goods_return_request_id': self.goods_return_request_id,
            'doc_no': self.doc_no or '',
            'purchase_invoice_id': self.purchase_invoice_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'vendor_ref_no': self.vendor_ref_no or '',
            'contact_person': self.contact_person or '', 'status': self.status,
            'posting_date':  str(self.posting_date)  if self.posting_date  else '',
            'delivery_date': str(self.delivery_date) if self.delivery_date else '',
            'document_date': str(self.document_date) if self.document_date else '',
            'total_before_discount': float(self.total_before_discount or 0),
            'total_discount': float(self.total_discount or 0),
            'total_freight':  float(self.total_freight  or 0),
            'total_excl_vat': float(self.total_excl_vat or 0),
            'vat_amount':     float(self.vat_amount     or 0),
            'total_incl_vat': float(self.total_incl_vat or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 6L. GOODS RETURN LINE ITEMS
#      PK: goods_return_line_item_id
#      FK: goods_return_request_id → goods_return_requests
# ─────────────────────────────────────────────────────────────────
class GoodsReturnLineItem(db.Model):
    __tablename__ = 'goods_return_line_items'
    goods_return_line_item_id = db.Column(db.Integer, primary_key=True)
    goods_return_request_id = db.Column(db.Integer, db.ForeignKey('goods_return_requests.goods_return_request_id', ondelete='CASCADE'), nullable=False)
    line_number   = db.Column(db.Integer, nullable=False, default=1)
    item_code     = db.Column(db.String(50))
    description   = db.Column(db.String(500))
    required_date = db.Column(db.Date)
    warehouse     = db.Column(db.String(150))
    uom           = db.Column(db.String(20),    nullable=False, default='unit')
    quantity      = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    rate          = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    discount      = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    freight       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    taxable       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tax_code      = db.Column(db.String(20),    nullable=False, default='VAT15')
    tax_amount    = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total         = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    goods_return_request = db.relationship('GoodsReturnRequest', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.goods_return_line_item_id,
            'goods_return_line_item_id': self.goods_return_line_item_id,
            'goods_return_request_id': self.goods_return_request_id,
            'line_number': self.line_number,
            'item_code': self.item_code or '', 'item_desc': self.description or '',
            'description': self.description or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '', 'uom': self.uom,
            'quantity': float(self.quantity or 0), 'rate': float(self.rate or 0),
            'discount': float(self.discount or 0), 'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0), 'tax_code': self.tax_code,
            'tax_amount': float(self.tax_amount or 0), 'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 7. PURCHASE DEBIT MEMO
#      FK: goods_return_request_id → goods_return_requests
#      FK: purchase_invoice_id     → purchase_invoices
# ─────────────────────────────────────────────────────────────────
class PurchaseDebitMemo(db.Model):
    __tablename__ = 'purchase_debit_memos'
    purchase_debit_memo_id  = db.Column(db.Integer, primary_key=True)
    doc_no                  = db.Column(db.String(20), unique=True)
    goods_return_request_id = db.Column(db.Integer, db.ForeignKey('goods_return_requests.goods_return_request_id'))
    purchase_invoice_id     = db.Column(db.Integer, db.ForeignKey('purchase_invoices.purchase_invoice_id'))
    vendor_id               = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    contact_person          = db.Column(db.String(150))
    vendor_ref_no           = db.Column(db.String(100))
    status                  = db.Column(db.String(20), default='Open')
    posting_date            = db.Column(db.Date)
    delivery_date           = db.Column(db.Date)
    document_date           = db.Column(db.Date)
    total_before_discount   = db.Column(db.Numeric(14, 2), default=0)
    total_discount          = db.Column(db.Numeric(14, 2), default=0)
    total_freight           = db.Column(db.Numeric(14, 2), default=0)
    total_excl_vat          = db.Column(db.Numeric(14, 2), default=0)
    vat_amount              = db.Column(db.Numeric(14, 2), default=0)
    total_incl_vat          = db.Column(db.Numeric(14, 2), default=0)
    created_at              = db.Column(db.DateTime, default=datetime.utcnow)
    created_by              = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('pdms', lazy=True))

    def to_dict(self):
        return {
            'id': self.purchase_debit_memo_id,
            'purchase_debit_memo_id': self.purchase_debit_memo_id,
            'doc_no': self.doc_no or '',
            'goods_return_request_id': self.goods_return_request_id,
            'purchase_invoice_id': self.purchase_invoice_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'vendor_ref_no': self.vendor_ref_no or '',
            'contact_person': self.contact_person or '', 'status': self.status,
            'posting_date':  str(self.posting_date)  if self.posting_date  else '',
            'delivery_date': str(self.delivery_date) if self.delivery_date else '',
            'document_date': str(self.document_date) if self.document_date else '',
            'total_before_discount': float(self.total_before_discount or 0),
            'total_discount': float(self.total_discount or 0),
            'total_freight':  float(self.total_freight  or 0),
            'total_excl_vat': float(self.total_excl_vat or 0),
            'vat_amount':     float(self.vat_amount     or 0),
            'total_incl_vat': float(self.total_incl_vat or 0),
        }


# ─────────────────────────────────────────────────────────────────
# 7L. PURCHASE DEBIT MEMO LINE ITEMS
#      PK: purchase_debit_memo_line_item_id
#      FK: purchase_debit_memo_id → purchase_debit_memos
# ─────────────────────────────────────────────────────────────────
class PurchaseDebitMemoLineItem(db.Model):
    __tablename__ = 'purchase_debit_memo_line_items'
    purchase_debit_memo_line_item_id = db.Column(db.Integer, primary_key=True)
    purchase_debit_memo_id = db.Column(db.Integer, db.ForeignKey('purchase_debit_memos.purchase_debit_memo_id', ondelete='CASCADE'), nullable=False)
    line_number   = db.Column(db.Integer, nullable=False, default=1)
    item_code     = db.Column(db.String(50))
    description   = db.Column(db.String(500))
    required_date = db.Column(db.Date)
    warehouse     = db.Column(db.String(150))
    uom           = db.Column(db.String(20),    nullable=False, default='unit')
    quantity      = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    rate          = db.Column(db.Numeric(14, 4), nullable=False, default=0)
    discount      = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    freight       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    taxable       = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tax_code      = db.Column(db.String(20),    nullable=False, default='VAT15')
    tax_amount    = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total         = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    purchase_debit_memo = db.relationship('PurchaseDebitMemo', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.purchase_debit_memo_line_item_id,
            'purchase_debit_memo_line_item_id': self.purchase_debit_memo_line_item_id,
            'purchase_debit_memo_id': self.purchase_debit_memo_id,
            'line_number': self.line_number,
            'item_code': self.item_code or '', 'item_desc': self.description or '',
            'description': self.description or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '', 'uom': self.uom,
            'quantity': float(self.quantity or 0), 'rate': float(self.rate or 0),
            'discount': float(self.discount or 0), 'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0), 'tax_code': self.tax_code,
            'tax_amount': float(self.tax_amount or 0), 'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────────────────────────
# PURCHASE ATTACHMENTS  (shared — doc_type + doc_id)
# ─────────────────────────────────────────────────────────────────
class PurchaseAttachment(db.Model):
    __tablename__ = 'purchase_attachments'
    id          = db.Column(db.Integer, primary_key=True)
    doc_type    = db.Column(db.String(10), nullable=False)
    doc_id      = db.Column(db.Integer,    nullable=False)
    filename    = db.Column(db.String(255), nullable=False)
    filepath    = db.Column(db.String(500), nullable=False)
    file_size   = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    def to_dict(self):
        return {
            'id': self.id, 'doc_type': self.doc_type, 'doc_id': self.doc_id,
            'filename': self.filename, 'filepath': self.filepath,
            'file_size': self.file_size or 0,
        }


# ─────────────────────────────────────────────────────────────────
# ITEM MASTER
# ─────────────────────────────────────────────────────────────────
class ItemCategory(db.Model):
    __tablename__ = 'item_categories'
    id         = db.Column(db.Integer, primary_key=True)
    name_en    = db.Column(db.String(100), nullable=False)
    name_ar    = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'name_en': self.name_en, 'name_ar': self.name_ar or ''}


class ItemSubCategory(db.Model):
    __tablename__ = 'item_sub_categories'
    id          = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('item_categories.id'), nullable=False)
    name_en     = db.Column(db.String(100), nullable=False)
    name_ar     = db.Column(db.String(100))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('ItemCategory', backref=db.backref('sub_categories', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {'id': self.id, 'category_id': self.category_id,
                'name_en': self.name_en, 'name_ar': self.name_ar or ''}


class TaxCategory(db.Model):
    __tablename__ = 'tax_categories'
    id      = db.Column(db.Integer, primary_key=True)
    name_en = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100))
    rate    = db.Column(db.Numeric(5, 2), default=0)

    def to_dict(self):
        return {'id': self.id, 'name_en': self.name_en,
                'name_ar': self.name_ar or '', 'rate': float(self.rate or 0)}


class ItemMaster(db.Model):
    __tablename__ = 'item_master'
    id                 = db.Column(db.Integer, primary_key=True)
    item_code          = db.Column(db.String(50), unique=True, nullable=False)
    article_no         = db.Column(db.String(50))
    name_en            = db.Column(db.String(200), nullable=False)
    name_ar            = db.Column(db.String(200))
    print_name         = db.Column(db.String(200))
    uom                = db.Column(db.String(20), default='unit')
    item_desc          = db.Column(db.Text)
    category_id        = db.Column(db.Integer, db.ForeignKey('item_categories.id'))
    sub_category_id    = db.Column(db.Integer, db.ForeignKey('item_sub_categories.id'))
    tax_category_id    = db.Column(db.Integer, db.ForeignKey('tax_categories.id'))
    vendor_id          = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    main_rate          = db.Column(db.Numeric(14, 2), default=0)
    last_purchase_rate = db.Column(db.Numeric(14, 2), default=0)
    retail_rate        = db.Column(db.Numeric(14, 2), default=0)
    wholesale_rate     = db.Column(db.Numeric(14, 2), default=0)
    special_rate       = db.Column(db.Numeric(14, 2), default=0)
    mrp                = db.Column(db.Numeric(14, 2), default=0)
    minimum_sp         = db.Column(db.Numeric(14, 2), default=0)
    is_active          = db.Column(db.Boolean, default=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    created_by         = db.Column(db.Integer, db.ForeignKey('users.id'))

    category     = db.relationship('ItemCategory',    backref=db.backref('items', lazy=True))
    sub_category = db.relationship('ItemSubCategory', backref=db.backref('items', lazy=True))
    tax_category = db.relationship('TaxCategory',     backref=db.backref('items', lazy=True))
    vendor       = db.relationship('VendorMaster',    backref=db.backref('items',  lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'item_code': self.item_code,
            'article_no': self.article_no or '',
            'name_en': self.name_en, 'name_ar': self.name_ar or '',
            'print_name': self.print_name or '',
            'uom': self.uom or 'unit', 'item_desc': self.item_desc or '',
            'category_id': self.category_id,
            'category_name': self.category.name_en if self.category else '',
            'sub_category_id': self.sub_category_id,
            'sub_category_name': self.sub_category.name_en if self.sub_category else '',
            'tax_category_id': self.tax_category_id,
            'tax_rate': float(self.tax_category.rate) if self.tax_category else 15,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'main_rate':          float(self.main_rate          or 0),
            'last_purchase_rate': float(self.last_purchase_rate or 0),
            'retail_rate':        float(self.retail_rate        or 0),
            'is_active': self.is_active,
        }