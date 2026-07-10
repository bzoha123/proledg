/* ══════════════════════════════════════════════════════════════════
   grid-kit.js
   Adds the grid features AG-Grid ships only in its paid Enterprise
   build, implemented on top of the free Community API.

   Toolbar is deliberately small — three controls, not six:

       [ Columns ▾ ]   [ Filters (2) ]   [ Export ▾ ]

   Everything else (pin, hide, auto-size, reset) lives inside the
   Columns dropdown, where it belongs.

   Version note
   ------------
   AG-Grid moved column operations from `columnApi` (v31 and earlier)
   onto `api` (v33+). `cols()` resolves whichever object is present, so
   this file works on both without a version check at every call site.

   Usage, inside onGridReady:

       GridKit.enhance(params, 'empGrid', { storageKey: 'employees' });

   `params` may be the whole onGridReady event, or just the api.
   ══════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var IS_AR = document.documentElement.getAttribute('dir') === 'rtl';

  var T = IS_AR ? {
    columns: 'الأعمدة', filters: 'الفلاتر', exportLbl: 'تصدير',
    showAll: 'إظهار الكل', hideAll: 'إخفاء الكل',
    autosize: 'ملاءمة العرض', reset: 'إعادة تعيين',
    clearFilters: 'مسح كل الفلاتر', noFilters: 'لا توجد فلاتر',
    csv: 'ملف CSV', excel: 'ملف Excel', pdf: 'طباعة / PDF',
    pinLeft: 'تثبيت لليسار', pinRight: 'تثبيت لليمين', unpin: 'إلغاء التثبيت',
    visible: 'مرئي'
  } : {
    columns: 'Columns', filters: 'Filters', exportLbl: 'Export',
    showAll: 'Show all', hideAll: 'Hide all',
    autosize: 'Fit widths', reset: 'Reset layout',
    clearFilters: 'Clear all filters', noFilters: 'No active filters',
    csv: 'CSV file', excel: 'Excel file', pdf: 'Print / PDF',
    pinLeft: 'Pin left', pinRight: 'Pin right', unpin: 'Unpin',
    visible: 'Visible'
  };

  /* ── Version bridge ───────────────────────────────────────────
     v31: column ops live on columnApi.  v33: they moved to api.   */
  function cols(ctx) {
    return ctx.columnApi || ctx.api;
  }

  function allColumns(ctx) {
    var c = cols(ctx);
    if (c.getAllGridColumns) return c.getAllGridColumns();   // v31
    if (c.getColumns) return c.getColumns();                 // v33
    return [];
  }

  function setVisible(ctx, colId, visible) {
    var c = cols(ctx);
    if (c.setColumnsVisible) c.setColumnsVisible([colId], visible);
    else if (c.setColumnVisible) c.setColumnVisible(colId, visible);
  }

  function setPinned(ctx, colId, side) {
    var c = cols(ctx);
    if (c.setColumnsPinned) c.setColumnsPinned([colId], side);
    else if (c.setColumnPinned) c.setColumnPinned(colId, side);
  }

  function autoSize(ctx) {
    var c = cols(ctx);
    var ids = allColumns(ctx).filter(function (x) { return x.isVisible(); })
                             .map(function (x) { return x.getColId(); });
    if (c.autoSizeColumns) c.autoSizeColumns(ids);
    else if (c.sizeColumnsToFit) c.sizeColumnsToFit();
  }

  function resetCols(ctx) {
    var c = cols(ctx);
    if (c.resetColumnState) c.resetColumnState();
  }

  function colState(ctx) {
    var c = cols(ctx);
    return c.getColumnState ? c.getColumnState() : null;
  }

  function applyState(ctx, state) {
    var c = cols(ctx);
    if (c.applyColumnState) c.applyColumnState({ state: state, applyOrder: true });
  }

  /* ── Storage ──────────────────────────────────────────────── */
  function load(k) {
    try { return JSON.parse(localStorage.getItem('gk:' + k) || 'null'); }
    catch (e) { return null; }
  }
  function save(k, v) {
    try { localStorage.setItem('gk:' + k, JSON.stringify(v)); } catch (e) {}
  }

  /* ── DOM helpers ──────────────────────────────────────────── */
  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function closeMenus() {
    document.querySelectorAll('.gk-pop').forEach(function (m) { m.remove(); });
    document.querySelectorAll('.gk-btn.gk-open').forEach(function (b) {
      b.classList.remove('gk-open');
    });
  }
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.gk-pop, .gk-btn')) closeMenus();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeMenus();
  });

  function popover(anchor) {
    closeMenus();
    anchor.classList.add('gk-open');
    var p = el('div', 'gk-pop');
    var r = anchor.getBoundingClientRect();
    p.style.top = (window.scrollY + r.bottom + 6) + 'px';
    var left = window.scrollX + r.left;
    // Keep the panel on screen.
    left = Math.min(left, window.scrollX + window.innerWidth - 268);
    p.style.left = Math.max(8, left) + 'px';
    document.body.appendChild(p);
    return p;
  }

  function colName(col) {
    var d = col.getColDef();
    return d.headerName || d.field || col.getColId();
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /* ══ Columns panel: visibility + pin + sizing, all in one ════ */
  function columnsPanel(ctx, anchor, key, onChange) {
    var p = popover(anchor);

    var head = el('div', 'gk-pop-head');
    head.appendChild(el('span', 'gk-pop-title', T.columns));
    var bulk = el('div', 'gk-pop-bulk');

    function bulkBtn(label, fn) {
      var b = el('button', 'gk-link', label);
      b.type = 'button';
      b.addEventListener('click', function () {
        fn();
        onChange();
        p.remove();
        columnsPanel(ctx, anchor, key, onChange);   // redraw
      });
      bulk.appendChild(b);
    }
    bulkBtn(T.showAll, function () {
      allColumns(ctx).forEach(function (c) { setVisible(ctx, c.getColId(), true); });
    });
    bulkBtn(T.autosize, function () { autoSize(ctx); });
    bulkBtn(T.reset, function () {
      resetCols(ctx);
      try { localStorage.removeItem('gk:' + key + ':cols'); } catch (e) {}
    });
    head.appendChild(bulk);
    p.appendChild(head);

    var list = el('div', 'gk-pop-list');
    allColumns(ctx).forEach(function (col) {
      var id = col.getColId();
      var row = el('div', 'gk-col-row');

      var lab = el('label', 'gk-col-name');
      var cb = el('input');
      cb.type = 'checkbox';
      cb.checked = col.isVisible();
      cb.addEventListener('change', function () {
        setVisible(ctx, id, cb.checked);   // instant — no refresh
        onChange();
      });
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(colName(col)));
      row.appendChild(lab);

      // Pin control: a 3-state segmented toggle, not another button row.
      var pin = el('div', 'gk-pin');
      [['left', 'L', T.pinLeft], [null, '–', T.unpin], ['right', 'R', T.pinRight]]
        .forEach(function (opt) {
          var b = el('button', 'gk-pin-btn', opt[1]);
          b.type = 'button';
          b.title = opt[2];
          if (col.getPinned() === opt[0] || (!col.getPinned() && opt[0] === null)) {
            b.classList.add('gk-pin-on');
          }
          b.addEventListener('click', function () {
            setPinned(ctx, id, opt[0]);
            onChange();
            pin.querySelectorAll('.gk-pin-btn').forEach(function (x) {
              x.classList.remove('gk-pin-on');
            });
            b.classList.add('gk-pin-on');
          });
          pin.appendChild(b);
        });
      row.appendChild(pin);
      list.appendChild(row);
    });
    p.appendChild(list);
  }

  /* ══ Filters panel ═══════════════════════════════════════════ */
  function filtersPanel(ctx, anchor) {
    var api = ctx.api;
    var p = popover(anchor);
    var model = api.getFilterModel ? (api.getFilterModel() || {}) : {};
    var keys = Object.keys(model);

    var head = el('div', 'gk-pop-head');
    head.appendChild(el('span', 'gk-pop-title', T.filters));
    p.appendChild(head);

    if (!keys.length) {
      p.appendChild(el('div', 'gk-empty', T.noFilters));
      return;
    }

    var list = el('div', 'gk-pop-list');
    keys.forEach(function (id) {
      var col = allColumns(ctx).filter(function (c) { return c.getColId() === id; })[0];
      var row = el('div', 'gk-col-row');
      row.appendChild(el('span', 'gk-col-name', esc(col ? colName(col) : id)));
      var x = el('button', 'gk-chip-x', '<i class="fas fa-times"></i>');
      x.type = 'button';
      x.addEventListener('click', function () {
        var m = api.getFilterModel();
        delete m[id];
        api.setFilterModel(m);
        p.remove();
        filtersPanel(ctx, anchor);
      });
      row.appendChild(x);
      list.appendChild(row);
    });
    p.appendChild(list);

    var clear = el('button', 'gk-link gk-danger', T.clearFilters);
    clear.type = 'button';
    clear.style.margin = '4px 8px 6px';
    clear.addEventListener('click', function () {
      api.setFilterModel(null);
      closeMenus();
    });
    p.appendChild(clear);
  }

  /* ══ Export ══════════════════════════════════════════════════ */
  function exportPanel(ctx, anchor, name) {
    var p = popover(anchor);
    p.appendChild(el('div', 'gk-pop-head',
      '<span class="gk-pop-title">' + T.exportLbl + '</span>'));

    function item(icon, label, colour, fn) {
      var row = el('button', 'gk-item',
        '<i class="fas ' + icon + '" style="color:' + colour + '"></i>' + label);
      row.type = 'button';
      row.addEventListener('click', function () { closeMenus(); fn(); });
      p.appendChild(row);
    }
    item('fa-file-csv', T.csv, '#16a34a', function () {
      ctx.api.exportDataAsCsv({ fileName: name + '.csv' });
    });
    item('fa-file-excel', T.excel, '#15803d', function () { toExcel(ctx, name); });
    item('fa-file-pdf', T.pdf, '#dc2626', function () { toPdf(ctx, name); });
  }

  function rows(ctx) {
    var visible = allColumns(ctx).filter(function (c) { return c.isVisible(); });
    var out = [];
    ctx.api.forEachNodeAfterFilterAndSort(function (node) {
      if (!node.data) return;
      out.push(visible.map(function (c) {
        var f = c.getColDef().field;
        var v = f ? node.data[f] : '';
        return v == null ? '' : v;
      }));
    });
    return { head: visible.map(colName), body: out };
  }

  function toExcel(ctx, name) {
    var d = rows(ctx);
    var html = '<html xmlns:x="urn:schemas-microsoft-com:office:excel"><head><meta charset="utf-8">' +
      '<style>th{background:#eff6ff;font-weight:bold;}' +
      'table,td,th{border:1px solid #cbd5e1;border-collapse:collapse;padding:4px;}</style></head><body><table><thead><tr>' +
      d.head.map(function (h) { return '<th>' + esc(h) + '</th>'; }).join('') +
      '</tr></thead><tbody>' +
      d.body.map(function (r) {
        return '<tr>' + r.map(function (c) { return '<td>' + esc(c) + '</td>'; }).join('') + '</tr>';
      }).join('') +
      '</tbody></table></body></html>';
    var blob = new Blob(['\ufeff' + html], { type: 'application/vnd.ms-excel' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name + '.xls';
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function toPdf(ctx, name) {
    var d = rows(ctx);
    var w = window.open('', '_blank');
    if (!w) return;
    w.document.write('<html dir="' + (IS_AR ? 'rtl' : 'ltr') + '"><head><meta charset="utf-8"><title>' +
      esc(name) + '</title><style>' +
      'body{font-family:system-ui,Segoe UI,Arial,sans-serif;padding:18px;}' +
      'h2{font-size:15px;margin:0 0 12px;color:#1e3a5f;}' +
      'table{width:100%;border-collapse:collapse;font-size:11px;}' +
      'th{background:#eff6ff;color:#1d4ed8;text-align:start;}' +
      'th,td{border:1px solid #cbd5e1;padding:5px 7px;}' +
      'tr:nth-child(even) td{background:#f8fafc;}@page{size:landscape;margin:12mm;}' +
      '</style></head><body><h2>' + esc(name) + '</h2><table><thead><tr>' +
      d.head.map(function (h) { return '<th>' + esc(h) + '</th>'; }).join('') +
      '</tr></thead><tbody>' +
      d.body.map(function (r) {
        return '<tr>' + r.map(function (c) { return '<td>' + esc(c) + '</td>'; }).join('') + '</tr>';
      }).join('') + '</tbody></table></body></html>');
    w.document.close(); w.focus();
    setTimeout(function () { w.print(); }, 250);
  }

  /* ══ enhance ═════════════════════════════════════════════════ */
  function enhance(params, containerId, opts) {
    opts = opts || {};

    // Accept either the onGridReady event or a bare api.
    var ctx = params && params.api ? params : { api: params, columnApi: null };
    if (!ctx.api) return;

    var container = typeof containerId === 'string'
      ? document.getElementById(containerId) : containerId;
    if (!container || container._gkReady) return;
    container._gkReady = true;

    var key = opts.storageKey || containerId;
    var name = opts.exportName || 'export';

    var saved = load(key + ':cols');
    if (saved && saved.length) applyState(ctx, saved);

    function persist() { var st = colState(ctx); if (st) save(key + ':cols', st); }

    var bar = el('div', 'gk-toolbar');

    function btn(icon, label, caret) {
      var b = el('button', 'gk-btn',
        '<i class="fas ' + icon + '"></i><span>' + label + '</span>' +
        (caret ? '<i class="fas fa-chevron-down gk-caret"></i>' : ''));
      b.type = 'button';
      bar.appendChild(b);
      return b;
    }

    var bCols = btn('fa-table-columns', T.columns, true);
    bCols.addEventListener('click', function (e) {
      e.stopPropagation();
      if (bCols.classList.contains('gk-open')) { closeMenus(); return; }
      columnsPanel(ctx, bCols, key, persist);
    });

    var bFilter = btn('fa-filter', T.filters, true);
    bFilter.addEventListener('click', function (e) {
      e.stopPropagation();
      if (bFilter.classList.contains('gk-open')) { closeMenus(); return; }
      filtersPanel(ctx, bFilter);
    });

    var bExp = btn('fa-download', T.exportLbl, true);
    bExp.addEventListener('click', function (e) {
      e.stopPropagation();
      if (bExp.classList.contains('gk-open')) { closeMenus(); return; }
      exportPanel(ctx, bExp, name);
    });

    container.parentNode.insertBefore(bar, container);

    function badge() {
      var n = Object.keys((ctx.api.getFilterModel && ctx.api.getFilterModel()) || {}).length;
      var old = bFilter.querySelector('.gk-badge');
      if (old) old.remove();
      bFilter.classList.toggle('gk-armed', n > 0);
      if (n) {
        var s = el('span', 'gk-badge', String(n));
        bFilter.insertBefore(s, bFilter.querySelector('.gk-caret'));
      }
    }
    badge();

    ctx.api.addEventListener('filterChanged', badge);
    ['columnMoved', 'columnVisible', 'columnPinned'].forEach(function (ev) {
      ctx.api.addEventListener(ev, persist);
    });
    ctx.api.addEventListener('columnResized', function (e) { if (e.finished) persist(); });
  }

  window.GridKit = { enhance: enhance };
})();
