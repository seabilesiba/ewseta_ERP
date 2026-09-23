# -*- coding: utf-8 -*-

from odoo import fields, models


class HelpdeskCategory(models.Model):
    _name = 'helpdesk.category'
    _description = 'ICT Helpdesk Category'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    ticket_count = fields.Integer(compute='_compute_ticket_count', string='Tickets')

    _name_unique = models.Constraint(
        'unique(name)',
        'Category name must be unique.',
    )

    def _compute_ticket_count(self):
        ticket_data = self.env['helpdesk.ticket'].sudo().read_group(
            [('category_id', 'in', self.ids)],
            ['category_id'],
            ['category_id'],
        )
        counts = {row['category_id'][0]: row['category_id_count'] for row in ticket_data}
        for category in self:
            category.ticket_count = counts.get(category.id, 0)

    def action_view_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'helpdesk.ticket',
            'view_mode': 'kanban,list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }
