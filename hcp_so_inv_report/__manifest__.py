# -*- coding: utf-8 -*-
{
    'name': 'SO/Invoice Difference',
    'summary': "SO/Invoice Difference",
    'description': """SO/Invoice Difference""",

    'author': 'Navabrind Solutions Pvt. Ltd.',
    'website': 'http://navabrindit.com',
    "support": "sales@navabrindit.com",

    'category': 'Warehouse',
    'version': '13.0.0.1.2',
    'depends': ['sale','account','base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/so_inv_wiz_view.xml',
        'report/report_action_view.xml',
    ],

    'license': "OPL-1",
    'price': 40,
    'currency': "EUR",

    'auto_install': False,
    'installable': True,

    #'images': ['static/description/main.png'],
}
