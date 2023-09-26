# -*- coding: utf-8 -*-
{
    'name': "HCP BOM IMPORT",

    'summary': """Module to import bill of material""",

    'description': """Module to import bill of material from excel report""",

    'author': "Navabrind IT Solutions",
    'website': "http://www.navabrinditsolutions.com",
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','mrp'],

    # always loaded
    'data': [
        #'security/ir.model.access.csv',
		'wizard/view_import_bom.xml',
		'wizard/view_import_routing.xml',
		'wizard/view_operation_mapping.xml'
    ],
    "application": False,
    "installable": True,
    'license': 'LGPL-3'
}
