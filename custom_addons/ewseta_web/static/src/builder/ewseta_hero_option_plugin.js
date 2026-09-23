/** @odoo-module **/

import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { withSequence } from "@html_editor/utils/resource";
import { WEBSITE_BACKGROUND_OPTIONS } from "@website/builder/option_sequence";
import { BaseWebsiteBackgroundOption } from "@website/builder/plugins/options/background_option";

/**
 * Enables image and background-video options on each EWSETA hero slide.
 */
export class EwsetaHeroSlideBackgroundOption extends BaseWebsiteBackgroundOption {
    static selector = ".s_ewseta_hero_carousel .carousel-item";
    static defaultProps = {
        withColors: true,
        withImages: true,
        withVideos: true,
        withShapes: false,
        withColorCombinations: true,
    };
}

class EwsetaHeroOptionPlugin extends Plugin {
    static id = "ewsetaHeroOption";

    resources = {
        builder_options: [
            withSequence(WEBSITE_BACKGROUND_OPTIONS, EwsetaHeroSlideBackgroundOption),
        ],
    };
}

registry.category("website-plugins").add(EwsetaHeroOptionPlugin.id, EwsetaHeroOptionPlugin);
