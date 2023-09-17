# -*- encoding: utf-8 -*-
{
    'name': 'Update Shipping Rates',
    'category': 'Shippment',
    'sequence': 7,
    'version': '0.3',
    'summary': "Manage your shippment methods with multiple conditions of Pricing/Weight/Quanity",
    'description': "Manage your shippment methods with multiple conditions of Pricing/Weight/Quanity",
    'depends': [
         'sale','delivery',
    ],
    'installable': True,
    'data': [

      'views/delivery_views.xml',

    ],
    'application': True,
    'installable': True,
}
