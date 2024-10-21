# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Inherited class stock location route
"""

from odoo import models, fields


class StockLocationRoute(models.Model):
    """
    inherited class to add is_removal_order boolean.
    """
    _inherit = "stock.route"

    is_removal_order = fields.Boolean("Is Removal Order ?", default=False)
