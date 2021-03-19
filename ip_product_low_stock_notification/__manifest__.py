# -*- coding: utf-8 -*-
{
    'name': 'Product Low Stock Report/ Notification',
    'summary': "Product Low Stock Report/ Notification based on minimum quantity. Get stock by selected company and location and notify to selected user",
    'description': """Product Low Stock Report/ Notification based on minimum quantity. Get stock by selected company and location and notify to selected user""",

    'author': 'iPredict IT Solutions Pvt. Ltd.',
    'website': 'http://ipredictitsolutions.com',
    "support": "ipredictitsolutions@gmail.com",

    'category': 'Warehouse',
    'version': '13.0.0.1.2',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/product_low_stock_wiz_view.xml',
        'views/product_view.xml',
        'views/stock_config_settings_view.xml',
        'report/report_action_view.xml',
        'report/report_product_low_stock.xml',
        'data/low_stock_notification_data.xml',
    ],

    'license': "OPL-1",
    'price': 40,
    'currency': "EUR",

    'auto_install': False,
    'installable': True,

    'images': ['static/description/main.png'],
}
