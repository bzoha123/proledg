from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='staff')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'


class Seller(db.Model):
    __tablename__ = 'sellers'
    id = db.Column(db.Integer, primary_key=True)
    seller_code = db.Column(db.String(20), unique=True, nullable=False)

    # Basic Information (EN)
    name = db.Column(db.String(200), nullable=False)
    vat_number = db.Column(db.String(100))
    crn = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    fax = db.Column(db.String(30))
    email = db.Column(db.String(150))
    website = db.Column(db.String(200))
    report_color = db.Column(db.String(10), default='#16a34a')
    logo_path = db.Column(db.String(500))
    bg_logo_path = db.Column(db.String(500))

    # Basic Information (AR)
    name_ar = db.Column(db.String(200))
    vat_number_ar = db.Column(db.String(100))
    crn_ar = db.Column(db.String(100))

    # Address Information (EN)
    street_name = db.Column(db.String(250))
    building_number = db.Column(db.String(50))
    additional_number = db.Column(db.String(50))
    district = db.Column(db.String(100))
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))

    # Address Information (AR)
    street_name_ar = db.Column(db.String(250))
    building_number_ar = db.Column(db.String(50))
    additional_number_ar = db.Column(db.String(50))
    district_ar = db.Column(db.String(100))
    city_ar = db.Column(db.String(100))
    postal_code_ar = db.Column(db.String(20))
    country_ar = db.Column(db.String(100))

    # Bank Information — multiple via relationship
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    banks = db.relationship('SellerBank', backref='seller', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('SellerDocument', backref='seller', lazy=True, cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='seller', lazy=True, cascade='all, delete-orphan')


class SellerBank(db.Model):
    __tablename__ = 'seller_banks'
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('sellers.id'), nullable=False)
    bank_name = db.Column(db.String(150), nullable=False)
    account_number = db.Column(db.String(50))
    branch = db.Column(db.String(100))
    swift_code = db.Column(db.String(20))
    iban = db.Column(db.String(50))
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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

    buyer = db.relationship('BuyerMaster', backref=db.backref('banks', cascade='all, delete-orphan', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'buyer_id': self.buyer_id,
            'bank_name': self.bank_name, 'account_number': self.account_number or '',
            'branch': self.branch or '', 'swift_code': self.swift_code or '',
            'iban': self.iban or '', 'is_primary': self.is_primary,
        }


class SellerDocument(db.Model):
    __tablename__ = 'seller_documents'
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('sellers.id'), nullable=False)
    document_type = db.Column(db.String(100), nullable=False)
    document_name = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    expiry_date = db.Column(db.Date)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('sellers.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='activity_logs')


class ProfessionMaster(db.Model):
    __tablename__ = 'profession_master'
    id = db.Column(db.Integer, primary_key=True)
    profession_en = db.Column(db.String(150), nullable=False)
    profession_ar = db.Column(db.String(150))
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


class BuyerMaster(db.Model):
    __tablename__ = 'buyers'
    id             = db.Column(db.Integer, primary_key=True)
    buyer_code     = db.Column(db.String(20), unique=True)
    buyer_name_en  = db.Column(db.String(200), nullable=False)
    buyer_name_ar  = db.Column(db.String(200))
    vat_number     = db.Column(db.String(50))
    crn            = db.Column(db.String(50))
    phone          = db.Column(db.String(30))
    fax            = db.Column(db.String(30))
    email          = db.Column(db.String(120))
    website        = db.Column(db.String(200))
    report_color   = db.Column(db.String(10), default='#2563eb')
    # Address
    street_name    = db.Column(db.String(200))
    street_name_ar = db.Column(db.String(200))
    building_number= db.Column(db.String(50))
    building_number_ar = db.Column(db.String(50))
    additional_number  = db.Column(db.String(50))
    additional_number_ar= db.Column(db.String(50))
    postal_code    = db.Column(db.String(20))
    postal_code_ar = db.Column(db.String(20))
    country        = db.Column(db.String(100), default='Saudi Arabia')
    country_ar     = db.Column(db.String(100))
    city           = db.Column(db.String(100))
    city_ar        = db.Column(db.String(100))
    district       = db.Column(db.String(100))
    district_ar    = db.Column(db.String(100))
    # Status
    status         = db.Column(db.String(20), default='active')
    is_active      = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by     = db.Column(db.Integer, db.ForeignKey('users.id'))

    def to_dict(self):
        return {
            'id': self.id, 'buyer_code': self.buyer_code or '',
            'name': self.buyer_name_en, 'name_ar': self.buyer_name_ar or '',
            'vat_number': self.vat_number or '', 'crn': self.crn or '',
            'phone': self.phone or '', 'email': self.email or '',
            'status': self.status or 'active', 'is_active': self.is_active,
            'report_color': self.report_color or '#2563eb',
        }


class BankMaster(db.Model):
    __tablename__ = 'bank_master'
    id = db.Column(db.Integer, primary_key=True)
    bank_name_en = db.Column(db.String(150), nullable=False)
    bank_name_ar = db.Column(db.String(150))
    swift_code   = db.Column(db.String(20))
    country      = db.Column(db.String(100), default='Saudi Arabia')
    is_active    = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    employee_code    = db.Column(db.String(20), unique=True, nullable=False)
    is_active        = db.Column(db.Boolean, default=True)
    is_muslim        = db.Column(db.Boolean, default=False)

    # Personal Information
    name             = db.Column(db.String(255), nullable=False)
    name_ar          = db.Column(db.String(255))
    nationality      = db.Column(db.String(100))
    nationality_ar   = db.Column(db.String(100))
    arrival_date     = db.Column(db.Date)
    birth_date       = db.Column(db.Date)
    passport_number  = db.Column(db.String(50))
    passport_expiry  = db.Column(db.Date)
    entry_number     = db.Column(db.String(50))
    iqama_number     = db.Column(db.String(50))
    iqama_expiry     = db.Column(db.Date)
    profession       = db.Column(db.String(100))
    profession_ar    = db.Column(db.String(100))
    employee_type    = db.Column(db.String(20))   # skilled / non_skilled
    education        = db.Column(db.String(100))
    education_ar     = db.Column(db.String(100))
    kafeel_name      = db.Column(db.String(150))
    kafeel_name_ar   = db.Column(db.String(150))
    kafeel_reference = db.Column(db.String(100))

    # Document Upload
    document_path    = db.Column(db.String(500))

    # Contact Information
    mobile           = db.Column(db.String(30))
    address          = db.Column(db.String(250))
    address_ar       = db.Column(db.String(250))
    email            = db.Column(db.String(150))
    home_city        = db.Column(db.String(100))
    home_city_ar     = db.Column(db.String(100))
    employee_reference = db.Column(db.String(100))

    # Salary Information
    po_rate          = db.Column(db.Float, default=0)
    po_rate_unit     = db.Column(db.String(10), default='hour')  # hour/day/month
    po_number        = db.Column(db.String(50))
    salary_type      = db.Column(db.String(20), default='salary')  # salary/azad/kafalat
    basic_salary     = db.Column(db.Float, default=0)
    total_allowances = db.Column(db.Float, default=0)   # sum of EmployeeAllowance rows
    net_salary       = db.Column(db.Float, default=0)   # basic_salary + total_allowances
    working_hours    = db.Column(db.Float, default=8)
    overtime_ratio   = db.Column(db.Float, default=1.5)  # e.g. 1.5x
    overtime_rate    = db.Column(db.Float, default=0)
    kafalat_number   = db.Column(db.String(50))          # kafalat reference number

    # Work Information
    joining_date     = db.Column(db.Date)
    end_date_work    = db.Column(db.Date)
    work_status      = db.Column(db.String(20), default='active')
    work_month       = db.Column(db.String(20))
    company          = db.Column(db.String(150))
    company_ar       = db.Column(db.String(150))
    department       = db.Column(db.String(100))
    department_ar    = db.Column(db.String(100))
    section          = db.Column(db.String(100))
    section_ar       = db.Column(db.String(100))
    shift_type       = db.Column(db.String(20), default='day')  # day/night/rotating
    forman           = db.Column(db.String(150))
    forman_ar        = db.Column(db.String(150))

    # Hostel Information
    hostel_name      = db.Column(db.String(150))
    hostel_name_ar   = db.Column(db.String(150))
    room_number      = db.Column(db.String(30))
    hostel_location  = db.Column(db.String(200))
    hostel_location_ar = db.Column(db.String(200))

    # Banking Information
    bank_name        = db.Column(db.String(150))
    bank_name_ar     = db.Column(db.String(150))
    bank_branch      = db.Column(db.String(150))
    bank_branch_ar   = db.Column(db.String(150))
    swift_code       = db.Column(db.String(20))
    account_number   = db.Column(db.String(50))
    iban             = db.Column(db.String(50))

    # Office Use
    crn              = db.Column(db.String(100))
    crn_ar           = db.Column(db.String(100))
    insurance_company = db.Column(db.String(150))
    insurance_company_ar = db.Column(db.String(150))
    insurance_expiry = db.Column(db.Date)
    labour_office    = db.Column(db.String(100))
    passport_location = db.Column(db.String(10), default='IN')  # IN/OUT
    # New fields
    kafeel_reference_ar = db.Column(db.String(100))
    employee_reference_ar = db.Column(db.String(100))
    document_type    = db.Column(db.String(50))   # id_card, passport, etc.
    buyer_id         = db.Column(db.Integer, db.ForeignKey('buyers.id'), nullable=True)
    allowances       = db.Column(db.Text)          # JSON list of allowances
    auto_code        = db.Column(db.Boolean, default=True)

    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'))


class EmployeeAllowance(db.Model):
    """One allowance row per employee per allowance type. Unique per (employee, type)."""
    __tablename__ = 'employee_allowances'
    __table_args__ = (db.UniqueConstraint('employee_id', 'allowance_type_id',
                                          name='uq_emp_allow_type'),)

    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    allowance_type_id = db.Column(db.Integer, db.ForeignKey('allowance_types.id'), nullable=True)
    name              = db.Column(db.String(150))  # kept for backward compat
    name_ar           = db.Column(db.String(150))
    amount            = db.Column(db.Float, default=0, nullable=False)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee          = db.relationship('Employee', backref=db.backref('allowance_rows', cascade='all, delete-orphan', lazy='dynamic'))
    allowance_type    = db.relationship('AllowanceType', backref='employee_allowances')

    def to_dict(self):
        at = self.allowance_type
        return {
            'id':                self.id,
            'employee_id':       self.employee_id,
            'allowance_type_id': self.allowance_type_id,
            'allowance_code':    at.allowance_code if at else '',
            'name':              at.allowance_name_en if at else (self.name or ''),
            'name_ar':           at.allowance_name_ar if at else (self.name_ar or ''),
            'amount':            self.amount,
            'created_at':        self.created_at.strftime('%Y-%m-%d') if self.created_at else '',
        }


class WorkAllocation(db.Model):
    __tablename__ = 'work_allocations'
    id             = db.Column(db.Integer, primary_key=True)
    employee_id    = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    status         = db.Column(db.String(20), default='active')   # active / inactive
    month          = db.Column(db.String(10))                      # e.g. Jan/25
    company        = db.Column(db.String(150))
    company_ar     = db.Column(db.String(150))
    department     = db.Column(db.String(100))
    department_ar  = db.Column(db.String(100))
    section        = db.Column(db.String(100))
    section_ar     = db.Column(db.String(100))
    shift_type     = db.Column(db.String(30))                      # day / night / rotating
    buyer_id       = db.Column(db.Integer, db.ForeignKey('buyers.id'), nullable=True)
    joining_date   = db.Column(db.Date)
    end_date       = db.Column(db.Date)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by     = db.Column(db.Integer, db.ForeignKey('users.id'))

    employee = db.relationship('Employee', backref=db.backref('work_allocations', lazy=True))
    buyer    = db.relationship('BuyerMaster', backref=db.backref('work_allocations', lazy=True), foreign_keys=[buyer_id])

    def to_dict(self):
        e = self.employee
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_code': e.employee_code if e else '',
            'name': e.name if e else '',
            'name_ar': e.name_ar if e else '',
            'nationality': e.nationality if e else '',
            'passport_number': e.passport_number if e else '',
            'iqama_number': e.iqama_number if e else '',
            'profession': e.profession if e else '',
            'kafeel_name': e.kafeel_name if e else '',
            'status': self.status or 'active',
            'month': self.month or '',
            'company': self.company or '',
            'company_ar': self.company_ar or '',
            'department': self.department or '',
            'department_ar': self.department_ar or '',
            'section': self.section or '',
            'section_ar': self.section_ar or '',
            'shift_type': self.shift_type or '',
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
            'joining_date': self.joining_date.strftime('%Y-%m-%d') if self.joining_date else '',
            'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else '',
        }


