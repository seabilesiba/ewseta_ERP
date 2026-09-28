/**
 * Procurement public site: dark/light theme toggle (runs in assets_frontend_minimal).
 * Do not attach click handlers to header dropdowns here — Bootstrap is not loaded yet.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'ew-proc-theme';
    var CLASS_DARK = 'ew-proc-dark';

    function applyTheme(theme) {
        var html = document.documentElement;
        var isDark = theme === 'dark';
        html.classList.toggle(CLASS_DARK, isDark);
        html.dataset.ewProcTheme = isDark ? 'dark' : 'light';
        html.style.colorScheme = isDark ? 'dark' : 'light';
        document.querySelectorAll('.ew-proc-theme-toggle').forEach(function (btn) {
            var icon = btn.querySelector('i');
            if (icon) {
                icon.className = isDark ? 'fa fa-sun-o' : 'fa fa-moon-o';
            }
            var label = isDark ? 'Switch to light mode' : 'Switch to dark mode';
            btn.setAttribute('aria-label', label);
            btn.title = label;
        });
    }

    function getStoredTheme() {
        try {
            return localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light';
        } catch (e) {
            return 'light';
        }
    }

    function bindThemeToggles() {
        document.querySelectorAll('.ew-proc-theme-toggle').forEach(function (btn) {
            if (btn.dataset.ewProcThemeBound) {
                return;
            }
            btn.dataset.ewProcThemeBound = '1';
            btn.addEventListener('click', function (ev) {
                ev.preventDefault();
                var html = document.documentElement;
                var next = html.classList.contains(CLASS_DARK) ? 'light' : 'dark';
                applyTheme(next);
                try {
                    localStorage.setItem(STORAGE_KEY, next);
                } catch (e) {}
            });
        });
    }

    function init() {
        applyTheme(getStoredTheme());
        bindThemeToggles();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
