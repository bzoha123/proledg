import os
from flask import Flask, session, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import config
from models import db, User, ActivityLog

try:
    from flask_migrate import Migrate
except Exception as exc:  # pragma: no cover - defensive for env issues
    Migrate = None
    MIGRATE_IMPORT_ERROR = exc
else:
    MIGRATE_IMPORT_ERROR = None

# Import document blueprints
from database.routes.vendor_doc import vendor_doc_bp
from database.routes.buyer_doc import buyer_doc_bp

# Try to import Flask-Babel; gracefully degrade if missing
try:
    import importlib
    flask_babel = importlib.import_module('flask_babel')
    Babel = flask_babel.Babel
    BABEL_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    Babel = None
    BABEL_AVAILABLE = False

login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate() if Migrate is not None else None


def get_locale():
    return session.get('lang', 'en')


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    if migrate is not None:
        migrate.init_app(app, db)

    if BABEL_AVAILABLE:
        babel = Babel()
        babel.init_app(app, locale_selector=get_locale)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        locale = session.get('lang', 'en')
        return dict(
            current_locale=locale,
            languages=app.config.get('LANGUAGES', {}),
        )

    # Register blueprints
    from database.routes.auth import auth_bp
    from database.routes.dashboard import dashboard_bp
    from database.routes.sellers import sellers_bp
    from database.routes.employees import employees_bp
    from database.routes.work_allocations import wa_bp
    from database.routes.purchase import pur_bp
    from database.routes.sales import sale_bp
    from database.routes.coa import coa_bp
    from database.routes.journal import journal_bp
    from database.routes.payroll import payroll_bp
    from database.routes import lookups_bp
    from database.routes.employee_import import emp_import_bp
    from database.routes.tax_codes import tax_bp
    from database.routes.financial import financial_bp  # ✅ ADD THIS
    
    app.register_blueprint(emp_import_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sellers_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(wa_bp)
    app.register_blueprint(pur_bp)
    app.register_blueprint(sale_bp)
    app.register_blueprint(coa_bp)
    app.register_blueprint(journal_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(lookups_bp)
    app.register_blueprint(vendor_doc_bp)
    app.register_blueprint(buyer_doc_bp)
    app.register_blueprint(financial_bp)  # ✅ ADD THIS
    app.register_blueprint(tax_bp)   

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    # Jinja filters
    @app.template_filter('filesizeformat')
    def filesizeformat_filter(value):
        if value is None:
            return 'N/A'
        if value < 1024:
            return f'{value} B'
        elif value < 1024 * 1024:
            return f'{value/1024:.1f} KB'
        else:
            return f'{value/(1024*1024):.1f} MB'

    return app


def init_db(app):
    """Initialize database and create default admin user."""
    from sqlalchemy.exc import OperationalError

    with app.app_context():
        try:
            db.create_all()
        except OperationalError as exc:
            if 'already exists' in str(exc).lower():
                print('Database already initialized, skipping create_all.')
            else:
                raise

        # Create default users if they don't exist
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@sellerms.com', role='admin')
            admin.set_password('Admin@123')
            db.session.add(admin)
            
            staff = User(username='staff', email='staff@sellerms.com', role='staff')
            staff.set_password('Staff@123')
            db.session.add(staff)
            db.session.commit()
            print('Default users created: admin / Admin@123 | staff / Staff@123')

        # ✅ FIX: Add tax_rate column to existing tax code tables
        try:
            from sqlalchemy import text
            # Check if tax_rate column exists in purchase_tax_code
            result = db.session.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='purchase_tax_code'"
            )).fetchone()
            
            if result:
                sql = result[0]
                if 'tax_rate' not in sql:
                    db.session.execute(text(
                        "ALTER TABLE purchase_tax_code ADD COLUMN tax_rate NUMERIC(10, 4) DEFAULT 0"
                    ))
                    db.session.commit()
                    print("Added tax_rate column to purchase_tax_code")
                
                # Check sales_tax_code
                result2 = db.session.execute(text(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='sales_tax_code'"
                )).fetchone()
                
                if result2 and 'tax_rate' not in result2[0]:
                    db.session.execute(text(
                        "ALTER TABLE sales_tax_code ADD COLUMN tax_rate NUMERIC(10, 4) DEFAULT 0"
                    ))
                    db.session.commit()
                    print("Added tax_rate column to sales_tax_code")
                    
                # Update existing tax codes with default rates
                try:
                    # Update purchase tax codes
                    db.session.execute(text(
                        "UPDATE purchase_tax_code SET tax_rate = 15 WHERE tax_code IN ('15', '15C', '15R')"
                    ))
                    db.session.execute(text(
                        "UPDATE purchase_tax_code SET tax_rate = 0 WHERE tax_code IN ('0', '0E', '0O')"
                    ))
                    
                    # Update sales tax codes
                    db.session.execute(text(
                        "UPDATE sales_tax_code SET tax_rate = 15 WHERE tax_code IN ('15', '15C', '15R')"
                    ))
                    db.session.execute(text(
                        "UPDATE sales_tax_code SET tax_rate = 0 WHERE tax_code IN ('0', '0E', '0O', '0S')"
                    ))
                    
                    db.session.commit()
                    print("Updated existing tax codes with default tax rates")
                except Exception as e:
                    print(f"Note: Could not update tax rates: {e}")
        except Exception as e:
            print(f"Note: Tax rate migration skipped: {e}")

        # Seed the Chart of Accounts (idempotent — safe on every startup)
        try:
            from models import seed_chart_of_accounts, seed_coa_levels_3_4_5
            result = seed_chart_of_accounts()
            if result['level_one_inserted'] or result['level_two_inserted']:
                print(f"Chart of Accounts seeded: "
                      f"{result['level_one_inserted']} Level 1, "
                      f"{result['level_two_inserted']} Level 2 records inserted.")
            deep = seed_coa_levels_3_4_5()
            if any(deep.values()):
                print(f"Chart of Accounts seeded: "
                      f"{deep['level_three']} Level 3, {deep['level_four']} Level 4, "
                      f"{deep['level_five']} Level 5 records inserted.")
        except Exception as exc:
            print(f'Chart of Accounts seed skipped: {exc}')

        # Seed tax codes (idempotent)
        try:
            from models import seed_tax_codes
            n = seed_tax_codes()
            if n:
                print(f'Tax codes seeded: {n} records inserted.')
        except Exception as exc:
            print(f'Tax code seed skipped: {exc}')


if __name__ == '__main__':
    os.makedirs('database', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)
    # Create uploads subdirectories
    os.makedirs('uploads/vendors', exist_ok=True)
    os.makedirs('uploads/buyers', exist_ok=True)
    os.makedirs('static/uploads/purchase', exist_ok=True)
    os.makedirs('static/uploads/sales', exist_ok=True)
    
    app = create_app()
    init_db(app)
    app.run(debug=True, port=5000)