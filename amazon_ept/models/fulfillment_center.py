# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added Amazon Fulfillment center class to store the amazon center details
"""
from odoo import models, fields, api


class AmazonFulfillmentCenter(models.Model):
    """
    Added class to store the fulfillment center details
    """
    _name = "amazon.fulfillment.center"
    _description = 'amazon.fulfillment.center'
    _rec_name = 'center_code'

    @api.depends('warehouse_id', 'warehouse_id.seller_id')
    def _compute_seller_id(self):
        if self.warehouse_id and self.warehouse_id.seller_id:
            self.seller_id = self.warehouse_id.seller_id.id

    center_code = fields.Char(size=50, string='Fulfillment Center Code', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller', compute="_compute_seller_id", store=True,
                                readonly=True)

    _sql_constraints = [('fulfillment_center_unique_constraint', 'unique(seller_id,center_code)',
                         "Fulfillment center must be unique by seller.")]

    @api.model
    def _map_amazon_fulfillment_centers_warehouse(self, seller, fulfillment_centers):
        """
        Map New Fulfillment centers to amazon warehouses
        when 'sync fulfilment center' button clicked form amazon configuration settings.
        :return:
        """
        fba_wh_ids = seller.amz_warehouse_ids.filtered(lambda l: l.is_fba_warehouse)
        fc_available = self.search([('seller_id', '=', seller.id)]).mapped('center_code')
        for fba_wh in fba_wh_ids:
            wh_country = fba_wh.partner_id and fba_wh.partner_id.country_id or \
                         fba_wh.company_id and fba_wh.company_id.partner_id and fba_wh.company_id.partner_id.country_id
            country_code = wh_country.code
            if not fulfillment_centers.get(country_code):
                continue
            fc_codes = fulfillment_centers.get(country_code)
            for fulfillment in fc_codes:
                try:
                    if fulfillment not in fc_available:
                        self.create({
                            'center_code': fulfillment,
                            'seller_id': seller.id,
                            'warehouse_id': fba_wh.id
                        })
                        fc_available.append(fulfillment)
                except:
                    continue
