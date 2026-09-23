# Search DB for stale field references
env.cr.execute("""
    SELECT id, name, key FROM ir_ui_view
    WHERE arch_db ILIKE '%hero_featured_portrait_image%'
       OR arch_db ILIKE '%hero_featured_portrait_web%'
""")
print('stale views:', env.cr.fetchall())

env.cr.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE column_name LIKE '%hero_featured%'
""")
print('featured columns:', env.cr.fetchall())

# Simulate homepage QWeb path
from odoo.addons.base.models import ir_qweb
website = env['website'].get_current_website()
Welcome = env['ewseta.home.welcome'].sudo()
welcome = Welcome.search([('is_published', '=', True)] + list(website.website_domain()), limit=1)
print('welcome search OK', welcome.title)
print('circle url', welcome.hero_circle_web_url)

# Try rendering combined hero view id used on homepage
view = env.ref('ewseta_web.s_ewseta_hero_carousel')
combined = view._get_combined_arch()
if 'hero_featured_portrait_image' in (combined or ''):
    print('STALE in combined arch!')
else:
    print('combined arch clean')

# Render with mock request context
from odoo.http import request as http_request
from odoo.tools import frozendict

class FakeRequest:
    env = env
    website = website
    session = frozendict({})
    def __getitem__(self, key):
        return getattr(self, key)

# Can't easily mock request in shell - use direct template values instead
try:
    values = {
        'website': website,
        'welcome': welcome,
        'portraits': env['ewseta.hero.slide'].sudo().search([('is_published', '=', True), ('slide_type', '=', 'portrait')], limit=3),
        'default_circle': welcome.hero_circle_web_url or '/ewseta_web/static/img/hero_energy.jpg',
        'default_small': welcome.hero_overlap_web_url or '/ewseta_web/static/img/hero_water.jpg',
        'featured_link': welcome.hero_featured_portrait_url or welcome.cta_url or '#',
    }
    html = env['ir.qweb']._render(env.ref('ewseta_cms.s_ewseta_hero_carousel_dynamic').id, values)
    print('render OK', len(html))
except Exception as e:
    print('render FAIL', type(e).__name__, e)
    import traceback; traceback.print_exc()
