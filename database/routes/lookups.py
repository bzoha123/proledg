"""Lookups — blueprint + shared helpers + module registration.

The original 911-line lookups.py was split into focused modules that live
alongside this file in database/routes/:

    professions.py
    allowance_types.py
    buyers.py
    allowances.py
    items.py

They all register their routes on the lookups_bp defined here, so every
endpoint name is unchanged (lookups.list_buyers, lookups.items_list, ...).
"""
from functools import wraps

from flask import Blueprint, request, redirect, url_for, flash, session
from flask_login import current_user

lookups_bp = Blueprint('lookups', __name__)


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


from . import professions           
from . import allowance_types       
from . import buyers                
from . import allowances            
from . import items                 

__all__ = ['lookups_bp', 'admin_required', '_t']