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
    district_ar         = db.Column(db.String(100))
    city_ar             = db.Column(db.String(100))
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


# ─────────────────────────────────────────────────────────────────
# SELLER WAREHOUSE  (one seller -> many warehouses)
# ─────────────────────────────────────────────────────────────────
class SellerWarehouse(db.Model):
    __tablename__ = 'seller_warehouses'
    id                = db.Column(db.Integer, primary_key=True)
    seller_id         = db.Column(db.Integer, db.ForeignKey('sellers.id', ondelete='CASCADE'), nullable=False)
    warehouse_name    = db.Column(db.String(200), nullable=False)
    warehouse_name_ar = db.Column(db.String(200))
    location          = db.Column(db.String(200))
    location_ar       = db.Column(db.String(200))
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    seller = db.relationship('Seller', backref=db.backref('warehouses', cascade='all, delete-orphan', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'seller_id': self.seller_id,
            'warehouse_name': self.warehouse_name,
            'warehouse_name_ar': self.warehouse_name_ar or '',
            'location': self.location or '',
            'location_ar': self.location_ar or '',
        }

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
    salary_order         = db.Column(db.Integer, default=1)
    phone                = db.Column(db.String(30))
    fax                  = db.Column(db.String(30))
    email                = db.Column(db.String(120))
    website              = db.Column(db.String(200))
    report_color         = db.Column(db.String(10), default='#2563eb')
    street_name          = db.Column(db.String(200))
    street_name_ar       = db.Column(db.String(200))
    building_number      = db.Column(db.String(50))
    additional_number    = db.Column(db.String(50))
    postal_code          = db.Column(db.String(20))
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
            # department and department_ar removed from to_dict
            'phone': self.phone or '', 'email': self.email or '',
            'city': self.city or '', 'is_active': self.is_active,
            'salary_order': self.salary_order or 1,
        }
    
# ─────────────────────────────────────────────────────────────────
# BUYER BANK   (stored in buyer_banks)
# ─────────────────────────────────────────────────────────────────
class BuyerBank(db.Model):
    __tablename__ = 'buyer_banks'
    id             = db.Column(db.Integer, primary_key=True)
    buyer_id       = db.Column(db.Integer, db.ForeignKey('buyers.id', ondelete='CASCADE'), nullable=False)
    bank_name      = db.Column(db.String(150), nullable=False)
    bank_name_ar   = db.Column(db.String(150))
    account_number = db.Column(db.String(50))
    branch         = db.Column(db.String(100))
    branch_ar      = db.Column(db.String(100))
    swift_code     = db.Column(db.String(20))
    iban           = db.Column(db.String(50))
    is_primary     = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    buyer = db.relationship('BuyerMaster', backref=db.backref('banks', cascade='all,delete-orphan', lazy=True))

    def to_dict(self):
        return {
            'id': self.id, 'buyer_id': self.buyer_id,
            'bank_name': self.bank_name, 
            'bank_name_ar': self.bank_name_ar or '',
            'account_number': self.account_number or '',
            'branch': self.branch or '', 
            'branch_ar': self.branch_ar or '',
            'swift_code': self.swift_code or '',
            'iban': self.iban or '', 
            'is_primary': self.is_primary,
        }
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

# ═══════════════════════════════════════════════════════════════════
# REPLACE the existing Employee, AllowanceType, and EmployeeAllowance
# classes in models.py with the versions below.
# (EmployeeBank and WorkAllocation stay as they are.)
#
# Notes:
#  - Columns cover every field bind_employee() / employee_json() touch,
#    so saving no longer silently drops data.
#  - employee_type is REMOVED per request.
#  - overtime_rate column added (your formula writes to it).
#  - `name`/`name_ar` are the primary name columns the routes use
#    (the old model called them name_en/name_ar — routes use `name`).
#    A `name_en` hybrid alias is provided so any code using name_en
#    still works.
# ═══════════════════════════════════════════════════════════════════

# EMPLOYEE ↔ PROFESSION JUNCTION TABLE (multi-select support)
# ═══════════════════════════════════════════════════════════════
class EmployeeProfession(db.Model):
    __tablename__ = 'employee_professions'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    profession_id = db.Column(db.Integer, db.ForeignKey('profession_master.id', ondelete='CASCADE'), nullable=False)
    profession_name    = db.Column(db.String(150))
    profession_name_ar = db.Column(db.String(150))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('employee_id', 'profession_id', name='uq_emp_prof'),)


class Employee(db.Model):
    __tablename__ = 'employees'
    id               = db.Column(db.Integer, primary_key=True)
    employee_code    = db.Column(db.String(20), unique=True, nullable=False)
    auto_code        = db.Column(db.Boolean, default=True)
    is_active        = db.Column(db.Boolean, default=True)
    is_muslim        = db.Column(db.Boolean, default=False)

    # ── Identity (bilingual) ──
    name             = db.Column(db.String(200), nullable=False)
    name_ar          = db.Column(db.String(200))
    nationality      = db.Column(db.String(100))
    nationality_ar   = db.Column(db.String(100))
    education        = db.Column(db.String(150))
    education_ar     = db.Column(db.String(150))

    # ── Kafeel / sponsor ──
    kafeel_name          = db.Column(db.String(200))
    kafeel_name_ar       = db.Column(db.String(200))
    kafeel_reference     = db.Column(db.String(100))
    kafeel_reference_ar  = db.Column(db.String(100))
    kafalat_number       = db.Column(db.String(100))

    # ── Documents / IDs ──
    passport_number  = db.Column(db.String(50))
    passport_expiry  = db.Column(db.Date)
    passport_location= db.Column(db.String(20), default='IN')
    entry_number     = db.Column(db.String(50))
    iqama_number     = db.Column(db.String(50))
    iqama_expiry     = db.Column(db.Date)
    document_type    = db.Column(db.String(80))

    # ── Dates ──
    arrival_date     = db.Column(db.Date)
    birth_date       = db.Column(db.Date)
    joining_date     = db.Column(db.Date)
    end_date_work    = db.Column(db.Date)

    # ── Contact ──
    mobile           = db.Column(db.String(30))
    email            = db.Column(db.String(120))
    address          = db.Column(db.String(300))
    address_ar       = db.Column(db.String(300))
    home_city        = db.Column(db.String(120))
    home_city_ar     = db.Column(db.String(120))

    # ── Employment / references ──
    employee_reference    = db.Column(db.String(120))
    employee_reference_ar = db.Column(db.String(120))
    work_status      = db.Column(db.String(30), default='active')

    # ── Payroll ──
    salary_category  = db.Column(db.String(20))   # 'Salary' or 'Azad'
    salary_type      = db.Column(db.String(30), default='salary')
    basic_salary     = db.Column(db.Numeric(12, 2), default=0)
    total_allowances = db.Column(db.Numeric(12, 2), default=0)
    net_salary       = db.Column(db.Numeric(12, 2), default=0)
    po_number        = db.Column(db.String(80))
    po_rate          = db.Column(db.Numeric(12, 2), default=0)
    working_hours    = db.Column(db.Numeric(6, 2), default=8)
    overtime_ratio   = db.Column(db.Numeric(6, 2), default=1.5)
    overtime_rate    = db.Column(db.Numeric(12, 2), default=0)

    # ── Hostel ──
    hostel_name        = db.Column(db.String(200))
    hostel_name_ar     = db.Column(db.String(200))
    room_number        = db.Column(db.String(50))
    hostel_location    = db.Column(db.String(200))
    hostel_location_ar = db.Column(db.String(200))

    # ── Compliance ──
    crn                   = db.Column(db.String(60))
    crn_ar                = db.Column(db.String(60))
    insurance_company     = db.Column(db.String(200))
    insurance_company_ar  = db.Column(db.String(200))
    insurance_expiry      = db.Column(db.Date)
    labour_office         = db.Column(db.String(150))

    # ── Misc / relations ──
    buyer_id         = db.Column(db.Integer, db.ForeignKey('buyers.id'))
    document_path    = db.Column(db.String(300))
    photo_path       = db.Column(db.String(300))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow)
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'))

    # ── Relationships ──
    buyer          = db.relationship('BuyerMaster', backref=db.backref('emp_employees', lazy=True))

    # Multi-select professions (junction table)
    professions = db.relationship('ProfessionMaster',
                    secondary='employee_professions',
                    lazy='dynamic',
                    backref=db.backref('employee_list', lazy='dynamic'))

    allowance_rows = db.relationship('EmployeeAllowance',
                        backref='employee_ref',
                        lazy='dynamic',
                        cascade='all, delete-orphan')

    banks = db.relationship('EmployeeBank',
                        backref='employee_ref',
                        lazy='dynamic',
                        cascade='all, delete-orphan')

    documents = db.relationship('EmployeeDocument',
                        backref='employee_ref',
                        lazy='dynamic',
                        cascade='all, delete-orphan')

    @property
    def name_en(self):
        return self.name
    @name_en.setter
    def name_en(self, v):
        self.name = v

    def to_dict(self):
        return {
            'id': self.id, 'employee_code': self.employee_code,
            'name': self.name, 'name_ar': self.name_ar or '',
            'nationality': self.nationality or '',
            'profession': ', '.join([p.name_en for p in self.professions.all()]) if hasattr(self,'professions') else '',
            'basic_salary': float(self.basic_salary or 0),
            'total_allowances': float(self.total_allowances or 0),
            'net_salary': float(self.net_salary or 0),
            'mobile': self.mobile or '', 'email': self.email or '',
            'is_active': self.is_active,
        }

