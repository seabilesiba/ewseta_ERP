/** Scroll-reveal animations for procurement landing page */
(function () {
    'use strict';

    function revealIfInView(el) {
        var rect = el.getBoundingClientRect();
        var vh = window.innerHeight || document.documentElement.clientHeight;
        return rect.top < vh * 0.92 && rect.bottom > 0;
    }

    function initReveal() {
        var landing = document.querySelector('.ew-landing');
        if (!landing) {
            return;
        }
        var nodes = landing.querySelectorAll('.ew-landing-reveal');
        if (!nodes.length) {
            return;
        }
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            nodes.forEach(function (el) {
                el.classList.add('is-visible');
            });
            return;
        }
        nodes.forEach(function (el) {
            if (revealIfInView(el)) {
                el.classList.add('is-visible');
            }
        });
        landing.classList.add('ew-landing--reveal-active');
        if (typeof IntersectionObserver === 'undefined') {
            nodes.forEach(function (el) {
                el.classList.add('is-visible');
            });
            return;
        }
        var observer = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-visible');
                        observer.unobserve(entry.target);
                    }
                });
            },
            { root: null, rootMargin: '0px 0px -8% 0px', threshold: 0.12 }
        );
        nodes.forEach(function (el) {
            if (!el.classList.contains('is-visible')) {
                observer.observe(el);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReveal);
    } else {
        initReveal();
    }
})();
