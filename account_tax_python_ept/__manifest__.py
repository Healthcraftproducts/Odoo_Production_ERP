# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Tax Based on Python Code Formula',
    'category': 'account tax',
    'license': 'OPL-1',
    'website': 'https://www.emiprotechnologies.com/',
    'version': '16.0.1.0',
    'description': """This app allowed to Calculate Tax Amount in which Tax type is Python Code 
    and Line Tax Amount set in Order Line and Account Move Line """,
    'depends': ['account_tax_python','sale'],
    'data': [
        'data/decimal_precision.xml',
        'data/account_tax.xml',
        'views/sale_order_line.xml',
        'views/account_move_line.xml'
    ],
    'installable': True,
    'application': True,
}
