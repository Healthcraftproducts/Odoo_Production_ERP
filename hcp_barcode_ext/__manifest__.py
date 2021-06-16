# -*- coding: utf-8 -*-
{
    'name': "HCP Barcode Ext",

    'summary': """Shipping Barcode Customization Added in the app""",

    'description': """Shipping Barcode Customization Added in the app""",

    'author': "NITS PVT LTD",
    'website': "http://www.navabrindsol.com",
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base','web','stock_barcode'],

    'data': [
        'views/asset.xml',
    ],
    'qweb': [
        "static/src/xml/qweb_templates.xml",
    ],

}
