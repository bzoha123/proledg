"""
Journal Entry — VIEW ONLY (master/detail).

The Journal page only displays entries; there is no manual add/edit form.
Entries are created programmatically from a source document (to be wired
later) via `create_journal_entry(...)`, which assigns the JEV-<FY>-<n>
number and enforces the active-financial-year rule.

    journal_entries(id, je_no, origion, origin_type, origin_id, refrence,
                    posting_date, due_date, document_date, narration, ...)
    journal_entry_detail(id, journal_entry_id FK, code, account_name,
                         control_account, debit, credit, narration)
"""

from datetime import date, datetime

from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required

from models import (db, JournalEntry, JournalEntryDetail,
                    next_je_no, NoActiveFinancialYearError)

journal_bp = Blueprint('journal', __name__, url_prefix='/journal')


def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ── Page (view only) ────────────────────────────────────────────
@journal_bp.route('/')
@login_required
def journal_list():
    return render_template('journal/list.html')


@journal_bp.route('/data')
@login_required
def journal_data():
    rows = JournalEntry.query.order_by(JournalEntry.id.desc()).all()
    out = []
    for j in rows:
        d = j.to_dict()
        d['total_debit'] = sum(x['debit'] for x in d['details'])
        d['total_credit'] = sum(x['credit'] for x in d['details'])
        d['lines'] = len(d['details'])
        out.append(d)
    return jsonify(out)


@journal_bp.route('/<int:je_id>/json')
@login_required
def journal_json(je_id):
    je = JournalEntry.query.get_or_404(je_id)
    return jsonify(je.to_dict())


# ── Programmatic creation (used by source documents later) ──────
def create_journal_entry(origion='', refrence='', posting_date=None,
                         due_date=None, narration='', lines=None,
                         origin_type='', origin_id=None):
    """Create a Journal Entry (+ detail lines) with an auto JEV number.

    lines: list of dicts with keys code, account_name, control_account,
           debit, credit, narration.
    Raises NoActiveFinancialYearError if no financial year is Open.
    Caller is responsible for committing (or use commit=True path below).
    """
    je = JournalEntry(
        je_no=next_je_no(),                       # enforces active FY
        origion=(origion or '').strip(),
        origin_type=(origin_type or '').strip(),
        origin_id=origin_id,
        refrence=(refrence or '').strip(),
        posting_date=posting_date or date.today(),
        due_date=due_date,
        document_date=date.today(),               # always today
        narration=(narration or '').strip(),
    )
    db.session.add(je)
    db.session.flush()
    for ln in (lines or []):
        db.session.add(JournalEntryDetail(
            journal_entry_id=je.id,
            code=(ln.get('code') or '').strip(),
            account_name=(ln.get('account_name') or '').strip(),
            control_account=(ln.get('control_account') or '').strip(),
            debit=_num(ln.get('debit')),
            credit=_num(ln.get('credit')),
            narration=(ln.get('narration') or '').strip(),
        ))
    return je


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
        return jsonify({'ok': False, 'error': str(e)}), 500


@journal_bp.errorhandler(NoActiveFinancialYearError)
def _no_fy(e):
    return jsonify({'ok': False, 'error': _t(
        'Please activate your financial year first.',
        'الرجاء تفعيل السنة المالية أولاً.')}), 400