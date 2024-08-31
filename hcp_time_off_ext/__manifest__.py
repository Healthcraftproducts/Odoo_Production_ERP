# -*- coding: utf-8 -*-
{
    'name': "HCP Time Off Ext",

    'summary': """Module to Extend Time Off""",

    'description': """Module To Extend Time Off Module For Customization""",

    'author': "Navabrind IT Solutions",
    'website': "http://www.navabrinditsolutions.com",
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'hr_holidays'],

    'assets': {
        'web.assets_backend': [
            'hcp_time_off_ext/static/src/dashboard/time_off_card.xml',
        ],
    },

    "application": True,
    "installable": True,
    'license': 'LGPL-3'
}
