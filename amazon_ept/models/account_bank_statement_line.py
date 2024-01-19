"""
Added this file because want to add field in bank statement line.
"""

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class AccountBankStatementLine(models.Model):
    """
    Inherited this call to add the amazon code in bank statement line.
    """
    _inherit = "account.bank.statement.line"

    amazon_code = fields.Char("Amazon Statement Line Code")
    reimbursement_invoice_id = fields.Many2one('account.move')
