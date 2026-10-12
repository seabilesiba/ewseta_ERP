/**
 * PDF preview on public submission track page (assets_frontend_minimal — Bootstrap loads later).
 */
(function () {
    'use strict';

    var MODAL_ID = 'ewProcDocPreviewModal';
    var FRAME_ID = 'ewProcDocPreviewFrame';
    var TITLE_ID = 'ewProcDocPreviewTitle';
    var BACKDROP_ID = 'ewProcDocPreviewBackdrop';

    function modalEl() {
        return document.getElementById(MODAL_ID);
    }

    function openPreview(url, title) {
        if (!url) {
            return;
        }
        var modal = modalEl();
        var frame = document.getElementById(FRAME_ID);
        var titleEl = document.getElementById(TITLE_ID);
        if (!modal || !frame) {
            window.open(url, '_blank', 'noopener,noreferrer');
            return;
        }
        if (titleEl) {
            titleEl.textContent = title || 'Document preview';
        }
        frame.src = url;

        modal.classList.add('show');
        modal.style.display = 'block';
        modal.setAttribute('aria-modal', 'true');
        modal.removeAttribute('aria-hidden');

        document.body.classList.add('modal-open');
        var backdrop = document.getElementById(BACKDROP_ID);
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.id = BACKDROP_ID;
            backdrop.className = 'modal-backdrop fade show ew-proc-doc-modal-backdrop';
            document.body.appendChild(backdrop);
        }
    }

    function closePreview() {
        var modal = modalEl();
        var frame = document.getElementById(FRAME_ID);
        if (!modal) {
            return;
        }
        modal.classList.remove('show');
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
        modal.removeAttribute('aria-modal');
        document.body.classList.remove('modal-open');
        var backdrop = document.getElementById(BACKDROP_ID);
        if (backdrop) {
            backdrop.remove();
        }
        if (frame) {
            frame.src = 'about:blank';
        }
    }

    function onDocumentClick(ev) {
        var previewBtn = ev.target.closest('.ew-proc-doc-preview');
        if (previewBtn) {
            ev.preventDefault();
            openPreview(
                previewBtn.getAttribute('data-file-url'),
                previewBtn.getAttribute('data-file-title')
            );
            return;
        }
        if (ev.target.closest('.ew-proc-doc-modal-close, [data-ew-proc-dismiss="modal"]')) {
            ev.preventDefault();
            closePreview();
            return;
        }
        if (ev.target.id === BACKDROP_ID) {
            closePreview();
        }
    }

    function bindDocPreview() {
        if (!document.getElementById(FRAME_ID)) {
            return;
        }
        document.addEventListener('click', onDocumentClick);
        document.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape' && modalEl() && modalEl().classList.contains('show')) {
                closePreview();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindDocPreview);
    } else {
        bindDocPreview();
    }
})();
