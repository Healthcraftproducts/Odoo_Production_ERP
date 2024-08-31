# -*- coding: utf-8 -*-pack
{

    # App information
    'name': 'FedEx Shipping Odoo Integration',
    'category': 'Website',
    'version': '16.0.0',
    'summary': """ """,
    'description': """ Our Odoo FedEx Shipping Integration will help you connect with FedEx Shipping Carrier with Odoo. automatically submit order information from Odoo to FedEx and get Shipping label, and Order Tracking number from FedEx to Odoo.we also provide the ups,dhl,usps,stamp.com,shipstation shipping integration.""",

    # Dependencies
    'depends': ['delivery'],

   # Views
      'data': [
            'data/ir_cron.xml',
            'data/delivery_fedex.xml',
            'views/res_company.xml',
            'views/delivery_carrier_view.xml',
            'views/sale_view.xml',
            ],

    # Author

    'author': 'Vraja Technologies',
    'website': 'https://www.vrajatechnologies.com',
    'maintainer': 'Vraja Technologies',
    'live_test_url': 'https://www.vrajatechnologies.com/contactus',
    'images': ['static/description/cover.gif'],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'price': '99',
    'currency': 'EUR',
    'license': 'OPL-1',

}
