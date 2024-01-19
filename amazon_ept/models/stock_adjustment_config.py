# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class to send mail and config the mail template with the reason to adjust the inventory.
"""

from odoo import models, fields


class AmazonStockAdjustmentConfig(models.Model):
    """
    Added class to add stock adjustment config for adjust the stock.
    """
    _name = "amazon.stock.adjustment.config"
    _description = "Amazon Stock Adjustment Config"

    def _get_email_template(self):
        """
        Get email template for stock adjustment report
        :return: template id
        """
        template = self.env.ref('amazon_ept.email_template_amazon_stock_adjustment_email_ept', raise_if_not_found=False)
        return template.id if template else False

    group_id = fields.Many2one("amazon.adjustment.reason.group", string="Group")
    seller_id = fields.Many2one("amazon.seller.ept", string="Seller")
    location_id = fields.Many2one("stock.location", string="Location")
    is_send_email = fields.Boolean("Is Send Email ?", default=False)
    email_template_id = fields.Many2one("mail.template", string="Email Template", default=_get_email_template)

    _sql_constraints = [('amazon_stock_adjustment_unique_constraint', 'unique(group_id,seller_id)',
                         "Group must be unique per seller")]
