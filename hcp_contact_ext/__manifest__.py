# -*- coding: utf-8 -*-
{
    'name': "HCP Contacts Extension",

    'summary': """Contact Customizations Added""",

    'description': """Contact Customizations Added""",

    'author': "Navabrind IT Solutions",
    'website': "http://www.navabrinditsolutions.com",
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','contacts','delivery','account'],

    # always loaded
    'data': [
        'data/ir_sequence_data.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
    ],
}
