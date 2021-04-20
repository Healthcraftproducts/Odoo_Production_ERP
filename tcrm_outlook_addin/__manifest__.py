# -*- coding: utf-8 -*-
{
    'name': "Microsoft Office 365 Add-In for Outlook",

    'summary': "If you live most of your day in Outlook, then you need our Outlook Add-In for Odoo ERP.  Living as a 'side bar' within your Outlook client, our add-in lets you interface with the most-needed functions of Odoo.",

    'description': "",
	'license': 'OPL-1',
    'images': ['images/image1.png', 'images/image2_screenshot.png'],
    'author': "TractionCRM",
    'website': "https://tractionerp.odoo.com/outlook-add-in-for-odoo-erp",

    'application': True,

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Productivity',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
    #    'views/ir_actions_server.xml', 
    #    'views/base_automation.xml',
        'views/view.xml'
    ]
    # only loaded in demonstration modes
    #'demo': [
    #    'demo/demo.xml',
    #]
}
