# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016-Today Geminate Consultancy Services (<http://geminatecs.com>).
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
    'name' : 'Partial Independent Work Order Process',
    'version' : '16.0.0.1',
    'author': 'Geminate Consultancy Services',
    'company': 'Geminate Consultancy Services',
    'category': 'Manufacturing',
    'website': 'https://www.geminatecs.com/',
    'summary' : 'Partial Independent Work Order Process',
    'description' : """Geminate comes with the features of Partial Independent Work Order Process. By the use of this feature, you can partially do the manufacturing process at work order level without generating a backorder. the beauty of this feature is, it allows you to process any workorder with partial quantity regardless of the sequence of chained work orders based on route or work centers. Now you can partially process work orders without creating backorders, so it will save time and make it easier to process your manufacturing orders.""",
    "license": "Other proprietary",
    'depends' : ['mrp','stock','mrp_workorder','mrp_account'],
    'data' : [
    ],
    'images':['static/description/poster.png'],
    'demo': [],
    'installable' : True,
    'application' : False,
    'price': 149.99,
    'currency': 'EUR'
}
