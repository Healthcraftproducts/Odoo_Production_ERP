# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Inherited ProcurementGroup class to relate with the removal order and inbound shipment.
"""

from odoo import models, fields


class ProcurementGroup(models.Model):
    """
    Inherited ProcurementGroup class to store the removal and shipment ref in group
    """
    _inherit = 'procurement.group'

    removal_order_id = fields.Many2one('amazon.removal.order.ept', string='Removal Order')
    odoo_shipment_id = fields.Many2one('amazon.inbound.shipment.ept', string='Shipment')
