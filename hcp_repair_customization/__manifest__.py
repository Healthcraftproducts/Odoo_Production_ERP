# -*- coding: utf-8 -*-
{
    'name': "HCP Repair Extension",

    'summary': """Repair Order Customization""",

    'description': """Repair Order Customization""",

    'author': "Navabrind IT Solutions",
    'website': "http://www.navabrinditsolutions.com",
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','repair','stock'],

    # always loaded
    'data': [
        'views/repair_views.xml',
    ],
}
