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


# ═════════════════════════════════════════════════════════════════
#  LEVELS 3, 4, 5
#  Shared helpers + CRUD. All three levels behave identically:
#    * code is auto-generated (read-only)
#    * code_length and description are fixed server-side
#    * a parent cannot be deleted while it has children
#    * duplicate drawers under the same parent are rejected
# ═════════════════════════════════════════════════════════════════
from models import (LevelThree, LevelFour, LevelFive,
                    next_level_three_code, next_level_four_code, next_level_five_code)

PER_PAGE = 25


def _paginate_filter_sort(model, parent_code_col, request):
    """Apply search / parent filter / sorting / pagination to a level query.

    Query-string params:
        q        free-text search over code + drawers
        parent   exact parent-code filter
        sort     one of: code, drawers, created_at   (prefix '-' for desc)
        page     1-based page number
    """
    q_text  = (request.args.get('q') or '').strip()
    parent  = (request.args.get('parent') or '').strip()
    sort    = (request.args.get('sort') or 'code').strip()
    page    = request.args.get('page', 1, type=int)

    query = model.query
    if q_text:
        like = f'%{q_text}%'
        query = query.filter(db.or_(model.code.ilike(like), model.drawers.ilike(like)))
    if parent:
        query = query.filter(parent_code_col == parent)

    desc = sort.startswith('-')
    field = sort[1:] if desc else sort
    col = {'code': model.code, 'drawers': model.drawers,
           'created_at': model.created_at}.get(field, model.code)
    query = query.order_by(col.desc() if desc else col.asc())

    return query.paginate(page=page, per_page=PER_PAGE, error_out=False), q_text, parent, sort


# ─── LEVEL THREE ─────────────────────────────────────────────────
@coa_bp.route('/level-three')
@login_required
def level_three_list():
    pg, q_text, parent, sort = _paginate_filter_sort(LevelThree, LevelThree.level_two_code, request)
    parents = LevelTwo.query.order_by(LevelTwo.code).all()
    return render_template('coa/level_three.html', pg=pg, rows=pg.items,
                           parents=parents, q=q_text, parent=parent, sort=sort)


@coa_bp.route('/level-three/next-code')
@login_required
def level_three_next_code():
    p = LevelTwo.query.get(request.args.get('level_two_id', type=int))
    return jsonify({'code': next_level_three_code(p) if p else ''})


@coa_bp.route('/level-three/add', methods=['POST'])
@login_required
@admin_required
def level_three_add():
    from forms import LevelThreeForm
    form = LevelThreeForm()
    form.level_two_id.choices = [(r.id, f'{r.code} — {r.drawers}') for r in LevelTwo.query.order_by(LevelTwo.code)]
    if not form.validate_on_submit():
        flash(_t('Please correct the errors.', 'يرجى تصحيح الأخطاء.'), 'danger')
        return redirect(url_for('coa.level_three_list'))
    parent = LevelTwo.query.get(form.level_two_id.data)
    if not parent:
        flash(_t('Parent not found.', 'الحساب الأب غير موجود.'), 'danger')
        return redirect(url_for('coa.level_three_list'))
    drawers = form.drawers.data.strip()
    if LevelThree.query.filter(LevelThree.level_two_id == parent.id,
                               db.func.lower(LevelThree.drawers) == drawers.lower()).first():
        flash(_t(f'"{drawers}" already exists under {parent.code}.',
                 f'"{drawers}" موجود بالفعل ضمن {parent.code}.'), 'danger')
        return redirect(url_for('coa.level_three_list'))
    db.session.add(LevelThree(code_length=5, level_two_id=parent.id, level_two_code=parent.code,
                              code=next_level_three_code(parent), drawers=drawers,
                              description='Heading Account'))
    db.session.commit()
    flash(_t('Level 3 account created.', 'تم إنشاء حساب المستوى الثالث.'), 'success')
    return redirect(url_for('coa.level_three_list'))