class AllowanceType(db.Model):
    """Master list of allowance types (Housing, Transport, Food, etc.)"""
    __tablename__ = 'allowance_types'

    id                = db.Column(db.Integer, primary_key=True)
    allowance_code    = db.Column(db.String(20), unique=True, nullable=False)
    allowance_name_en = db.Column(db.String(150), nullable=False)
    allowance_name_ar = db.Column(db.String(150))
    description       = db.Column(db.Text)
    is_active         = db.Column(db.Boolean, default=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':                self.id,
            'allowance_code':    self.allowance_code,
            'allowance_name_en': self.allowance_name_en,
            'allowance_name_ar': self.allowance_name_ar or '',
            'description':       self.description or '',
            'is_active':         self.is_active,
        }

    def __repr__(self):
        return f'<AllowanceType {self.allowance_code}>'


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id                = db.Column(db.Integer, primary_key=True)
    invoice_no        = db.Column(db.String(30), unique=True, nullable=False)  # auto: STDINV-00001
    custom_invoice_no = db.Column(db.String(50))
    dr_cr_type        = db.Column(db.String(10), default='S')   # S=Standard, D=Debit Receipt, C=Credit Note
    payment_type      = db.Column(db.String(10), default='credit')  # credit/cash
    invoice_date      = db.Column(db.Date, nullable=False)
    month             = db.Column(db.String(20))
    po_number         = db.Column(db.String(50))
    project_reference = db.Column(db.String(100))
    due_date          = db.Column(db.Date)
    period_start      = db.Column(db.Date)
    period_end        = db.Column(db.Date)
    invoice_type      = db.Column(db.String(50))
    invoice_department= db.Column(db.String(100))
    seller_id         = db.Column(db.Integer, db.ForeignKey('sellers.id'), nullable=False)
    buyer_id          = db.Column(db.Integer, db.ForeignKey('buyers.id'), nullable=False)
    gross_total       = db.Column(db.Numeric(12,2), default=0)
    total_discount    = db.Column(db.Numeric(12,2), default=0)
    vat_amount        = db.Column(db.Numeric(12,2), default=0)
    total_amount      = db.Column(db.Numeric(12,2), default=0)  # incl. VAT
    retention_pct     = db.Column(db.Numeric(5,2), default=0)
    retention_amount  = db.Column(db.Numeric(12,2), default=0)
    balance_due       = db.Column(db.Numeric(12,2), default=0)
    status            = db.Column(db.String(20), default='active')
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    created_by        = db.Column(db.Integer, db.ForeignKey('users.id'))

    seller      = db.relationship('Seller', backref=db.backref('invoices', lazy=True))
    buyer       = db.relationship('BuyerMaster', backref=db.backref('invoices', lazy=True), foreign_keys=[buyer_id])
    line_items  = db.relationship('InvoiceLineItem', backref='invoice', lazy=True, cascade='all, delete-orphan')
    payments    = db.relationship('InvoicePayment', backref='invoice', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_no': self.invoice_no,
            'custom_invoice_no': self.custom_invoice_no or '',
            'dr_cr_type': self.dr_cr_type,
            'payment_type': self.payment_type,
            'invoice_date': self.invoice_date.strftime('%d/%m/%Y') if self.invoice_date else '',
            'month': self.month or '',
            'po_number': self.po_number or '',
            'invoice_type': self.invoice_type or '',
            'invoice_department': self.invoice_department or '',
            'seller_id': self.seller_id,
            'seller_name': self.seller.name if self.seller else '',
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
            'gross_total': float(self.gross_total or 0),
            'vat_amount': float(self.vat_amount or 0),
            'total_amount': float(self.total_amount or 0),
            'balance_due': float(self.balance_due or 0),
            'retention_pct': float(self.retention_pct or 0),
            'status': self.status,
            'line_items': [li.to_dict() for li in self.line_items],
        }


