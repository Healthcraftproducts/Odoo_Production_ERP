# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Mass Produce Manufacturing Orders',
    'version': '16.0.0.3',
    'category': 'Manufacturing',
    'summary': 'Produce multiple manufacturing Produce mass production for mrp mass produce manufacturing order mass production mass manufacturing produce mass MO mass produce order mrp mass production for manufacturing order mass produce multiple manufacturing order',
    "description": """ This odoo app helps user to produce multiple manufacturing orders at single click even if manufacturing orders in draft, state, confirmed, or partially produced, Also raise warning if any manufacturing orders in done state or if manufacturing component quantity not available. """,
    'author': 'BrowseInfo',
    'website': 'https://www.browseinfo.in',
    "price": 39,
    "currency": 'EUR',
    'depends': ['base', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/bulk_mo_produce_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    "live_test_url":'https://youtu.be/4rXm7zJtfiY',
    "images":["static/description/Banner.gif"],
    'license': 'OPL-1',
}