@coa_bp.route('/level-three/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def level_three_edit(id):
    row = LevelThree.query.get_or_404(id)
    from forms import LevelThreeEditForm
    form = LevelThreeEditForm()
    if not form.validate_on_submit():
        flash(_t('Please correct the errors.', 'يرجى تصحيح الأخطاء.'), 'danger')
        return redirect(url_for('coa.level_three_list'))
    drawers = form.drawers.data.strip()
    if LevelThree.query.filter(LevelThree.level_two_id == row.level_two_id,
                               db.func.lower(LevelThree.drawers) == drawers.lower(),
                               LevelThree.id != row.id).first():
        flash(_t('Duplicate drawers under the same parent.', 'اسم مكرر ضمن نفس الأب.'), 'danger')
        return redirect(url_for('coa.level_three_list'))
    row.drawers, row.code_length, row.description = drawers, 5, 'Heading Account'
    db.session.commit()
    flash(_t('Level 3 account updated.', 'تم تحديث الحساب.'), 'success')
    return redirect(url_for('coa.level_three_list'))


@coa_bp.route('/level-three/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def level_three_delete(id):
    row = LevelThree.query.get_or_404(id)
    if row.level_fours:
        flash(_t('Cannot delete: this account has Level 4 children.',
                 'لا يمكن الحذف: يحتوي على حسابات فرعية.'), 'danger')
        return redirect(url_for('coa.level_three_list'))
    db.session.delete(row); db.session.commit()
    flash(_t('Level 3 account deleted.', 'تم حذف الحساب.'), 'success')
    return redirect(url_for('coa.level_three_list'))


@coa_bp.route('/level-three/data')
@login_required
def level_three_data():
    return jsonify([r.to_dict() for r in LevelThree.query.order_by(LevelThree.code).all()])


# ─── LEVEL FOUR ──────────────────────────────────────────────────
@coa_bp.route('/level-four')
@login_required
def level_four_list():
    pg, q_text, parent, sort = _paginate_filter_sort(LevelFour, LevelFour.level_three_code, request)
    parents = LevelThree.query.order_by(LevelThree.code).all()
    return render_template('coa/level_four.html', pg=pg, rows=pg.items,
                           parents=parents, q=q_text, parent=parent, sort=sort)


@coa_bp.route('/level-four/next-code')
@login_required
def level_four_next_code():
    p = LevelThree.query.get(request.args.get('level_three_id', type=int))
    return jsonify({'code': next_level_four_code(p) if p else ''})


@coa_bp.route('/level-four/add', methods=['POST'])
@login_required
@admin_required
def level_four_add():
    from forms import LevelFourForm
    form = LevelFourForm()
    form.level_three_id.choices = [(r.id, f'{r.code} — {r.drawers}') for r in LevelThree.query.order_by(LevelThree.code)]
    if not form.validate_on_submit():
        flash(_t('Please correct the errors.', 'يرجى تصحيح الأخطاء.'), 'danger')
        return redirect(url_for('coa.level_four_list'))
    parent = LevelThree.query.get(form.level_three_id.data)
    if not parent:
        flash(_t('Parent not found.', 'الحساب الأب غير موجود.'), 'danger')
        return redirect(url_for('coa.level_four_list'))
    drawers = form.drawers.data.strip()
    if LevelFour.query.filter(LevelFour.level_three_id == parent.id,
                              db.func.lower(LevelFour.drawers) == drawers.lower()).first():
        flash(_t(f'"{drawers}" already exists under {parent.code}.',
                 f'"{drawers}" موجود بالفعل ضمن {parent.code}.'), 'danger')
        return redirect(url_for('coa.level_four_list'))
    db.session.add(LevelFour(code_length=8, level_three_id=parent.id, level_three_code=parent.code,
                             code=next_level_four_code(parent), drawers=drawers,
                             description='Heading Account'))
    db.session.commit()
    flash(_t('Level 4 account created.', 'تم إنشاء حساب المستوى الرابع.'), 'success')
    return redirect(url_for('coa.level_four_list'))


@coa_bp.route('/level-four/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def level_four_edit(id):
    row = LevelFour.query.get_or_404(id)
    from forms import LevelFourEditForm
    form = LevelFourEditForm()
    if not form.validate_on_submit():
        flash(_t('Please correct the errors.', 'يرجى تصحيح الأخطاء.'), 'danger')
        return redirect(url_for('coa.level_four_list'))
    drawers = form.drawers.data.strip()
    if LevelFour.query.filter(LevelFour.level_three_id == row.level_three_id,
                              db.func.lower(LevelFour.drawers) == drawers.lower(),
                              LevelFour.id != row.id).first():
        flash(_t('Duplicate drawers under the same parent.', 'اسم مكرر ضمن نفس الأب.'), 'danger')
        return redirect(url_for('coa.level_four_list'))
    row.drawers, row.code_length, row.description = drawers, 8, 'Heading Account'
    db.session.commit()
    flash(_t('Level 4 account updated.', 'تم تحديث الحساب.'), 'success')
    return redirect(url_for('coa.level_four_list'))


@coa_bp.route('/level-four/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def level_four_delete(id):
    row = LevelFour.query.get_or_404(id)
    if row.level_fives:
        flash(_t('Cannot delete: this account has Level 5 children.',
                 'لا يمكن الحذف: يحتوي على حسابات فرعية.'), 'danger')
        return redirect(url_for('coa.level_four_list'))
    db.session.delete(row); db.session.commit()
    flash(_t('Level 4 account deleted.', 'تم حذف الحساب.'), 'success')
    return redirect(url_for('coa.level_four_list'))


@coa_bp.route('/level-four/data')
@login_required
def level_four_data():
    return jsonify([r.to_dict() for r in LevelFour.query.order_by(LevelFour.code).all()])


# ─── LEVEL FIVE ──────────────────────────────────────────────────
@coa_bp.route('/level-five')
@login_required
def level_five_list():
    pg, q_text, parent, sort = _paginate_filter_sort(LevelFive, LevelFive.level_four_code, request)
    parents = LevelFour.query.order_by(LevelFour.code).all()
    return render_template('coa/level_five.html', pg=pg, rows=pg.items,
                           parents=parents, q=q_text, parent=parent, sort=sort)


@coa_bp.route('/level-five/next-code')
@login_required
def level_five_next_code():
    p = LevelFour.query.get(request.args.get('level_four_id', type=int))
    return jsonify({'code': next_level_five_code(p) if p else ''})


@coa_bp.route('/level-five/add', methods=['POST'])
@login_required
@admin_required
def level_five_add():
    from forms import LevelFiveForm
    form = LevelFiveForm()
    form.level_four_id.choices = [(r.id, f'{r.code} — {r.drawers}') for r in LevelFour.query.order_by(LevelFour.code)]
    if not form.validate_on_submit():
        flash(_t('Please correct the errors.', 'يرجى تصحيح الأخطاء.'), 'danger')
        return redirect(url_for('coa.level_five_list'))
    parent = LevelFour.query.get(form.level_four_id.data)
    if not parent:
        flash(_t('Parent not found.', 'الحساب الأب غير موجود.'), 'danger')
        return redirect(url_for('coa.level_five_list'))
    drawers = form.drawers.data.strip()
    if LevelFive.query.filter(LevelFive.level_four_id == parent.id,
                              db.func.lower(LevelFive.drawers) == drawers.lower()).first():
        flash(_t(f'"{drawers}" already exists under {parent.code}.',
                 f'"{drawers}" موجود بالفعل ضمن {parent.code}.'), 'danger')
        return redirect(url_for('coa.level_five_list'))
    db.session.add(LevelFive(code_length=12, level_four_id=parent.id, level_four_code=parent.code,
                             code=next_level_five_code(parent), drawers=drawers,
                             description='Transactional Account'))
    db.session.commit()
    flash(_t('Level 5 account created.', 'تم إنشاء حساب المستوى الخامس.'), 'success')
    return redirect(url_for('coa.level_five_list'))


@coa_bp.route('/level-five/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def level_five_edit(id):
    row = LevelFive.query.get_or_404(id)
    from forms import LevelFiveEditForm
    form = LevelFiveEditForm()
    if not form.validate_on_submit():
        flash(_t('Please correct the errors.', 'يرجى تصحيح الأخطاء.'), 'danger')
        return redirect(url_for('coa.level_five_list'))
    drawers = form.drawers.data.strip()
    if LevelFive.query.filter(LevelFive.level_four_id == row.level_four_id,
                              db.func.lower(LevelFive.drawers) == drawers.lower(),
                              LevelFive.id != row.id).first():
        flash(_t('Duplicate drawers under the same parent.', 'اسم مكرر ضمن نفس الأب.'), 'danger')
        return redirect(url_for('coa.level_five_list'))
    row.drawers, row.code_length, row.description = drawers, 12, 'Transactional Account'
    db.session.commit()
    flash(_t('Level 5 account updated.', 'تم تحديث الحساب.'), 'success')
    return redirect(url_for('coa.level_five_list'))


@coa_bp.route('/level-five/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def level_five_delete(id):
    row = LevelFive.query.get_or_404(id)
    db.session.delete(row); db.session.commit()
    flash(_t('Level 5 account deleted.', 'تم حذف الحساب.'), 'success')
    return redirect(url_for('coa.level_five_list'))


@coa_bp.route('/level-five/data')
@login_required
def level_five_data():
    return jsonify([r.to_dict() for r in LevelFive.query.order_by(LevelFive.code).all()])