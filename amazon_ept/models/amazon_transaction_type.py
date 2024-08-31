# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
created class of amazon transaction type to store the amazon transaction type which is used in
process of settlement report added constraint to add unique Amazon Transaction type by seller
"""

from odoo import models, fields


class AmazonTransactionType(models.Model):
    """
    Added class to store the amazon transaction type details
    """
    _name = "amazon.transaction.type"
    _description = 'amazon.transaction.type'

    name = fields.Char(size=256)
    amazon_code = fields.Char(size=256, string='Transaction Code')
    is_reimbursement = fields.Boolean("REIMBURSEMENT ?", default=False)

    _sql_constraints = [('amazon_transaction_type_unique_constraint', 'unique(amazon_code)',
                         "Amazon Transaction type must be unique by Amazon Code.")]
