"""
Generic Import / Export for master pages.

One blueprint (`io_bp`) exposes:
    GET  /io/<key>/export?fmt=xlsx|csv     -> download all rows of a registered model
    POST /io/<key>/import                  -> import rows (add-new-only by default)
    GET  /io/<key>/template?fmt=xlsx|csv   -> download an empty template

Each master page registers itself once via `register_io(...)`, declaring its
model, which columns to include, and the unique key used to skip existing rows
on import. No per-page route code is needed beyond that one registration.

Purchases and Sales documents are intentionally NOT registered here.
"""

import io as _io
import csv as _csv
from datetime import date, datetime

from flask import Blueprint, request, jsonify, send_file, session
from flask_login import login_required

from models import db

io_bp = Blueprint('io', __name__, url_prefix='/io')

# key -> spec dict
_REGISTRY = {}


def register_io(key, model, columns, unique='code', label=None, parents=None,
                coerce=None):
    """Register a model for generic import/export.

    key      : short url-safe id, e.g. 'work-allocations'
    model    : the SQLAlchemy model class
    columns  : list of (header, attribute) pairs to export/import
    unique   : attribute used to detect existing rows on import (skip if present)
    label    : human title (defaults to key)
    parents  : optional list of (header, fk_attr, parent_model, parent_key_attr,
               parent_id_attr) to resolve a parent by a natural key on import
    coerce   : optional dict {attr: callable(value)->value} for type conversion
    """
    _REGISTRY[key] = {
        'model': model, 'columns': columns, 'unique': unique,
        'label': label or key, 'parents': parents or [],
        'coerce': coerce or {},
    }


def _t(en, ar):
    return ar if session.get('lang') == 'ar' else en


def _val_out(v):
    if v is None:
        return ''
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, bool):
        return '1' if v else '0'
    return v


def _coerce_value(attr, raw, spec):
    fn = spec['coerce'].get(attr)
    if fn:
        try:
            return fn(raw)
        except Exception:
            return None
    return (str(raw).strip() if raw is not None else None) or None


