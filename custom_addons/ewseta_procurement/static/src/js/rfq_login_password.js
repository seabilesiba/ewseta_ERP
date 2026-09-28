/** Password visibility on /web/login (minimal bundle — lazy JS blocks .o_show_password otherwise) */
(function () {
    'use strict';

    function bindToggle(btn) {
        if (btn.dataset.ewProcLoginPwBound) {
            return;
        }
        const group = btn.closest('.input-group');
        const input = group && group.querySelector("input[name='password']");
        if (!input) {
            return;
        }
        btn.dataset.ewProcLoginPwBound = '1';
        btn.addEventListener('click', function (ev) {
            ev.preventDefault();
            const reveal = input.type === 'password';
            input.type = reveal ? 'text' : 'password';
            const icon = btn.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-eye', !reveal);
                icon.classList.toggle('fa-eye-slash', reveal);
            }
        });
    }

    function init() {
        document.querySelectorAll('.ew-proc-login .o_show_password').forEach(bindToggle);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
