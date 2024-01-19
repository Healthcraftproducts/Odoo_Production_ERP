# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
"""
Added class to store the amazon product search term.
"""

from odoo import models, fields


class AmazonProductSearchTerm(models.Model):
    """
    Added class to relate with the amazon product search term and relate with the amazon
    product.
    """
    _name = "amazon.product.search.term"
    _description = 'amazon.product.search.term'

    amazon_product_id = fields.Many2one('amazon.product.ept', string="Amazon Product")
    name = fields.Char(string="Search Term", size=200)
