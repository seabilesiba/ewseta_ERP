/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const STORAGE_KEY = "ew-proc-theme";
const CLASS_DARK = "ew-proc-dark";

export function applyEwProcTheme(theme) {
    const html = document.documentElement;
    const isDark = theme === "dark";
    html.classList.toggle(CLASS_DARK, isDark);
    html.dataset.ewProcTheme = isDark ? "dark" : "light";
    html.style.colorScheme = isDark ? "dark" : "light";
    document.querySelectorAll(".ew-proc-theme-toggle").forEach((btn) => {
        const icon = btn.querySelector("i");
        if (icon) {
            icon.className = isDark ? "fa fa-sun-o" : "fa fa-moon-o";
        }
        const label = isDark ? "Switch to light mode" : "Switch to dark mode";
        btn.setAttribute("aria-label", label);
        btn.title = label;
    });
}

function getStoredTheme() {
    try {
        return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
    } catch {
        return "light";
    }
}

export class EwProcThemeToggle extends Interaction {
    static selector = ".ew-proc-theme-toggle";

    dynamicContent = {
        _root: { "t-on-click": this.onToggle },
    };

    start() {
        applyEwProcTheme(getStoredTheme());
        return super.start();
    }

    onToggle() {
        const next = document.documentElement.classList.contains(CLASS_DARK) ? "light" : "dark";
        applyEwProcTheme(next);
        try {
            localStorage.setItem(STORAGE_KEY, next);
        } catch {
            // Storage blocked — theme still applies for this session.
        }
    }
}

registry.category("public.interactions").add("ewseta_procurement.theme", EwProcThemeToggle);
