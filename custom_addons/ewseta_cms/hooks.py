# -*- coding: utf-8 -*-

import re
from datetime import date


def post_init_hook(env):
    """Seed homepage CMS content and fix public website menu URLs."""
    website = env.ref('website.default_website', raise_if_not_found=False)
    if not website:
        return

    _migrate_hero_slides(env)
    _seed_content(env, website)
    _update_menu_urls(env, website)


def _migrate_hero_slides(env):
    """Convert legacy split slides to CHIETA-style banner + portrait layout."""
    Slide = env['ewseta.hero.slide'].sudo()
    banner_types = {'split', 'image', 'video', 'dual_video'}
    for slide in Slide.search([]):
        vals = {
            'overlay_opacity': 0.0,
            'video_url': False,
            'video_url_secondary': False,
        }
        if slide.slide_type in banner_types:
            vals['slide_type'] = 'banner'
        if not slide.image_url and slide.video_poster_url:
            vals['image_url'] = slide.video_poster_url
        elif not slide.image_url and slide.video_poster_secondary_url:
            vals['image_url'] = slide.video_poster_secondary_url
        slide.write(vals)

    website = env.ref('website.default_website', raise_if_not_found=False)
    if not website:
        return
    if not Slide.search_count([
        ('website_id', '=', website.id),
        ('slide_type', '=', 'portrait'),
    ]):
        Slide.create([
            {
                'name': 'Energy Learner',
                'sequence': 10,
                'slide_type': 'portrait',
                'image_url': '/ewseta_web/static/img/hero_energy.jpg',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Water Learner',
                'sequence': 20,
                'slide_type': 'portrait',
                'image_url': '/ewseta_web/static/img/hero_water.jpg',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Sustainability Learner',
                'sequence': 30,
                'slide_type': 'portrait',
                'image_url': '/ewseta_web/static/img/hero_sustainability.jpg',
                'is_published': True,
                'website_id': website.id,
            },
        ])

    Welcome = env['ewseta.home.welcome'].sudo()
    welcome_fields = Welcome._fields
    for welcome in Welcome.search([('website_id', '=', website.id)]):
        vals = {}
        if 'hero_circle_image_url' in welcome_fields and not welcome.hero_circle_image_url:
            vals['hero_circle_image_url'] = '/ewseta_web/static/img/hero_energy.jpg'
        if 'hero_overlap_image_url' in welcome_fields and not welcome.hero_overlap_image_url:
            vals['hero_overlap_image_url'] = '/ewseta_web/static/img/hero_water.jpg'
        if 'hero_featured_portrait_image_url' in welcome_fields and not welcome.hero_featured_portrait_image_url:
            vals['hero_featured_portrait_image_url'] = '/ewseta_web/static/img/hero_sustainability.jpg'
        if welcome.cta_label == 'Discover Our Mandate':
            vals['cta_label'] = 'Read More...'
        if vals:
            welcome.write(vals)


