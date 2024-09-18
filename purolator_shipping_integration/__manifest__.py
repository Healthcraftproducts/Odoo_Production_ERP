# -*- coding: utf-8 -*-pack
{

    # App information
    'name': 'Purolator Shipping Integration',
    'category': 'Website',
    'version': '16.0.0',
    'summary': """Using Purolator Easily manage Shipping Operation in odoo.Export Order While Validate Delivery Order.Import Tracking From Purolator to odoo.Generate Label in odoo.We also Provide the gls,envia,fedex shipping integration.""",
    'description': """""",

    # Dependencies
    'depends': ['delivery'],

     # Views
    'data': [
        'security/ir.model.access.csv',
        'views/res_company.xml',
        'views/sale_view.xml',
        'views/delivery_carrier.xml'
    ],

    # Author
    'author': 'Vraja Technologies',
    'website': 'http://www.vrajatechnologies.com',
    'maintainer': 'Vraja Technologies',
    'live_test_url': 'http://www.vrajatechnologies.com/contactus',
    'images': ['static/description/cover.gif'],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'price': '149',
    'currency': 'EUR',
    'license': 'OPL-1',

}
#Version Log
# 12.0.23.03.2023 12.0 initial version
