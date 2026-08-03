"""
Store pages — Fixed Asset / Consumable / Non-Consumable.
Grid view only (no add form); rows are created from Item Master's Store field.
"""
from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from models import FixedAssetStore, ConsumableStore, NonConsumableStore

stores_bp = Blueprint('stores', __name__, url_prefix='/stores')

_STORES = {
    'fixed-asset':    (FixedAssetStore,   'Fixed Asset Store',   'مخزن الأصول الثابتة'),
    'consumable':     (ConsumableStore,   'Consumable Store',    'المخزن الاستهلاكي'),
    'non-consumable': (NonConsumableStore,'Non-Consumable Store','المخزن غير الاستهلاكي'),
}


@stores_bp.route('/<key>')
@login_required
def store_page(key):
    if key not in _STORES:
        return 'Unknown store', 404
    _model, title_en, title_ar = _STORES[key]
    return render_template('stores/store_grid.html',
                           store_key=key, title_en=title_en, title_ar=title_ar)


@stores_bp.route('/<key>/data')
@login_required
def store_data(key):
    if key not in _STORES:
        return jsonify([])
    model = _STORES[key][0]
    rows = model.query.order_by(model.id.desc()).all()
    return jsonify([r.to_dict() for r in rows])