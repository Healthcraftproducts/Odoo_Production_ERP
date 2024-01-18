# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
"""
Added class to store the bullet amazon product bullet description.
"""

from odoo import models, fields


class AmazonProductBulletDescription(models.Model):
    """
    Added class to relate with the amazon product bullet description and relate with the amazon
    product.
    """
    _name = "amazon.product.bullet.description"
    _description = 'amazon.product.bullet.description'

    amazon_product_id = fields.Many2one('amazon.product.ept', string="Amazon Product")
    name = fields.Text(string="Description")
