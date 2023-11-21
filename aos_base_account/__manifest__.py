# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2017 Alphasoft
#    (<https://www.alphasoft.co.id/>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Account Base',
    'version': '16.0.0.1.0',
    'license': 'OPL-1',
    'author': "Alphasoft",
    'sequence': 1,
    'website': 'https://www.alphasoft.co.id/',
    'images':  ['images/main_screenshot.png'],
    'category': 'Hidden',
    'summary': 'Advance of a module by Alphasoft',
    'depends': ['account'],
    'description': """
Module based on Ade Anshori
=====================================================
* Create Groups Account
* Multi to Draft Invoice
* Multi Unposted Journal Entries
""",
    'demo': [],
    'test': [],
    'data': [
        #'security/account_security.xml',
        'views/menuitem_view.xml',
        #'views/account_journal_dashboard_view.xml',
        #'views/account_journal_view.xml',
        #'views/account_invoice_view.xml',
        'wizard/unpost_account_move_view.xml',
     ],
    'css': [],
    'js': [],
    'price': 35.00,
    'currency': 'EUR',
    'installable': True,
    'application': False,
    'auto_install': False,
    #'uninstall_hook': "uninstall_hook",
}
