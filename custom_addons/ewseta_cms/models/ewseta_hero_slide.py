# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EwsetaHeroSlide(models.Model):
    _name = 'ewseta.hero.slide'
    _description = 'EWSETA Hero Carousel Slide'
    _inherit = ['mail.thread', 'website.published.multi.mixin']
    _order = 'sequence, id'

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    badge = fields.Char(string='Badge Label')
    badge_color = fields.Selection(
        selection=[
            ('orange', 'Orange'),
            ('blue', 'Blue'),
            ('green', 'Green'),
        ],
        default='orange',
    )
    title = fields.Char(string='Headline')
    body = fields.Html(sanitize_attributes=False)
    cta_primary_label = fields.Char(string='Primary Button Label')
    cta_primary_url = fields.Char(string='Primary Button URL')
    cta_secondary_label = fields.Char(string='Secondary Button Label')
    cta_secondary_url = fields.Char(string='Secondary Button URL')
    overlay_opacity = fields.Float(
        string='Overlay Opacity',
        default=0.88,
        help='Dark overlay over the banner image or video. '
             'Set to 0% for pre-designed banners that already include text.',
    )
    image = fields.Image(string='Slide Image')
    image_url = fields.Char(
        string='Slide Image URL',
        help='Optional static image path (e.g. /ewseta_web/static/img/hero_energy.jpg). '
             'Used when no uploaded image is set.',
    )
    side_image_web_url = fields.Char(
        string='Slide Image Web URL',
        compute='_compute_side_image_web_url',
    )
    video_file = fields.Binary(string='Background Video File', attachment=True)
    video_filename = fields.Char(string='Video Filename')
    video_url = fields.Char(
        string='Background Video URL',
        help='Optional external MP4/YouTube/Vimeo URL. Uploaded video file takes priority.',
    )
    video_file_secondary = fields.Binary(string='Secondary Video File', attachment=True)
    video_filename_secondary = fields.Char(string='Secondary Video Filename')
    video_url_secondary = fields.Char(
        string='Secondary Video URL',
        help='Optional second video URL for dual-video slides. Uploaded file takes priority.',
    )
    video_poster = fields.Image(string='Video Poster')
    video_poster_url = fields.Char(string='Video Poster URL')
    video_poster_secondary_url = fields.Char(string='Secondary Video Poster URL')
    slide_type = fields.Selection(
        selection=[
            ('banner', 'Banner Strip'),
            ('portrait', 'Hero Portrait'),
            ('image', 'Image Banner (legacy)'),
            ('video', 'Video Banner (legacy)'),
            ('dual_video', 'Dual Video Banner (legacy)'),
        ],
        default='banner',
        required=True,
    )
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )

    @api.model
    def _get_published_domain(self, website_id=None):
        domain = [('is_published', '=', True)]
        if website_id:
            domain.append(('website_id', 'in', (False, website_id)))
        return domain

    def _has_hero_content(self):
        self.ensure_one()
        return bool(
            self.badge
            or self.title
            or self.body
            or self.cta_primary_label
            or self.cta_secondary_label
        )

    def _overlay_style(self):
        self.ensure_one()
        opacity = self.overlay_opacity
        if opacity is None:
            opacity = 0.88
        opacity = max(0.0, min(1.0, opacity))
        if opacity <= 0:
            return 'opacity: 0; pointer-events: none;'
        return 'opacity: %s;' % opacity

    def _badge_css_class(self):
        self.ensure_one()
        mapping = {
            'orange': 'ewseta-hero-badge',
            'blue': 'ewseta-hero-badge ewseta-badge-blue',
            'green': 'ewseta-hero-badge ewseta-badge-green',
        }
        return mapping.get(self.badge_color, 'ewseta-hero-badge')

    def _image_web_url(self):
        self.ensure_one()
        if self.image:
            return '/web/image/ewseta.hero.slide/%s/image' % self.id
        return self.image_url or False

    @api.depends('image', 'image_url')
    def _compute_side_image_web_url(self):
        for slide in self:
            slide.side_image_web_url = slide._image_web_url() or '/ewseta_web/static/img/hero_energy.jpg'

    def _is_video_banner(self):
        self.ensure_one()
        return self.slide_type in ('video', 'dual_video')

    def _has_video_source(self, secondary=False):
        self.ensure_one()
        return bool(self._video_source_url(secondary=secondary))

    def _background_image_style(self):
        self.ensure_one()
        url = self._image_web_url()
        if not url and self._is_video_banner():
            poster = self._poster_url()
            if poster:
                url = poster
        if not url:
            return ''
        return "background-image: url('%s');" % url

    def _video_source_url(self, secondary=False):
        self.ensure_one()
        if secondary:
            if self.video_filename_secondary or self.video_file_secondary:
                filename = self.video_filename_secondary or 'video.mp4'
                return '/web/content/ewseta.hero.slide/%s/video_file_secondary/%s' % (self.id, filename)
            return self.video_url_secondary or False
        if self.video_filename or self.video_file:
            filename = self.video_filename or 'video.mp4'
            return '/web/content/ewseta.hero.slide/%s/video_file/%s' % (self.id, filename)
        return self.video_url or False

    def _poster_url(self, secondary=False):
        self.ensure_one()
        if secondary:
            if self.video_poster_secondary_url:
                return self.video_poster_secondary_url
            image_url = self._image_web_url()
            return image_url or '/ewseta_web/static/img/hero_water.jpg'
        if self.video_poster:
            return '/web/image/ewseta.hero.slide/%s/video_poster' % self.id
        if self.video_poster_url:
            return self.video_poster_url
        image_url = self._image_web_url()
        return image_url or '/ewseta_web/static/img/hero_energy.jpg'

    @api.model
    def run_chieta_layout_migration(self):
        from odoo.addons.ewseta_cms.hooks import _migrate_hero_slides
        _migrate_hero_slides(self.env)