class InvoiceLineItem(db.Model):
    __tablename__ = 'invoice_line_items'
    id          = db.Column(db.Integer, primary_key=True)
    invoice_id  = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    uom         = db.Column(db.String(20), default='hour')
    quantity    = db.Column(db.Numeric(10,2), default=0)
    rate        = db.Column(db.Numeric(10,2), default=0)
    discount    = db.Column(db.Numeric(10,2), default=0)
    taxable     = db.Column(db.Boolean, default=True)
    tax_rate    = db.Column(db.Numeric(5,2), default=15.00)
    tax_amount  = db.Column(db.Numeric(10,2), default=0)
    total       = db.Column(db.Numeric(10,2), default=0)

    employee = db.relationship('Employee', backref=db.backref('invoice_lines', lazy=True))

    def to_dict(self):
        e = self.employee
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'employee_id': self.employee_id,
            'employee_name': e.name if e else '',
            'employee_code': e.employee_code if e else '',
            'uom': self.uom,
            'quantity': float(self.quantity or 0),
            'rate': float(self.rate or 0),
            'discount': float(self.discount or 0),
            'taxable': self.taxable,
            'tax_rate': float(self.tax_rate or 15),
            'tax_amount': float(self.tax_amount or 0),
            'total': float(self.total or 0),
        }