def _seed_performance_content(env, website):
    Settings = env['ewseta.home.settings'].sudo()
    for settings in Settings.search([('website_id', '=', website.id)]):
        vals = {}
        if not settings.performance_eyebrow:
            vals['performance_eyebrow'] = 'Our Impact'
        if not settings.performance_title:
            vals['performance_title'] = 'Performance Overview'
        if not settings.performance_lead:
            vals['performance_lead'] = (
                'Key outcomes from EWSETA\'s skills development programmes '
                'across the energy and water sectors.'
            )
        if not settings.performance_cta_label:
            vals['performance_cta_label'] = 'View Annual Performance Plan'
        if vals:
            settings.write(vals)

    Performance = env['ewseta.performance.metric'].sudo()
    if Performance.search_count([('website_id', '=', website.id)]):
        return
    Performance.create([
        {
            'name': 'Learners Enrolled',
            'sequence': 10,
            'value': '12,450',
            'label': 'Learners Enrolled',
            'description': 'Across accredited programmes nationwide',
            'progress': 82.0,
            'progress_label': '82% of annual target',
            'color': 'orange',
            'icon_class': 'fa-users',
            'is_published': True,
            'website_id': website.id,
        },
        {
            'name': 'Employers Supported',
            'sequence': 20,
            'value': '850+',
            'label': 'Employers Supported',
            'description': 'Workplace skills plans and grant beneficiaries',
            'progress': 76.0,
            'progress_label': '76% of annual target',
            'color': 'blue',
            'icon_class': 'fa-building',
            'is_published': True,
            'website_id': website.id,
        },
        {
            'name': 'Grants Disbursed',
            'sequence': 30,
            'value': 'R245M',
            'label': 'Grants Disbursed',
            'description': 'Mandatory and discretionary skills funding',
            'progress': 68.0,
            'progress_label': '68% of annual target',
            'color': 'green',
            'icon_class': 'fa-money',
            'is_published': True,
            'website_id': website.id,
        },
        {
            'name': 'Qualifications Registered',
            'sequence': 40,
            'value': '156',
            'label': 'Qualifications Registered',
            'description': 'Occupational and trade qualifications on scope',
            'progress': 0.0,
            'color': 'dark',
            'icon_class': 'fa-certificate',
            'is_published': True,
            'website_id': website.id,
        },
    ])


