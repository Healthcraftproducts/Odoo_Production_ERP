# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Inherited stock inventory class to relate with the amazon instance and fba live stock report.
"""

from odoo import models, fields, api


class StockQuant(models.Model):
    """
    Inherited stock inventory class to relate with the amazon instance and fba live stock report.
    """
    _inherit = 'stock.quant'

    amazon_instance_id = fields.Many2one('amazon.instance.ept', string='Marketplace')
    fba_live_stock_report_id = fields.Many2one('amazon.fba.live.stock.report.ept',
                                               "FBA Live Inventory Report")

    def prepare_vals_for_inventory_adjustment(self, location_id, product_id, product_qty):
        """
        Prepare values for inventory adjustment
        :param location_id:stock.location id
        :param product_id:product.product id
        :param product_qty: float
        :return: dict
        """
        vals = super(StockQuant, self).prepare_vals_for_inventory_adjustment(location_id, product_id, product_qty)
        fba_live_stk_id = self._context.get('fba_live_inv_id', False)
        if vals and fba_live_stk_id:
            vals.update({'fba_live_stock_report_id': fba_live_stk_id})
        return vals

    @api.model
    def _get_inventory_fields_write(self):
        """
        Inherited the method to allow custom field while create / write stock quant
        :return: Returns a list of fields user can edit when he want to edit a quant in `inventory_mode`.
        """
        return super(StockQuant, self)._get_inventory_fields_write() + ['fba_live_stock_report_id']
