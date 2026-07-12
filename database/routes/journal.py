"""Journal Entries module — accounting.

Routes:
    /journal                     list page (AG-Grid)
    /journal/data                JSON rows for the grid
    /journal/next-no             preview the next JE number
    /journal/level-five/children?level_four_id=..   L5 accounts under an L4
    /journal/level-five/<id>/hierarchy              drawer chain + code for an L5
    /journal/add                 create
    /journal/<id>/json           single record (for edit)
    /journal/<id>/edit           update
    /journal/<id>/delete         delete

Business rules enforced server-side (never trust the client):
    * ``je_no`` is unique and auto-generated (JE-000001).
    * ``month`` is derived from ``je_date``.
    * The five drawer fields are filled from the selected Level 5 account's
      Chart-of-Accounts hierarchy, not from the client.
    * ``debit`` / ``credit`` may not be negative; ``je_balance`` is computed.
    * A row may only be ``Posted`` when debit == credit.
"""
from datetime import datetime
from functools import wraps
from flask import (Blueprint, render_template, request, jsonify, session)
from flask_login import login_required, current_user

from models import (db, JournalEntry, next_je_no,
                    LevelOne, LevelTwo, LevelThree, LevelFour, LevelFive)

journal_bp = Blueprint('journal', __name__, url_prefix='/journal')


def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en


# ── Chart-of-Accounts hierarchy resolution ───────────────────────
def _hierarchy_for_level_five(l5):
    """Walk L5 -> L1 and return the code + the five drawer names."""
    l4 = l5.level_four if l5 else None
    l3 = l4.level_three if l4 else None
    l2 = l3.level_two if l3 else None
    l1 = l2.level_one if l2 else None
    return {
        'level5_code': l5.code if l5 else '',
        'level1_drawer': l1.drawers if l1 else '',
        'level2_drawer': l2.drawers if l2 else '',
        'level3_drawer': l3.drawers if l3 else '',
        'level4_drawer': l4.drawers if l4 else '',
        'level5_drawer': l5.drawers if l5 else '',
    }


# ── Pages ─────────────────────────────────────────────────────────
@journal_bp.route('/')
@login_required
def journal_list():
    level_ones = (LevelOne.query
                  .filter(LevelOne.status == 'active')
                  .order_by(LevelOne.code).all())
    return render_template('journal/list.html', level_ones=level_ones)


@journal_bp.route('/data')
@login_required
def journal_data():
    rows = JournalEntry.query.order_by(JournalEntry.id.desc()).all()
    return jsonify([r.to_dict() for r in rows])


@journal_bp.route('/next-no')
@login_required
def journal_next_no():
    return jsonify({'je_no': next_je_no()})


# ── Cascading dropdown: Level 5 accounts under a Level 4 ──────────
@journal_bp.route('/level-five/children')
@login_required
def level_five_children():
    pid = request.args.get('level_four_id', type=int)
    if not pid:
        return jsonify([])
    rows = (LevelFive.query
            .filter(LevelFive.level_four_id == pid, LevelFive.status == 'active')
            .order_by(LevelFive.code).all())
    return jsonify([{
        'id': r.id, 'code': r.code, 'drawers': r.drawers,
        'label': f'{r.code} - {r.drawers}',
    } for r in rows])


@journal_bp.route('/level-five/<int:l5_id>/hierarchy')
@login_required
def level_five_hierarchy(l5_id):
    l5 = LevelFive.query.get_or_404(l5_id)
    return jsonify(_hierarchy_for_level_five(l5))


# ── Helpers for save ──────────────────────────────────────────────
def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _apply_form(je, f):
    """Populate a JournalEntry from the submitted form. Returns (ok, error)."""
    # Date (required)
    date_str = (f.get('je_date', '') or '').strip()
    if not date_str:
        return False, _t('Date is required.', 'التاريخ مطلوب.')
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return False, _t('Invalid date.', 'تاريخ غير صالح.')
    je.je_date = d
    je.month = d.strftime('%B')                    # month name derived from date

    # Level 5 account (required) -> fills the drawer hierarchy server-side
    l5_id = f.get('level_five_id', type=int)
    if not l5_id:
        return False, _t('Level 5 account is required.', 'حساب المستوى الخامس مطلوب.')
    l5 = LevelFive.query.get(l5_id)
    if not l5:
        return False, _t('Selected Level 5 account was not found.',
                         'حساب المستوى الخامس غير موجود.')
    h = _hierarchy_for_level_five(l5)
    je.level5_code = h['level5_code']
    je.level1_drawer = h['level1_drawer']
    je.level2_drawer = h['level2_drawer']
    je.level3_drawer = h['level3_drawer']
    je.level4_drawer = h['level4_drawer']
    je.level5_drawer = h['level5_drawer']

    # Debit / Credit (no negatives)
    debit = _num(f.get('debit'), 0.0)
    credit = _num(f.get('credit'), 0.0)
    if debit < 0 or credit < 0:
        return False, _t('Debit and Credit cannot be negative.',
                         'المدين والدائن لا يمكن أن يكونا سالبين.')
    je.debit = debit
    je.credit = credit
    je.je_balance = round(debit - credit, 2)

    je.description = (f.get('description', '') or '').strip() or None
    je.project_client = (f.get('project_client', '') or '').strip() or None
    je.payment_ref_method = (f.get('payment_ref_method', '') or '').strip() or None

    # Status — Posted only when balanced
    status = (f.get('status', 'Draft') or 'Draft').strip()
    if status not in ('Draft', 'Posted', 'Cancelled'):
        status = 'Draft'
    if status == 'Posted' and round(debit - credit, 2) != 0:
        return False, _t('Cannot post: total Debit must equal total Credit.',
                         'لا يمكن الترحيل: يجب أن يساوي إجمالي المدين إجمالي الدائن.')
    je.status = status
    return True, None


# ── CRUD ──────────────────────────────────────────────────────────
@journal_bp.route('/add', methods=['POST'])
@login_required
def journal_add():
    je = JournalEntry(je_no=next_je_no())
    ok, err = _apply_form(je, request.form)
    if not ok:
        return jsonify({'ok': False, 'error': err}), 400
    try:
        db.session.add(je)
        db.session.commit()
        return jsonify({'ok': True, 'id': je.id, 'je_no': je.je_no})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not save the entry.',
                                                 'تعذّر حفظ القيد.')}), 500


@journal_bp.route('/<int:je_id>/json')
@login_required
def journal_json(je_id):
    je = JournalEntry.query.get_or_404(je_id)
    d = je.to_dict()
    # Provide the L5 id so the edit form can repopulate the cascade.
    l5 = LevelFive.query.filter_by(code=je.level5_code).first()
    d['level_five_id'] = l5.id if l5 else None
    return jsonify(d)


@journal_bp.route('/<int:je_id>/edit', methods=['POST'])
@login_required
def journal_edit(je_id):
    je = JournalEntry.query.get_or_404(je_id)
    ok, err = _apply_form(je, request.form)
    if not ok:
        return jsonify({'ok': False, 'error': err}), 400
    try:
        db.session.commit()
        return jsonify({'ok': True, 'id': je.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not update the entry.',
                                                 'تعذّر تحديث القيد.')}), 500


@journal_bp.route('/<int:je_id>/delete', methods=['POST'])
@login_required
def journal_delete(je_id):
    je = JournalEntry.query.get_or_404(je_id)
    try:
        db.session.delete(je)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': _t('Could not delete the entry.',
                                                 'تعذّر حذف القيد.')}), 500