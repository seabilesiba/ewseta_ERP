# -*- coding: utf-8 -*-
{
    'name': 'ICT Helpdesk',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'ICT Helpdesk ticket management for intern training',
    'description': """
ICT Helpdesk Ticket Management System
=====================================

Employees submit ICT support tickets (hardware, software, network, email).
Technicians assign, work on and resolve tickets through a simple workflow:

New → Assigned → In Progress → Resolved → Closed

Includes categories, security groups, kanban view, chatter and PDF reports.
    """,
    'author': 'Intern Training',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/helpdesk_security.xml',
        'security/ir.model.access.csv',
        'data/helpdesk_sequence.xml',
        'data/helpdesk_category_data.xml',
        'views/helpdesk_ticket_views.xml',
        'views/helpdesk_category_views.xml',
        'report/helpdesk_report_templates.xml',
        'report/helpdesk_ticket_report.xml',
        'views/helpdesk_menus.xml',
    ],
    'application': True,
    'installable': True,
}
