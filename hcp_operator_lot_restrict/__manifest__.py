# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# -*- encoding: utf-8 -*-
{
    'name': 'HCP Operator Lot Restriction',
    'category': 'Manufacturing',
    'version': '1.0',
    'author' : 'nits',
    'description': "HCP Operator Lot restriction for create",
    'depends': ['stock','hcp_operator_customization','multiple_mrp_orders','mrp'],
    'installable': True,
    'data': [  
        'security/ir.model.access.csv',
        'views/view.xml',
    ],
    "installable": True,
    "application": False,
    'license': 'LGPL-3',
}

