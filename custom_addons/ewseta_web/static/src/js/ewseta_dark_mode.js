/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const STORAGE_KEY = "ewseta-theme";
const ALL_THEMES = ["light", "dark", "blue", "green", "orange"];

const BUILTIN_CLASS_MAP = {
    dark: "ewseta-dark-mode",
    blue: "ewseta-blue-mode",
    green: "ewseta-green-mode",
    orange: "ewseta-orange-mode",
};

const BUILTIN_THEME_CLASSES = [
    "ewseta-dark-mode",
    "ewseta-blue-mode",
    "ewseta-green-mode",
    "ewseta-orange-mode",
    "ewseta-custom-mode",
];

const CSS_VAR_KEYS = [
    "--ewseta-dm-bg",
    "--ewseta-dm-bg-elevated",
    "--ewseta-dm-bg-subtle",
    "--ewseta-dm-bg-deep",
    "--ewseta-dm-text",
    "--ewseta-dm-text-muted",
    "--ewseta-dm-border",
    "--ewseta-dm-shadow",
    "--ewseta-voice-gradient-start",
    "--ewseta-body-gradient",
];

const DEFAULT_THEME_META = {
    light: { type: "builtin", label: "White (Light)", toggleIcon: "sun-o" },
    dark: { type: "builtin", label: "Dark", toggleIcon: "moon-o" },
    blue: { type: "builtin", label: "Blue", toggleIcon: "tint" },
    green: { type: "builtin", label: "Green", toggleIcon: "leaf" },
    orange: { type: "builtin", label: "Orange", toggleIcon: "fire" },
};

export function getEwsetaThemeConfig() {
    const config = window.ewsetaThemeConfig;
    if (config && Array.isArray(config.themes) && config.themes.length) {
        return config;
    }
    return {
        toggleEnabled: true,
        defaultTheme: "light",
        rememberUserChoice: true,
        themes: ALL_THEMES,
        themeMeta: DEFAULT_THEME_META,
    };
}

export function getEwsetaThemes() {
    return getEwsetaThemeConfig().themes;
}

export function getThemeMeta(themeKey) {
    const config = getEwsetaThemeConfig();
    return (config.themeMeta && config.themeMeta[themeKey]) || DEFAULT_THEME_META[themeKey] || {
        type: "custom",
        toggleIcon: "paint-brush",
        label: themeKey,
    };
}

function clearThemeState(html) {
    html.classList.remove(...BUILTIN_THEME_CLASSES);
    CSS_VAR_KEYS.forEach((key) => html.style.removeProperty(key));
    html.style.removeProperty("color-scheme");
}

export function applyEwsetaTheme(theme) {
    const html = document.documentElement;
    const config = getEwsetaThemeConfig();
    const themes = config.themes;
    const resolvedTheme = themes.includes(theme) ? theme : config.defaultTheme || "light";
    const meta = getThemeMeta(resolvedTheme);

    clearThemeState(html);

    if (resolvedTheme === "light") {
        // Default light theme uses the base stylesheet.
    } else if (meta.type === "custom" && meta.cssVars) {
        html.classList.add("ewseta-custom-mode");
        html.style.colorScheme = "dark";
        Object.entries(meta.cssVars).forEach(([key, value]) => {
            html.style.setProperty(key, value);
        });
    } else if (BUILTIN_CLASS_MAP[resolvedTheme]) {
        html.classList.add(BUILTIN_CLASS_MAP[resolvedTheme]);
    }

    html.dataset.ewsetaTheme = resolvedTheme;
    updateToggleIcon(resolvedTheme);
    return resolvedTheme;
}

export function updateToggleIcon(currentTheme) {
    const button = document.querySelector(".ewseta-theme-toggle");
    if (!button) {
        return;
    }

    const themes = getEwsetaThemes();
    const index = themes.indexOf(currentTheme);
    const nextTheme = themes[index >= 0 ? (index + 1) % themes.length : 0];
    const nextMeta = getThemeMeta(nextTheme);

    button.querySelectorAll(".ewseta-theme-icon").forEach((icon) => {
        icon.style.display = "none";
    });

    let dynamicIcon = button.querySelector(".ewseta-theme-icon-dynamic");
    if (!dynamicIcon) {
        dynamicIcon = document.createElement("i");
        dynamicIcon.className = "fa ewseta-theme-icon ewseta-theme-icon-dynamic";
        dynamicIcon.setAttribute("aria-hidden", "true");
        button.appendChild(dynamicIcon);
    }

    dynamicIcon.className = `fa fa-${nextMeta.toggleIcon || "paint-brush"} ewseta-theme-icon ewseta-theme-icon-dynamic`;
    dynamicIcon.style.display = "inline";
    button.title = `Next theme: ${nextMeta.label || nextTheme}`;
    button.setAttribute("aria-label", button.title);
}

export function getStoredEwsetaTheme() {
    try {
        return localStorage.getItem(STORAGE_KEY);
    } catch {
        return null;
    }
}

export function resolveEwsetaTheme() {
    const config = getEwsetaThemeConfig();
    const themes = config.themes;

    if (config.rememberUserChoice) {
        const stored = getStoredEwsetaTheme();
        if (stored && themes.includes(stored)) {
            return stored;
        }
    }

    if (themes.includes(config.defaultTheme)) {
        return config.defaultTheme;
    }
    return themes[0] || "light";
}

export class EwsetaDarkMode extends Interaction {
    static selector = ".ewseta-theme-toggle";

    dynamicContent = {
        _root: { "t-on-click": this.onToggle },
    };

    start() {
        applyEwsetaTheme(resolveEwsetaTheme());
        return super.start();
    }

    onToggle() {
        const themes = getEwsetaThemes();
        const current = document.documentElement.dataset.ewsetaTheme || resolveEwsetaTheme();
        const index = themes.indexOf(current);
        const nextIndex = index >= 0 ? (index + 1) % themes.length : 0;
        const nextTheme = applyEwsetaTheme(themes[nextIndex]);
        if (getEwsetaThemeConfig().rememberUserChoice) {
            try {
                localStorage.setItem(STORAGE_KEY, nextTheme);
            } catch {
                // Private browsing or blocked storage — theme still toggles for this page.
            }
        }
    }
}

registry.category("public.interactions").add("ewseta_web.dark_mode", EwsetaDarkMode);
