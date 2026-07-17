"""Lookups: items routes.

Split out of the original monolithic lookups.py.
Routes register on the shared lookups_bp, so endpoint names are unchanged
(url_for('lookups.list_buyers') etc. keep working).
"""
from flask import (render_template, request, jsonify,
                   redirect, url_for, flash, session)
from flask_login import login_required, current_user

from models import db
from .lookups import lookups_bp, admin_required, _t


# ══════════════════════════════════════════════════════════════════
# ITEM MASTER
# ══════════════════════════════════════════════════════════════════
import urllib.request, urllib.parse, json as _json
from models import ItemMaster, ItemCategory, ItemSubCategory, TaxCategory, VendorMaster

@lookups_bp.route('/items')
@login_required
def items_list():
    cats    = ItemCategory.query.order_by(ItemCategory.name_en).all()
    subcats = ItemSubCategory.query.order_by(ItemSubCategory.name_en).all()
    taxcats = TaxCategory.query.order_by(TaxCategory.name_en).all()
    vendors = VendorMaster.query.order_by(VendorMaster.vendor_name_en).all()
    uoms    = ['unit','hour','day','month','kg','gram','meter','liter','box','piece','set','pair','dozen']
    return render_template('lookups/items.html',
        cats=cats, subcats=subcats, taxcats=taxcats, vendors=vendors, uoms=uoms)

@lookups_bp.route('/items/data')
@login_required
def items_data():
    return jsonify([i.to_dict() for i in ItemMaster.query.order_by(ItemMaster.id.desc()).all()])

@lookups_bp.route('/items/<int:id>/json')
@login_required
def item_json(id):
    return jsonify(ItemMaster.query.get_or_404(id).to_dict())

@lookups_bp.route('/items/add', methods=['POST'])
@login_required
def item_add():
    f = request.form
    item = ItemMaster(
        item_code   = f.get('item_code','').strip(),
        item_type   = f.get('item_type','Product'),
        article_no  = f.get('article_no','').strip(),
        name_en     = f.get('name_en','').strip(),
        name_ar     = f.get('name_ar','').strip(),
        print_name  = f.get('print_name','').strip(),
        uom         = f.get('uom','unit'),
        item_desc   = f.get('item_desc','').strip(),
        category_id     = int(f['category_id'])     if f.get('category_id')     else None,
        sub_category_id = int(f['sub_category_id']) if f.get('sub_category_id') else None,
        tax_category_id = int(f['tax_category_id']) if f.get('tax_category_id') else None,
        vendor_id       = int(f['vendor_id'])        if f.get('vendor_id')       else None,
        main_rate       = float(f.get('main_rate','0') or 0),
        po_rate         = float(f.get('po_rate','0') or 0),
        last_purchase_rate = float(f.get('last_purchase_rate','0') or 0),
        retail_rate     = float(f.get('retail_rate','0') or 0),
        wholesale_rate  = float(f.get('wholesale_rate','0') or 0),
        special_rate    = float(f.get('special_rate','0') or 0),
        mrp             = float(f.get('mrp','0') or 0),
        minimum_sp      = float(f.get('minimum_sp','0') or 0),
        is_active       = f.get('is_active','1') == '1',
        created_by      = current_user.id,
    )
    db.session.add(item); db.session.commit()
    return jsonify({'ok': True, 'id': item.id})

@lookups_bp.route('/items/<int:id>/edit', methods=['POST'])
@login_required
def item_edit(id):
    item = ItemMaster.query.get_or_404(id)
    f = request.form
    item.item_code   = f.get('item_code','').strip()
    item.article_no  = f.get('article_no','').strip()
    item.name_en     = f.get('name_en','').strip()
    item.item_type   = f.get('item_type','Product')
    item.name_ar     = f.get('name_ar','').strip()
    item.print_name  = f.get('print_name','').strip()
    item.uom         = f.get('uom','unit')
    item.item_desc   = f.get('item_desc','').strip()
    item.category_id     = int(f['category_id'])     if f.get('category_id')     else None
    item.sub_category_id = int(f['sub_category_id']) if f.get('sub_category_id') else None
    item.tax_category_id = int(f['tax_category_id']) if f.get('tax_category_id') else None
    item.vendor_id       = int(f['vendor_id'])        if f.get('vendor_id')       else None
    item.main_rate       = float(f.get('main_rate','0') or 0)
    item.po_rate         = float(f.get('po_rate','0') or 0)
    item.last_purchase_rate = float(f.get('last_purchase_rate','0') or 0)
    item.retail_rate     = float(f.get('retail_rate','0') or 0)
    item.wholesale_rate  = float(f.get('wholesale_rate','0') or 0)
    item.special_rate    = float(f.get('special_rate','0') or 0)
    item.mrp             = float(f.get('mrp','0') or 0)
    item.minimum_sp      = float(f.get('minimum_sp','0') or 0)
    item.is_active       = f.get('is_active','1') == '1'
    db.session.commit()
    return jsonify({'ok': True})

