"""Chart of Accounts module — Level 1 and Level 2.

Routes:
    /coa/level-one          list Level 1
    /coa/level-one/add      create Level 1
    /coa/level-one/<id>/edit
    /coa/level-one/<id>/delete
    /coa/level-two          list Level 2
    /coa/level-two/add      create Level 2  (code auto-generated)
    /coa/level-two/<id>/edit
    /coa/level-two/<id>/delete
    /coa/level-two/next-code?level_one_id=..   preview next auto code

Business rules enforced server-side (never trust the client):
    * Level 1 ``code_length`` is always 1; ``code`` is fixed after creation.
    * Level 2 ``code_length`` is always 2; ``description`` is always
      'Heading Account'; ``code`` is generated as <L1 code><n>, with an
      independent sequence per Level 1.
"""
import re
from functools import wraps
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session, jsonify)
from flask_login import login_required, current_user

from models import db, LevelOne, LevelTwo

coa_bp = Blueprint('coa', __name__, url_prefix='/coa')


# ── helpers ──────────────────────────────────────────────────────
def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en


def admin_required(f):
    """Only admins may create / edit / delete accounts."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            flash(_t('Access denied.', 'الوصول مرفوض'), 'danger')
            return redirect(url_for('coa.level_one_list'))
        return f(*args, **kwargs)
    return decorated


def _next_level_two_code(level_one):
    """Return the next Level 2 code for a given LevelOne row.

    Sequence is independent per Level 1: reads existing Level 2 rows for that
    parent, finds the highest numeric suffix, and increments. Starts at 1 when
    none exist -> e.g. A1, A2, A3 ...
    """
    prefix = level_one.code
    rows = LevelTwo.query.filter_by(level_one_id=level_one.id).all()
    highest = 0
    for r in rows:
        # Strip the leading letter(s) and read the trailing number.
        m = re.match(r'^' + re.escape(prefix) + r'(\d+)$', r.code or '')
        if m:
            highest = max(highest, int(m.group(1)))
    candidate = f'{prefix}{highest + 1}'
    # Guard against a rare collision (e.g. manually inserted codes).
    while LevelTwo.query.filter_by(code=candidate).first():
        highest += 1
        candidate = f'{prefix}{highest + 1}'
    return candidate


# ═════════════════════════════════════════════════════════════════
#  LEVEL ONE
# ═════════════════════════════════════════════════════════════════
@coa_bp.route('/level-one')
@login_required
def level_one_list():
    rows = LevelOne.query.order_by(LevelOne.id).all()
    return render_template('coa/level_one.html', rows=rows)


@coa_bp.route('/level-one/add', methods=['POST'])
@login_required
@admin_required
def level_one_add():
    from forms import LevelOneForm
    form = LevelOneForm()
    if not form.validate_on_submit():
        flash(_t('Please correct the errors and try again.',
                 'يرجى تصحيح الأخطاء والمحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('coa.level_one_list'))

    code = (form.code.data or '').strip().upper()
    # Uniqueness check.
    if LevelOne.query.filter_by(code=code).first():
        flash(_t(f'Code "{code}" already exists.',
                 f'الكود "{code}" موجود بالفعل.'), 'danger')
        return redirect(url_for('coa.level_one_list'))

    l1 = LevelOne(
        code_length=1,                       # always 1
        code=code,
        drawers=(form.drawers.data or '').strip(),
        description=(form.description.data or '').strip(),
    )
    db.session.add(l1)
    db.session.commit()
    flash(_t(f'Level 1 account "{code}" created.',
             f'تم إنشاء حساب المستوى الأول "{code}".'), 'success')
    return redirect(url_for('coa.level_one_list'))


@coa_bp.route('/level-one/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def level_one_edit(id):
    l1 = LevelOne.query.get_or_404(id)
    from forms import LevelOneEditForm
    form = LevelOneEditForm()
    if not form.validate_on_submit():
        flash(_t('Please correct the errors and try again.',
                 'يرجى تصحيح الأخطاء والمحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('coa.level_one_list'))

    # NOTE: code is fixed and cannot be changed after creation.
    l1.drawers = (form.drawers.data or '').strip()
    l1.description = (form.description.data or '').strip()
    l1.code_length = 1                       # keep fixed
    db.session.commit()
    flash(_t('Level 1 account updated.', 'تم تحديث حساب المستوى الأول.'), 'success')
    return redirect(url_for('coa.level_one_list'))


@coa_bp.route('/level-one/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def level_one_delete(id):
    l1 = LevelOne.query.get_or_404(id)
    if l1.level_twos:
        flash(_t('Cannot delete: this Level 1 has Level 2 accounts.',
                 'لا يمكن الحذف: هذا الحساب يحتوي على حسابات مستوى ثاني.'), 'danger')
        return redirect(url_for('coa.level_one_list'))
    db.session.delete(l1)
    db.session.commit()
    flash(_t('Level 1 account deleted.', 'تم حذف حساب المستوى الأول.'), 'success')
    return redirect(url_for('coa.level_one_list'))


@coa_bp.route('/level-one/data')
@login_required
def level_one_data():
    return jsonify([r.to_dict() for r in LevelOne.query.order_by(LevelOne.id).all()])


# ═════════════════════════════════════════════════════════════════
#  LEVEL TWO
# ═════════════════════════════════════════════════════════════════
@coa_bp.route('/level-two')
@login_required
def level_two_list():
    rows = LevelTwo.query.order_by(LevelTwo.level_one_code, LevelTwo.id).all()
    level_ones = LevelOne.query.order_by(LevelOne.code).all()
    return render_template('coa/level_two.html', rows=rows, level_ones=level_ones)


@coa_bp.route('/level-two/next-code')
@login_required
def level_two_next_code():
    """Preview the auto code for the selected Level 1 (used by the form UI)."""
    l1_id = request.args.get('level_one_id', type=int)
    l1 = LevelOne.query.get(l1_id) if l1_id else None
    if not l1:
        return jsonify({'code': ''})
    return jsonify({'code': _next_level_two_code(l1), 'level_one_code': l1.code})


@coa_bp.route('/level-two/add', methods=['POST'])
@login_required
@admin_required
def level_two_add():
    from forms import LevelTwoForm
    form = LevelTwoForm()
    # Populate the select choices before validating.
    form.level_one_id.choices = [
        (l1.id, f'{l1.code} — {l1.drawers}')
        for l1 in LevelOne.query.order_by(LevelOne.code).all()
    ]
    if not form.validate_on_submit():
        flash(_t('Please correct the errors and try again.',
                 'يرجى تصحيح الأخطاء والمحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('coa.level_two_list'))

    l1 = LevelOne.query.get(form.level_one_id.data)
    if not l1:
        flash(_t('Selected Level 1 account does not exist.',
                 'حساب المستوى الأول المحدد غير موجود.'), 'danger')
        return redirect(url_for('coa.level_two_list'))

    drawers = (form.drawers.data or '').strip()
    # Recommended: prevent duplicate drawers under the same Level 1.
    dup = LevelTwo.query.filter(
        LevelTwo.level_one_id == l1.id,
        db.func.lower(LevelTwo.drawers) == drawers.lower()
    ).first()
    if dup:
        flash(_t(f'"{drawers}" already exists under {l1.code}.',
                 f'"{drawers}" موجود بالفعل ضمن {l1.code}.'), 'danger')
        return redirect(url_for('coa.level_two_list'))

    # Auto-generate the code (independent sequence per Level 1).
    code = _next_level_two_code(l1)

    l2 = LevelTwo(
        code_length=2,                       # always 2
        level_one_id=l1.id,
        level_one_code=l1.code,
        code=code,
        drawers=drawers,
        description='Heading Account',       # always
    )
    db.session.add(l2)
    db.session.commit()
    flash(_t(f'Level 2 account "{code}" created.',
             f'تم إنشاء حساب المستوى الثاني "{code}".'), 'success')
    return redirect(url_for('coa.level_two_list'))


@coa_bp.route('/level-two/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def level_two_edit(id):
    l2 = LevelTwo.query.get_or_404(id)
    from forms import LevelTwoEditForm
    form = LevelTwoEditForm()
    if not form.validate_on_submit():
        flash(_t('Please correct the errors and try again.',
                 'يرجى تصحيح الأخطاء والمحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('coa.level_two_list'))

    drawers = (form.drawers.data or '').strip()
    # NOTE: code, level_one, code_length and description are all fixed.
    dup = LevelTwo.query.filter(
        LevelTwo.level_one_id == l2.level_one_id,
        db.func.lower(LevelTwo.drawers) == drawers.lower(),
        LevelTwo.id != l2.id
    ).first()
    if dup:
        flash(_t(f'"{drawers}" already exists under {l2.level_one_code}.',
                 f'"{drawers}" موجود بالفعل ضمن {l2.level_one_code}.'), 'danger')
        return redirect(url_for('coa.level_two_list'))

    l2.drawers = drawers
    l2.code_length = 2                       # keep fixed
    l2.description = 'Heading Account'       # keep fixed
    db.session.commit()
    flash(_t('Level 2 account updated.', 'تم تحديث حساب المستوى الثاني.'), 'success')
    return redirect(url_for('coa.level_two_list'))


@coa_bp.route('/level-two/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def level_two_delete(id):
    l2 = LevelTwo.query.get_or_404(id)
    db.session.delete(l2)
    db.session.commit()
    flash(_t('Level 2 account deleted.', 'تم حذف حساب المستوى الثاني.'), 'success')
    return redirect(url_for('coa.level_two_list'))


@coa_bp.route('/level-two/data')
@login_required
def level_two_data():
    return jsonify([r.to_dict() for r in
                    LevelTwo.query.order_by(LevelTwo.level_one_code, LevelTwo.id).all()])