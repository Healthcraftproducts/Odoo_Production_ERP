# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class to define the different stock adjustment reason code.
"""

from odoo import models, fields


class AmazonAdjustmentReasonCode(models.Model):
    """
    Added class to define the different stock adjustment reason code.
    """
    _name = "amazon.adjustment.reason.code"
    _description = "Amazon Adjustment Reason Code"

    name = fields.Char(required=True)
    type = fields.Selection([('-', '-'), ('+', '+')])
    description = fields.Char()
    long_description = fields.Text(string="Long Description", help="Description of Amazon Adjustment Reason Code.")
    group_id = fields.Many2one("amazon.adjustment.reason.group", string="Group")
    counter_part_id = fields.Many2one("amazon.adjustment.reason.code", string="Counter Part")
    is_reimbursed = fields.Boolean(string="Is Reimbursed ?", default=False,
                                   help=" True, If used as Reimbursement adjustment code.")
