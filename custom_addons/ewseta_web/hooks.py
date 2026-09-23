# Part of EWSETA Web module.

REMOVED_TOP_LEVEL_MENUS = (
    'Power Up',
    'QA & Compliance',
    'News & Events',
    'Stakeholder Portal',
    'Learner Resources',
)

NAV_MENU_SEQUENCE = {
    'Home': 10,
    'About': 20,
    'Skills Development': 30,
    'Supply Chain': 40,
    'Contact Us': 50,
}


def _nav_card(href, icon, color, title, desc):
    return (
        '      <div class="col-lg-3 col-md-6">\n'
        f'        <a href="{href}" class="ewseta-nav-card text-decoration-none">\n'
        f'          <span class="ewseta-nav-card-icon ewseta-icon-{color}">\n'
        f'            <i class="fa {icon}"/>\n'
        '          </span>\n'
        '          <span class="ewseta-nav-card-body">\n'
        f'            <strong class="ewseta-nav-card-title">{title}</strong>\n'
        f'            <span class="ewseta-nav-card-desc">{desc}</span>\n'
        '          </span>\n'
        '        </a>\n'
        '      </div>'
    )


def _mega_menu_cards(sections):
    parts = [
        '<section class="s_mega_menu_odoo_menu ewseta-mega-menu-cards o_colored_level pt16 pb16">',
        '  <div class="container">',
    ]
    for index, (section_title, cards) in enumerate(sections):
        if index:
            parts.append('    <div class="ewseta-mega-section-divider"></div>')
        parts.append(f'    <h6 class="ewseta-mega-section-title">{section_title}</h6>')
        parts.append('    <div class="row g-3">')
        for card in cards:
            parts.append(_nav_card(*card))
        parts.append('    </div>')
    parts.extend(['  </div>', '</section>'])
    return '\n'.join(parts)


MEGA_MENU_ABOUT = _mega_menu_cards([
    ('About EWSETA', [
        ('#', 'fa-eye', 'orange', 'Our Vision, Mission &amp; Values', 'Who we are and what drives us'),
        ('#', 'fa-balance-scale', 'blue', 'Accounting Authority', 'Governance and accountability'),
        ('#', 'fa-industry', 'green', 'Scope of Industrial Coverage', 'Sectors and mandate coverage'),
        ('#', 'fa-file-text-o', 'orange', 'Discretionary Grant Policy', 'Grant framework and guidelines'),
    ]),
    ('Programmes', [
        ('/power-up', 'fa-bolt', 'orange', 'Power Up', 'Energy sector skills programmes'),
    ]),
    ('News &amp; Events', [
        ('/news', 'fa-newspaper-o', 'blue', 'Latest News', 'Updates and announcements from EWSETA'),
        ('#', 'fa-calendar', 'green', 'Events', 'Workshops, roadshows and engagements'),
        ('#', 'fa-book', 'orange', 'Publications', 'Reports, briefs and sector publications'),
    ]),
])

