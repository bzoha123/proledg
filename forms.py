from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, BooleanField, PasswordField, DateField
from wtforms.validators import DataRequired, Email, Length, Optional

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 80)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class SellerForm(FlaskForm):
    # Basic
    name = StringField('Name* / الاسم*', validators=[DataRequired(), Length(2, 200)])
    vat_number = StringField('VAT Number* / رقم ضريبة القيمة المضافة*', validators=[DataRequired(), Length(max=100)])
    crn = StringField('CRN* / رقم السجل التجاري*', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone / الهاتف', validators=[Optional(), Length(max=30)])
    fax = StringField('Fax / الفاكس', validators=[Optional(), Length(max=30)])
    email = StringField('Email / البريد الإلكتروني', validators=[Optional(), Email(), Length(max=150)])
    website = StringField('Website / الموقع الإلكتروني', validators=[Optional(), Length(max=200)])
    report_color = StringField('Report Heading Color Code / رمز لون عنوان التقرير*', validators=[Optional()])
    logo = FileField('Browse Logo / تصفح الشعار', validators=[FileAllowed(['jpg','jpeg','png'], 'Images only!')])
    bg_logo = FileField('Browse Background Logo / تصفح الشعار الخلفي', validators=[FileAllowed(['jpg','jpeg','png'], 'Images only!')])
    # Address
    street_name = StringField('Street Name / اسم الشارع', validators=[Optional(), Length(max=250)])
    building_number = StringField('Building Number / رقم المبنى', validators=[Optional(), Length(max=50)])
    additional_number = StringField('Additional Number / رقم إضافي', validators=[Optional(), Length(max=50)])
    district = StringField('District / المنطقة', validators=[Optional(), Length(max=100)])
    city = StringField('City / المدينة', validators=[Optional(), Length(max=100)])
    postal_code = StringField('Postal Code / الرمز البريدي', validators=[Optional(), Length(max=20)])
    country = StringField('Country / الدولة', validators=[Optional(), Length(max=100)])

class BankForm(FlaskForm):
    bank_name = StringField('Bank Name / اسم البنك', validators=[DataRequired(), Length(max=150)])
    account_number = StringField('Account Number / رقم الحساب', validators=[Optional(), Length(max=50)])
    branch = StringField('Branch / الفرع', validators=[Optional(), Length(max=100)])
    swift_code = StringField('SWIFT Code', validators=[Optional(), Length(max=20)])
    iban = StringField('IBAN', validators=[Optional(), Length(max=50)])
    is_primary = BooleanField('Primary / رئيسي')

class SearchForm(FlaskForm):
    q = StringField('Search', validators=[Optional()])