class AllowanceType(db.Model):
    __tablename__ = 'employee_allowance_types'   
    id                = db.Column(db.Integer, primary_key=True)
    allowance_code    = db.Column(db.String(20))
    allowance_name_en = db.Column(db.String(150), nullable=False)
    allowance_name_ar = db.Column(db.String(150))
    is_active         = db.Column(db.Boolean, default=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id,
                'allowance_code': self.allowance_code or '',
                'allowance_name_en': self.allowance_name_en,
                'allowance_name_ar': self.allowance_name_ar or '',
                'is_active': self.is_active}

class EmployeeAllowance(db.Model):
    __tablename__ = 'employee_allowances'
    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    allowance_type_id = db.Column(db.Integer, db.ForeignKey('employee_allowance_types.id'))   
    allowance_code    = db.Column(db.String(20))
    name              = db.Column(db.String(150))
    name_ar           = db.Column(db.String(150))
    amount            = db.Column(db.Numeric(12, 2), default=0)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    allowance_type = db.relationship('AllowanceType', backref=db.backref('employee_allowances', lazy=True))

   
    def to_dict(self):
        return {
            'id': self.id, 'employee_id': self.employee_id,
            'allowance_type_id': self.allowance_type_id,
            'allowance_code': self.allowance_code or (self.allowance_type.allowance_code if self.allowance_type else ''),
            'name': self.name or (self.allowance_type.allowance_name_en if self.allowance_type else ''),
            'name_ar': self.name_ar or (self.allowance_type.allowance_name_ar if self.allowance_type else ''),
            'amount': float(self.amount or 0),
        }


class EmployeeBank(db.Model):
    __tablename__ = 'employee_banks'
    id             = db.Column(db.Integer, primary_key=True)
    employee_id    = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    bank_name      = db.Column(db.String(150), nullable=False)
    bank_name_ar   = db.Column(db.String(150))
    branch         = db.Column(db.String(120))
    branch_ar      = db.Column(db.String(120))
    account_number = db.Column(db.String(60))
    swift_code     = db.Column(db.String(30))
    iban           = db.Column(db.String(60))
    is_primary     = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'employee_id': self.employee_id,
            'bank_name': self.bank_name, 'bank_name_ar': self.bank_name_ar or '',
            'branch': self.branch or '', 'branch_ar': self.branch_ar or '',
            'account_number': self.account_number or '',
            'swift_code': self.swift_code or '', 'iban': self.iban or '',
            'is_primary': self.is_primary,
        }


class EmployeeDocument(db.Model):
    __tablename__ = 'employee_documents'
    id            = db.Column(db.Integer, primary_key=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False)
    document_type = db.Column(db.String(80))
    file_path     = db.Column(db.String(300), nullable=False)
    original_name = db.Column(db.String(200))
    uploaded_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'employee_id': self.employee_id,
            'document_type': self.document_type or '',
            'file_path': self.file_path,
            'original_name': self.original_name or '',
            'uploaded_at': self.uploaded_at.strftime('%Y-%m-%d %H:%M') if self.uploaded_at else '',
        }


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
# ─────────────────────────────────────────────────────────────────
# VENDOR DOCUMENT
# ─────────────────────────────────────────────────────────────────
class VendorDocument(db.Model):
    __tablename__ = 'vendor_documents'
    id            = db.Column(db.Integer, primary_key=True)
    vendor_id     = db.Column(db.Integer, db.ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False)
    document_type = db.Column(db.String(100))
    document_name = db.Column(db.String(255))
    issue_date    = db.Column(db.Date, nullable=True)
    expiry_date   = db.Column(db.Date, nullable=True)
    file_path     = db.Column(db.String(500))
    file_size     = db.Column(db.Integer)
    uploaded_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at   = db.Column(db.DateTime, default=datetime.utcnow)

    vendor   = db.relationship('VendorMaster', backref=db.backref('documents', lazy=True, cascade='all,delete-orphan'))
    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'vendor_code': self.vendor.vendor_code if self.vendor else '',
            'document_type': self.document_type or '',
            'document_name': self.document_name or '',
            'issue_date': str(self.issue_date) if self.issue_date else '',
            'expiry_date': str(self.expiry_date) if self.expiry_date else '',
            'file_path': self.file_path or '',
            'file_size_kb': round((self.file_size or 0) / 1024, 1),
            'uploaded_by': self.uploaded_by,
            'uploaded_by_name': self.uploader.username if self.uploader else '',
            'uploaded_at': self.uploaded_at.strftime('%Y-%m-%d %H:%M') if self.uploaded_at else '',
        }


