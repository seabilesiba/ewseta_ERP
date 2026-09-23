/** Scroll-reveal animations for procurement landing page */
(function () {
    'use strict';

    function initReveal() {
        const nodes = document.querySelectorAll('.ew-landing .ew-landing-reveal');
        if (!nodes.length) {
            return;
        }
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            nodes.forEach((el) => el.classList.add('is-visible'));
            return;
        }
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-visible');
                        observer.unobserve(entry.target);
                    }
                });
            },
            { root: null, rootMargin: '0px 0px -8% 0px', threshold: 0.12 }
        );
        nodes.forEach((el) => observer.observe(el));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReveal);
    } else {
        initReveal();
    }
})();
