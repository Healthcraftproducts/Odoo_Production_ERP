# -*- encoding: utf-8 -*-

{
    'name': 'HCP Customer Price Lists Products in SO',
    'category': 'Sales/Sales',
    'version': '1.0',
    'description': "Show Products Based on Customer Pricelists",
    'depends': [
        'sale', 'product', 'crm', 'sale_crm', 'sale_coupon', 'delivery',
    ],
    'installable': True,
    'data': [  
        'views/hcp_partner_pricelist_view.xml',   
        'views/hcp_crm_view.xml',
        'security/ir.model.access.csv',
        'data/crm_stage_data.xml',
    ],
    'application': True,
}
