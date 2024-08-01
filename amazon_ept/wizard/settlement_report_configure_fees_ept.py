# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class to configure the settlement report fees and added class to relate with the
settlement and configure the report lines.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SettlementReportConfigureFeesEPT(models.TransientModel):
    """
    Added class to configure the settlement report fees.
    """
    _name = "settlement.report.configure.fees.ept"
    _description = "Configure Fees in Settlement Report"

    settlement_report_configure_line_ids = fields.One2many(
        'settlement.report.configure.fees.lines.ept',
        'settlement_configure_fee_id',
        string="Configure Fees Lines")

    @api.model
    def default_get(self, field):
        """
        Load data in wizard of Missing Configure Fees
        @author: Deval Jagad (19/12/2019)
        """
        res = super(SettlementReportConfigureFeesEPT, self).default_get(field)
        transaction_type_obj = self.env['amazon.transaction.type']
        settlement = self._context.get('settlement_id', False)
        settlement_id = self.env['settlement.report.ept'].browse(settlement)
        amazon_code_list = settlement_id.statement_id.line_ids.filtered(
            lambda x: x.amazon_code and not x.is_reconciled).mapped('amazon_code')
        statement_amazon_code = amazon_code_list and list(set(amazon_code_list))
        transaction_amazon_code_list = settlement_id.seller_id.transaction_line_ids.filtered(
            lambda x: x.amazon_code).mapped('amazon_code')
        transaction_amazon_code = transaction_amazon_code_list and list(
            set(transaction_amazon_code_list))
        missing_account_id_list = settlement_id.seller_id.transaction_line_ids.filtered(
            lambda l: not l.account_id).mapped('amazon_code')

        unavailable_amazon_code = [code for code in statement_amazon_code if
                                   code not in transaction_amazon_code
                                   or code in missing_account_id_list]
        result_data = []
        for amazon_code in unavailable_amazon_code:
            vals = {'amazon_code': amazon_code}
            transaction_type_id = transaction_type_obj.search([('amazon_code', '=', amazon_code)])
            if transaction_type_id:
                vals.update({'transaction_type_id': transaction_type_id.id,
                             'is_reimbursement': transaction_type_id.is_reimbursement or False})
            result_data.append((0, 0, vals))
        if not result_data:
            raise UserError(
                _("All Fees are Configure for this %s Settlement Report" % (settlement_id.name)))
        res.update({'settlement_report_configure_line_ids': result_data})
        return res

    def get_amazon_transaction_type(self, trans_type_id, amazon_code):
        """
        This method search and create the amazon transaction type.
        """
        transaction_type_obj = self.env['amazon.transaction.type']
        if not trans_type_id:
            trans_type = transaction_type_obj.search([('amazon_code', '=', amazon_code)])
            if trans_type:
                trans_type_id = trans_type
            else:
                trans_type_id = transaction_type_obj.create(
                    {'name': amazon_code, 'amazon_code': amazon_code})
        return trans_type_id

    def get_amazon_transaction_line(self, seller_id, amazon_code, values):
        """
        This method search and create the amazon transaction line.
        """
        transaction_line_obj = self.env['amazon.transaction.line.ept']
        line_id = transaction_line_obj.search(
            [('amazon_code', '=', amazon_code), ('seller_id', '=', seller_id)])
        if not line_id:
            transaction_line_obj.create(values)
        return line_id

    @staticmethod
    def update_transaction_line_vals(tax_id, values, analytic_account_id):
        """
        This method will set the tax and analytical account into the transaction line
        :param tax_id: account.tax()
        :param values: dict {}
        :param analytic_account_id: account.analytic.account()
        :return: dict {}
        """
        if tax_id:
            values.update({'tax_id': tax_id})
        if analytic_account_id:
            values.update({'analytic_account_id': analytic_account_id})
        return values

    def configure_settlement_report_fees(self):
        """
        Save Data of Amazon Transaction Type and Amazon Transaction Type Line from load data
        @author: Deval Jagad (19/12/2019)
        # Search for amazon code in transaction type.
        # If found then get or set it's transaction type id else create new transaction type.
        """
        settlement = self._context.get('settlement_id', False)
        settlement_id = self.env['settlement.report.ept'].browse(settlement)
        seller_id = settlement_id.seller_id.id
        for configure_line in self.settlement_report_configure_line_ids:
            amazon_code = configure_line.amazon_code
            account_id = configure_line.account_id.id
            if not account_id:
                continue
            tax_id = configure_line.tax_id.id if configure_line.tax_id else False
            analytic_account_id = configure_line.analytic_account_id.id if configure_line.analytic_account_id else False
            trans_type_id = configure_line.transaction_type_id or False
            is_reimbursement = configure_line.is_reimbursement or False
            if amazon_code:
                values = {'amazon_code': amazon_code, 'seller_id': seller_id, 'account_id': account_id}
                trans_type_id = self.get_amazon_transaction_type(trans_type_id, amazon_code)
                trans_type_id.write({'is_reimbursement': is_reimbursement})
                values.update({'transaction_type_id': trans_type_id.id})
                values = self.update_transaction_line_vals(tax_id, values, analytic_account_id)
                line_id = self.get_amazon_transaction_line(seller_id, amazon_code, values)
                line_id.write({'account_id': account_id, 'tax_id': tax_id, 'analytic_account_id': analytic_account_id})
        return True


class SettlementReportConfigureFeesLineEPT(models.TransientModel):
    """
    Added class to configure the settlement report lines with details amazon code, Reimbursement,
    transaction type, account and others
    """
    _name = "settlement.report.configure.fees.lines.ept"
    _description = "Settlement Report Configuration Fee Line"

    amazon_code = fields.Char()
    transaction_type_id = fields.Many2one("amazon.transaction.type", string="Transaction Type")
    account_id = fields.Many2one("account.account", string="Account")
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account',
                                          help='Analytic Account')
    tax_id = fields.Many2one("account.tax", string="Tax")
    is_reimbursement = fields.Boolean("Reimbursement", default=False)
    settlement_configure_fee_id = fields.Many2one("settlement.report.configure.fees.ept",
                                                  string="Settlement Report Configure Fee")