MEGA_MENU_SKILLS = _mega_menu_cards([
    ('Strategic Plans', [
        ('#', 'fa-line-chart', 'orange', 'Strategic Plan 2025/26 – 2029/30', 'Long-term sector skills direction'),
        ('#', 'fa-bar-chart', 'blue', 'Annual Performance Plan 2025/26', 'Yearly targets and delivery focus'),
    ]),
    ('Research &amp; Reports', [
        ('#', 'fa-bolt', 'orange', 'Energy Sector', 'Energy workforce research and insights'),
        ('#', 'fa-tint', 'blue', 'Water Sector', 'Water sector skills intelligence'),
        ('#', 'fa-handshake-o', 'green', 'Research Partnerships', 'Collaborate on sector research'),
    ]),
    ('Skills Planning', [
        ('#', 'fa-sitemap', 'green', 'Sector Skills Plan', 'Sector-wide skills planning framework'),
        ('#', 'fa-list-alt', 'blue', 'Pivotal Skills List', 'Priority occupations and skills'),
    ]),
    ('Mandatory Grants', [
        ('#', 'fa-money', 'orange', 'EWSETA Grants Policy', 'Mandatory grant rules and process'),
        ('#', 'fa-pencil-square-o', 'blue', 'Workplace Skills Plan', 'WSP submission guidance'),
        ('#', 'fa-exchange', 'green', 'Inter-SETA Transfers', 'Transfer requests between SETAs'),
    ]),
    ('QA &amp; Compliance', [
        ('#', 'fa-graduation-cap', 'orange', 'Occupational Qualifications Development', 'Qualification design support'),
        ('#', 'fa-university', 'blue', 'Accreditation of Skills Development Providers', 'Provider accreditation process'),
        ('#', 'fa-id-badge', 'green', 'Assessor / Moderator Registration', 'Register facilitators and moderators'),
        ('#', 'fa-check-square-o', 'orange', 'Assessment Centre Accreditation', 'Accredited assessment centres'),
        ('mailto:waronleaks@ewseta.org.za', 'fa-envelope-o', 'blue', 'QA Compliance Email', 'waronleaks@ewseta.org.za'),
        ('mailto:tradetestapplications@ewseta.org.za', 'fa-envelope-o', 'green', 'Trade Test Applications', 'tradetestapplications@ewseta.org.za'),
        ('mailto:tradetestreports@ewseta.org.za', 'fa-envelope-o', 'orange', 'Trade Test Reports', 'tradetestreports@ewseta.org.za'),
    ]),
    ('Stakeholder Portals', [
        ('#', 'fa-user-plus', 'orange', 'SDF Registration', 'Register as a skills development facilitator'),
        ('#', 'fa-sign-in', 'blue', 'SDF Login Portal', 'Access the mandatory grants window'),
        ('#', 'fa-file-text', 'green', 'WSP / ATR Submission Manual', 'Submission guides and templates'),
        ('#', 'fa-building-o', 'orange', 'Workplace Application', 'Workplace skills programme applications'),
        ('#', 'fa-university', 'blue', 'Provider Registration', 'Skills development provider registration'),
        ('#', 'fa-certificate', 'green', 'Assessor / Moderator Registration', 'ETQA practitioner registration'),
        ('#', 'fa-external-link', 'orange', 'DG Application Portal', 'Discretionary grant applications'),
        ('#', 'fa-gift', 'blue', 'EWSETA Grants Policy', 'Discretionary grant policy documents'),
        ('#', 'fa-book', 'green', 'DG Window Guidelines 2025', 'Current DG window guidance'),
        ('#', 'fa-life-ring', 'orange', 'DG Application Support', 'Help with discretionary grant applications'),
        ('#', 'fa-support', 'blue', 'MG Support Portal', 'Mandatory grants support desk'),
        ('#', 'fa-desktop', 'green', 'ICT Support', 'Technical support for online systems'),
    ]),
    ('Learner Support', [
        ('#', 'fa-compass', 'blue', 'Career Guidance', 'Explore energy and water career paths'),
        ('/jobs', 'fa-briefcase', 'green', 'Job Opportunities', 'Current vacancies at EWSETA'),
    ]),
])

MEGA_MENU_SUPPLY = _mega_menu_cards([
    ('Tenders', [
        ('/tenders', 'fa-gavel', 'orange', 'EWSETA RFPs', 'Open requests for proposals'),
        ('#', 'fa-archive', 'blue', 'Archived Tenders', 'Previously published tender notices'),
        ('#', 'fa-trophy', 'green', 'Awarded Tenders', 'Successfully awarded contracts'),
    ]),
    ('Request for Quotes', [
        ('/rfqs', 'fa-file-text-o', 'orange', 'EWSETA RFQs 2026/27', 'Current request for quote cycle'),
        ('#', 'fa-folder-open-o', 'blue', 'EWSETA RFQs 2025/26', 'Previous financial year RFQs'),
        ('#', 'fa-archive', 'green', 'Archived RFQs', 'Historical RFQ listings'),
    ]),
    ('Contact SCM', [
        ('tel:+27112744700', 'fa-phone', 'orange', 'Supply Chain Hotline', '+27 11 274-4700'),
        ('mailto:info@ewseta.org.za', 'fa-envelope-o', 'blue', 'SCM Email', 'info@ewseta.org.za'),
    ]),
])

MEGA_MENU_CONTENT = {
    'About': MEGA_MENU_ABOUT,
    'Skills Development': MEGA_MENU_SKILLS,
    'Supply Chain': MEGA_MENU_SUPPLY,
}


def post_init_hook(env):
    """Replace default website menus with EWSETA navigation."""
    website = env.ref('website.default_website', raise_if_not_found=False)
    if not website:
        return

    website.write({'name': 'EWSETA'})
    main_menu = website.menu_id
    if not main_menu:
        return

    main_menu.child_id.unlink()
    Menu = env['website.menu'].sudo()

    def create_menu(name, url='#', sequence=10, parent=None, mega_content=None):
        parent = parent or main_menu
        vals = {
            'name': name,
            'url': url,
            'sequence': sequence,
            'parent_id': parent.id,
            'website_id': website.id,
        }
        if mega_content:
            vals['mega_menu_content'] = mega_content
        return Menu.create(vals)

    create_menu('Home', '/', NAV_MENU_SEQUENCE['Home'])
    create_menu('About', sequence=NAV_MENU_SEQUENCE['About'], mega_content=MEGA_MENU_ABOUT)
    create_menu('Skills Development', sequence=NAV_MENU_SEQUENCE['Skills Development'], mega_content=MEGA_MENU_SKILLS)
    create_menu('Supply Chain', sequence=NAV_MENU_SEQUENCE['Supply Chain'], mega_content=MEGA_MENU_SUPPLY)
    create_menu('Contact Us', '/contactus', NAV_MENU_SEQUENCE['Contact Us'])
