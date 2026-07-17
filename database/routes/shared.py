"""Shared helpers for the lookups sub-blueprints.

Kept in one place so every sub-module (professions, buyers, items, ...) uses the
exact same admin check and translation helper that the original lookups.py had.
"""
from functools import wraps

from flask import request, redirect, url_for, flash, session
from flask_login import current_user


def admin_required(f):
    @wraps(f)
    def d(*a, **k):
        if not current_user.is_admin():
            flash('Access denied', 'danger')
            return redirect(request.referrer or url_for('dashboard.index'))
        return f(*a, **k)
    return d


def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en