# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Inherited rating class to relate with the amazon rating report and added methods return
the action of the amazon instance and amazon seller.
"""

from odoo import models, fields


class Rating(models.Model):
    """
    Inherited rating class to relate with the amazon rating report.
    """
    _inherit = "rating.rating"

    amz_instance_id = fields.Many2one('amazon.instance.ept', string='Marketplace',
                                      help="Amazon Instance")
    amz_fulfillment_by = fields.Selection(
        [('FBA', 'Amazon Fulfillment Network'), ('FBM', 'Merchant Fulfillment Network')],
        string="Fulfillment By", help="Fulfillment Center by Amazon or Merchant")
    amz_rating_report_id = fields.Many2one("rating.report.history",
                                           "Amazon Rating Report History")
    amz_rating_submitted_date = fields.Date("Amazon Rating Submitted Date", readonly=True)

    publisher_comment = fields.Text()

    def action_open_rated_instance_object(self):
        """
        This method will return the action of the amazon instance.
        """
        return {
            'name': 'Amazon Rating Instance',
            'type': 'ir.actions.act_window',
            'res_model': 'amazon.instance.ept',
            'domain': "[('id', 'in', " + str(self.amz_instance_id.ids) + " )]",
            'view_mode': 'tree,form',
        }

    def action_open_rated_seller_object(self):
        """
        This method will return the action of Amazon Seller.
        """
        return {
            'name': 'Amazon Rating Seller',
            'type': 'ir.actions.act_window',
            'res_model': 'amazon.seller.ept',
            'domain': "[('id', 'in', " + str(self.amz_instance_id.seller_id.ids) + " )]",
            'view_mode': 'tree,form',}
