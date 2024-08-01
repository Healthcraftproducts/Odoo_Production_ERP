# -*- coding: utf-8 -*-
{
    'name': "HCP Helpdesk Ext",

    'summary': """Module to Extend Helpdesk""",

    'description': """Module To Extend Helpdesk Module For Customization""",

    'author': "Navabrind IT Solutions",
    'website': "http://www.navabrinditsolutions.com",
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'helpdesk','helpdesk_sale'],

    'data': [
      'views/views.xml',
    ],

    "application": True,
    "installable": True,
    'license': 'LGPL-3'
}
