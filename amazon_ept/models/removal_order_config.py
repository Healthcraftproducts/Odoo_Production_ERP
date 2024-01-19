# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class and fields to do removal order configurations.
"""
from odoo import models, fields


class RemovalOrderConfiguration(models.Model):
    """
    Added class to do removal order configurations and added constraint to set unique
    disposition per instance.
    """
    _name = "removal.order.config.ept"
    _description = "removal.order.config.ept"
    _rec_name = "removal_disposition"

    removal_disposition = fields.Selection([('Return', 'Return'), ('Disposal', 'Disposal'),
                                            ('Liquidations', 'Liquidations')],
                                           default='Return', required=True, string="Disposition")
    picking_type_id = fields.Many2one("stock.picking.type", string="Picking Type")
    location_id = fields.Many2one("stock.location", string="Location")
    unsellable_route_id = fields.Many2one("stock.route", string="UnSellable Route")
    sellable_route_id = fields.Many2one("stock.route", string="Sellable Route")
    instance_id = fields.Many2one("amazon.instance.ept", string="Marketplace")

    _sql_constraints = [ \
        ('amazon_removal_order_unique_constraint', 'unique(removal_disposition,instance_id)',
         "Disposition must be unique per Instance.")]
