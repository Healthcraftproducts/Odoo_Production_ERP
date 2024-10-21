"""
This File will perform the settlement report's  bank statement operations and inherited
methods to update the settlement report state when bank statement state is updated.
"""

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
SETTLEMENT_REPORT_EPT = 'settlement.report.ept'



class AccountBankStatement(models.Model):
    """
    Inherited AccountBankStatement class to process settlement report's statement
    """
    _inherit = 'account.bank.statement'

    settlement_ref = fields.Char(size=350, string='Amazon Settlement Ref')

    @api.depends('line_ids.journal_id')
    def _compute_journal_id(self):
        """
        Override this method because some time in the settlement report total amount is zero
        so when we create account bank statement odoo default _compute_journal_id() method call and
        set statement.line_ids.journal_id in the bank statement but when we create only bank statement
        there is no any statement lines so it set journal_id False in the bank statement and it's crates
        issue later on other amazon transaction bank statement lines process.
        :Note: Here journal_id in the statement and bank statement lines is same
        :return:
        """
        for statement in self:
            statement.journal_id = statement.line_ids.journal_id or statement.journal_id

    def button_validate_or_action(self):
        """
        Migration done by twinkalc on 28 sep, 2020,Inherited to update the state of settlement
        report to validated.
        """
        if self.settlement_ref:
            settlement = self.env[SETTLEMENT_REPORT_EPT].search([('statement_id', '=', self.id)])
            settlement.write({'state': 'confirm'})
        return super(AccountBankStatement, self).button_validate_or_action()

    def button_reprocess(self):
        """
        Added by twinkalc on 28 sep, 2020, Inherited to update the state of settlement report to
        processed if bank statement is reprocessed.
        """
        if self.settlement_ref:
            settlement = self.env[SETTLEMENT_REPORT_EPT].search([('statement_id', '=', self.id)])
            settlement.write({'state': 'processed'})
        return super(AccountBankStatement, self).button_reprocess()

    def button_reopen(self):
        """
        Added by twinkalc on 28 sep, 2020,Inherited to update the state of settlement report to
        imported if bank statement is reopened.

        Updated code by twinkalc on 22 March to delete an reimbusement invoice line and set state
        to draft during statement is reopened.
        """
        if self.settlement_ref:
            settlement = self.env[SETTLEMENT_REPORT_EPT].search([('statement_id', '=', self.id)])
            settlement.write({'state': 'imported'})
        return super(AccountBankStatement, self).button_reopen()
