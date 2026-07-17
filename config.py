import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'seller-ms-secret-key-2024-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'database', 'sellers.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    # Total request size cap (form + line items + ALL attachments in one POST).
    # Must be comfortably larger than the per-file limit (16MB in the upload
    # routes), otherwise a single max-size file can never be saved: the form
    # data pushes the request over the cap and Flask returns a 413 before the
    # route runs.
    MAX_CONTENT_LENGTH = 64 * 1024 * 1024  # 64MB max per request
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    ALLOWED_MIMETYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/msword',  # .doc - add this
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'application/vnd.ms-excel',  # .xls 
}
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # Flask-Babel
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_DEFAULT_TIMEZONE = 'UTC'
    LANGUAGES = {'en': 'English', 'ar': 'العربية'}

    ITEMS_PER_PAGE = 15

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}