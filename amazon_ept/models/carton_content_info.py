# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class to store the amazon carton details and added fields
"""
from odoo import models, fields


class CartonContentInfo(models.Model):
    """
    Added class to store the amazon carton details (amazon product, pkg information, seller, and
    quantity)
    """
    _name = "amazon.carton.content.info.ept"
    _description = 'amazon.carton.content.info.ept'

    package_id = fields.Many2one("stock.quant.package", string="Package")
    amazon_product_id = fields.Many2one("amazon.product.ept", string="Amazon Product")
    seller_sku = fields.Char(size=120, related="amazon_product_id.seller_sku", readonly=True)
    quantity = fields.Float("Carton Qty", digits=(16, 2))
