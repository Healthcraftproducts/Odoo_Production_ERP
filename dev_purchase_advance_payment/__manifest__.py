# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

{
    'name': 'Payment from Purchase Order',
    'version': '13.0.1.0',
    'sequence': 1,
    'category': 'Purchases',
    'description':
        """
This Module add below functionality into odoo

        1.Make payment before creating bill in purchase order\n
Payment from Purchase Order
Odoo Payment from Purchase Order
Manage purchase order 
Odoo manage purchase order 
Payment purchase order 
Odoo payment purchase order 
Odoo application allows you to make direct payment from Purchase Order before creating Vendor Bill.
Make direct Payments from Purchase Order
Odoo Navigate to Payments from Purchase Order screen
Odoo Make direct Payments from Purchase Order
Make advance payment 
Odoo make adavnce payment 
Advance payment for purchase order
Odoo advance payment for purchase order 
Advance payment into ventor bill 
Odoo advance payment into vendor bill 
Payment from Purchase Order
Odoo Payment from Purchase Order
Manage purchase order 
Odoo manage purchase order 
Payment purchase order 
Odoo payment purchase order 
Odoo application allows you to make direct payment from Purchase Order before creating Vendor Bill.
Make direct Payments from Purchase Order
Odoo Navigate to Payments from Purchase Order screen
Odoo Make direct Payments from Purchase Order
Make advance payment 
Odoo make adavnce payment 
Advance payment for purchase order
Odoo advance payment for purchase order 
Advance payment into ventor bill 
Odoo advance payment into vendor bill 
Purchase Advance Payment 
Odoo purchase Advance Payment 
Purchase Payment 
Odoo purchase Payment 
Manage purchase Payment 
Manage purchase Advance Payment 
Odoo manage purchase Aadvance Payment 
Advance Payment 
Odoo Advance Payment 
Manage Advance Payment 
Odoo Manage Advance Payment 
Billable Payment 
Odoo Billable Payment 
Manage Billable Payment 
Odoo manage Billable Payment 
Vendor bill Payment 
Odoo Vendor bill Payment 
Manage vendor bill Payment 
Odoo Manage vendor bill Payment 
Purchase payable bill 
Odoo Purchase payable bill 


    """,
    'summary': 'odoo app will allow to make Payment from Purchase Order',
    'depends': ['purchase', 'account'],
    'data': [
        'views/purchase_views.xml',
        ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    
    # author and support Details =============#
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'http://www.devintellecs.com',    
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd', 
    'support': 'devintelle@gmail.com',
    'price':15.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
