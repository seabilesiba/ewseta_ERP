/** @odoo-module **/

/**
 * Odoo stores webclient menus in localStorage without the user id.
 * After switching accounts, the previous user's app list can flash or stick.
 * Scope menu cache keys per uid and drop the legacy shared keys.
 */
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";

const MENUS_KEY = "webclient_menus";
const VERSION_KEY = "webclient_menus_version";

function scopedKey(key) {
    return session.uid ? `${key}_uid_${session.uid}` : key;
}

const storage = browser.localStorage;
const nativeGet = storage.getItem.bind(storage);
const nativeSet = storage.setItem.bind(storage);

try {
    storage.removeItem(MENUS_KEY);
    storage.removeItem(VERSION_KEY);
} catch {
    // private browsing / blocked storage
}

storage.getItem = (key) => {
    if (key === MENUS_KEY || key === VERSION_KEY) {
        if (session.ew_procurement_only_apps) {
            return null;
        }
        return nativeGet(scopedKey(key));
    }
    return nativeGet(key);
};

storage.setItem = (key, value) => {
    if (key === MENUS_KEY || key === VERSION_KEY) {
        return nativeSet(scopedKey(key), value);
    }
    return nativeSet(key, value);
};
