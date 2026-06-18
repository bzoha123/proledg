/* Seller Master System – app.js */

document.addEventListener('DOMContentLoaded', function () {

    // ---- Sidebar Toggle (Desktop) ----
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    const mainContent = document.querySelector('.main-content');

    if (toggleBtn && sidebar) {
        // Restore state
        if (localStorage.getItem('sidebarCollapsed') === '1') {
            sidebar.classList.add('collapsed');
        }

        toggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('collapsed');
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed') ? '1' : '0');
        });
    }

    // ---- Sidebar Toggle (Mobile) ----
    const mobileToggle = document.getElementById('sidebarToggleMobile');
    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener('click', function () {
            sidebar.classList.toggle('mobile-open');
        });
        // Close on backdrop click
        document.addEventListener('click', function (e) {
            if (window.innerWidth <= 768 && !sidebar.contains(e.target) && e.target !== mobileToggle) {
                sidebar.classList.remove('mobile-open');
            }
        });
    }

    // ---- Auto-dismiss alerts ----
    document.querySelectorAll('.alert').forEach(function (alert) {
        if (!alert.classList.contains('alert-danger') && !alert.classList.contains('alert-warning')) {
            setTimeout(function () {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            }, 5000);
        }
    });

    // ---- Form validation highlight ----
    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
                // Switch to tab with first error
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    const tabPane = firstInvalid.closest('.tab-pane');
                    if (tabPane) {
                        const tabId = tabPane.id;
                        const tabBtn = document.querySelector(`[data-bs-target="#${tabId}"]`);
                        if (tabBtn) tabBtn.click();
                    }
                    firstInvalid.focus();
                }
            }
            form.classList.add('was-validated');
        });
    });

    // ---- Seller Code formatter (display only) ----
    const codeInput = document.querySelector('[name="seller_code"]');
    if (codeInput) {
        codeInput.setAttribute('readonly', true);
    }

    // ---- Tooltips ----
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el);
    });

    // ---- Table row click to view ----
    document.querySelectorAll('tr[data-href]').forEach(function (row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function (e) {
            if (!e.target.closest('button, a, input')) {
                window.location.href = row.dataset.href;
            }
        });
    });

    // ---- Confirm forms ----
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (!confirm(el.dataset.confirm)) e.preventDefault();
        });
    });

    // ---- Number inputs: prevent negative ----
    document.querySelectorAll('input[type="number"]').forEach(function (input) {
        input.addEventListener('input', function () {
            if (parseFloat(input.value) < 0) input.value = 0;
        });
    });

    // ---- File input label ----
    document.querySelectorAll('input[type="file"]').forEach(function (input) {
        input.addEventListener('change', function () {
            const label = input.nextElementSibling;
            if (label && label.tagName === 'LABEL') {
                label.textContent = input.files[0]?.name || 'Choose file';
            }
        });
    });

});
