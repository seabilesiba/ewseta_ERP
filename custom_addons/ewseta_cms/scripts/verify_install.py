# -*- coding: utf-8 -*-
website = env.ref('website.default_website')

# Fix mega menu URLs (idempotent)
from odoo.addons.ewseta_cms.hooks import _update_menu_urls
_update_menu_urls(env, website)

print('=== Seed counts ===')
for model in ['ewseta.hero.slide', 'ewseta.home.welcome', 'ewseta.home.settings', 'ewseta.programme.card', 'ewseta.sector.card', 'ewseta.news.article']:
    print(model, env[model].sudo().search_count([('website_id', '=', website.id)]))

print('\n=== Menu URLs ===')
menus = env['website.menu'].sudo().search([('website_id', '=', website.id), ('name', 'in', ['Latest News', 'Job Opportunities'])])
for m in menus:
    print(m.name, '->', m.url)

supply = env['website.menu'].sudo().search([('website_id', '=', website.id), ('name', '=', 'Supply Chain')], limit=1)
if supply:
    print('Supply mega has /tenders:', '/tenders' in (supply.mega_menu_content or ''))
    print('Supply mega has /rfqs:', '/rfqs' in (supply.mega_menu_content or ''))

groups = {
    'marketing': env.ref('ewseta_cms.group_ewseta_marketing'),
    'hr': env.ref('ewseta_cms.group_ewseta_hr'),
    'supply': env.ref('ewseta_cms.group_ewseta_supply_chain'),
}
users = {
    'ewseta.marketing@test.com': groups['marketing'],
    'ewseta.hr@test.com': groups['hr'],
    'ewseta.supply@test.com': groups['supply'],
}
for login, group in users.items():
    user = env['res.users'].sudo().search([('login', '=', login)], limit=1)
    if not user:
        user = env['res.users'].sudo().create({
            'name': login.split('@')[0].replace('.', ' ').title(),
            'login': login,
            'password': 'Test1234!',
            'group_ids': [(6, 0, [group.id])],
        })
        print('Created user', login)
    else:
        user.sudo().write({'group_ids': [(6, 0, [group.id])]})
        print('Updated user', login)

print('\n=== Access checks ===')
checks = [
    ('ewseta.marketing@test.com', 'ewseta.hero.slide', True),
    ('ewseta.marketing@test.com', 'ewseta.tender', False),
    ('ewseta.hr@test.com', 'ewseta.hero.slide', False),
    ('ewseta.hr@test.com', 'hr.job', True),
    ('ewseta.supply@test.com', 'ewseta.tender', True),
    ('ewseta.supply@test.com', 'ewseta.news.article', False),
]
for login, model, should_access in checks:
    user = env['res.users'].sudo().search([('login', '=', login)], limit=1)
    try:
        env[model].with_user(user).check_access('read')
        can_read = True
    except Exception:
        can_read = False
    ok = can_read == should_access
    print(f"{login} read {model}: {can_read} ({'OK' if ok else 'FAIL'})")

env.cr.commit()
