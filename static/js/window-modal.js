/* ══════════════════════════════════════════════════════════════════
   window-modal.js
   Turns every Bootstrap modal into a desktop-style window.

   Auto-applies to all `.modal` elements — no template changes needed.
   Opt out on a specific modal with  data-wm="off".

   Features
     • Title bar with Minimize (_), Maximize/Restore (□), Close (✕)
     • Drag by the title bar, clamped to the viewport
     • Resize from the right edge, bottom edge and bottom-right corner
     • Minimized windows collapse to a taskbar strip at the bottom
     • Close prompts when the form has unsaved changes
     • Double-click the title bar to toggle maximize
     • Esc restores a maximized window before closing
   ══════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var IS_AR = document.documentElement.getAttribute('dir') === 'rtl';
  var T = {
    minimize: IS_AR ? 'تصغير' : 'Minimize',
    maximize: IS_AR ? 'تكبير' : 'Maximize',
    restore:  IS_AR ? 'استعادة' : 'Restore',
    close:    IS_AR ? 'إغلاق' : 'Close',
    unsaved:  IS_AR
      ? 'لديك تغييرات غير محفوظة. هل تريد الإغلاق دون حفظ؟'
      : 'You have unsaved changes. Close without saving?',
    untitled: IS_AR ? 'نافذة' : 'Window'
  };

  var MIN_W = 320;
  var MIN_H = 180;

  /* ── Taskbar ──────────────────────────────────────────────── */
  function taskbar() {
    var el = document.getElementById('wmTaskbar');
    if (!el) {
      el = document.createElement('div');
      el.id = 'wmTaskbar';
      document.body.appendChild(el);
    }
    return el;
  }

  /* ── Helpers ──────────────────────────────────────────────── */
  /* This app uses a dozen different header conventions — `.modal-header`,
     `.pur-hdr`, `.emp-modal-header`, `.qa-hdr`, `.bm-hdr` and more. Rather
     than chase class names, find the header structurally: the first element
     child of `.modal-content` that carries a title. */
  function header(modal) {
    var content = modal.querySelector('.modal-content');
    if (!content) return null;

    // 1. The canonical Bootstrap header, when present.
    var std = content.querySelector(':scope > .modal-header');
    if (std) return std;

    // 2. Any direct child whose class looks like a header.
    var kids = content.children;
    for (var i = 0; i < kids.length; i++) {
      var k = kids[i];
      if (k.tagName === 'FORM') continue;             // forms wrap body+footer
      var cls = (k.className || '').toString();
      if (/(^|[\s-])(hdr|header)([\s-]|$)/i.test(cls)) return k;
    }

    // 3. Fall back to whichever direct child holds the title element.
    for (var j = 0; j < kids.length; j++) {
      var kid = kids[j];
      if (kid.tagName === 'FORM') continue;
      if (kid.querySelector(':scope > .modal-title, :scope > h5, :scope > h6, :scope > div > .modal-title')) {
        return kid;
      }
    }

    // 4. Some modals style their header purely with inline `style=` and no
    //    class or heading tag. Treat the first non-body child as the header
    //    when it sits directly above `.modal-body` and reads like a bar.
    for (var k2 = 0; k2 < kids.length; k2++) {
      var node = kids[k2];
      if (node.tagName === 'FORM') continue;
      if (node.classList.contains('modal-body') ||
          node.classList.contains('modal-footer')) break;   // no header present
      var next = node.nextElementSibling;
      var leadsBody = next && (next.classList.contains('modal-body') ||
                               next.querySelector(':scope > .modal-body'));
      var st = node.getAttribute('style') || '';
      if (leadsBody && /padding/i.test(st) && node.textContent.trim()) {
        return node;
      }
    }
    return null;
  }

  function dialog(modal) {
    return modal.querySelector('.modal-dialog');
  }

  function titleText(modal) {
    var t = modal.querySelector('.modal-title, .modal-content h5, .modal-content h6');
    var s = t ? t.textContent.trim() : '';
    if (!s) {
      // Inline-styled headers carry their title as plain text.
      var hdr = modal._wmHeader;
      if (hdr) s = (hdr.textContent || '').trim().split('\n')[0].trim();
    }
    if (s.length > 42) s = s.slice(0, 40) + '…';
    return s || T.untitled;
  }

  /* A header is "light" when it has no dark background of its own. */
  function isLightHeader(hdr) {
    var bg = window.getComputedStyle(hdr).backgroundColor || '';
    var m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (!m) return true;
    var lum = (0.299 * +m[1] + 0.587 * +m[2] + 0.114 * +m[3]) / 255;
    return lum > 0.6;
  }

  /* ── Dirty tracking (unsaved changes) ─────────────────────── */
  function snapshot(modal) {
    var vals = [];
    modal.querySelectorAll('input, select, textarea').forEach(function (el) {
      if (el.type === 'file') return;               // cannot snapshot files
      if (el.type === 'checkbox' || el.type === 'radio') vals.push(el.checked ? '1' : '0');
      else vals.push(el.value == null ? '' : String(el.value));
    });
    return vals.join('\u0001');
  }

  function isDirty(modal) {
    if (modal.dataset.wmConfirm === 'off') return false;
    var base = modal._wmSnapshot;
    if (base === undefined) return false;
    return snapshot(modal) !== base;
  }

  /* ── Maximize / restore ───────────────────────────────────── */
  function toggleMaximize(modal) {
    var dlg = dialog(modal);
    if (!dlg) return;
    var max = dlg.classList.toggle('wm-maximized');
    if (max) {
      // Remember where the window was so Restore puts it back.
      dlg._wmPrev = {
        transform: dlg.style.transform,
        width: dlg.style.width,
        moved: dlg.classList.contains('wm-moved')
      };
      dlg.style.transform = '';
      dlg.classList.remove('wm-moved');
      var c = modal.querySelector('.modal-content');
      if (c) { c.style.width = ''; c.style.height = ''; }
    } else if (dlg._wmPrev) {
      dlg.style.transform = dlg._wmPrev.transform || '';
      dlg.style.width = dlg._wmPrev.width || '';
      if (dlg._wmPrev.moved) dlg.classList.add('wm-moved');
    }
    var btn = modal.querySelector('.wm-btn-max');
    if (btn) {
      btn.title = max ? T.restore : T.maximize;
      btn.innerHTML = max
        ? '<i class="far fa-clone"></i>'
        : '<i class="far fa-square"></i>';
    }
  }

  /* ── Minimize / restore from taskbar ──────────────────────── */
  function minimize(modal) {
    modal.classList.add('wm-minimized');
    var bd = document.querySelector('.modal-backdrop:not(.wm-minimized)');
    if (bd) { bd.classList.add('wm-minimized'); modal._wmBackdrop = bd; }

    var chip = document.createElement('div');
    chip.className = 'wm-task';
    chip.innerHTML =
      '<i class="fas fa-window-restore"></i>' +
      '<span class="wm-task-label"></span>' +
      '<button type="button" class="wm-task-close" title="' + T.close + '">' +
      '<i class="fas fa-times"></i></button>';
    chip.querySelector('.wm-task-label').textContent = titleText(modal);
    chip.title = titleText(modal);

    chip.addEventListener('click', function (e) {
      if (e.target.closest('.wm-task-close')) return;
      restore(modal);
    });
    chip.querySelector('.wm-task-close').addEventListener('click', function (e) {
      e.stopPropagation();
      restore(modal);
      requestAnimationFrame(function () { attemptClose(modal); });
    });

    taskbar().appendChild(chip);
    modal._wmChip = chip;
  }

  function restore(modal) {
    modal.classList.remove('wm-minimized');
    if (modal._wmBackdrop) {
      modal._wmBackdrop.classList.remove('wm-minimized');
      modal._wmBackdrop = null;
    }
    if (modal._wmChip) {
      modal._wmChip.remove();
      modal._wmChip = null;
    }
  }

  /* ── Close (with unsaved-changes guard) ───────────────────── */
  /* The prompt only fires for closes the *user* started — the ✕ button,
     Esc, or a backdrop click. Code that calls `.hide()` after a successful
     save must never be interrupted, so we arm the guard just before a
     user-driven dismissal and disarm it immediately afterwards. */
  function attemptClose(modal) {
    if (isDirty(modal) && !window.confirm(T.unsaved)) return;
    modal._wmSkipGuard = true;
    var inst = window.bootstrap && bootstrap.Modal.getInstance(modal);
    if (inst) inst.hide();
    else modal.classList.remove('show');
  }

  /* Arm the guard for the dismissals Bootstrap handles itself. */
  function armGuard(modal) { modal._wmGuardArmed = true; }

  /* ── Dragging ─────────────────────────────────────────────── */
  function makeDraggable(modal, hdr) {
    hdr.addEventListener('mousedown', function (e) {
      if (window.innerWidth < 768) return;             // no dragging on phones
      if (e.button !== 0) return;
      if (e.target.closest('.wm-controls, button, a, input, select')) return;

      var dlg = dialog(modal);
      if (!dlg || dlg.classList.contains('wm-maximized')) return;

      var rect = dlg.getBoundingClientRect();
      var startX = e.clientX;
      var startY = e.clientY;
      var origin = dlg._wmPos || { x: 0, y: 0 };

      dlg.classList.add('wm-moved');
      modal.classList.add('wm-dragging');
      document.body.classList.add('wm-drag-active');

      function onMove(ev) {
        var nx = origin.x + (ev.clientX - startX);
        var ny = origin.y + (ev.clientY - startY);

        // Clamp so the window can never be dragged out of sight.
        var minX = -(rect.left - origin.x) + 8;
        var maxX = window.innerWidth - (rect.left - origin.x) - rect.width - 8;
        var minY = -(rect.top - origin.y) + 8;
        var maxY = window.innerHeight - (rect.top - origin.y) - 40;

        nx = Math.min(Math.max(nx, minX), maxX);
        ny = Math.min(Math.max(ny, minY), maxY);

        dlg._wmPos = { x: nx, y: ny };
        dlg.style.transform = 'translate(' + nx + 'px,' + ny + 'px)';
      }

      function onUp() {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        modal.classList.remove('wm-dragging');
        document.body.classList.remove('wm-drag-active');
      }

      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
      e.preventDefault();
    });

    hdr.addEventListener('dblclick', function (e) {
      if (e.target.closest('.wm-controls, button')) return;
      toggleMaximize(modal);
    });
  }

  /* ── Resizing ─────────────────────────────────────────────── */
  function makeResizable(modal) {
    var content = modal.querySelector('.modal-content');
    if (!content || content.querySelector('.wm-resizer')) return;

    ['e', 's', 'se'].forEach(function (dir) {
      var grip = document.createElement('div');
      grip.className = 'wm-resizer wm-resizer-' + dir;
      content.appendChild(grip);

      grip.addEventListener('mousedown', function (e) {
        if (window.innerWidth < 768) return;
        var dlg = dialog(modal);
        if (dlg && dlg.classList.contains('wm-maximized')) return;

        var rect = content.getBoundingClientRect();
        var startX = e.clientX, startY = e.clientY;
        var startW = rect.width, startH = rect.height;

        document.body.classList.add('wm-resize-active');

        function onMove(ev) {
          if (dir.indexOf('e') !== -1) {
            content.style.width = Math.max(MIN_W, startW + (ev.clientX - startX)) + 'px';
            if (dlg) dlg.style.maxWidth = 'none';
          }
          if (dir.indexOf('s') !== -1) {
            content.style.height = Math.max(MIN_H, startH + (ev.clientY - startY)) + 'px';
            var body = modal.querySelector('.modal-body');
            if (body) { body.style.maxHeight = 'none'; body.style.overflow = 'auto'; }
          }
        }
        function onUp() {
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          document.body.classList.remove('wm-resize-active');
        }
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        e.preventDefault();
        e.stopPropagation();
      });
    });
  }

  /* ── Build the control cluster ────────────────────────────── */
  function addControls(modal, hdr) {
    if (hdr.querySelector('.wm-controls')) return;

    hdr.classList.add('wm-titlebar');
    if (isLightHeader(hdr)) hdr.classList.add('wm-light');
    // Make sure the controls sit hard right regardless of the header's layout.
    var cs = window.getComputedStyle(hdr);
    if (cs.display.indexOf('flex') === -1) hdr.style.display = 'flex';
    hdr.style.alignItems = 'center';

    var wrap = document.createElement('div');
    wrap.className = 'wm-controls';

    function mk(cls, title, html, fn) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'wm-btn ' + cls;
      b.title = title;
      b.setAttribute('aria-label', title);
      b.innerHTML = html;
      b.addEventListener('click', function (e) { e.stopPropagation(); fn(); });
      return b;
    }

    wrap.appendChild(mk('wm-btn-min', T.minimize, '<i class="fas fa-minus"></i>',
                        function () { minimize(modal); }));
    wrap.appendChild(mk('wm-btn-max', T.maximize, '<i class="far fa-square"></i>',
                        function () { toggleMaximize(modal); }));
    wrap.appendChild(mk('wm-btn-close', T.close, '<i class="fas fa-times"></i>',
                        function () { attemptClose(modal); }));

    hdr.appendChild(wrap);
  }

  /* ── Upgrade one modal ────────────────────────────────────── */
  function upgrade(modal) {
    if (modal._wmReady || modal.dataset.wm === 'off') return;
    var hdr = header(modal);
    if (!hdr) return;                       // headerless modals are left alone

    modal._wmHeader = hdr;                  // titleText() may need it
    addControls(modal, hdr);
    makeDraggable(modal, hdr);
    makeResizable(modal);
    modal._wmReady = true;
  }

  /* ── Wire global modal events ─────────────────────────────── */
  document.addEventListener('show.bs.modal', function (e) {
    upgrade(e.target);
  });

  document.addEventListener('shown.bs.modal', function (e) {
    var modal = e.target;
    // Baseline for dirty-checking, taken once the form is populated.
    modal._wmSnapshot = snapshot(modal);
    // Always open centered.
    var dlg = dialog(modal);
    if (dlg && !dlg.classList.contains('wm-maximized')) {
      dlg.style.transform = '';
      dlg._wmPos = { x: 0, y: 0 };
      dlg.classList.remove('wm-moved');
    }
  });

  document.addEventListener('hidden.bs.modal', function (e) {
    var modal = e.target;
    restore(modal);                          // drop any taskbar chip
    modal._wmSnapshot = undefined;
    var dlg = dialog(modal);
    if (dlg) {
      dlg.classList.remove('wm-maximized', 'wm-moved');
      dlg.style.transform = '';
      dlg.style.maxWidth = '';
      dlg._wmPos = { x: 0, y: 0 };
    }
    var c = modal.querySelector('.modal-content');
    if (c) { c.style.width = ''; c.style.height = ''; }
  });

  /* Bootstrap's own dismissals (Esc, backdrop, data-bs-dismiss) must honour
     the unsaved-changes guard. Programmatic `.hide()` calls — the 53 places
     that close a modal after a successful save — must not be interrupted. */
  document.addEventListener('hide.bs.modal', function (e) {
    var modal = e.target;
    if (modal._wmSkipGuard) { modal._wmSkipGuard = false; return; }
    if (!modal._wmGuardArmed) return;          // programmatic close -> allow
    modal._wmGuardArmed = false;
    if (isDirty(modal) && !window.confirm(T.unsaved)) {
      e.preventDefault();
    }
  });

  /* Arm the guard the moment the user does something that closes a modal. */
  document.addEventListener('mousedown', function (e) {
    var modal = e.target.closest('.modal');
    if (!modal) return;
    // Backdrop click: the mousedown lands on the .modal element itself.
    if (e.target === modal) armGuard(modal);
    var dismiss = e.target.closest('[data-bs-dismiss="modal"]');
    if (dismiss) armGuard(modal);
  }, true);

  /* Esc: restore a maximized window first, then let Bootstrap close it. */
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = document.querySelector('.modal.show:not(.wm-minimized)');
    if (!open) return;
    var dlg = dialog(open);
    if (dlg && dlg.classList.contains('wm-maximized')) {
      toggleMaximize(open);          // first Esc un-maximizes
      e.stopPropagation();
      return;
    }
    armGuard(open);                  // second Esc closes -> guard applies
  }, true);

  /* Keep windows on screen when the viewport shrinks. */
  window.addEventListener('resize', function () {
    document.querySelectorAll('.modal.show .modal-dialog.wm-moved').forEach(function (dlg) {
      var r = dlg.getBoundingClientRect();
      if (r.right > window.innerWidth || r.bottom > window.innerHeight) {
        dlg.style.transform = '';
        dlg._wmPos = { x: 0, y: 0 };
      }
    });
  });

  /* Expose a tiny API for pages that want to drive windows directly. */
  window.WindowModal = {
    minimize: minimize,
    restore: restore,
    toggleMaximize: toggleMaximize,
    close: attemptClose,
    /** Close without prompting (call after a successful save). */
    forceClose: function (modal) {
      modal._wmSkipGuard = true;
      modal._wmSnapshot = snapshot(modal);
      var inst = window.bootstrap && bootstrap.Modal.getInstance(modal);
      if (inst) inst.hide();
    },
    /** Re-baseline the dirty check (call after loading data into a form). */
    markClean: function (modal) { modal._wmSnapshot = snapshot(modal); }
  };
})();
