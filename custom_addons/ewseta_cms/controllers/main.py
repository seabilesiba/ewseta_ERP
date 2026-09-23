# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class EwsetaCmsController(http.Controller):

    def _website_domain(self):
        return request.website.website_domain()

    def _published_news_domain(self):
        domain = list(self._website_domain())
        domain.append(('is_published', '=', True))
        return domain

    def _published_tender_domain(self):
        domain = list(self._website_domain())
        domain.extend([('is_published', '=', True), ('state', '=', 'published')])
        return domain

    def _published_rfq_domain(self):
        domain = list(self._website_domain())
        domain.extend([('is_published', '=', True), ('state', '=', 'published')])
        return domain

    @http.route(['/news', '/news/page/<int:page>'], type='http', auth='public', website=True, sitemap=True)
    def news_list(self, page=1, **kwargs):
        Article = request.env['ewseta.news.article'].sudo()
        domain = self._published_news_domain()
        total = Article.search_count(domain)
        pager = request.website.pager(
            url='/news',
            total=total,
            page=page,
            step=12,
        )
        articles = Article.search(domain, limit=12, offset=pager['offset'], order='publish_date desc, id desc')
        return request.render('ewseta_cms.news_list', {
            'articles': articles,
            'pager': pager,
        })

    @http.route(['/news/<string:slug>'], type='http', auth='public', website=True, sitemap=True)
    def news_detail(self, slug, **kwargs):
        article = request.env['ewseta.news.article'].sudo().search([
            ('slug', '=', slug),
            ('is_published', '=', True),
        ] + list(request.website.website_domain()), limit=1)
        if not article:
            return request.not_found()
        return request.render('ewseta_cms.news_detail', {
            'article': article,
            'main_object': article,
        })

    @http.route(['/tenders', '/tenders/page/<int:page>'], type='http', auth='public', website=True, sitemap=True)
    def tender_list(self, page=1, **kwargs):
        Tender = request.env['ewseta.tender'].sudo()
        domain = self._published_tender_domain()
        total = Tender.search_count(domain)
        pager = request.website.pager(
            url='/tenders',
            total=total,
            page=page,
            step=20,
        )
        tenders = Tender.search(domain, limit=20, offset=pager['offset'], order='closing_date desc, id desc')
        return request.render('ewseta_cms.tender_list', {
            'tenders': tenders,
            'pager': pager,
        })

    @http.route(['/tenders/<string:slug>'], type='http', auth='public', website=True, sitemap=True)
    def tender_detail(self, slug, **kwargs):
        tender = request.env['ewseta.tender'].sudo().search([
            ('slug', '=', slug),
            ('is_published', '=', True),
            ('state', '=', 'published'),
        ] + list(request.website.website_domain()), limit=1)
        if not tender:
            return request.not_found()
        return request.render('ewseta_cms.tender_detail', {
            'tender': tender,
            'main_object': tender,
        })

    @http.route(['/rfqs', '/rfqs/page/<int:page>'], type='http', auth='public', website=True, sitemap=True)
    def rfq_list(self, page=1, **kwargs):
        Rfq = request.env['ewseta.rfq'].sudo()
        domain = self._published_rfq_domain()
        total = Rfq.search_count(domain)
        pager = request.website.pager(
            url='/rfqs',
            total=total,
            page=page,
            step=20,
        )
        rfqs = Rfq.search(domain, limit=20, offset=pager['offset'], order='closing_date desc, id desc')
        return request.render('ewseta_cms.rfq_list', {
            'rfqs': rfqs,
            'pager': pager,
        })

    @http.route(['/rfqs/<string:slug>'], type='http', auth='public', website=True, sitemap=True)
    def rfq_detail(self, slug, **kwargs):
        rfq = request.env['ewseta.rfq'].sudo().search([
            ('slug', '=', slug),
            ('is_published', '=', True),
            ('state', '=', 'published'),
        ] + list(request.website.website_domain()), limit=1)
        if not rfq:
            return request.not_found()
        return request.render('ewseta_cms.rfq_detail', {
            'rfq': rfq,
            'main_object': rfq,
        })
