# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import http, _
from odoo.http import request
from odoo.modules.module import get_resource_path
from odoo.osv import expression
from odoo.tools import pdf, split_every
from odoo.tools.misc import file_open

from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController

class CustomStockBarcodeController(StockBarcodeController):

    def _get_groups_data(self):
        return {
            'group_stock_multi_locations': request.env.user.has_group('stock.group_stock_multi_locations'),
            'group_tracking_owner': request.env.user.has_group('stock.group_tracking_owner'),
            'group_tracking_lot': request.env.user.has_group('stock.group_tracking_lot'),
            'group_production_lot': request.env.user.has_group('stock.group_production_lot'),
            'group_uom': request.env.user.has_group('uom.group_uom'),
            'group_stock_packaging': request.env.user.has_group('product.group_stock_packaging'),
            'group_barcode_admin': request.env.user.has_group('hcp_contact_ext.custom_barcode_admin'),
        }