class InvoicePayment(db.Model):
    __tablename__ = 'invoice_payments'
    id           = db.Column(db.Integer, primary_key=True)
    invoice_id   = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount       = db.Column(db.Numeric(12,2), nullable=False)
    method       = db.Column(db.String(50))
    reference    = db.Column(db.String(100))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'))


# ─────────────────────────────────────────────────────────────────
# VENDOR REGISTRATION
# ─────────────────────────────────────────────────────────────────
class VendorMaster(db.Model):
    __tablename__ = 'vendors'
    id               = db.Column(db.Integer, primary_key=True)
    vendor_code      = db.Column(db.String(20), unique=True)
    vendor_name_en   = db.Column(db.String(200), nullable=False)
    vendor_name_ar   = db.Column(db.String(200))
    vat_number       = db.Column(db.String(50))
    crn              = db.Column(db.String(50))
    phone            = db.Column(db.String(30))
    fax              = db.Column(db.String(30))
    email            = db.Column(db.String(120))
    website          = db.Column(db.String(200))
    contact_person   = db.Column(db.String(150))
    # Address
    street_name      = db.Column(db.String(200))
    street_name_ar   = db.Column(db.String(200))
    building_number  = db.Column(db.String(50))
    additional_number= db.Column(db.String(50))
    postal_code      = db.Column(db.String(20))
    country          = db.Column(db.String(100), default='Saudi Arabia')
    country_ar       = db.Column(db.String(100))
    city             = db.Column(db.String(100))
    city_ar          = db.Column(db.String(100))
    district         = db.Column(db.String(100))
    district_ar      = db.Column(db.String(100))
    # Bank
    bank_name        = db.Column(db.String(150))
    bank_branch      = db.Column(db.String(100))
    swift_code       = db.Column(db.String(20))
    account_number   = db.Column(db.String(50))
    iban             = db.Column(db.String(50))
    # Invoice link
    invoice_id       = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    status           = db.Column(db.String(20), default='active')
    is_active        = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'))

    invoice          = db.relationship('Invoice', backref=db.backref('vendors', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'vendor_code': self.vendor_code or '',
            'vendor_name_en': self.vendor_name_en,
            'vendor_name_ar': self.vendor_name_ar or '',
            'vat_number': self.vat_number or '', 'crn': self.crn or '',
            'phone': self.phone or '', 'email': self.email or '',
            'city': self.city or '', 'status': self.status or 'active',
            'invoice_id': self.invoice_id,
            'invoice_no': self.invoice.invoice_no if self.invoice else '',
            'contact_person': self.contact_person or '',
            'is_active': self.is_active,
        }


# ─────────────────────────────────────────────────────────────────
# PURCHASE REQUEST
# ─────────────────────────────────────────────────────────────────
class PurchaseRequest(db.Model):
    __tablename__ = 'purchase_requests'
    id             = db.Column(db.Integer, primary_key=True)
    doc_no         = db.Column(db.String(20), unique=True)      # 2026-0001
    requester      = db.Column(db.String(150))
    requester_name = db.Column(db.String(200))
    vendor_id      = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    status         = db.Column(db.String(20), default='Open')
    posting_date   = db.Column(db.Date)
    valid_until    = db.Column(db.Date)
    document_date  = db.Column(db.Date)
    required_date  = db.Column(db.Date)
    remarks        = db.Column(db.Text)
    approved_by    = db.Column(db.String(150))
    # Totals
    total_before_discount = db.Column(db.Numeric(14,2), default=0)
    total_discount        = db.Column(db.Numeric(14,2), default=0)
    total_freight         = db.Column(db.Numeric(14,2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14,2), default=0)
    vat_amount            = db.Column(db.Numeric(14,2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14,2), default=0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    created_by     = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor    = db.relationship('VendorMaster', backref=db.backref('purchase_requests', lazy=True))
    # items fetched via query in routes

    def to_dict(self):
        return {
            'id': self.id, 'doc_no': self.doc_no,
            'requester': self.requester or '', 'requester_name': self.requester_name or '',
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'status': self.status, 'posting_date': str(self.posting_date) if self.posting_date else '',
            'valid_until': str(self.valid_until) if self.valid_until else '',
            'document_date': str(self.document_date) if self.document_date else '',
            'required_date': str(self.required_date) if self.required_date else '',
            'remarks': self.remarks or '', 'approved_by': self.approved_by or '',
            'total_before_discount': float(self.total_before_discount or 0),
            'total_discount': float(self.total_discount or 0),
            'total_freight': float(self.total_freight or 0),
            'total_excl_vat': float(self.total_excl_vat or 0),
            'vat_amount': float(self.vat_amount or 0),
            'total_incl_vat': float(self.total_incl_vat or 0),
        }


# ─────────────────────────────────────────────────────────────────
# PURCHASE QUOTATION
# ─────────────────────────────────────────────────────────────────
class PurchaseQuotation(db.Model):
    __tablename__ = 'purchase_quotations'
    id             = db.Column(db.Integer, primary_key=True)
    doc_no         = db.Column(db.String(20), unique=True)
    pr_id          = db.Column(db.Integer, db.ForeignKey('purchase_requests.id'), nullable=True)
    requester      = db.Column(db.String(150))
    requester_name = db.Column(db.String(200))
    vendor_id      = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    status         = db.Column(db.String(20), default='Open')
    posting_date   = db.Column(db.Date)
    valid_until    = db.Column(db.Date)
    document_date  = db.Column(db.Date)
    required_date  = db.Column(db.Date)
    remarks        = db.Column(db.Text)
    approved_by    = db.Column(db.String(150))
    total_before_discount = db.Column(db.Numeric(14,2), default=0)
    total_discount        = db.Column(db.Numeric(14,2), default=0)
    total_freight         = db.Column(db.Numeric(14,2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14,2), default=0)
    vat_amount            = db.Column(db.Numeric(14,2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14,2), default=0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    created_by     = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('purchase_quotations', lazy=True))
    pr     = db.relationship('PurchaseRequest', backref=db.backref('quotations', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'doc_no': self.doc_no,
            'pr_id': self.pr_id, 'pr_no': self.pr.doc_no if self.pr else '',
            'requester': self.requester or '', 'requester_name': self.requester_name or '',
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'status': self.status,
            'posting_date': str(self.posting_date) if self.posting_date else '',
            'remarks': self.remarks or '', 'approved_by': self.approved_by or '',
            'total_incl_vat': float(self.total_incl_vat or 0),
            'total_discount': float(self.total_discount or 0),
        }


# ─────────────────────────────────────────────────────────────────
# PURCHASE ORDER
# ─────────────────────────────────────────────────────────────────
class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id              = db.Column(db.Integer, primary_key=True)
    doc_no          = db.Column(db.String(20), unique=True)
    pq_id           = db.Column(db.Integer, db.ForeignKey('purchase_quotations.id'), nullable=True)
    vendor_id       = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    vendor_ref_no   = db.Column(db.String(100))
    status          = db.Column(db.String(20), default='Open')
    posting_date    = db.Column(db.Date)
    delivery_date   = db.Column(db.Date)
    document_date   = db.Column(db.Date)
    total_before_discount = db.Column(db.Numeric(14,2), default=0)
    total_discount        = db.Column(db.Numeric(14,2), default=0)
    total_freight         = db.Column(db.Numeric(14,2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14,2), default=0)
    vat_amount            = db.Column(db.Numeric(14,2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14,2), default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))

    vendor = db.relationship('VendorMaster', backref=db.backref('purchase_orders', lazy=True))
    pq     = db.relationship('PurchaseQuotation', backref=db.backref('orders', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'doc_no': self.doc_no,
            'pq_id': self.pq_id, 'pq_no': self.pq.doc_no if self.pq else '',
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'vendor_ref_no': self.vendor_ref_no or '',
            'status': self.status,
            'posting_date': str(self.posting_date) if self.posting_date else '',
            'delivery_date': str(self.delivery_date) if self.delivery_date else '',
            'document_date': str(self.document_date) if self.document_date else '',
            'total_incl_vat': float(self.total_incl_vat or 0),
            'total_discount': float(self.total_discount or 0),
            'total_freight': float(self.total_freight or 0),
        }


# ─────────────────────────────────────────────────────────────────
# SHARED: PURCHASE LINE ITEMS (PR / PQ / PO)
# ─────────────────────────────────────────────────────────────────
class PurchaseLineItem(db.Model):
    __tablename__ = 'purchase_line_items'
    id            = db.Column(db.Integer, primary_key=True)
    doc_type      = db.Column(db.String(5))   # PR / PQ / PO
    doc_id        = db.Column(db.Integer)
    item_code     = db.Column(db.String(50))
    item_desc     = db.Column(db.String(500))
    required_date = db.Column(db.Date)
    warehouse     = db.Column(db.String(150))
    uom           = db.Column(db.String(20), default='unit')
    quantity      = db.Column(db.Numeric(12,2), default=0)
    rate          = db.Column(db.Numeric(12,2), default=0)
    discount      = db.Column(db.Numeric(12,2), default=0)
    freight       = db.Column(db.Numeric(12,2), default=0)
    taxable       = db.Column(db.Numeric(12,2), default=0)  # auto = qty*rate
    tax_code      = db.Column(db.String(20), default='VAT15')
    tax_amount    = db.Column(db.Numeric(12,2), default=0)
    total         = db.Column(db.Numeric(12,2), default=0)

    def to_dict(self):
        return {
            'id': self.id, 'doc_type': self.doc_type, 'doc_id': self.doc_id,
            'item_code': self.item_code or '', 'item_desc': self.item_desc or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '', 'uom': self.uom,
            'quantity': float(self.quantity or 0), 'rate': float(self.rate or 0),
            'discount': float(self.discount or 0), 'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0), 'tax_code': self.tax_code or 'VAT15',
            'tax_amount': float(self.tax_amount or 0), 'total': float(self.total or 0),
        }


# ─────────────────────────────────────────────────────────────────
# SHARED: PURCHASE ATTACHMENTS
# ─────────────────────────────────────────────────────────────────
class PurchaseAttachment(db.Model):
    __tablename__ = 'purchase_attachments'
    id         = db.Column(db.Integer, primary_key=True)
    doc_type   = db.Column(db.String(5))   # PR / PQ / PO / VND
    doc_id     = db.Column(db.Integer)
    filename   = db.Column(db.String(300))
    filepath   = db.Column(db.String(500))
    file_size  = db.Column(db.Integer)
    uploaded_at= db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by= db.Column(db.Integer, db.ForeignKey('users.id'))


# ─────────────────────────────────────────────────────────────────
# GOODS RECEIPT NOTE
# ─────────────────────────────────────────────────────────────────
class GoodsReceiptNote(db.Model):
    __tablename__ = 'goods_receipt_notes'
    id              = db.Column(db.Integer, primary_key=True)
    doc_no          = db.Column(db.String(25), unique=True)
    po_id           = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=True)
    vendor_id       = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    contact_person  = db.Column(db.String(150))
    vendor_ref_no   = db.Column(db.String(100))
    status          = db.Column(db.String(20), default='Open')
    posting_date    = db.Column(db.Date)
    delivery_date   = db.Column(db.Date)
    document_date   = db.Column(db.Date)
    total_before_discount = db.Column(db.Numeric(14,2), default=0)
    total_discount        = db.Column(db.Numeric(14,2), default=0)
    total_freight         = db.Column(db.Numeric(14,2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14,2), default=0)
    vat_amount            = db.Column(db.Numeric(14,2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14,2), default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    vendor          = db.relationship('VendorMaster', backref=db.backref('grns', lazy=True))
    po              = db.relationship('PurchaseOrder', backref=db.backref('grns', lazy=True))
    def to_dict(self):
        return {'id':self.id,'doc_no':self.doc_no,'po_id':self.po_id,
                'po_no':self.po.doc_no if self.po else '',
                'vendor_id':self.vendor_id,'vendor_name':self.vendor.vendor_name_en if self.vendor else '',
                'contact_person':self.contact_person or '','vendor_ref_no':self.vendor_ref_no or '',
                'status':self.status,'posting_date':str(self.posting_date) if self.posting_date else '',
                'delivery_date':str(self.delivery_date) if self.delivery_date else '',
                'document_date':str(self.document_date) if self.document_date else '',
                'total_incl_vat':float(self.total_incl_vat or 0),
                'total_discount':float(self.total_discount or 0)}


# ─────────────────────────────────────────────────────────────────
# PURCHASE INVOICE
# ─────────────────────────────────────────────────────────────────
class PurchaseInvoice(db.Model):
    __tablename__ = 'purchase_invoices'
    id              = db.Column(db.Integer, primary_key=True)
    doc_no          = db.Column(db.String(25), unique=True)
    po_id           = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=True)
    vendor_id       = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    vendor_ref_no   = db.Column(db.String(100))
    status          = db.Column(db.String(20), default='Open')
    posting_date    = db.Column(db.Date)
    delivery_date   = db.Column(db.Date)
    document_date   = db.Column(db.Date)
    total_before_discount = db.Column(db.Numeric(14,2), default=0)
    total_discount        = db.Column(db.Numeric(14,2), default=0)
    total_freight         = db.Column(db.Numeric(14,2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14,2), default=0)
    vat_amount            = db.Column(db.Numeric(14,2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14,2), default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    vendor          = db.relationship('VendorMaster', backref=db.backref('purchase_invoices', lazy=True))
    po              = db.relationship('PurchaseOrder', backref=db.backref('purchase_invoices', lazy=True))
    def to_dict(self):
        return {'id':self.id,'doc_no':self.doc_no,'po_id':self.po_id,
                'po_no':self.po.doc_no if self.po else '',
                'vendor_id':self.vendor_id,'vendor_name':self.vendor.vendor_name_en if self.vendor else '',
                'vendor_ref_no':self.vendor_ref_no or '',
                'status':self.status,'posting_date':str(self.posting_date) if self.posting_date else '',
                'total_incl_vat':float(self.total_incl_vat or 0),
                'total_discount':float(self.total_discount or 0)}


# ─────────────────────────────────────────────────────────────────
# GOODS RETURN REQUEST
# ─────────────────────────────────────────────────────────────────
class GoodsReturnRequest(db.Model):
    __tablename__ = 'goods_return_requests'
    id              = db.Column(db.Integer, primary_key=True)
    doc_no          = db.Column(db.String(25), unique=True)
    pi_id           = db.Column(db.Integer, db.ForeignKey('purchase_invoices.id'), nullable=True)
    po_id           = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=True)
    vendor_id       = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    contact_person  = db.Column(db.String(150))
    vendor_ref_no   = db.Column(db.String(100))
    status          = db.Column(db.String(20), default='Open')
    posting_date    = db.Column(db.Date)
    delivery_date   = db.Column(db.Date)
    document_date   = db.Column(db.Date)
    total_before_discount = db.Column(db.Numeric(14,2), default=0)
    total_discount        = db.Column(db.Numeric(14,2), default=0)
    total_freight         = db.Column(db.Numeric(14,2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14,2), default=0)
    vat_amount            = db.Column(db.Numeric(14,2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14,2), default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    vendor          = db.relationship('VendorMaster', backref=db.backref('return_requests', lazy=True))
    pi              = db.relationship('PurchaseInvoice', backref=db.backref('return_requests', lazy=True))
    def to_dict(self):
        return {'id':self.id,'doc_no':self.doc_no,'pi_id':self.pi_id,
                'pi_no':self.pi.doc_no if self.pi else '',
                'po_id':self.po_id,'po_no':self.po.doc_no if self.po else '' if hasattr(self,'po') and self.po else '',
                'vendor_id':self.vendor_id,'vendor_name':self.vendor.vendor_name_en if self.vendor else '',
                'status':self.status,'posting_date':str(self.posting_date) if self.posting_date else '',
                'total_incl_vat':float(self.total_incl_vat or 0)}


# ─────────────────────────────────────────────────────────────────
# PURCHASE DEBIT MEMO
# ─────────────────────────────────────────────────────────────────
class PurchaseDebitMemo(db.Model):
    __tablename__ = 'purchase_debit_memos'
    id              = db.Column(db.Integer, primary_key=True)
    doc_no          = db.Column(db.String(25), unique=True)
    po_id           = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=True)
    grr_id          = db.Column(db.Integer, db.ForeignKey('goods_return_requests.id'), nullable=True)
    vendor_id       = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    contact_person  = db.Column(db.String(150))
    vendor_ref_no   = db.Column(db.String(100))
    status          = db.Column(db.String(20), default='Open')
    posting_date    = db.Column(db.Date)
    delivery_date   = db.Column(db.Date)
    document_date   = db.Column(db.Date)
    total_before_discount = db.Column(db.Numeric(14,2), default=0)
    total_discount        = db.Column(db.Numeric(14,2), default=0)
    total_freight         = db.Column(db.Numeric(14,2), default=0)
    total_excl_vat        = db.Column(db.Numeric(14,2), default=0)
    vat_amount            = db.Column(db.Numeric(14,2), default=0)
    total_incl_vat        = db.Column(db.Numeric(14,2), default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    vendor          = db.relationship('VendorMaster', backref=db.backref('debit_memos', lazy=True))
    grr             = db.relationship('GoodsReturnRequest', backref=db.backref('debit_memos', lazy=True))
    def to_dict(self):
        return {'id':self.id,'doc_no':self.doc_no,'po_id':self.po_id,
                'grr_id':self.grr_id,'grr_no':self.grr.doc_no if self.grr else '',
                'vendor_id':self.vendor_id,'vendor_name':self.vendor.vendor_name_en if self.vendor else '',
                'status':self.status,'posting_date':str(self.posting_date) if self.posting_date else '',
                'total_incl_vat':float(self.total_incl_vat or 0)}