@lookups_bp.route('/items/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def item_delete(id):
    db.session.delete(ItemMaster.query.get_or_404(id))
    db.session.commit()
    return jsonify({'ok': True})

@lookups_bp.route('/items/categories/data')
@login_required
def item_cats_data():
    return jsonify([c.to_dict() for c in ItemCategory.query.order_by(ItemCategory.name_en).all()])

@lookups_bp.route('/items/categories/add', methods=['POST'])
@login_required
def item_category_add():
    """Quick-add a category from the Item Master form popup."""
    f = request.form
    name_en = f.get('name_en', '').strip()
    if not name_en:
        return jsonify({'ok': False, 'error': 'Category name (EN) is required'}), 400
    cat = ItemCategory(name_en=name_en, name_ar=f.get('name_ar', '').strip() or None)
    db.session.add(cat)
    db.session.commit()
    return jsonify({'ok': True, 'category': cat.to_dict()})

@lookups_bp.route('/items/sub-categories/<int:cat_id>')
@login_required
def item_subcats(cat_id):
    return jsonify([s.to_dict() for s in ItemSubCategory.query.filter_by(category_id=cat_id).all()])

@lookups_bp.route('/items/sub-categories/add', methods=['POST'])
@login_required
def item_subcategory_add():
    """Quick-add a sub-category from the Item Master form popup."""
    f = request.form
    category_id = f.get('category_id')
    name_en = f.get('name_en', '').strip()
    if not category_id:
        return jsonify({'ok': False, 'error': 'Category is required'}), 400
    if not name_en:
        return jsonify({'ok': False, 'error': 'Sub-category name (EN) is required'}), 400
    sub = ItemSubCategory(
        category_id=int(category_id),
        name_en=name_en,
        name_ar=f.get('name_ar', '').strip() or None,
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({'ok': True, 'sub_category': sub.to_dict()})

@lookups_bp.route('/items/tax-categories/data')
@login_required
def item_tax_cats_data():
    return jsonify([t.to_dict() for t in TaxCategory.query.order_by(TaxCategory.name_en).all()])

@lookups_bp.route('/items/tax-categories/add', methods=['POST'])
@login_required
def item_tax_category_add():
    """Quick-add a tax category from the Item Master form popup."""
    f = request.form
    name_en = f.get('name_en', '').strip()
    if not name_en:
        return jsonify({'ok': False, 'error': 'Tax category name (EN) is required'}), 400
    rate_raw = f.get('rate', '0').strip()
    try:
        rate = float(rate_raw) if rate_raw else 0
    except ValueError:
        return jsonify({'ok': False, 'error': 'Tax rate must be a number'}), 400
    tax = TaxCategory(name_en=name_en, name_ar=f.get('name_ar', '').strip() or None, rate=rate)
    db.session.add(tax)
    db.session.commit()
    return jsonify({'ok': True, 'tax_category': tax.to_dict()})


# ── Translation API ─────────────────────────────────────────────────
# Uses the free unofficial Google Translate web endpoint (same pattern
# as sellers.py's translate_text route) — no external package needed,
# no API key, no GoogleTranslator import that was previously missing.
@lookups_bp.route('/items/translate', methods=['POST'])
@login_required
def item_translate():
    data      = request.get_json(silent=True) or {}
    text      = (data.get('text') or request.args.get('text') or '').strip()
    direction = data.get('dir') or request.args.get('dir', 'en2ar')

    if not text:
        return jsonify({'ok': True, 'translated': ''})

    src, tgt = ('en', 'ar') if direction == 'en2ar' else ('ar', 'en')

    # Primary: unofficial Google Translate endpoint
    try:
        params = urllib.parse.urlencode({'client': 'gtx', 'sl': src, 'tl': tgt, 'dt': 't', 'q': text})
        url    = f'https://translate.googleapis.com/translate_a/single?{params}'
        req    = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as r:
            result = _json.loads(r.read().decode('utf-8'))
        translated = ''.join(chunk[0] for chunk in result[0] if chunk[0])
        if translated:
            return jsonify({'ok': True, 'translated': translated.strip()})
    except Exception:
        pass

    # Fallback: MyMemory (also free, no key)
    try:
        q   = urllib.parse.quote(text)
        url = f'https://api.mymemory.translated.net/get?q={q}&langpair={src}|{tgt}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            result = _json.loads(r.read().decode())
        translated = result.get('responseData', {}).get('translatedText', '')
        return jsonify({'ok': True, 'translated': translated})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'translated': ''}), 502