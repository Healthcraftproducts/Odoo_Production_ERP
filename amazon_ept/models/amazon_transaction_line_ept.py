# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class to configure the amazon seller transaction type
"""
from odoo import models, fields, api


class AmazonTransactionLineEpt(models.Model):
    """
    Added class to store the configured transaction line data
    """
    _name = "amazon.transaction.line.ept"
    _description = 'amazon.transaction.line.ept'

    @api.depends('transaction_type_id')
    def _compute_get_transaction_code(self):
        for record in self:
            record.amazon_code = record.transaction_type_id.amazon_code

    transaction_type_id = fields.Many2one('amazon.transaction.type', string="Transaction Type")
    seller_id = fields.Many2one('amazon.seller.ept', string="Seller")
    amazon_code = fields.Char(compute="_compute_get_transaction_code", store=True)
    account_id = fields.Many2one('account.account', string="Account")
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', help='Analytic Account')
    tax_id = fields.Many2one('account.tax', string="Tax")

    _sql_constraints = [('amazon_transaction_unique_constraint',
                         'unique(seller_id,transaction_type_id)',
                         "Transaction type must be unique by seller.")]
