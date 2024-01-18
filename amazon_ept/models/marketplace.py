# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class to  and fields to store the Amazon Marketplace Details.
"""
from odoo import models, fields, api


class AmazonMarketplaceEpt(models.Model):
    """
    Added class to store Amazon Marketplace Details and find instance based on marketplace
    """
    _name = "amazon.marketplace.ept"
    _description = 'Amazon Marketplace Details'

    name = fields.Char(size=120, required=True)
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller')
    market_place_id = fields.Char("Marketplace")
    is_participated = fields.Boolean("Marketplace Participation")
    country_id = fields.Many2one('res.country', string='Country')
    amazon_domain = fields.Char(size=120)
    currency_id = fields.Many2one('res.currency', string='Currency')
    lang_id = fields.Many2one('res.lang', string='Language')
    domain = fields.Char()

    @api.model
    def find_instance(self, seller, sales_channel):
        """
        Find Amazon Instance from seller_id and and Marketplace
        :param seller:
        :param sales_channel:
        :return: amazon.instance.ept()
        """

        amazon_instance_ept_obj = self.env['amazon.instance.ept']
        marketplace = self.search([('seller_id', '=', seller.id), ('name', '=', sales_channel)])
        if marketplace:
            instance = amazon_instance_ept_obj.search( \
                [('seller_id', '=', seller.id), ('marketplace_id', '=', marketplace[0].id)])
            return instance and instance[0]
        return amazon_instance_ept_obj
