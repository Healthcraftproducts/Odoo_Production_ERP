# -*- coding: utf-8 -*-
{
    'name': "HCP Custom Reports",

    'summary': """
        Customization of Reports""",

    'description': """
        This module is used to customize the sale,quotation,invoice reports
    """,

    'author': "NITS PVT LTD",
    'website': "http://www.navabrindsol.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','sale','account','mail','contacts','portal','utm','purchase','web','delivery','stock','hcp_mrp_module','hcp_product_ext'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        # 'reports/sale_custom_header.xml',
        'reports/all_print_menu.xml',
        'reports/sale_custom_report_inherit.xml',
        'reports/invoice_custom_report_inherit.xml',
        'reports/purchase_quotation_inherit.xml',
        'reports/purchase_report_inherit.xml',
        'reports/delivery_picking_slip_inherit.xml',
        'reports/print_label_barcode_report_inherit.xml',
        'reports/operator_bom_efficiency_report.xml',
        'reports/operator_bom_efficiency.xml',
        'reports/report_lot_barcode.xml',
        'reports/report_lot_barcode_vertical.xml',
        'reports/lot_serial_number_pdf_inherit.xml',
        'reports/report_lot_barcode_internal_reference.xml',
        'views/sale_views.xml',
        'views/invoice_views.xml',
        'wizard/product_discount_consolidated_wizard_views.xml',
        'wizard/product_discount_individual_report_customers_views.xml',
        'wizard/inventory_count_cycle_wizard_view.xml',
        'reports/report_action_view.xml',
        'reports/report_product_discount_detailed.xml',
        'data/mail_template_data.xml',
        'data/sale_sequence.xml',
        # 'data/sale_default_data.xml',
        
        # 'reports/invoice_custom_header.xml',
        
        # 'reports/purchase_custom_header.xml',
        
        
    ],
    "application": False,
    "installable": True,
    'license': 'LGPL-3'
    # only loaded in demonstration mode
    # 'demo': [
    #     'demo/demo.xml',
    # ],
}
