# -*- coding: utf-8 -*-
{
    'name': "HCP MRP BOM Customization",

    'summary': """
        This module is used for manufacturing customizations""",

    'description': """
        Long description of module's purpose
    """,

    'author': "NITS PVT LTD",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mrp', 'product', 'purchase', 'maintenance'],

    # always loaded
    'data': [
        'views/mrp_bom_ext.xml',
		#'views/account_invoice_inherit.xml',
    ],
    # only loaded in demonstration mode
    # 'demo': [
    #     'demo/demo.xml',
    # ],
}
