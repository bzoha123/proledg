from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from forms import LoginForm

def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page or url_for('dashboard.index'))
        flash(_t('Invalid username or password.', 'اسم المستخدم أو كلمة المرور غير صحيحة'), 'danger')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash(_t('You have been logged out.', 'تم تسجيل خروجك بنجاح'), 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/set_language/<lang>')
def set_language(lang):
    supported = ['en', 'ar']
    if lang in supported:
        session['lang'] = lang
    return redirect(request.referrer or url_for('dashboard.index'))