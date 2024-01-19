# -*- coding: utf-8 -*-pack
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Defined class of amazon return reason.
"""

from odoo import models, fields


class AmazonReturnReasonEpt(models.Model):
    """
    Added class to define the amazon return reason.
    """
    _name = "amazon.return.reason.ept"
    _description = "Amazon Return Reasons"

    name = fields.Char(required=True)
    description = fields.Char(help="Description")
    is_reimbursed = fields.Boolean("Is Reimbursed ?", default=False, help="Is Reimbursed?")
