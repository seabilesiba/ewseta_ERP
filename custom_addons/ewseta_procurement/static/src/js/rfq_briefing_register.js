/**
 * Attendance-register popup on the public apply page (assets_frontend_minimal).
 * Bootstrap modal JS is not reliable here, so this is a lightweight open/close.
 * Also keeps apply-form and register-form contact fields in sync.
 */
(function () {
    'use strict';

    var MODAL_ID = 'ewProcBriefingRegisterModal';
    var BACKDROP_ID = 'ewProcBriefingRegisterBackdrop';
    var SYNC_FIELDS = ['company_name', 'contact_name', 'contact_email', 'contact_phone'];

    function modalEl() {
        return document.getElementById(MODAL_ID);
    }

    function applyForm() {
        return document.querySelector('form.ew-proc-portal__apply-form');
    }

    function registerForm() {
        var modal = modalEl();
        return modal ? modal.querySelector('form.ew-proc-portal__briefing-inline-form') : null;
    }

    function namedInput(form, name) {
        if (!form) {
            return null;
        }
        return form.querySelector('input[name="' + name + '"]');
    }

    function copyFields(fromForm, toForm) {
        if (!fromForm || !toForm || fromForm === toForm) {
            return;
        }
        SYNC_FIELDS.forEach(function (name) {
            var src = namedInput(fromForm, name);
            var dst = namedInput(toForm, name);
            if (!src || !dst) {
                return;
            }
            var val = (src.value || '').trim();
            if (val) {
                dst.value = src.value;
            }
        });
    }

    function copyApplyToRegister() {
        copyFields(applyForm(), registerForm());
    }

    function copyRegisterToApply() {
        copyFields(registerForm(), applyForm());
    }

    function openModal() {
        var modal = modalEl();
        if (!modal) {
            return;
        }
        if (modal.parentNode !== document.body) {
            document.body.appendChild(modal);
        }
        copyApplyToRegister();
        modal.classList.add('show');
        modal.style.display = 'block';
        modal.setAttribute('aria-modal', 'true');
        modal.removeAttribute('aria-hidden');
        document.body.classList.add('modal-open');
        var backdrop = document.getElementById(BACKDROP_ID);
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.id = BACKDROP_ID;
            backdrop.className = 'modal-backdrop fade show ew-proc-briefing-register-backdrop';
            document.body.appendChild(backdrop);
        }
        var first = modal.querySelector('input:not([type="hidden"])');
        if (first) {
            first.focus();
        }
    }

    function closeModal() {
        var modal = modalEl();
        if (!modal) {
            return;
        }
        copyRegisterToApply();
        modal.classList.remove('show');
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
        modal.removeAttribute('aria-modal');
        document.body.classList.remove('modal-open');
        var backdrop = document.getElementById(BACKDROP_ID);
        if (backdrop) {
            backdrop.remove();
        }
    }

    function bindRegisterModal() {
        if (!modalEl() || document.documentElement.dataset.ewProcBriefingRegisterBound) {
            return;
        }
        document.documentElement.dataset.ewProcBriefingRegisterBound = '1';
        var register = registerForm();
        if (register) {
            register.addEventListener('input', copyRegisterToApply);
            register.addEventListener('change', copyRegisterToApply);
            register.addEventListener('submit', copyRegisterToApply);
        }
        var apply = applyForm();
        if (apply) {
            apply.addEventListener('input', function () {
                if (modalEl() && modalEl().classList.contains('show')) {
                    copyApplyToRegister();
                }
            });
        }
        document.querySelectorAll('.ew-proc-briefing-register-open').forEach(function (btn) {
            btn.addEventListener('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                openModal();
            });
        });
        document.addEventListener('click', function (ev) {
            if (ev.target.closest('#' + MODAL_ID + ' [data-ew-proc-dismiss="modal"]')) {
                ev.preventDefault();
                closeModal();
                return;
            }
            if (ev.target.id === BACKDROP_ID || ev.target.id === MODAL_ID) {
                closeModal();
            }
        });
        document.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape' && modalEl() && modalEl().classList.contains('show')) {
                closeModal();
            }
        });
        var modal = modalEl();
        if (window.location.hash === '#briefing-register' || modal.getAttribute('data-ew-proc-autoload') === '1') {
            openModal();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindRegisterModal);
    } else {
        bindRegisterModal();
    }
})();
