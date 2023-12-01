# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'HCP MPS Customization',
    'version' : '0.1',
    'sequence': 165,
    'category': 'Extra Tools',
    'website' : 'http://www.navabrinditsolutions.com',
    'summary' : 'MPS Customization For Manufacturing Order Creations',
    'description' : """MPS Customization For Manufacturing Order Creations""",
    'depends': ['base','stock','mrp','mrp_mps','purchase_stock','sale_stock'],
    'data': [ 'views/mrp_views.xml',
              'data/ir_sequence.xml',
              'wizard/cancel_multi_order_wizard_view.xml'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
