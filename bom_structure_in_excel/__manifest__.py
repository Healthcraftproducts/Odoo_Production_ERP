# -*- coding: utf-8 -*-

# Part of Probuse Consulting Service Pvt Ltd. See LICENSE file for full copyright and licensing details.

{
    'name': 'BOM Structure & Cost Report in Excel',
    'version': '2.1.2',
    'price': 49.0,
    'currency': 'EUR',
    'category': 'Manufacturing/Manufacturing',
    'license': 'Other proprietary',
    'live_test_url': 'http://probuseappdemo.com/probuse_apps/bom_structure_in_excel/203',
    # 'https://youtu.be/ZOAfLLVf_0s',
    'images': [
        'static/description/img.jpg',
    ],
    'summary': 'This app allows you to export "BOM Structure & Cost Report" in excel format. This app exports the same report which Odoo standard prints in PDF format and our app prints the same report / data in excel as shown in below screenshots',
    'description': """
This app allows you to export "BOM Structure & Cost Report" in excel format. This app exports the same report which Odoo standard prints in PDF format and our app prints the same report / data in excel as shown in below screenshots
    - Allow you to export “BoM Structure & Cost Report in Excel” in excel format.
    - This gives the same output which the PDF report of Odoo standard gives.
    - For more details please check below screenshots and watch the video.
    """,
    'author': 'Probuse Consulting Service Pvt. Ltd.',
    'website': 'www.probuse.com',
    'depends': [
        'mrp','maintenance',
    ],
    'support': 'contact@probuse.com',
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_bom_structure_excel_view.xml'
    ],
    'qweb': [
         ],
    'installable': True,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
