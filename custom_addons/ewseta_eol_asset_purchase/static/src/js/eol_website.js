# -*- coding: utf-8 -*-

/** Keep the main website header visible and sticky on EOL pages (Odoo scroll JS fights CSS alone). */
function ewEolInitStickyNav() {
    const page = document.querySelector('.ew-eol-page');
    if (!page) {
        return;
    }
    const wrap = document.getElementById('wrapwrap');
    if (wrap) {
        wrap.classList.add('ew-eol-public-wrap');
    }
    const header = wrap && wrap.querySelector('header#top');
    const main = wrap && wrap.querySelector('main');
    if (!header) {
        return;
    }

    function neutralizeHeaderScrollEffects() {
        header.style.removeProperty('transform');
        if (main) {
            main.style.removeProperty('padding-top');
        }
        const hideOnScroll = header.querySelector('.o_header_hide_on_scroll');
        if (hideOnScroll) {
            hideOnScroll.classList.remove('hidden');
        }
    }

    neutralizeHeaderScrollEffects();
    const observer = new MutationObserver(neutralizeHeaderScrollEffects);
    observer.observe(header, { attributes: true, attributeFilter: ['style', 'class'] });
    if (main) {
        observer.observe(main, { attributes: true, attributeFilter: ['style'] });
    }
    document.addEventListener('scroll', neutralizeHeaderScrollEffects, { passive: true });
}

document.addEventListener('DOMContentLoaded', function () {
    ewEolInitStickyNav();

    const form = document.querySelector('.ew-eol-request-form');
    if (!form) {
        return;
    }
    const serialBlock = form.querySelector('.ew-eol-serial-block');
    const requestTypeInputs = form.querySelectorAll('input[name="request_type"]');

    function syncSerialVisibility() {
        const selected = form.querySelector('input[name="request_type"]:checked');
        const assigned = selected && selected.value === 'assigned';
        if (serialBlock) {
            serialBlock.classList.toggle('d-none', !assigned);
        }
        const serialInput = form.querySelector('input[name="serial_or_tag"]');
        if (serialInput) {
            serialInput.required = assigned;
        }
    }

    requestTypeInputs.forEach(function (input) {
        input.addEventListener('change', syncSerialVisibility);
    });
    syncSerialVisibility();
});
