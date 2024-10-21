# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class of shipped order data queue line to store the shipped order data in lines and
store the order details line instance, order id, state, last processed date and etc.
"""

from odoo import models, fields


class ShippedOrderDataQueueLine(models.Model):
    """
    Added class to store the shipped order data and relate with the shipped queue.
    """
    _name = "shipped.order.data.queue.line.ept"
    _description = 'Shipped Order Data Queue Line Ept'

    amz_instance_id = fields.Many2one('amazon.instance.ept', string='Marketplace',
                                      help="Amazon Instance")
    order_id = fields.Char()
    order_data_id = fields.Char()
    state = fields.Selection([('draft', 'Draft'), ('failed', 'Failed'), ('done', 'Done')],
                             default='draft')
    last_process_date = fields.Datetime(readonly=True)
    shipped_order_data_queue_id = fields.Many2one('shipped.order.data.queue.ept',
                                                  string='Shipped Order Data Queue',
                                                  required=True, ondelete='cascade', copy=False)