# ─────────────────────────────────────────────────────────────────
# BUYER DOCUMENT
# ─────────────────────────────────────────────────────────────────
class BuyerDocument(db.Model):
    __tablename__ = 'buyer_documents'
    id            = db.Column(db.Integer, primary_key=True)
    buyer_id      = db.Column(db.Integer, db.ForeignKey('buyers.id', ondelete='CASCADE'), nullable=False)
    document_type = db.Column(db.String(100))
    document_name = db.Column(db.String(255))
    issue_date    = db.Column(db.Date, nullable=True)
    expiry_date   = db.Column(db.Date, nullable=True)
    file_path     = db.Column(db.String(500))
    file_size     = db.Column(db.Integer)
    uploaded_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at   = db.Column(db.DateTime, default=datetime.utcnow)

    buyer    = db.relationship('BuyerMaster', backref=db.backref('documents', lazy=True, cascade='all,delete-orphan'))
    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    def to_dict(self):
        return {
            'id': self.id,
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
            'buyer_code': self.buyer.buyer_code if self.buyer else '',
            'document_type': self.document_type or '',
            'document_name': self.document_name or '',
            'issue_date': str(self.issue_date) if self.issue_date else '',
            'expiry_date': str(self.expiry_date) if self.expiry_date else '',
            'file_path': self.file_path or '',
            'file_size_kb': round((self.file_size or 0) / 1024, 1),
            'uploaded_by': self.uploaded_by,
            'uploaded_by_name': self.uploader.username if self.uploader else '',
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
    kind                  = db.Column(db.String(20), default='Goods')
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
            'kind': self.kind or 'Goods',
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
    kind                  = db.Column(db.String(20), default='Goods')
    purchase_request_id   = db.Column(db.Integer, db.ForeignKey('purchase_requests.purchase_request_id'))
    requester             = db.Column(db.String(150))
    requester_name        = db.Column(db.String(200))
    vendor_id             = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    vendor_ref_no         = db.Column(db.String(100))
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
    purchase_request = db.relationship('PurchaseRequest', backref=db.backref('purchase_quotations', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'id': self.purchase_quotation_id,
            'purchase_quotation_id': self.purchase_quotation_id,
            'doc_no': self.doc_no or '',
            'purchase_request_id': self.purchase_request_id,
            'pr_doc_no': self.purchase_request.doc_no if self.purchase_request else '',
            'requester': self.requester or '',
            'requester_name': self.requester_name or '',
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'vendor_ref_no': self.vendor_ref_no or '',
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
# ─────────────────────────────────────────────────────────────────
# PURCHASE ORDER HEADER
# ─────────────────────────────────────────────────────────────────
class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    purchase_order_id     = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    kind                  = db.Column(db.String(20), default='Goods')
    purchase_quotation_id = db.Column(db.Integer, db.ForeignKey('purchase_quotations.purchase_quotation_id'))
    vendor_id             = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    vendor_ref_no         = db.Column(db.String(100))
    remarks               = db.Column(db.Text)
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
    pq = db.relationship('PurchaseQuotation', backref=db.backref('purchase_orders', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'id': self.purchase_order_id,
            'purchase_order_id': self.purchase_order_id,
            'doc_no': self.doc_no or '',
            'purchase_quotation_id': self.purchase_quotation_id,
            'pq_id': self.purchase_quotation_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.vendor_name_en if self.vendor else '',
            'vendor_ref_no': self.vendor_ref_no or '',
            'remarks': self.remarks or '',
            'status': self.status,
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
# PURCHASE ORDER LINE ITEMS
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
            'item_code': self.item_code or '',
            'item_desc': self.description or '',
            'description': self.description or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '',
            'uom': self.uom,
            'quantity': float(self.quantity or 0),
            'rate': float(self.rate or 0),
            'discount': float(self.discount or 0),
            'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0),
            'tax_code': self.tax_code,
            'tax_amount': float(self.tax_amount or 0),
            'total': float(self.total or 0),
        }
# 4. GOODS RECEIPT NOTE
#      FK: purchase_order_id → purchase_orders
# ─────────────────────────────────────────────────────────────────
class GoodsReceiptNote(db.Model):
    __tablename__ = 'goods_receipt_notes'
    goods_receipt_note_id = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    kind                  = db.Column(db.String(20), default='Goods')
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
    purchase_order = db.relationship('PurchaseOrder', backref=db.backref('grn_docs', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'id': self.goods_receipt_note_id,
            'goods_receipt_note_id': self.goods_receipt_note_id,
            'doc_no': self.doc_no or '',
            'purchase_order_id': self.purchase_order_id,
            'po_no': self.purchase_order.doc_no if self.purchase_order else '',
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
    kind                  = db.Column(db.String(20), default='Goods')
    payment_method        = db.Column(db.String(20), default='Credit')
    bank_account_id       = db.Column(db.Integer)
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
    purchase_order = db.relationship('PurchaseOrder', backref=db.backref('invoices', lazy=True))
    goods_receipt_note = db.relationship('GoodsReceiptNote', backref=db.backref('invoices', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'payment_method': self.payment_method or 'Credit',
            'bank_account_id': self.bank_account_id,
            'id': self.purchase_invoice_id,
            'purchase_invoice_id': self.purchase_invoice_id,
            'doc_no': self.doc_no or '',
            'purchase_order_id': self.purchase_order_id,
            'po_no': self.purchase_order.doc_no if self.purchase_order else '',
            'goods_receipt_note_id': self.goods_receipt_note_id,
            'grn_no': self.goods_receipt_note.doc_no if self.goods_receipt_note else '',
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
    kind                  = db.Column(db.String(20), default='Goods')
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
    purchase_invoice = db.relationship('PurchaseInvoice', backref=db.backref('return_requests', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'id': self.goods_return_request_id,
            'goods_return_request_id': self.goods_return_request_id,
            'doc_no': self.doc_no or '',
            'purchase_invoice_id': self.purchase_invoice_id,
            'pi_no': self.purchase_invoice.doc_no if self.purchase_invoice else '',
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
    kind                  = db.Column(db.String(20), default='Goods')
    payment_method        = db.Column(db.String(20), default='Credit')
    bank_account_id       = db.Column(db.Integer)
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
    goods_return_request = db.relationship('GoodsReturnRequest', backref=db.backref('debit_memos', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'payment_method': self.payment_method or 'Credit',
            'bank_account_id': self.bank_account_id,
            'id': self.purchase_debit_memo_id,
            'purchase_debit_memo_id': self.purchase_debit_memo_id,
            'doc_no': self.doc_no or '',
            'goods_return_request_id': self.goods_return_request_id,
            'grr_no': self.goods_return_request.doc_no if self.goods_return_request else '',
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
    item_type          = db.Column(db.String(20), default='Product')  # Product / Service
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
    po_rate            = db.Column(db.Numeric(14, 2), default=0)
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
            'item_type': self.item_type or 'Product',
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
            'po_rate':            float(self.po_rate            or 0),
            'last_purchase_rate': float(self.last_purchase_rate or 0),
            'retail_rate':        float(self.retail_rate        or 0),
            'wholesale_rate':     float(self.wholesale_rate     or 0),
            'special_rate':       float(self.special_rate       or 0),
            'mrp':                float(self.mrp                or 0),
            'minimum_sp':         float(self.minimum_sp         or 0),
            'is_active': self.is_active,
            'uoms': [u.to_dict() for u in self.uoms] if self.uoms else [],
        }


# ─────────────────────────────────────────────────────────────────
# UNIT OF MEASUREMENT (master list) + ITEM ↔ UOM (multi per item)
# ─────────────────────────────────────────────────────────────────
class UnitOfMeasurement(db.Model):
    __tablename__ = 'unit_of_measurement'
    id           = db.Column(db.Integer, primary_key=True)
    unit_name    = db.Column(db.String(50), nullable=False, unique=True)
    unit_name_ar = db.Column(db.String(50))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'unit_name': self.unit_name,
            'unit_name_ar': self.unit_name_ar or '',
        }


class ItemUOM(db.Model):
    __tablename__ = 'item_uom'
    id         = db.Column(db.Integer, primary_key=True)
    item_id    = db.Column(db.Integer, db.ForeignKey('item_master.id', ondelete='CASCADE'), nullable=False)
    uom_id     = db.Column(db.Integer, db.ForeignKey('unit_of_measurement.id'), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('ItemMaster', backref=db.backref('uoms', lazy=True, cascade='all,delete-orphan'))
    uom  = db.relationship('UnitOfMeasurement', backref=db.backref('item_links', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'item_id': self.item_id,
            'uom_id': self.uom_id,
            'unit_name': self.uom.unit_name if self.uom else '',
            'unit_name_ar': (self.uom.unit_name_ar or '') if self.uom else '',
            'is_default': bool(self.is_default),
        }

# ═════════════════════════════════════════════════════════════════
#  SALES DOCUMENTS  (mirror of the purchase chain)
#  SR → SQ → SO → DN → SINV → SRR → SCM   —  all reference buyers
#  Auto-generated to match the purchase module structure.
# ═════════════════════════════════════════════════════════════════


class SalesRequest(db.Model):
    __tablename__ = 'sales_requests'
    sales_request_id   = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    kind                  = db.Column(db.String(20), default='Goods')
    requester             = db.Column(db.String(150))
    requester_name        = db.Column(db.String(200))
    buyer_id             = db.Column(db.Integer, db.ForeignKey('buyers.id'))
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

    buyer = db.relationship('BuyerMaster', backref=db.backref('sales_requests', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'id': self.sales_request_id,
            'sales_request_id': self.sales_request_id,
            'doc_no': self.doc_no or '', 'requester': self.requester or '',
            'requester_name': self.requester_name or '', 'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
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
#      PK: sales_request_line_item_id
#      FK: sales_request_id → sales_requests
# ─────────────────────────────────────────────────────────────────
class SalesRequestLineItem(db.Model):
    __tablename__ = 'sales_request_line_items'
    sales_request_line_item_id = db.Column(db.Integer, primary_key=True)
    sales_request_id = db.Column(db.Integer, db.ForeignKey('sales_requests.sales_request_id', ondelete='CASCADE'), nullable=False)
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

    sales_request = db.relationship('SalesRequest', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.sales_request_line_item_id,
            'sales_request_line_item_id': self.sales_request_line_item_id,
            'sales_request_id': self.sales_request_id,
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
#      FK: sales_request_id → sales_requests
# ─────────────────────────────────────────────────────────────────
class SalesQuotation(db.Model):
    __tablename__ = 'sales_quotations'
    sales_quotation_id = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    kind                  = db.Column(db.String(20), default='Goods')
    sales_request_id   = db.Column(db.Integer, db.ForeignKey('sales_requests.sales_request_id'))
    requester             = db.Column(db.String(150))
    requester_name        = db.Column(db.String(200))
    buyer_id             = db.Column(db.Integer, db.ForeignKey('buyers.id'))
    buyer_ref_no         = db.Column(db.String(100))
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

    buyer = db.relationship('BuyerMaster', backref=db.backref('sales_quotations', lazy=True))
    sales_request = db.relationship('SalesRequest', backref=db.backref('sales_quotations', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'id': self.sales_quotation_id,
            'sales_quotation_id': self.sales_quotation_id,
            'doc_no': self.doc_no or '',
            'sales_request_id': self.sales_request_id,
            'pr_doc_no': self.sales_request.doc_no if self.sales_request else '',
            'requester': self.requester or '',
            'requester_name': self.requester_name or '',
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
            'buyer_ref_no': self.buyer_ref_no or '',
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
#      PK: sales_quotation_line_item_id
#      FK: sales_quotation_id → sales_quotations
# ─────────────────────────────────────────────────────────────────
class SalesQuotationLineItem(db.Model):
    __tablename__ = 'sales_quotation_line_items'
    sales_quotation_line_item_id = db.Column(db.Integer, primary_key=True)
    sales_quotation_id = db.Column(db.Integer, db.ForeignKey('sales_quotations.sales_quotation_id', ondelete='CASCADE'), nullable=False)
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

    sales_quotation = db.relationship('SalesQuotation', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.sales_quotation_line_item_id,
            'sales_quotation_line_item_id': self.sales_quotation_line_item_id,
            'sales_quotation_id': self.sales_quotation_id,
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
# ─────────────────────────────────────────────────────────────────
# PURCHASE ORDER HEADER
# ─────────────────────────────────────────────────────────────────
class SalesOrder(db.Model):
    __tablename__ = 'sales_orders'
    sales_order_id     = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    kind                  = db.Column(db.String(20), default='Goods')
    sales_quotation_id = db.Column(db.Integer, db.ForeignKey('sales_quotations.sales_quotation_id'))
    buyer_id             = db.Column(db.Integer, db.ForeignKey('buyers.id'))
    buyer_ref_no         = db.Column(db.String(100))
    remarks               = db.Column(db.Text)
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

    buyer = db.relationship('BuyerMaster', backref=db.backref('sales_orders', lazy=True))
    pq = db.relationship('SalesQuotation', backref=db.backref('sales_orders', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'id': self.sales_order_id,
            'sales_order_id': self.sales_order_id,
            'doc_no': self.doc_no or '',
            'sales_quotation_id': self.sales_quotation_id,
            'pq_id': self.sales_quotation_id,
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
            'buyer_ref_no': self.buyer_ref_no or '',
            'remarks': self.remarks or '',
            'status': self.status,
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
# PURCHASE ORDER LINE ITEMS
# ─────────────────────────────────────────────────────────────────
class SalesOrderLineItem(db.Model):
    __tablename__ = 'sales_order_line_items'
    sales_order_line_item_id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_orders.sales_order_id', ondelete='CASCADE'), nullable=False)
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

    sales_order = db.relationship('SalesOrder', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.sales_order_line_item_id,
            'sales_order_line_item_id': self.sales_order_line_item_id,
            'sales_order_id': self.sales_order_id,
            'line_number': self.line_number,
            'item_code': self.item_code or '',
            'item_desc': self.description or '',
            'description': self.description or '',
            'required_date': str(self.required_date) if self.required_date else '',
            'warehouse': self.warehouse or '',
            'uom': self.uom,
            'quantity': float(self.quantity or 0),
            'rate': float(self.rate or 0),
            'discount': float(self.discount or 0),
            'freight': float(self.freight or 0),
            'taxable': float(self.taxable or 0),
            'tax_code': self.tax_code,
            'tax_amount': float(self.tax_amount or 0),
            'total': float(self.total or 0),
        }
# 4. GOODS RECEIPT NOTE
#      FK: sales_order_id → sales_orders
# ─────────────────────────────────────────────────────────────────
class DeliveryNote(db.Model):
    __tablename__ = 'delivery_notes'
    delivery_note_id = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    kind                  = db.Column(db.String(20), default='Goods')
    sales_order_id     = db.Column(db.Integer, db.ForeignKey('sales_orders.sales_order_id'))
    buyer_id             = db.Column(db.Integer, db.ForeignKey('buyers.id'))
    contact_person        = db.Column(db.String(150))
    buyer_ref_no         = db.Column(db.String(100))
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

    buyer = db.relationship('BuyerMaster', backref=db.backref('delivery_notes', lazy=True))
    sales_order = db.relationship('SalesOrder', backref=db.backref('dn_docs', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'id': self.delivery_note_id,
            'delivery_note_id': self.delivery_note_id,
            'doc_no': self.doc_no or '',
            'sales_order_id': self.sales_order_id,
            'so_no': self.sales_order.doc_no if self.sales_order else '',
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
            'buyer_ref_no': self.buyer_ref_no or '',
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
#      PK: delivery_line_item_id
#      FK: delivery_note_id → delivery_notes
# ─────────────────────────────────────────────────────────────────
class DeliveryLineItem(db.Model):
    __tablename__ = 'delivery_line_items'
    delivery_line_item_id = db.Column(db.Integer, primary_key=True)
    delivery_note_id = db.Column(db.Integer, db.ForeignKey('delivery_notes.delivery_note_id', ondelete='CASCADE'), nullable=False)
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

    delivery_note = db.relationship('DeliveryNote', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.delivery_line_item_id,
            'delivery_line_item_id': self.delivery_line_item_id,
            'delivery_note_id': self.delivery_note_id,
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
#      FK: sales_order_id → sales_orders
#      FK: delivery_note_id → delivery_notes
# ─────────────────────────────────────────────────────────────────
class SalesInvoice(db.Model):
    __tablename__ = 'sales_invoices'
    sales_invoice_id   = db.Column(db.Integer, primary_key=True)
    doc_no                = db.Column(db.String(20), unique=True)
    kind                  = db.Column(db.String(20), default='Goods')
    payment_method        = db.Column(db.String(20), default='Credit')
    bank_account_id       = db.Column(db.Integer)
    seller_id             = db.Column(db.Integer)
    sales_order_id     = db.Column(db.Integer, db.ForeignKey('sales_orders.sales_order_id'))
    delivery_note_id = db.Column(db.Integer, db.ForeignKey('delivery_notes.delivery_note_id'))
    buyer_id             = db.Column(db.Integer, db.ForeignKey('buyers.id'))
    buyer_ref_no         = db.Column(db.String(100))
    transaction_type     = db.Column(db.String(20))   # STD_CR, STD_DR, SMP_CR, SMP_DR
    invoice_category     = db.Column(db.String(20))   # standard | simplified
    reference_invoices   = db.Column(db.String(300))  # comma-separated sales_invoice_id list
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

    buyer = db.relationship('BuyerMaster', backref=db.backref('sales_invoices', lazy=True))
    sales_order = db.relationship('SalesOrder', backref=db.backref('sales_invoices_link', lazy=True))
    delivery_note = db.relationship('DeliveryNote', backref=db.backref('sales_invoices_link', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'payment_method': self.payment_method or 'Credit',
            'bank_account_id': self.bank_account_id,
            'seller_id': self.seller_id,
            'id': self.sales_invoice_id,
            'sales_invoice_id': self.sales_invoice_id,
            'doc_no': self.doc_no or '',
            'sales_order_id': self.sales_order_id,
            'so_no': self.sales_order.doc_no if self.sales_order else '',
            'delivery_note_id': self.delivery_note_id,
            'dn_no': self.delivery_note.doc_no if self.delivery_note else '',
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
            'buyer_ref_no': self.buyer_ref_no or '', 'status': self.status,
            'transaction_type': self.transaction_type or '',
            'invoice_category': self.invoice_category or '',
            'reference_invoices': self.reference_invoices or '',
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
#      PK: sales_invoice_line_item_id
#      FK: sales_invoice_id → sales_invoices
# ─────────────────────────────────────────────────────────────────
class SalesInvoiceLineItem(db.Model):
    __tablename__ = 'sales_invoice_line_items'
    sales_invoice_line_item_id = db.Column(db.Integer, primary_key=True)
    sales_invoice_id = db.Column(db.Integer, db.ForeignKey('sales_invoices.sales_invoice_id', ondelete='CASCADE'), nullable=False)
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

    sales_invoice = db.relationship('SalesInvoice', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.sales_invoice_line_item_id,
            'sales_invoice_line_item_id': self.sales_invoice_line_item_id,
            'sales_invoice_id': self.sales_invoice_id,
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
#      FK: sales_invoice_id → sales_invoices
# ─────────────────────────────────────────────────────────────────
class SalesReturnRequest(db.Model):
    __tablename__ = 'sales_return_requests'
    sales_return_request_id = db.Column(db.Integer, primary_key=True)
    doc_no                  = db.Column(db.String(20), unique=True)
    kind                  = db.Column(db.String(20), default='Goods')
    sales_invoice_id     = db.Column(db.Integer, db.ForeignKey('sales_invoices.sales_invoice_id'))
    buyer_id               = db.Column(db.Integer, db.ForeignKey('buyers.id'))
    contact_person          = db.Column(db.String(150))
    buyer_ref_no           = db.Column(db.String(100))
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

    buyer = db.relationship('BuyerMaster', backref=db.backref('sales_return_requests', lazy=True))
    sales_invoice = db.relationship('SalesInvoice', backref=db.backref('sales_return_requests_link', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'id': self.sales_return_request_id,
            'sales_return_request_id': self.sales_return_request_id,
            'doc_no': self.doc_no or '',
            'sales_invoice_id': self.sales_invoice_id,
            'si_no': self.sales_invoice.doc_no if self.sales_invoice else '',
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
            'buyer_ref_no': self.buyer_ref_no or '',
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
#      PK: sales_return_line_item_id
#      FK: sales_return_request_id → sales_return_requests
# ─────────────────────────────────────────────────────────────────
class SalesReturnLineItem(db.Model):
    __tablename__ = 'sales_return_line_items'
    sales_return_line_item_id = db.Column(db.Integer, primary_key=True)
    sales_return_request_id = db.Column(db.Integer, db.ForeignKey('sales_return_requests.sales_return_request_id', ondelete='CASCADE'), nullable=False)
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

    sales_return_request = db.relationship('SalesReturnRequest', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.sales_return_line_item_id,
            'sales_return_line_item_id': self.sales_return_line_item_id,
            'sales_return_request_id': self.sales_return_request_id,
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
#      FK: sales_return_request_id → sales_return_requests
#      FK: sales_invoice_id     → sales_invoices
# ─────────────────────────────────────────────────────────────────
class SalesCreditMemo(db.Model):
    __tablename__ = 'sales_credit_memos'
    sales_credit_memo_id  = db.Column(db.Integer, primary_key=True)
    doc_no                  = db.Column(db.String(20), unique=True)
    kind                  = db.Column(db.String(20), default='Goods')
    payment_method        = db.Column(db.String(20), default='Credit')
    bank_account_id       = db.Column(db.Integer)
    seller_id             = db.Column(db.Integer)
    sales_return_request_id = db.Column(db.Integer, db.ForeignKey('sales_return_requests.sales_return_request_id'))
    sales_invoice_id     = db.Column(db.Integer, db.ForeignKey('sales_invoices.sales_invoice_id'))
    buyer_id               = db.Column(db.Integer, db.ForeignKey('buyers.id'))
    contact_person          = db.Column(db.String(150))
    buyer_ref_no           = db.Column(db.String(100))
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

    buyer = db.relationship('BuyerMaster', backref=db.backref('sales_credit_memos', lazy=True))
    sales_return_request = db.relationship('SalesReturnRequest', backref=db.backref('sales_credit_memos_link', lazy=True))

    def to_dict(self):
        return {
            'kind': self.kind or 'Goods',
            'payment_method': self.payment_method or 'Credit',
            'bank_account_id': self.bank_account_id,
            'seller_id': self.seller_id,
            'id': self.sales_credit_memo_id,
            'sales_credit_memo_id': self.sales_credit_memo_id,
            'doc_no': self.doc_no or '',
            'sales_return_request_id': self.sales_return_request_id,
            'srr_no': self.sales_return_request.doc_no if self.sales_return_request else '',
            'sales_invoice_id': self.sales_invoice_id,
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.buyer_name_en if self.buyer else '',
            'buyer_ref_no': self.buyer_ref_no or '',
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
#      PK: sales_credit_memo_line_item_id
#      FK: sales_credit_memo_id → sales_credit_memos
# ─────────────────────────────────────────────────────────────────
class SalesCreditMemoLineItem(db.Model):
    __tablename__ = 'sales_credit_memo_line_items'
    sales_credit_memo_line_item_id = db.Column(db.Integer, primary_key=True)
    sales_credit_memo_id = db.Column(db.Integer, db.ForeignKey('sales_credit_memos.sales_credit_memo_id', ondelete='CASCADE'), nullable=False)
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

    sales_credit_memo = db.relationship('SalesCreditMemo', backref=db.backref('line_items', lazy=True, cascade='all,delete-orphan'))

    def to_dict(self):
        return {
            'id': self.sales_credit_memo_line_item_id,
            'sales_credit_memo_line_item_id': self.sales_credit_memo_line_item_id,
            'sales_credit_memo_id': self.sales_credit_memo_id,
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


class SalesAttachment(db.Model):
    __tablename__ = 'sales_attachments'
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



# ═════════════════════════════════════════════════════════════════
#  CHART OF ACCOUNTS  —  Level 1 (level_one) & Level 2 (level_two)
#  Level 1 = the fixed financial-statement elements (A, L, E, R, ...)
#  Level 2 = heading accounts under each Level 1, auto-coded A1, A2, ...
# ═════════════════════════════════════════════════════════════════

class LevelOne(db.Model):
    """Chart of Accounts — Level 1 (top-level financial statement elements).

    ``code`` is a single, fixed letter (A, L, E, ...) and cannot be edited
    once created. ``code_length`` is always 1.
    """
    __tablename__ = 'level_one'

    id          = db.Column(db.Integer, primary_key=True)
    code_length = db.Column(db.Integer, nullable=False, default=1)          # fixed = 1
    code        = db.Column(db.String(1), nullable=False, unique=True)      # A, L, E, ...
    drawers     = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    status      = db.Column(db.String(10), nullable=False, default='active')  # active | inactive
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # One Level 1 has many Level 2 rows.
    level_twos  = db.relationship(
        'LevelTwo',
        backref=db.backref('level_one', lazy=True),
        lazy=True,
        cascade='all, delete-orphan',
        order_by='LevelTwo.id',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'code_length': self.code_length,
            'code': self.code,
            'drawers': self.drawers,
            'description': self.description,
            'status': self.status or 'active',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'level_two_count': len(self.level_twos) if self.level_twos is not None else 0,
        }


class LevelTwo(db.Model):
    """Chart of Accounts — Level 2 (heading accounts under a Level 1).

    ``code`` is generated automatically as ``<LevelOneCode><n>`` (A1, A2, ...)
    with an independent sequence per Level 1. ``code_length`` is always 2 and
    ``description`` is always 'Heading Account'.
    """
    __tablename__ = 'level_two'

    id             = db.Column(db.Integer, primary_key=True)
    code_length    = db.Column(db.Integer, nullable=False, default=2)       # fixed = 2
    level_one_id   = db.Column(db.Integer, db.ForeignKey('level_one.id', ondelete='CASCADE'), nullable=False)
    level_one_code = db.Column(db.String(1), nullable=False)                # denormalised for fast search
    code           = db.Column(db.String(10), nullable=False, unique=True)  # A1, A2, ...
    drawers        = db.Column(db.String(150), nullable=False)
    description    = db.Column(db.String(255), nullable=False, default='Heading Account')
    status         = db.Column(db.String(10), nullable=False, default='active')  # active | inactive
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'code_length': self.code_length,
            'level_one_id': self.level_one_id,
            'level_one_code': self.level_one_code,
            'code': self.code,
            'drawers': self.drawers,
            'description': self.description,
            'status': self.status or 'active',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }


# ── Default data for the two tables ──────────────────────────────
# (code_length, code, drawers, description)
LEVEL_ONE_DEFAULTS = [
    (1, 'A', 'Asset',             'Elements of Financial Statements'),
    (1, 'L', 'Liabilities',       'Elements of Financial Statements'),
    (1, 'E', 'Equity & Reserve',  'Elements of Financial Statements'),
    (1, 'R', 'Revenue',           'Elements of Financial Statements'),
    (1, 'C', 'Cost of Revenue',   'Elements of Financial Statements'),
    (1, 'O', 'Operating Cost',    'Elements of Financial Statements'),
    (1, 'F', 'Finance Cost',      'Elements of Financial Statements'),
    (1, 'I', 'OCI',               'Elements of Financial Statements'),
]

# (level_one_code, code, drawers)  — description is always 'Heading Account'
LEVEL_TWO_DEFAULTS = [
    ('A', 'A1', 'Non-current Assets'),
    ('A', 'A2', 'Current Assets'),
    ('L', 'L1', 'Non-current Liabilities'),
    ('L', 'L2', 'Current Liabilities'),
    ('E', 'E1', 'Equity'),
    ('E', 'E2', 'Reserves'),
    ('R', 'R1', 'Operating Revenue'),
    ('R', 'R2', 'Non-operative Revenue'),
    ('C', 'C1', 'Cost of Revenue'),
    ('O', 'O1', 'Operating Cost'),
    ('F', 'F1', 'Finance Cost'),
]


def seed_chart_of_accounts():
    """Idempotently insert the default Level 1 and Level 2 records.

    Safe to call on every startup — existing rows (matched by ``code``) are
    never duplicated. Must be called inside an application context.
    """
    inserted_l1 = 0
    for code_length, code, drawers, description in LEVEL_ONE_DEFAULTS:
        if not LevelOne.query.filter_by(code=code).first():
            db.session.add(LevelOne(
                code_length=1,               # always 1
                code=code,
                drawers=drawers,
                description=description,
            ))
            inserted_l1 += 1
    if inserted_l1:
        db.session.commit()

    # Map Level 1 code -> id for the Level 2 foreign keys.
    l1_by_code = {l1.code: l1 for l1 in LevelOne.query.all()}

    inserted_l2 = 0
    for l1_code, code, drawers in LEVEL_TWO_DEFAULTS:
        parent = l1_by_code.get(l1_code)
        if not parent:
            continue
        if not LevelTwo.query.filter_by(code=code).first():
            db.session.add(LevelTwo(
                code_length=2,               # always 2
                level_one_id=parent.id,
                level_one_code=parent.code,
                code=code,
                drawers=drawers,
                description='Heading Account',
            ))
            inserted_l2 += 1
    if inserted_l2:
        db.session.commit()

    return {'level_one_inserted': inserted_l1, 'level_two_inserted': inserted_l2}


# ═════════════════════════════════════════════════════════════════
#  CHART OF ACCOUNTS — Levels 3, 4, 5
#  L3: <L2code>-NN        e.g. A1-01   (code_length 5,  Heading Account)
#  L4: <L3code>-NN        e.g. A1-01-01(code_length 8,  Heading Account)
#  L5: <L4code>-NNN       e.g. A1-01-01-001 (code_length 12, Transactional Account)
# ═════════════════════════════════════════════════════════════════

class LevelThree(db.Model):
    """Level 3 — heading accounts under a Level 2 (code: A1-01)."""
    __tablename__ = 'level_three'

    id             = db.Column(db.Integer, primary_key=True)
    code_length    = db.Column(db.Integer, nullable=False, default=5)        # fixed = 5
    level_two_id   = db.Column(db.Integer, db.ForeignKey('level_two.id', ondelete='RESTRICT'), nullable=False)
    level_two_code = db.Column(db.String(10), nullable=False)                # denormalised for search
    code           = db.Column(db.String(20), nullable=False, unique=True)
    drawers        = db.Column(db.String(200), nullable=False)
    description    = db.Column(db.String(255), nullable=False, default='Heading Account')
    status         = db.Column(db.String(10), nullable=False, default='active')  # active | inactive
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    level_two   = db.relationship('LevelTwo', backref=db.backref('level_threes', lazy=True))
    level_fours = db.relationship('LevelFour', backref=db.backref('level_three', lazy=True), lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'code_length': self.code_length,
            'level_two_id': self.level_two_id, 'level_two_code': self.level_two_code,
            'code': self.code, 'drawers': self.drawers, 'description': self.description,
            'status': self.status or 'active',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'child_count': len(self.level_fours) if self.level_fours is not None else 0,
        }


class LevelFour(db.Model):
    """Level 4 — heading accounts under a Level 3 (code: A1-01-01)."""
    __tablename__ = 'level_four'

    id               = db.Column(db.Integer, primary_key=True)
    code_length      = db.Column(db.Integer, nullable=False, default=8)      # fixed = 8
    level_three_id   = db.Column(db.Integer, db.ForeignKey('level_three.id', ondelete='RESTRICT'), nullable=False)
    level_three_code = db.Column(db.String(20), nullable=False)
    code             = db.Column(db.String(30), nullable=False, unique=True)
    drawers          = db.Column(db.String(200), nullable=False)
    description      = db.Column(db.String(255), nullable=False, default='Heading Account')
    status           = db.Column(db.String(10), nullable=False, default='active')  # active | inactive
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    level_fives = db.relationship('LevelFive', backref=db.backref('level_four', lazy=True), lazy=True)

    def to_dict(self):
        return {
            'id': self.id, 'code_length': self.code_length,
            'level_three_id': self.level_three_id, 'level_three_code': self.level_three_code,
            'code': self.code, 'drawers': self.drawers, 'description': self.description,
            'status': self.status or 'active',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'child_count': len(self.level_fives) if self.level_fives is not None else 0,
        }


class LevelFive(db.Model):
    """Level 5 — transactional accounts under a Level 4 (code: A1-01-01-001)."""
    __tablename__ = 'level_five'

    id              = db.Column(db.Integer, primary_key=True)
    code_length     = db.Column(db.Integer, nullable=False, default=12)      # fixed = 12
    level_four_id   = db.Column(db.Integer, db.ForeignKey('level_four.id', ondelete='RESTRICT'), nullable=False)
    level_four_code = db.Column(db.String(30), nullable=False)
    code            = db.Column(db.String(40), nullable=False, unique=True)
    drawers         = db.Column(db.String(250), nullable=False)
    description     = db.Column(db.String(255), nullable=False, default='Transactional Account')
    status          = db.Column(db.String(10), nullable=False, default='active')  # active | inactive
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'code_length': self.code_length,
            'level_four_id': self.level_four_id, 'level_four_code': self.level_four_code,
            'code': self.code, 'drawers': self.drawers, 'description': self.description,
            'status': self.status or 'active',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }


# ── Auto code generation (shared by routes and the seeder) ───────
def _next_child_code(parent_code, model, code_col, parent_id_col, parent_id, width):
    """Return ``<parent_code>-<n>`` zero-padded to ``width`` digits.

    Scans existing children of ``parent_id`` for the highest numeric suffix and
    increments it. Starts at 1 when the parent has no children, so the first
    child of A1 is A1-01 and the first child of A1-01-01 is A1-01-01-001.
    """
    import re as _re
    rows = model.query.filter(parent_id_col == parent_id).all()
    pattern = _re.compile(r'^' + _re.escape(parent_code) + r'-(\d+)$')
    highest = 0
    for r in rows:
        m = pattern.match(getattr(r, 'code') or '')
        if m:
            highest = max(highest, int(m.group(1)))
    candidate = f'{parent_code}-{highest + 1:0{width}d}'
    # Guard against collisions from manually inserted codes.
    while model.query.filter(code_col == candidate).first():
        highest += 1
        candidate = f'{parent_code}-{highest + 1:0{width}d}'
    return candidate


def next_level_three_code(level_two):
    return _next_child_code(level_two.code, LevelThree, LevelThree.code,
                            LevelThree.level_two_id, level_two.id, 2)


def next_level_four_code(level_three):
    return _next_child_code(level_three.code, LevelFour, LevelFour.code,
                            LevelFour.level_three_id, level_three.id, 2)


def next_level_five_code(level_four):
    return _next_child_code(level_four.code, LevelFive, LevelFive.code,
                            LevelFive.level_four_id, level_four.id, 3)


def seed_coa_levels_3_4_5():
    """Idempotently insert the Level 3/4/5 defaults.

    Records are matched on (parent, drawers); codes are generated by the same
    algorithm the UI uses, so re-running never creates duplicates.
    """
    from database.coa_seed_data import (LEVEL_THREE_SEED, LEVEL_FOUR_SEED, LEVEL_FIVE_SEED)
    counts = {'level_three': 0, 'level_four': 0, 'level_five': 0}

    # ---- Level 3 (parent = level_two.code) ----
    l2_by_code = {r.code: r for r in LevelTwo.query.all()}
    for parent_code, drawers in LEVEL_THREE_SEED:
        parent = l2_by_code.get(parent_code)
        if not parent:
            continue
        exists = LevelThree.query.filter_by(level_two_id=parent.id, drawers=drawers).first()
        if exists:
            continue
        db.session.add(LevelThree(
            code_length=5, level_two_id=parent.id, level_two_code=parent.code,
            code=next_level_three_code(parent), drawers=drawers,
            description='Heading Account',
        ))
        db.session.flush()          # so the next code sees this row
        counts['level_three'] += 1
    if counts['level_three']:
        db.session.commit()

    # ---- Level 4 (parent = level_three.code) ----
    l3_by_code = {r.code: r for r in LevelThree.query.all()}
    for parent_code, drawers in LEVEL_FOUR_SEED:
        parent = l3_by_code.get(parent_code)
        if not parent:
            continue
        exists = LevelFour.query.filter_by(level_three_id=parent.id, drawers=drawers).first()
        if exists:
            continue
        db.session.add(LevelFour(
            code_length=8, level_three_id=parent.id, level_three_code=parent.code,
            code=next_level_four_code(parent), drawers=drawers,
            description='Heading Account',
        ))
        db.session.flush()
        counts['level_four'] += 1
    if counts['level_four']:
        db.session.commit()

    # ---- Level 5 (parent = level_four.code) ----
    l4_by_code = {r.code: r for r in LevelFour.query.all()}
    for parent_code, drawers in LEVEL_FIVE_SEED:
        parent = l4_by_code.get(parent_code)
        if not parent:
            continue
        exists = LevelFive.query.filter_by(level_four_id=parent.id, drawers=drawers).first()
        if exists:
            continue
        db.session.add(LevelFive(
            code_length=12, level_four_id=parent.id, level_four_code=parent.code,
            code=next_level_five_code(parent), drawers=drawers,
            description='Transactional Account',
        ))
        db.session.flush()
        counts['level_five'] += 1
    if counts['level_five']:
        db.session.commit()

    return counts


# ═════════════════════════════════════════════════════════════════
#  DEPARTMENT LOCATION  +  BUYER DEPARTMENT
#  A buyer (company / HR) has many departments; each department sits
#  at one location. Locations are a shared lookup with quick-add.
# ═════════════════════════════════════════════════════════════════

class BuyerDepartment(db.Model):
    """A department belonging to a buyer. The location is entered manually
    on the buyer form and stored here (no lookup table)."""
    __tablename__ = 'buyer_departments'

    id                 = db.Column(db.Integer, primary_key=True)
    buyer_id           = db.Column(db.Integer, db.ForeignKey('buyers.id', ondelete='CASCADE'),
                                   nullable=False)
    department_name    = db.Column(db.String(150), nullable=False)
    department_name_ar = db.Column(db.String(150))
    location_name      = db.Column(db.String(150))
    location_name_ar   = db.Column(db.String(150))
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)

    buyer    = db.relationship('BuyerMaster',
                               backref=db.backref('departments', lazy=True,
                                                  cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'buyer_id': self.buyer_id,
            'department_name': self.department_name or '',
            'department_name_ar': self.department_name_ar or '',
            'location_name': self.location_name or '',
            'location_name_ar': self.location_name_ar or '',
        }


# ═════════════════════════════════════════════════════════════════
# FINANCIAL YEAR (Master) + FINANCIAL YEAR DETAIL (Financial Months)
# ═════════════════════════════════════════════════════════════════

import calendar as _calendar

_MONTH_ABBR = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']


class FinancialYear(db.Model):
    __tablename__ = 'financial_year'
    id             = db.Column(db.Integer, primary_key=True)
    financial_year = db.Column(db.String(20), unique=True, nullable=False)  # FY-2026
    range          = db.Column(db.String(60))                               # 01-Jan-2026 → 31-Dec-2026
    year           = db.Column(db.Integer)                                  # 2026
    status         = db.Column(db.String(10), default='Open')               # Open / Closed
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    months = db.relationship('FinancialYearDetail', backref='parent',
                             cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'financial_year': self.financial_year,
            'range': self.range or '',
            'year': self.year,
            'status': self.status or 'Open',
            'months_count': len(self.months),
        }


class FinancialYearDetail(db.Model):
    __tablename__ = 'financial_year_detail'
    id                = db.Column(db.Integer, primary_key=True)
    financial_year_id = db.Column(db.Integer,
                                  db.ForeignKey('financial_year.id', ondelete='CASCADE'),
                                  nullable=False)
    financial_year    = db.Column(db.String(20))   # FY-2026 (copied from parent)
    label             = db.Column(db.String(30))    # FM-Jan-2026
    range             = db.Column(db.String(60))    # 01-Jan-2026 → 31-Jan-2026
    month_no          = db.Column(db.Integer)       # 1..12
    status            = db.Column(db.String(10), default='Open')
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'financial_year_id': self.financial_year_id,
            'financial_year': self.financial_year or '',
            'label': self.label or '',
            'range': self.range or '',
            'month_no': self.month_no,
            'status': self.status or 'Open',
        }


def build_financial_months(year):
    """Return a list of 12 dicts describing each financial month for a year,
    with correct last-day handling (incl. leap-year February)."""
    fy = f'FY-{year}'
    out = []
    for m in range(1, 13):
        last = _calendar.monthrange(year, m)[1]     # correct leap-year Feb
        abbr = _MONTH_ABBR[m - 1]
        rng  = f'01-{abbr}-{year} → {last:02d}-{abbr}-{year}'
        out.append({
            'financial_year': fy,
            'label': f'FM-{abbr}-{year}',
            'range': rng,
            'month_no': m,
            'status': 'Open',
        })
    return out


# ═════════════════════════════════════════════════════════════════
# PURCHASE / SALES TAX CODES
# ═════════════════════════════════════════════════════════════════

class PurchaseTaxCode(db.Model):
    __tablename__ = 'purchase_tax_code'
    id           = db.Column(db.Integer, primary_key=True)
    account_code = db.Column(db.String(60), nullable=False, index=True)   # VAT 15%
    tax_code     = db.Column(db.String(20), unique=True, nullable=False, index=True)  # P1
    section      = db.Column(db.String(255), nullable=False)
    status       = db.Column(db.String(10), default='Active')             # Active / Inactive
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'account_code': self.account_code,
            'tax_code': self.tax_code, 'section': self.section,
            'status': self.status or 'Active',
        }


class SalesTaxCode(db.Model):
    __tablename__ = 'sales_tax_code'
    id           = db.Column(db.Integer, primary_key=True)
    account_code = db.Column(db.String(60), nullable=False, index=True)   # VAT 15%
    tax_code     = db.Column(db.String(20), unique=True, nullable=False, index=True)  # S1
    section      = db.Column(db.String(255), nullable=False)
    status       = db.Column(db.String(10), default='Active')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'account_code': self.account_code,
            'tax_code': self.tax_code, 'section': self.section,
            'status': self.status or 'Active',
        }


DEFAULT_PURCHASE_TAX_CODES = [
    ('VAT 15%',      'P1',   'Standard rated domestic purchases'),
    ('VAT 15%',      'PC',   'Imports subject to VAT paid at customs'),
    ('Import',       'PRCM', 'Imports subject to VAT accounted for through Reverse Charge Mechanism (RCM)'),
    ('VAT 0%',       'P0',   'Zero rated purchases'),
    ('Exempt',       'PE',   'Exempt purchases'),
    ('Out of Scope', 'POC',  'Out of Scope expenses'),
]

DEFAULT_SALES_TAX_CODES = [
    ('VAT 15%',         'S1',  'Standard rated supplies'),
    ('VAT 0%',          'S0',  'Zero rated domestic supplies'),
    ('VAT 0%',          'SE',  'Exports'),
    ('Exempt Supplies', 'SES', 'Exempt supplies'),
    ('Out of Scope',    'SOC', 'Out of Scope expenses'),
]


def seed_tax_codes():
    """Idempotently seed default purchase & sales tax codes."""
    added = 0
    for acc, code, section in DEFAULT_PURCHASE_TAX_CODES:
        if not PurchaseTaxCode.query.filter_by(tax_code=code).first():
            db.session.add(PurchaseTaxCode(account_code=acc, tax_code=code,
                                           section=section, status='Active'))
            added += 1
    for acc, code, section in DEFAULT_SALES_TAX_CODES:
        if not SalesTaxCode.query.filter_by(tax_code=code).first():
            db.session.add(SalesTaxCode(account_code=acc, tax_code=code,
                                        section=section, status='Active'))
            added += 1
    if added:
        db.session.commit()
    return added


# ═════════════════════════════════════════════════════════════════
#  JOURNAL ENTRIES  (accounting module)
#  Single-row-per-entry as specified: each row carries one debit/credit
#  line plus the auto-filled Chart-of-Accounts drawer hierarchy taken
#  from the selected Level 5 account.
# ═════════════════════════════════════════════════════════════════
class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'

    id                 = db.Column(db.Integer, primary_key=True)
    je_no              = db.Column(db.String(30), unique=True, nullable=False)
    je_date            = db.Column(db.Date, nullable=False)
    month              = db.Column(db.String(20))
    level5_code        = db.Column(db.String(20), nullable=False)
    level1_drawer      = db.Column(db.String(100))
    level2_drawer      = db.Column(db.String(100))
    level3_drawer      = db.Column(db.String(100))
    level4_drawer      = db.Column(db.String(100))
    level5_drawer      = db.Column(db.String(100))
    description        = db.Column(db.Text)
    project_client     = db.Column(db.String(150))
    debit              = db.Column(db.Numeric(18, 2), default=0)
    credit             = db.Column(db.Numeric(18, 2), default=0)
    payment_ref_method = db.Column(db.String(100))
    je_balance         = db.Column(db.Numeric(18, 2), default=0)
    status             = db.Column(db.String(20), default='Draft')
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at         = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        def _f(v):
            return float(v) if v is not None else 0.0
        return {
            'id': self.id,
            'je_no': self.je_no,
            'je_date': self.je_date.strftime('%Y-%m-%d') if self.je_date else '',
            'month': self.month or '',
            'level5_code': self.level5_code or '',
            'level1_drawer': self.level1_drawer or '',
            'level2_drawer': self.level2_drawer or '',
            'level3_drawer': self.level3_drawer or '',
            'level4_drawer': self.level4_drawer or '',
            'level5_drawer': self.level5_drawer or '',
            'description': self.description or '',
            'project_client': self.project_client or '',
            'debit': _f(self.debit),
            'credit': _f(self.credit),
            'payment_ref_method': self.payment_ref_method or '',
            'je_balance': _f(self.je_balance),
            'status': self.status or 'Draft',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
        }


def next_je_no():
    """Generate the next unique JE number in the JE-000001 format."""
    last = JournalEntry.query.order_by(JournalEntry.id.desc()).first()
    n = 1
    if last and last.je_no and last.je_no.startswith('JE-'):
        try:
            n = int(last.je_no.split('-')[1]) + 1
        except (ValueError, IndexError):
            n = (last.id or 0) + 1
    return f'JE-{n:06d}'


# ═════════════════════════════════════════════════════════════════
#  SALARY CONSOLIDATION  (payroll)
#  One row per employee per payroll run. Most fields are copied from
#  the Employee record at generation time; day/OT/salary figures are
#  computed. Editable fields (absent, holidays, bonus, advance) let the
#  user adjust before finalising.  See SALARY_STATUS.md for the exact
#  default formulas used.
# ═════════════════════════════════════════════════════════════════
class SalaryConsolidation(db.Model):
    __tablename__ = 'salary_consolidation'

    id               = db.Column(db.Integer, primary_key=True)
    employee_id      = db.Column(db.Integer, db.ForeignKey('employees.id'))
    salary_order     = db.Column(db.String(30))          # payroll batch ref (SAL-000001)
    month_from       = db.Column(db.Date)                # range start (e.g. 20-06-26)
    month_to         = db.Column(db.Date)                # range end   (e.g. 20-07-26)
    month            = db.Column(db.String(20))          # derived month name
    buyer_id         = db.Column(db.Integer)             # company / buyer filter
    department       = db.Column(db.String(150))
    kafeel           = db.Column(db.String(200))
    sheet_no         = db.Column(db.String(30))          # time sheet no
    name             = db.Column(db.String(200))         # employee name
    profession       = db.Column(db.String(150))
    nationality      = db.Column(db.String(100))
    iqama            = db.Column(db.String(50))
    day_hour_salary  = db.Column(db.Numeric(12, 2), default=0)
    allowance        = db.Column(db.Numeric(12, 2), default=0)
    days             = db.Column(db.Integer, default=0)
    fridays          = db.Column(db.Integer, default=0)
    holidays         = db.Column(db.Integer, default=0)
    absent           = db.Column(db.Integer, default=0)
    monthly_salary   = db.Column(db.Numeric(12, 2), default=0)
    total_hours      = db.Column(db.Numeric(10, 2), default=0)
    working_hour     = db.Column(db.Numeric(10, 2), default=0)
    ot_hour          = db.Column(db.Numeric(10, 2), default=0)
    extra_ot_hour    = db.Column(db.Numeric(10, 2), default=0)
    ot_rate          = db.Column(db.Numeric(12, 2), default=0)
    ot_amount        = db.Column(db.Numeric(12, 2), default=0)
    bonus            = db.Column(db.Numeric(12, 2), default=0)
    total_salary     = db.Column(db.Numeric(12, 2), default=0)
    advance          = db.Column(db.Numeric(12, 2), default=0)
    salary_payable   = db.Column(db.Numeric(12, 2), default=0)
    paid_balance     = db.Column(db.Numeric(12, 2), default=0)
    iqama_expiry     = db.Column(db.Date)
    status           = db.Column(db.String(20), default='Draft')
    bank_code        = db.Column(db.String(60))
    iban_no          = db.Column(db.String(60))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        def _f(v): return float(v) if v is not None else 0.0
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'salary_order': self.salary_order or '',
            'month_from': self.month_from.strftime('%Y-%m-%d') if self.month_from else '',
            'month_to': self.month_to.strftime('%Y-%m-%d') if self.month_to else '',
            'month': self.month or '',
            'buyer_id': self.buyer_id,
            'department': self.department or '',
            'kafeel': self.kafeel or '',
            'sheet_no': self.sheet_no or '',
            'name': self.name or '',
            'profession': self.profession or '',
            'nationality': self.nationality or '',
            'iqama': self.iqama or '',
            'day_hour_salary': _f(self.day_hour_salary),
            'allowance': _f(self.allowance),
            'days': self.days or 0,
            'fridays': self.fridays or 0,
            'holidays': self.holidays or 0,
            'absent': self.absent or 0,
            'monthly_salary': _f(self.monthly_salary),
            'total_hours': _f(self.total_hours),
            'working_hour': _f(self.working_hour),
            'ot_hour': _f(self.ot_hour),
            'extra_ot_hour': _f(self.extra_ot_hour),
            'ot_rate': _f(self.ot_rate),
            'ot_amount': _f(self.ot_amount),
            'bonus': _f(self.bonus),
            'total_salary': _f(self.total_salary),
            'advance': _f(self.advance),
            'salary_payable': _f(self.salary_payable),
            'paid_balance': _f(self.paid_balance),
            'iqama_expiry': self.iqama_expiry.strftime('%Y-%m-%d') if self.iqama_expiry else '',
            'status': self.status or 'Draft',
            'bank_code': self.bank_code or '',
            'iban_no': self.iban_no or '',
        }


def next_salary_order():
    """Next payroll batch reference in SAL-000001 format."""
    last = SalaryConsolidation.query.order_by(SalaryConsolidation.id.desc()).first()
    n = 1
    if last and last.salary_order and last.salary_order.startswith('SAL-'):
        try:
            n = int(last.salary_order.split('-')[1]) + 1
        except (ValueError, IndexError):
            n = (last.id or 0) + 1
    return f'SAL-{n:06d}'

# ═════════════════════════════════════════════════════════════════
#  EMPLOYEE WORK ALLOCATION  (replaces the old work_allocations table)
#  One row per employee assignment. Multiple employees are added on the
#  work-allocation form (each becomes a row). Fields mirror the employee
#  plus the assignment specifics (buyer, department, location, shift).
# ═════════════════════════════════════════════════════════════════
class EmployeeWorkAllocation(db.Model):
    __tablename__ = 'employee_work_allocation'

    id                = db.Column(db.Integer, primary_key=True)
    employee_id       = db.Column(db.Integer, db.ForeignKey('employees.id'))
    kafeel            = db.Column(db.String(200))
    name              = db.Column(db.String(200))
    nationality       = db.Column(db.String(100))
    profession        = db.Column(db.String(150))
    iqama             = db.Column(db.String(50))
    month             = db.Column(db.String(20))
    joining_date      = db.Column(db.Date)
    end_date          = db.Column(db.Date)
    buyer_id            = db.Column(db.Integer, db.ForeignKey('buyers.id'))
    buyer_name          = db.Column(db.String(200))
    buyer_name_ar       = db.Column(db.String(200))
    buyer_department    = db.Column(db.String(150))
    buyer_department_ar = db.Column(db.String(150))
    location            = db.Column(db.String(150))
    location_ar         = db.Column(db.String(150))
    shift             = db.Column(db.String(10))        # 'day' or 'night'
    status            = db.Column(db.String(20), default='active')
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    created_by        = db.Column(db.Integer, db.ForeignKey('users.id'))

    employee = db.relationship('Employee', foreign_keys=[employee_id], lazy=True)
    buyer    = db.relationship('BuyerMaster', foreign_keys=[buyer_id], lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'kafeel': self.kafeel or '',
            'name': self.name or '',
            'nationality': self.nationality or '',
            'profession': self.profession or '',
            'iqama': self.iqama or '',
            'month': self.month or '',
            'joining_date': self.joining_date.strftime('%Y-%m-%d') if self.joining_date else '',
            'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else '',
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer_name or '',
            'buyer_name_ar': self.buyer_name_ar or '',
            'buyer_department': self.buyer_department or '',
            'buyer_department_ar': self.buyer_department_ar or '',
            'location': self.location or '',
            'location_ar': self.location_ar or '',
            'shift': self.shift or '',
            'status': self.status or 'active',
            # ── aliases so the existing Work Allocation grid keeps working ──
            'company': self.buyer_name or '',
            'company_ar': self.buyer_name_ar or '',
            'department': self.buyer_department or '',
            'department_ar': self.buyer_department_ar or '',
            'section': self.location or '',
            'section_ar': self.location_ar or '',
            'shift_type': self.shift or '',
            # employee details the grid shows
            'employee_code': (self.employee.employee_code if self.employee else ''),
            'name_ar': (self.employee.name_ar if self.employee else ''),
            'passport_number': (self.employee.passport_number if self.employee else ''),
            'kafeel_name': self.kafeel or '',
            'iqama_number': self.iqama or '',
        }