def _seed_content(env, website):
    Slide = env['ewseta.hero.slide'].sudo()
    if not Slide.search_count([('website_id', '=', website.id)]):
        Slide.create([
            {
                'name': 'Skills Development Banner',
                'sequence': 10,
                'slide_type': 'banner',
                'image_url': '/ewseta_web/static/img/hero_energy.jpg',
                'cta_primary_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Water Sector Banner',
                'sequence': 20,
                'slide_type': 'banner',
                'image_url': '/ewseta_web/static/img/hero_water.jpg',
                'cta_primary_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Hydrogen Programme Banner',
                'sequence': 30,
                'slide_type': 'banner',
                'image_url': '/ewseta_web/static/img/hero_sustainability.jpg',
                'cta_primary_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
        ])

    Welcome = env['ewseta.home.welcome'].sudo()
    if not Welcome.search_count([('website_id', '=', website.id)]):
        Welcome.create({
            'name': 'Welcome Section',
            'eyebrow': 'Who We Are',
            'title': 'Welcome to EWSETA',
            'section_title': 'About Us',
            'body': '<p>The Energy &amp; Water Sector Education and Training Authority (EWSETA) is a statutory body established under the Skills Development Act. Our purpose is to facilitate skills development in the energy and water sectors. We are committed to ensuring that skills needs are identified and addressed through several initiatives, providing skills development to the industry and our stakeholders.</p>',
            'cta_label': 'Read More...',
            'cta_url': '#',
            'hero_circle_image_url': '/ewseta_web/static/img/hero_energy.jpg',
            'hero_overlap_image_url': '/ewseta_web/static/img/hero_water.jpg',
            'hero_featured_portrait_image_url': '/ewseta_web/static/img/hero_sustainability.jpg',
            'is_published': True,
            'website_id': website.id,
            'stat_ids': [
                (0, 0, {'sequence': 10, 'value': '2', 'label': 'Core Sectors', 'description': 'Energy & Water', 'color': 'orange', 'display_mode': 'number'}),
                (0, 0, {'sequence': 20, 'value': '4+', 'label': 'Grant Programmes', 'description': 'Skills funding', 'color': 'blue', 'display_mode': 'number'}),
                (0, 0, {'sequence': 30, 'value': '1000s', 'label': 'Learners Supported', 'description': 'Nationwide', 'color': 'green', 'display_mode': 'number'}),
                (0, 0, {'sequence': 40, 'value': '', 'label': 'Head Office', 'description': 'Parktown, Johannesburg', 'color': 'dark', 'display_mode': 'icon', 'icon_class': 'fa-map-marker'}),
            ],
        })

    Topbar = env['ewseta.website.topbar'].sudo()
    Topbar.seed_default_content()

    Navbar = env['ewseta.navbar.settings'].sudo()
    Navbar.seed_default_content()

    Theme = env['ewseta.theme.settings'].sudo()
    Theme.seed_default_content()
    _migrate_theme_settings_defaults(env)


def _migrate_theme_settings_defaults(env):
    """Map legacy default_theme selection values to default_preset_theme."""
    cr = env.cr
    cr.execute("""
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'ewseta_theme_settings'
           AND column_name = 'default_theme'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        SELECT id, default_theme
          FROM ewseta_theme_settings
         WHERE default_theme IS NOT NULL
    """)
    ThemeSettings = env['ewseta.theme.settings'].sudo()
    for row in cr.fetchall():
        record = ThemeSettings.browse(row[0])
        if record.exists() and row[1]:
            record.write({
                'default_theme_mode': 'preset',
                'default_preset_theme': row[1],
            })

    Settings = env['ewseta.home.settings'].sudo()
    if not Settings.search_count([('website_id', '=', website.id)]):
        Settings.create({
            'name': 'Homepage Settings',
            'website_id': website.id,
            'programme_eyebrow': 'What We Offer',
            'programme_title': 'Skills Development Programmes',
            'programme_lead': 'Funding and support for employers, training providers, and learners in the energy and water sectors.',
            'sector_eyebrow': 'Our Focus Areas',
            'sector_title': "Powering South Africa's Future",
            'sector_lead': 'Skills development at the heart of energy, water, and sustainability challenges.',
            'news_eyebrow': 'Stay Informed',
            'news_title': 'Latest News',
            'performance_eyebrow': 'Our Impact',
            'performance_title': 'Performance Overview',
            'performance_lead': 'Key outcomes from EWSETA\'s skills development programmes across the energy and water sectors.',
            'performance_cta_label': 'View Annual Performance Plan',
            'performance_cta_url': '#',
        })

    _seed_performance_content(env, website)

    Programme = env['ewseta.programme.card'].sudo()
    if not Programme.search_count([('website_id', '=', website.id)]):
        Programme.create([
            {
                'name': 'Skills Planning',
                'sequence': 10,
                'icon': 'fa-line-chart',
                'icon_color': 'orange',
                'title': 'Skills Planning',
                'description': '<p>Coordinated skills development informed by quality research to address South Africa\'s triple challenge of poverty, inequality and unemployment.</p>',
                'link_label': 'Learn more',
                'link_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Mandatory Grants',
                'sequence': 20,
                'icon': 'fa-money',
                'icon_color': 'blue',
                'title': 'Mandatory Grants',
                'description': '<p>Eligible employers who contribute the skills development levy and receive WSP/ATR approval can access Mandatory Grant funding.</p>',
                'link_label': 'Learn more',
                'link_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Discretionary Grants',
                'sequence': 30,
                'icon': 'fa-handshake-o',
                'icon_color': 'green',
                'title': 'Discretionary Grants',
                'description': '<p>Board-approved funding subject to stringent assessment of applications received during approved discretionary grant windows.</p>',
                'link_label': 'Learn more',
                'link_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Learning Programmes',
                'sequence': 40,
                'icon': 'fa-graduation-cap',
                'icon_color': 'orange',
                'title': 'Learning Programmes',
                'description': '<p>Programmes funded in accordance with skills development priorities defined in the annually reviewed EWSETA Sector Skills Plan.</p>',
                'link_label': 'Learn more',
                'link_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
        ])

    Sector = env['ewseta.sector.card'].sudo()
    if not Sector.search_count([('website_id', '=', website.id)]):
        Sector.create([
            {
                'name': 'Energy',
                'sequence': 10,
                'title': 'Energy',
                'description': 'Effective skills development as a key growth driver amid infrastructure challenges and growing demand across the energy sector.',
                'image_url': '/ewseta_web/static/img/sector_energy.jpg',
                'icon': 'fa-bolt',
                'css_class': 'ewseta-sector-energy',
                'link_label': 'Explore Energy',
                'link_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Water',
                'sequence': 20,
                'title': 'Water',
                'description': 'Critical water skills for South Africa\'s future supply — addressing ageing infrastructure, technical shortages, and rising demand.',
                'image_url': '/ewseta_web/static/img/sector_water.jpg',
                'icon': 'fa-tint',
                'css_class': 'ewseta-sector-water',
                'link_label': 'Explore Water',
                'link_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Sustainability',
                'sequence': 30,
                'title': 'Sustainability',
                'description': 'Remarkable growth in renewable energy presents numerous opportunities for skills development and green economy careers.',
                'image_url': '/ewseta_web/static/img/sector_sustainability.jpg',
                'icon': 'fa-leaf',
                'css_class': 'ewseta-sector-sustainability',
                'link_label': 'Explore Sustainability',
                'link_url': '#',
                'is_published': True,
                'website_id': website.id,
            },
        ])

    News = env['ewseta.news.article'].sudo()
    if not News.search_count([('website_id', '=', website.id)]):
        News.create([
            {
                'name': 'Mrs Kedibone Moroane-Nkhobo Appointed as EWSETA CEO',
                'subtitle': 'The Board of EWSETA is pleased to welcome Mrs Kedibone Moroane-Nkhobo as Chief Executive Officer, leading the organisation into a new chapter of skills development excellence.',
                'body': '<p>The Board of EWSETA is pleased to welcome Mrs Kedibone Moroane-Nkhobo as Chief Executive Officer.</p>',
                'featured_image_url': '/ewseta_web/static/img/hero_energy.jpg',
                'publish_date': date(2026, 7, 20),
                'is_featured': True,
                'slug': 'kedibone-moroane-nkhobo-appointed-ewseta-ceo',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Transactional Arrangement for Pre-2009 Qualifications',
                'featured_image_url': '/ewseta_web/static/img/hero_water.jpg',
                'publish_date': date(2026, 7, 2),
                'slug': 'transactional-arrangement-pre-2009-qualifications',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'QCTO National Roadshows 2026',
                'featured_image_url': '/ewseta_web/static/img/sector_energy.jpg',
                'publish_date': date(2026, 7, 2),
                'slug': 'qcto-national-roadshows-2026',
                'is_published': True,
                'website_id': website.id,
            },
            {
                'name': 'Backlog in QCTO Artisan Certification Applications',
                'featured_image_url': '/ewseta_web/static/img/sector_water.jpg',
                'publish_date': date(2026, 3, 18),
                'slug': 'backlog-qcto-artisan-certification-applications',
                'is_published': True,
                'website_id': website.id,
            },
        ])


def _update_menu_urls(env, website):
    Menu = env['website.menu'].sudo()
    url_map = {
        'Latest News': '/news',
        'Job Opportunities': '/jobs',
        'Power Up': '/power-up',
    }
    for name, url in url_map.items():
        menus = Menu.search([
            ('website_id', '=', website.id),
            ('name', '=', name),
        ])
        menus.write({'url': url})

    supply_menu = Menu.search([
        ('website_id', '=', website.id),
        ('name', '=', 'Supply Chain'),
    ], limit=1)
    if supply_menu and supply_menu.mega_menu_content:
        content = supply_menu.mega_menu_content
        for label, url in (
            ('EWSETA RFPs', '/tenders'),
            ('EWSETA RFQs 2026/27', '/rfqs'),
        ):
            content = re.sub(
                rf'(<a\s+href=["\'])#(["\'][^>]*>)\s*{re.escape(label)}',
                rf'\1{url}\2{label}',
                content,
            )
        supply_menu.write({'mega_menu_content': content})

    learner_menu = Menu.search([
        ('website_id', '=', website.id),
        ('name', '=', 'Learner Resources'),
    ], limit=1)
    if learner_menu:
        job_child = Menu.search([
            ('parent_id', '=', learner_menu.id),
            ('name', '=', 'Job Opportunities'),
        ], limit=1)
        if job_child:
            job_child.write({'url': '/jobs'})