@io_bp.route('/<key>/export')
@login_required
def io_export(key):
    spec = _REGISTRY.get(key)
    if not spec:
        return jsonify({'ok': False, 'error': 'Unknown export'}), 404
    fmt = (request.args.get('fmt') or 'xlsx').lower()
    model = spec['model']
    rows = model.query.all()
    headers = [h for h, _ in spec['columns']]

    if fmt == 'csv':
        buf = _io.StringIO()
        w = _csv.writer(buf)
        w.writerow(headers)
        for r in rows:
            w.writerow([_val_out(getattr(r, a, '')) for _, a in spec['columns']])
        data = buf.getvalue().encode('utf-8-sig')
        return send_file(_io.BytesIO(data), as_attachment=True,
                         download_name=f'{key}.csv', mimetype='text/csv')

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = spec['label'][:31] or key[:31]
    fill = PatternFill('solid', fgColor='1E3A5F')
    font = Font(color='FFFFFF', bold=True, size=10)
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.fill = fill; c.font = font
        ws.column_dimensions[get_column_letter(i)].width = max(14, len(h) + 3)
    ws.freeze_panes = 'A2'
    for r_i, r in enumerate(rows, 2):
        for c_i, (_, a) in enumerate(spec['columns'], 1):
            ws.cell(row=r_i, column=c_i, value=_val_out(getattr(r, a, '')))
    out = _io.BytesIO(); wb.save(out); out.seek(0)
    return send_file(out, as_attachment=True, download_name=f'{key}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@io_bp.route('/<key>/template')
@login_required
def io_template(key):
    """Empty file with just the headers, for filling in and importing."""
    spec = _REGISTRY.get(key)
    if not spec:
        return jsonify({'ok': False, 'error': 'Unknown template'}), 404
    fmt = (request.args.get('fmt') or 'xlsx').lower()
    headers = [h for h, _ in spec['columns']]
    if fmt == 'csv':
        buf = _io.StringIO(); _csv.writer(buf).writerow(headers)
        data = buf.getvalue().encode('utf-8-sig')
        return send_file(_io.BytesIO(data), as_attachment=True,
                         download_name=f'{key}_template.csv', mimetype='text/csv')
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = 'Template'
    fill = PatternFill('solid', fgColor='1E3A5F'); font = Font(color='FFFFFF', bold=True)
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h); c.fill = fill; c.font = font
        ws.column_dimensions[get_column_letter(i)].width = max(14, len(h) + 3)
    out = _io.BytesIO(); wb.save(out); out.seek(0)
    return send_file(out, as_attachment=True, download_name=f'{key}_template.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def _read_uploaded(f):
    """Return (headers, list-of-row-dicts) from an uploaded csv/xlsx."""
    name = f.filename.lower()
    if name.endswith('.csv'):
        text = f.read().decode('utf-8-sig', errors='replace')
        reader = _csv.DictReader(_io.StringIO(text))
        return list(reader)
    if name.endswith('.xlsx') or name.endswith('.xlsm'):
        from openpyxl import load_workbook
        wb = load_workbook(f, data_only=True, read_only=True)
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        try:
            headers = [str(h).strip() if h is not None else '' for h in next(it)]
        except StopIteration:
            return []
        rows = []
        for raw in it:
            if raw is None:
                continue
            rows.append({headers[i]: raw[i] for i in range(min(len(headers), len(raw)))})
        return rows
    raise ValueError('Unsupported file type. Use .csv or .xlsx')


@io_bp.route('/<key>/import', methods=['POST'])
@login_required
def io_import(key):
    spec = _REGISTRY.get(key)
    if not spec:
        return jsonify({'ok': False, 'error': 'Unknown import'}), 404
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'No file uploaded.'}), 400

    model = spec['model']
    ukey = spec['unique']
    hdr_by_attr = {a: h for h, a in spec['columns']}

    try:
        rows = _read_uploaded(f)
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

    # Existing unique values to skip.
    existing = set()
    if ukey and hasattr(model, ukey):
        existing = {getattr(r, ukey) for r in
                    model.query.with_entities(getattr(model, ukey)).all()}

    # Parent lookup maps.
    parent_maps = {}
    for phdr, fk_attr, pmodel, pkey_attr, pid_attr in spec['parents']:
        parent_maps[phdr] = (fk_attr, pid_attr,
                             {getattr(p, pkey_attr): p.id for p in
                              pmodel.query.with_entities(getattr(pmodel, pkey_attr), pmodel.id).all()})

    added = skipped = 0
    errors = []
    for idx, row in enumerate(rows, 2):
        uheader = hdr_by_attr.get(ukey)
        uval = (str(row.get(uheader, '')).strip() if uheader else '')
        if ukey and not uval:
            continue  # skip blank key rows
        if ukey and uval in existing:
            skipped += 1
            continue

        obj = model()
        for header, attr in spec['columns']:
            if attr in (fk for _, fk, *_ in spec['parents']):
                continue  # parents handled below
            if header not in row:
                continue
            setattr(obj, attr, _coerce_value(attr, row.get(header), spec))

        ok = True
        for phdr, (fk_attr, pid_attr, pmap) in parent_maps.items():
            pval = str(row.get(phdr, '')).strip()
            if pval and pval in pmap:
                setattr(obj, fk_attr, pval)
                setattr(obj, pid_attr, pmap[pval])
            elif pval:
                errors.append(f'Row {idx}: parent "{pval}" not found; skipped.')
                ok = False
                break
        if not ok:
            continue

        db.session.add(obj)
        if ukey:
            existing.add(uval)
        added += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

    return jsonify({'ok': True, 'added': added, 'skipped': skipped,
                    'errors': errors[:50]})