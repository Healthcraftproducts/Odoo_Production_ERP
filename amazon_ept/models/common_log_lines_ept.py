# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Inherited class to create log lines and relate with the queue log record
"""
from odoo import models, fields


class CommonLogLineEpt(models.Model):
    """
    Inherited class to add common method to create order and product log lines and relate with
    the order queue
    """
    _inherit = "common.log.lines.ept"
    _rec_name = "log_book_id"

    order_queue_data_id = fields.Many2one('shipped.order.data.queue.ept', string='Shipped Order Data Queue')
    fulfillment_by = fields.Selection([('FBA', 'Amazon Fulfillment Network'), ('FBM', 'Merchant Fullfillment Network')],
                                      string="Fulfillment By", help="Fulfillment Center by Amazon or Merchant")
    product_title = fields.Char(string="Product Title", default=False, help="Product Title")
    amz_instance_ept = fields.Many2one(comodel_name='amazon.instance.ept', string="Amazon Instance")
    amz_seller_ept = fields.Many2one(comodel_name='amazon.seller.ept', string="Amazon Seller")

    def amz_find_mismatch_details_log_lines(self, res_id, model_name, mismatch=False):
        """
        This method will search the mismatch details log lines based on resource id.
        :param: res_id : int
        :param: model_name: str
        :return: list of common.log.lines.ept() objects or []
        """
        model = self._get_model_id(model_name)
        domain = [('model_id', '=', model.id if model else False), ('res_id', '=', res_id)]
        if mismatch:
            domain.append(('mismatch_details', '=', True))
        return self.search(domain)
