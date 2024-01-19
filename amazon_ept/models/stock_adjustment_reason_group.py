# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class to create an stock adjustment reason group.
"""

from odoo import models, fields


class AmazonAdjustmentReasonGroup(models.Model):
    """
    Added class to define the different stock adjustment reason group like
    Damaged Inventory, Misplaced and Found, s/w correction or etc.
    """
    _name = "amazon.adjustment.reason.group"
    _description = "Amazon Adjustment Reason Group"

    def _compute_is_counter_part_group(self):
        is_counter_part_group = False
        for code in self.reason_code_ids:
            if code.counter_part_id:
                is_counter_part_group = True
                break
        self.is_counter_part_group = is_counter_part_group

    name = fields.Char("Name", required=True)
    is_counter_part_group = fields.Boolean(compute="_compute_is_counter_part_group", string="Is counter Part group")
    reason_code_ids = fields.One2many('amazon.adjustment.reason.code', 'group_id', string="Reason Codes")
