import os
from flask import Flask, session, request
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import config
from models import db, User

login_manager = LoginManager()
csrf = CSRFProtect()

# Try to import Flask-Babel; gracefully degrade if missing
try:
    from flask_babel import Babel
    BABEL_AVAILABLE = True
except ImportError:
    BABEL_AVAILABLE = False

def get_locale():
    return session.get('lang', 'en')

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

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
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.sellers import sellers_bp
    from routes.employees import employees_bp
    from routes.work_allocations import wa_bp
    from routes.invoices import inv_bp
    from routes.purchase import pur_bp
    from routes.lookups import lookups_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sellers_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(wa_bp)
    app.register_blueprint(inv_bp)
    app.register_blueprint(pur_bp)
    app.register_blueprint(lookups_bp)

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('errors/403.html'), 403

    # Jinja filters
    @app.template_filter('filesizeformat')
    def filesizeformat(value):
        if value is None:
            return 'N/A'
        if value < 1024:
            return f'{value} B'
        elif value < 1024 * 1024:
            return f'{value/1024:.1f} KB'
        else:
            return f'{value/(1024*1024):.1f} MB'

    return app

app = create_app()

def init_db():
    """Initialize database and create default admin user."""
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@sellerms.com', role='admin')
            admin.set_password('Admin@123')
            db.session.add(admin)
            staff = User(username='staff', email='staff@sellerms.com', role='staff')
            staff.set_password('Staff@123')
            db.session.add(staff)
            db.session.commit()
            print('Default users created:  admin / Admin@123  |  staff / Staff@123')

if __name__ == '__main__':
    os.makedirs('database', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)
    init_db()
    app.run(debug=True, port=5000)