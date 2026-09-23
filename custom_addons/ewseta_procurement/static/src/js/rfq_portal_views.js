/** Cards / list toggle on /application/rfqs */
(function () {
    'use strict';

    const STORAGE_KEY = 'ewseta_procurement_portal_rfq_view';

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

    function init() {
        const root = document.querySelector('.ew-proc-portal');
        if (!root || !root.querySelector('.ew-proc-portal__view-toggle')) {
            return;
        }
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

        root.querySelector('.ew-proc-portal__view-toggle').addEventListener('click', (ev) => {
            const btn = ev.target.closest('.ew-proc-portal__view-btn');
            if (!btn) {
                return;
            }
            const next = btn.getAttribute('data-ew-portal-view');
            if (next === 'cards' || next === 'list') {
                setView(root, next);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
