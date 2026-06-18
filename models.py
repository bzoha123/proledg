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
    id = db.Column(db.Integer, primary_key=True)
    buyer_name_en = db.Column(db.String(200), nullable=False)
    buyer_name_ar = db.Column(db.String(200))
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


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
    rate             = db.Column(db.Float, default=0)
    po_rate          = db.Column(db.Float, default=0)
    po_number        = db.Column(db.String(50))
    salary_type      = db.Column(db.String(20))   # azad / salary / kafalat
    food_allowance   = db.Column(db.Float, default=0)
    rent             = db.Column(db.Float, default=0)
    basic_salary     = db.Column(db.Float, default=0)
    net_salary       = db.Column(db.Float, default=0)
    working_hours    = db.Column(db.Float, default=8)
    overtime_rate    = db.Column(db.Float, default=0)

    # Work Information
    joining_date     = db.Column(db.Date)
    department       = db.Column(db.String(100))
    department_ar    = db.Column(db.String(100))
    shift_type       = db.Column(db.String(20), default='day')  # day/evening/night
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