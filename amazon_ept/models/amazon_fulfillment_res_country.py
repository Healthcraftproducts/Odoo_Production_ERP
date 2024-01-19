# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class and fields to relate fulfillment code with the country.
"""
from odoo import fields, api, models


class AmazonFulfillmentCenter(models.Model):
    """
    Added class to relate fulfillment code with the country
    """
    _name = "amazon.fulfillment.country.rel"
    _description = 'amazon.fulfillment.country.rel'

    fulfillment_code = fields.Char(string="Fulfillment Center Code")
    country_id = fields.Many2one('res.country', string="Fulfillment Country Id")

    @api.model
    def load_fulfillment_code(self, country, seller_id, warehouse_id):
        """
        This method is used to create the fulfillment center
        """
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        fulfillment_codes = country.fulfillment_code_ids
        for fulfillment in fulfillment_codes:
            fulfillment_center_obj.create( \
                {'center_code': fulfillment.fulfillment_code,
                 'seller_id': seller_id,
                 'warehouse_id': warehouse_id
                 })
        return True

class ResCountry(models.Model):
    """
    Inherited class to relate the country with the fulfillment center
    """
    _inherit = "res.country"

    fulfillment_code_ids = fields.One2many('amazon.fulfillment.country.rel', 'country_id',
                                           string="Fulfillment Center code")
