# -*- coding: utf-8 -*-

# Odoo manifest file for the EWSETA Website module.
{
    # The name of the module as it will appear in Odoo apps list.
    'name': 'EWSETA Website',

    # The version of the module, following Odoo best practices.
    'version': '19.0.1.9.48',

    # Category under which module will be grouped in Odoo.
    'category': 'Website/Website',

    # Short summary shown in the module list.
    'summary': 'EWSETA public website theme and landing page',

    # Long description for module details.
    'description': """
Energy & Water SETA public website built on Odoo Website.
Includes branded header, footer, navigation, and homepage snippets.
    """,

    # Dependencies: This module requires Odoo's 'website' and 'html_builder' modules.
    'depends': ['website', 'html_builder', 'portal'],

    # List of data files loaded at module install/update/uninstall.
    'data': [
        # Main base template (likely for initial header/footer structure)
        'data/generate_primary_template.xml',
        # Generic website template(s)
        'views/website_templates.xml',
        'views/ewseta_debrand_templates.xml',
        'views/ewseta_login_templates.xml',
        'views/ewseta_contact_templates.xml',
        # Custom homepage sections/snippets
        'views/snippets/s_ewseta_hero_carousel.xml',
        'views/snippets/s_ewseta_welcome.xml',
        'views/snippets/s_ewseta_performance.xml',
        'views/snippets/s_ewseta_programmes.xml',
        'views/snippets/s_ewseta_sectors.xml',
        'views/snippets/s_ewseta_news.xml',
        'views/snippets/s_ewseta_voice.xml',
        'views/snippets/s_ewseta_subscribe.xml',
        'views/snippets/snippets.xml',
        # Homepage composition/inheritance
        'data/homepage_content.xml',
    ],

    # Frontend and website builder asset bundles.
    'assets': {
        # Assets that will be included in standard website frontend
        'web.assets_frontend': [
            # Main SCSS file with all customized styles for EWSETA
            ('after', 'website/static/src/scss/website.scss', 'ewseta_web/static/src/scss/ewseta_web.scss'),
            ('after', 'ewseta_web/static/src/scss/ewseta_web.scss', 'ewseta_web/static/src/scss/ewseta_login.scss'),
            ('after', 'ewseta_web/static/src/scss/ewseta_web.scss', 'ewseta_web/static/src/scss/ewseta_dark_mode.scss'),
            # JS for carousel functionality or effects
            'ewseta_web/static/src/js/ewseta_hero_carousel.js',
            'ewseta_web/static/src/js/ewseta_dark_mode.js',
        ],
        # Assets for the website builder (Odoo Studio, page editors)
        'website.website_builder_assets': [
            # Custom plugin for snippet options in the builder
            'ewseta_web/static/src/builder/ewseta_hero_option_plugin.js',
        ],
        # Asset bundle for overriding SCSS variable definitions for themes
        'web._assets_primary_variables': [
            'ewseta_web/static/src/scss/primary_variables.scss',
        ],
        # Helper styles that override Bootstrap defaults (prepended for priority)
        'web._assets_frontend_helpers': [
            ('prepend', 'ewseta_web/static/src/scss/bootstrap_overridden.scss'),
        ],
    },

    # Collection of homepage snippets for rapid composition via the Odoo configurator
    'configurator_snippets': {
        # Defines the sequence of snippets on the homepage when generated
        'homepage': [
            's_ewseta_hero_carousel',
            's_ewseta_welcome',
            's_ewseta_performance',
            's_ewseta_programmes',
            's_ewseta_sectors',
            's_ewseta_news',
            's_ewseta_voice',
            's_ewseta_subscribe',
        ],
    },

    # Templates for creating new pages using collections of snippets
    'new_page_templates': {
        'landing': {
            # Defines the layout/sections of the default landing page
            '0': [
                's_ewseta_hero_carousel',
                's_ewseta_welcome',
                's_ewseta_performance',
                's_ewseta_programmes',
                's_ewseta_sectors',
                's_ewseta_news',
                's_ewseta_voice',
                's_ewseta_subscribe',
            ],
        },
    },

    # Name of a function to run after module installation (for post-process, setup, etc).
    'post_init_hook': 'post_init_hook',

    # Basic Odoo manifest flags
    'installable': True,   # Can be installed via Apps menu
    'application': False,  # Not a top-level application (is a theme/website extension)
    'license': 'LGPL-3',  # License type
    'author': 'EWSETA',   # Author of the module
}
