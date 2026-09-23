# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _description = 'ICT Helpdesk Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'opened_date desc, id desc'

    STATES = [
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]
    PRIORITIES = [
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ]

    name = fields.Char(
        string='Ticket Number',
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    title = fields.Char(required=True, tracking=True)
    description = fields.Text(required=True, tracking=True)
    requester_id = fields.Many2one(
        'res.users',
        string='Requester',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )
    category_id = fields.Many2one(
        'helpdesk.category',
        string='Category',
        tracking=True,
        index=True,
    )
    technician_id = fields.Many2one(
        'res.users',
        string='Technician',
        tracking=True,
        index=True,
        domain="[('share', '=', False)]",
    )
    priority = fields.Selection(
        selection=PRIORITIES,
        string='Priority',
        default='1',
        required=True,
        tracking=True,
        index=True,
    )
    opened_date = fields.Datetime(
        string='Opened Date',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        tracking=True,
    )
    deadline = fields.Date(string='Deadline', tracking=True)
    state = fields.Selection(
        selection=STATES,
        string='Status',
        default='new',
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
    resolution = fields.Text(string='Resolution', tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    is_overdue = fields.Boolean(compute='_compute_is_overdue', string='Overdue')
    priority_label = fields.Char(compute='_compute_priority_label', string='Priority Label')
    color = fields.Integer(compute='_compute_color')

    @api.depends('priority')
    def _compute_priority_label(self):
        labels = dict(self.PRIORITIES)
        for ticket in self:
            ticket.priority_label = labels.get(ticket.priority, '')

    @api.depends('priority')
    def _compute_color(self):
        color_map = {'0': 10, '1': 4, '2': 2, '3': 1}
        for ticket in self:
            ticket.color = color_map.get(ticket.priority, 0)

    @api.depends('deadline', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        closed_states = {'resolved', 'closed', 'cancelled'}
        for ticket in self:
            ticket.is_overdue = bool(
                ticket.deadline
                and ticket.deadline < today
                and ticket.state not in closed_states
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('helpdesk.ticket') or _('New')
        return super().create(vals_list)

    def _check_technician_access(self):
        if not (
            self.env.user.has_group('intern_helpdesk.group_helpdesk_technician')
            or self.env.user.has_group('intern_helpdesk.group_helpdesk_manager')
        ):
            raise UserError(_('Only technicians or managers can perform this action.'))

    def action_assign(self):
        self._check_technician_access()
        for ticket in self:
            if ticket.state != 'new':
                raise UserError(_('Only new tickets can be assigned.'))
            if not ticket.technician_id:
                raise UserError(_('Please select a technician before assigning the ticket.'))
            ticket.state = 'assigned'
        return True

    def action_start_work(self):
        self._check_technician_access()
        for ticket in self:
            if ticket.state != 'assigned':
                raise UserError(_('Only assigned tickets can be started.'))
            ticket.state = 'in_progress'
        return True

    def action_resolve(self):
        self._check_technician_access()
        for ticket in self:
            if ticket.state != 'in_progress':
                raise UserError(_('Only tickets in progress can be resolved.'))
            if not ticket.resolution:
                raise UserError(_('Please enter a resolution before marking the ticket as resolved.'))
            ticket.state = 'resolved'
        return True

    def action_close(self):
        if not self.env.user.has_group('intern_helpdesk.group_helpdesk_manager'):
            raise UserError(_('Only helpdesk managers can close tickets.'))
        for ticket in self:
            if ticket.state != 'resolved':
                raise UserError(_('Only resolved tickets can be closed.'))
            ticket.state = 'closed'
        return True

    def action_reopen(self):
        self._check_technician_access()
        for ticket in self:
            if ticket.state not in ('closed', 'cancelled', 'resolved'):
                raise UserError(_('Only closed, cancelled or resolved tickets can be reopened.'))
            ticket.state = 'assigned' if ticket.technician_id else 'new'
        return True

    def action_cancel(self):
        for ticket in self:
            if ticket.state == 'closed':
                raise UserError(_('Closed tickets cannot be cancelled.'))
            ticket.state = 'cancelled'
        return True

    def action_assign_to_me(self):
        self._check_technician_access()
        for ticket in self:
            ticket.technician_id = self.env.user
            if ticket.state == 'new':
                ticket.state = 'assigned'
        return True
