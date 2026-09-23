/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const CROSSFADE_MS = 350;

/**
 * CHIETA-style hero: portrait thumbnails swap the centre circle image on hover.
 */
export class EwsetaHeroCarousel extends Interaction {
    static selector = ".s_ewseta_hero_carousel";

    dynamicContent = {
        ".ewseta-hero-portrait-thumb": {
            "t-on-mouseenter": this.onPortraitEnter,
            "t-on-focus": this.onPortraitEnter,
            "t-on-click": this.onPortraitClick,
        },
    };

    start() {
        this.circleImg = this.el.querySelector(
            ".ewseta-hero-rings-composition .ewseta-hero-circle-img-main"
        );
        this.smallImg = this.el.querySelector(".ewseta-hero-circle-img-small");
        this.featuredImg = this.el.querySelector(".ewseta-hero-featured-portrait-img");
        const welcome = this.el.querySelector(".ewseta-hero-welcome");
        if (welcome) {
            requestAnimationFrame(() => welcome.classList.add("is-loaded"));
        }
        return super.start();
    }

    get prefersReducedMotion() {
        return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    wait(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    normalizeSrc(src) {
        if (!src) {
            return "";
        }
        try {
            return new URL(src, window.location.origin).pathname;
        } catch {
            return src.split("?")[0];
        }
    }

    async crossfadeImg(img, url) {
        if (!img || !url) {
            return;
        }
        if (this.normalizeSrc(img.getAttribute("src")) === this.normalizeSrc(url)) {
            return;
        }
        if (this.prefersReducedMotion) {
            img.src = url;
            return;
        }
        img.classList.add("is-fading");
        await this.wait(CROSSFADE_MS);
        img.src = url;
        await this.wait(50);
        img.classList.remove("is-fading");
    }

    async setMainCircleImage(imageUrl) {
        if (!imageUrl || !this.circleImg) {
            return;
        }
        await this.crossfadeImg(this.circleImg, imageUrl);
    }

    async setSmallCircleImage(imageUrl) {
        if (!imageUrl || !this.smallImg) {
            return;
        }
        await this.crossfadeImg(this.smallImg, imageUrl);
    }

    async setFeaturedPortraitImage(imageUrl) {
        if (!imageUrl || !this.featuredImg) {
            return;
        }
        await this.crossfadeImg(this.featuredImg, imageUrl);
    }

    async onPortraitEnter(ev) {
        const thumb = ev.currentTarget;
        const imageUrl = thumb.dataset.heroImage;
        const smallUrl = thumb.dataset.heroSmallImage;
        if (!imageUrl || !this.circleImg) {
            return;
        }
        this.el.querySelectorAll(".ewseta-hero-portrait-thumb").forEach((el) => {
            el.classList.toggle("is-active", el === thumb);
        });
        await this.setMainCircleImage(imageUrl);
        if (smallUrl) {
            await this.setSmallCircleImage(smallUrl);
        }
    }

    onPortraitClick(ev) {
        ev.preventDefault();
        this.onPortraitEnter(ev);
    }
}

const SECTION_SELECTOR =
    ".s_ewseta_welcome, .s_ewseta_programmes, .s_ewseta_sectors, .s_ewseta_news, .s_ewseta_voice, .s_ewseta_subscribe";
const VISIBLE_CLASS = "ewseta-section-visible";
const SECTION_REVEAL_DELAY_MS = 2500;

function isInViewport(el, topRatio = 0.85, bottomRatio = 0.1) {
    const rect = el.getBoundingClientRect();
    const viewHeight = window.innerHeight || document.documentElement.clientHeight;
    return rect.top < viewHeight * topRatio && rect.bottom > viewHeight * bottomRatio;
}

export class EwsetaSectionAnimations extends Interaction {
    static selector = SECTION_SELECTOR;

    start() {
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            this.reveal(true);
            return super.start();
        }

        if (CSS.supports("animation-timeline", "view()")) {
            return super.start();
        }

        if (this.el.classList.contains(VISIBLE_CLASS)) {
            return super.start();
        }

        this.revealFallback = window.setTimeout(() => this.reveal(true), 8000);

        if (this.isInViewport()) {
            this.reveal(true);
            return super.start();
        }

        this.observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        this.reveal(true);
                        break;
                    }
                }
            },
            { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
        );
        this.observer.observe(this.el);

        return super.start();
    }

    destroy() {
        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }
        if (this.revealFallback) {
            window.clearTimeout(this.revealFallback);
            this.revealFallback = null;
        }
        if (this.revealTimer) {
            window.clearTimeout(this.revealTimer);
            this.revealTimer = null;
        }
        return super.destroy();
    }

    isInViewport() {
        const rect = this.el.getBoundingClientRect();
        const viewHeight = window.innerHeight || document.documentElement.clientHeight;
        return rect.top < viewHeight * 0.88 && rect.bottom > viewHeight * 0.08;
    }

    reveal(immediate = false) {
        if (this.el.classList.contains(VISIBLE_CLASS)) {
            return;
        }
        const applyVisible = () => {
            if (this.el.classList.contains(VISIBLE_CLASS)) {
                return;
            }
            this.el.classList.add(VISIBLE_CLASS);
            if (this.observer) {
                this.observer.disconnect();
                this.observer = null;
            }
            if (this.revealFallback) {
                window.clearTimeout(this.revealFallback);
                this.revealFallback = null;
            }
            if (this.revealTimer) {
                window.clearTimeout(this.revealTimer);
                this.revealTimer = null;
            }
        };

        if (immediate) {
            applyVisible();
            return;
        }

        if (this.revealTimer) {
            return;
        }

        this.revealTimer = window.setTimeout(applyVisible, SECTION_REVEAL_DELAY_MS);
    }
}

const KPI_STAGGER_MS = 550;
const KPI_INITIAL_DELAY_MS = 0;
const KPI_OBSERVER_ROOT_MARGIN = "0px 0px 25% 0px";

export class EwsetaKpiAnimations extends Interaction {
    static selector = ".s_ewseta_performance";

    start() {
        this.kpis = this.el.querySelectorAll(".ewseta-kpi");
        this.cta = this.el.querySelector(".ewseta-kpi-cta-wrap");

        this.fallbackTimer = window.setTimeout(() => this.revealAll(true), 3000);

        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            this.revealAll(true);
            return super.start();
        }

        if (isInViewport(this.el)) {
            this.revealAll();
            return super.start();
        }

        this.observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        this.revealAll();
                        break;
                    }
                }
            },
            { threshold: 0.05, rootMargin: KPI_OBSERVER_ROOT_MARGIN }
        );
        this.observer.observe(this.el);

        return super.start();
    }

    destroy() {
        if (this.fallbackTimer) {
            window.clearTimeout(this.fallbackTimer);
            this.fallbackTimer = null;
        }
        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }
        for (const timer of this.timers || []) {
            window.clearTimeout(timer);
        }
        this.timers = [];
        return super.destroy();
    }

    revealAll(immediate = false) {
        if (this.revealed) {
            return;
        }
        this.revealed = true;
        this.timers = [];

        if (this.fallbackTimer) {
            window.clearTimeout(this.fallbackTimer);
            this.fallbackTimer = null;
        }

        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }

        this.el.classList.add("ewseta-kpis-animated");

        const showKpi = (kpi) => kpi.classList.add("ewseta-kpi-is-visible");

        if (immediate) {
            this.kpis.forEach(showKpi);
            this.cta?.classList.add("ewseta-kpi-cta-visible");
            return;
        }

        this.kpis.forEach((kpi, index) => {
            const delay = KPI_INITIAL_DELAY_MS + index * KPI_STAGGER_MS;
            this.timers.push(window.setTimeout(() => showKpi(kpi), delay));
        });

        const ctaDelay = KPI_INITIAL_DELAY_MS + this.kpis.length * KPI_STAGGER_MS + 500;
        if (this.cta) {
            this.timers.push(
                window.setTimeout(() => this.cta.classList.add("ewseta-kpi-cta-visible"), ctaDelay)
            );
        }
    }
}

registry.category("public.interactions").add("ewseta_web.hero_carousel", EwsetaHeroCarousel);
registry.category("public.interactions").add("ewseta_web.section_animations", EwsetaSectionAnimations);
registry.category("public.interactions").add("ewseta_web.kpi_animations", EwsetaKpiAnimations);
