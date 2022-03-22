# -*- coding: utf-8 -*-

{
    'name': "Import Product Valuation Difference",
    'version': '1.0',
    'price': 0.0,
    'currency': 'EUR',
    'license': 'Other proprietary',
    'summary': """Import Product Valuation Difference""",
    'description': """
    Import Product Valuation Difference
    """,
    'category': 'Operations/Inventory',
    'depends': [
                'stock_account',
                ],
    'data':[
            'wizard/import_product_valuation_difference_wizard.xml',
            
    ],
    'installable' : True,
    'application' : False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
