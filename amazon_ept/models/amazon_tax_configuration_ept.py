# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added tax config class and added constraint to add unique tax config with country and is outside
eu for seller
"""

from odoo import models, fields


class AmazonTaxConfigurationEpt(models.Model):
    """
    Added class to config the amazon tax for seller
    """
    _name = 'amazon.tax.configuration.ept'
    _description = 'Amazon Tax Configuration'

    seller_id = fields.Many2one('amazon.seller.ept')
    tax_id = fields.Many2one('account.tax', string="Tax")
    is_outside_eu = fields.Boolean(string="Is Outside EU ?")
    jurisdiction_country_id = fields.Many2one('res.country', string="Jurisdiction Country")

    _sql_constraints = [
        ("amazon_tax_configuration_unique_co",
         "UNIQUE(seller_id,is_outside_eu,jurisdiction_country_id)",
         "Jurisdiction Country and Is Outside EU? must be unique for Seller.")]
