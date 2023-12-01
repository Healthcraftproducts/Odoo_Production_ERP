# -*- coding: utf-8 -*-
{
    'name': "HCP MRP Customization",

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
    'depends': ['base','mrp','product','purchase','timesheet_grid'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/all_print_menu.xml',
        'views/mrp_production_report_inherit.xml',
        'views/mrp_production_views.xml',
        # 'views/report.xml',
        # 'views/templates.xml',
    ],
    # only loaded in demonstration mode
    # 'demo': [
    #     'demo/demo.xml',
    # ],
'assets': {
    'web.assets_backend': [
        'hcp_mrp_module/static/src/**/*.xml',
    ],
},

}

