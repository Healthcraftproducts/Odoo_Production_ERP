# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'HCP-Deringer XML Intergration',
    'version': '1.0',
    'category': 'Generate Deringer XML Template for posting shipment data',
    'summary': 'Generate Deringer XML Template for posting shipment data',
    'description': """This module allow to generate shipment data in xml format for deringer integration""",
    'depends': ['base','account','report_xml','hcp_product_ext'],
    'data': [
        'security/ir.model.access.csv',
        'views/deringer_views.xml',
        'views/other_form_fields.xml',
        'data/ir_sequence_data.xml',
        'data/mail_data.xml',
    ],

    'installable': True,

}
