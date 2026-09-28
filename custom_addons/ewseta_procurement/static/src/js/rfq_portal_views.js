/** Open/Closed tabs + cards/list toggle on /application/rfqs (minimal bundle — no lazy-click wait) */
(function () {
    'use strict';

    const STORAGE_KEY = 'ewseta_procurement_portal_rfq_view';
    let clickBound = false;

    function activateTab(link) {
        const tablist = link.closest('.ew-proc-portal__tabs');
        if (!tablist) {
            return;
        }
        const targetSel = link.getAttribute('href');
        if (!targetSel || targetSel.charAt(0) !== '#') {
            return;
        }
        const pane = document.querySelector(targetSel);
        if (!pane) {
            return;
        }
        tablist.querySelectorAll('.nav-link').forEach((l) => l.classList.remove('active'));
        link.classList.add('active');
        const content = pane.closest('.tab-content');
        if (content) {
            content.querySelectorAll('.tab-pane').forEach((p) => {
                p.classList.remove('show', 'active');
            });
        }
        pane.classList.add('show', 'active');
    }

    function setView(root, mode) {
        const cards = mode === 'cards';
        root.querySelectorAll('.ew-proc-portal__view-pane--cards').forEach((el) => {
            el.classList.toggle('d-none', !cards);
        });
        root.querySelectorAll('.ew-proc-portal__view-pane--list').forEach((el) => {
            el.classList.toggle('d-none', cards);
        });
        root.querySelectorAll('.ew-proc-portal__view-btn').forEach((btn) => {
            const active = btn.getAttribute('data-ew-portal-view') === mode;
            btn.classList.toggle('active', active);
            btn.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        try {
            sessionStorage.setItem(STORAGE_KEY, mode);
        } catch (_e) {
            /* ignore */
        }
        document.dispatchEvent(new CustomEvent('ew-portal-view-changed', { detail: { mode } }));
    }

    function bindPortalClicks(root) {
        if (clickBound) {
            return;
        }
        clickBound = true;
        root.addEventListener('click', (ev) => {
            const tabLink = ev.target.closest('.ew-proc-portal__tabs .nav-link');
            if (tabLink) {
                ev.preventDefault();
                activateTab(tabLink);
                return;
            }
            const btn = ev.target.closest('.ew-proc-portal__view-btn');
            if (!btn || !root.contains(btn)) {
                return;
            }
            const next = btn.getAttribute('data-ew-portal-view');
            if (next === 'cards' || next === 'list') {
                setView(root, next);
            }
        });
    }

    function init() {
        const root = document.querySelector('.ew-proc-portal');
        if (!root) {
            return;
        }
        if (root.querySelector('.ew-proc-portal__view-toggle')) {
            let mode = 'cards';
            try {
                const saved = sessionStorage.getItem(STORAGE_KEY);
                if (saved === 'list' || saved === 'cards') {
                    mode = saved;
                }
            } catch (_e) {
                /* ignore */
            }
            setView(root, mode);
        }
        bindPortalClicks(root);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    window.addEventListener('load', init);
})();
