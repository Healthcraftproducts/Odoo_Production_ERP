# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# -*- encoding: utf-8 -*-
{
    'name': 'HCP MRP Customization',
    'category': 'Manufacturing',
    'version': '1.0',
    'description': "MRP Customization included in this app",
    'depends': [
        'purchase', 'stock', 'mrp','base','mrp_mps'],
    'installable': True,
    'data': [  
        'views/forecast_view.xml',  
        'wizard/reservation_bug_fix.xml',
    ],
    'application': True,
    'uninstall_hook': 'uninstall_hook',
}

