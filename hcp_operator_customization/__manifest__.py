# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# -*- encoding: utf-8 -*-*
{
    'name': 'HCP Operator Role Customization',
    'category': 'Manufacturing',
    'version': '1.0',
    'description': "HCP Operator Role Customization",
    'depends': ['stock', 'mrp','base','mrp_workorder'],
    'installable': True,
    'data': [  
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/mrp_view.xml',
    ],
    'application': True,
    'uninstall_hook': 'uninstall_hook',

'assets': {
    'web.assets_backend': [
        'hcp_operator_customization/static/src/**/*.xml',
    ],
},
}

