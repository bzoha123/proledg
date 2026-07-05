from flask import Blueprint, render_template
from flask_login import login_required
from models import db, Seller, SellerDocument
from datetime import datetime, timedelta
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    total_sellers = Seller.query.count()
    active_sellers = Seller.query.filter_by(status='active').count()
    inactive_sellers = Seller.query.filter_by(status='inactive').count()

    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
    new_this_month = Seller.query.filter(Seller.created_at >= month_start).count()

    expiry_threshold = datetime.utcnow().date() + timedelta(days=30)
    expiring_docs = SellerDocument.query.filter(
        SellerDocument.expiry_date != None,
        SellerDocument.expiry_date <= expiry_threshold,
        SellerDocument.expiry_date >= datetime.utcnow().date()
    ).count()

    recent_sellers = Seller.query.order_by(Seller.created_at.desc()).limit(8).all()

    stats = {
        'total': total_sellers,
        'active': active_sellers,
        'inactive': inactive_sellers,
        'new_month': new_this_month,
        'expiring_docs': expiring_docs,
    }
    return render_template('dashboard/index.html', stats=stats, recent_sellers=recent_sellers)