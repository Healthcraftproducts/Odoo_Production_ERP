# -*- coding: utf-8 -*-
{
    'name': "HCP Product Extended",

    'summary': """
        This module is used for products""",

    'description': """
        This module is used for products customization
    """,

    'author': "NITS PVT LTD",
    'website': "http://www.navabrindsol.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','product','sale','stock','purchase'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/product_cycle_views.xml',
        'views/products_views.xml',

        
    ],
    # only loaded in demonstration mode
    
}
