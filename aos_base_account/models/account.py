
import json

from odoo import api, fields, models, _
from datetime import datetime 
from odoo.tools.misc import formatLang

# class AccountJournal(models.Model):
#     _inherit = "account.journal"
#     
#     def _kanban_dashboard_graph(self):
#         for journal in self:
#             if (journal.type in ['sale', 'purchase', 'sale_refund', 'purchase_refund', 'sale_advance', 'purchase_advance']):
#                 journal.kanban_dashboard_graph = json.dumps(journal.get_bar_graph_datas())
#             elif (journal.type in ['cash', 'bank']):
#                 journal.kanban_dashboard_graph = json.dumps(journal.get_line_graph_datas())
#             else:
#                 journal.kanban_dashboard_graph = False
#             
#     type = fields.Selection(selection_add=[
#             ('sale_refund', 'Sale Refund'),
#             ('purchase_refund', 'Purchase Refund'),
#             ('sale_advance', 'Advance Sale'),
#             ('purchase_advance', 'Advance Purchase')])
#     
#     def _graph_title_and_key(self):
#         if self.type in ['sale','sale_refund','sale_advance']:
#             return ['', _('Sales: Untaxed Total')]
#         elif self.type in ['purchase','purchase_refund','purchase_advance']:
#             return ['', _('Purchase: Untaxed Total')]
#         elif self.type == 'cash':
#             return ['', _('Cash: Balance')]
#         elif self.type == 'bank':
#             return ['', _('Bank: Balance')]
#     
#     
#     def get_journal_dashboard_datas(self):
#         currency = self.currency_id or self.company_id.currency_id
#         number_to_reconcile = number_to_check = last_balance = account_sum = 0
#         title = ''
#         number_draft = number_waiting = number_late = to_check_balance = 0
#         sum_draft = sum_waiting = sum_late = 0.0
#         if self.type in ['bank', 'cash']:
#             last_bank_stmt = self.env['account.bank.statement'].search([('journal_id', 'in', self.ids)], order="date desc, id desc", limit=1)
#             last_balance = last_bank_stmt and last_bank_stmt[0].balance_end or 0
#             #Get the number of items to reconcile for that bank journal
#             self.env.cr.execute("""SELECT COUNT(DISTINCT(line.id))
#                             FROM account_bank_statement_line AS line
#                             LEFT JOIN account_bank_statement AS st
#                             ON line.statement_id = st.id
#                             WHERE st.journal_id IN %s AND st.state = 'open' AND line.amount != 0.0 AND line.account_id IS NULL
#                             AND not exists (select 1 from account_move_line aml where aml.statement_line_id = line.id)
#                         """, (tuple(self.ids),))
#             number_to_reconcile = self.env.cr.fetchone()[0]
#             to_check_ids = self.to_check_ids()
#             number_to_check = len(to_check_ids)
#             to_check_balance = sum([r.amount for r in to_check_ids])
#             # optimization to read sum of balance from account_move_line
#             account_ids = tuple(ac for ac in [self.default_debit_account_id.id, self.default_credit_account_id.id] if ac)
#             if account_ids:
#                 amount_field = 'aml.balance' if (not self.currency_id or self.currency_id == self.company_id.currency_id) else 'aml.amount_currency'
#                 query = """SELECT sum(%s) FROM account_move_line aml
#                            LEFT JOIN account_move move ON aml.move_id = move.id
#                            WHERE aml.account_id in %%s
#                            AND move.date <= %%s AND move.state = 'posted';""" % (amount_field,)
#                 self.env.cr.execute(query, (account_ids, fields.Date.context_today(self),))
#                 query_results = self.env.cr.dictfetchall()
#                 if query_results and query_results[0].get('sum') != None:
#                     account_sum = query_results[0].get('sum')
#         #TODO need to check if all invoices are in the same currency than the journal!!!!
#         #elif self.type in ['sale', 'purchase']:
#         elif self.type in ['sale', 'purchase', 'sale_advance', 'purchase_advance', 'sale_refund', 'purchase_refund']:
#             title = _('Bills to pay') if self.type == 'purchase' else _('Invoices owed to you')
#             self.env['account.move'].flush(['amount_residual', 'currency_id', 'type', 'invoice_date', 'company_id', 'journal_id', 'date', 'state', 'payment_state'])
# 
#             (query, query_args) = self._get_open_bills_to_pay_query()
#             self.env.cr.execute(query, query_args)
#             query_results_to_pay = self.env.cr.dictfetchall()
# 
#             (query, query_args) = self._get_draft_bills_query()
#             self.env.cr.execute(query, query_args)
#             query_results_drafts = self.env.cr.dictfetchall()
# 
#             today = fields.Date.today()
#             query = '''
#                 SELECT
#                     (CASE WHEN type IN ('out_refund', 'in_refund') THEN -1 ELSE 1 END) * amount_residual AS amount_total,
#                     currency_id AS currency,
#                     type,
#                     invoice_date,
#                     company_id
#                 FROM account_move move
#                 WHERE journal_id = %s
#                 AND date <= %s
#                 AND state = 'posted'
#                 AND payment_state = 'not_paid'
#                 AND type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt');
#             '''
#             self.env.cr.execute(query, (self.id, today))
#             late_query_results = self.env.cr.dictfetchall()
#             curr_cache = {}
#             (number_waiting, sum_waiting) = self._count_results_and_sum_amounts(query_results_to_pay, currency, curr_cache=curr_cache)
#             (number_draft, sum_draft) = self._count_results_and_sum_amounts(query_results_drafts, currency, curr_cache=curr_cache)
#             (number_late, sum_late) = self._count_results_and_sum_amounts(late_query_results, currency, curr_cache=curr_cache)
#             read = self.env['account.move'].read_group([('journal_id', '=', self.id), ('to_check', '=', True)], ['amount_total'], 'journal_id', lazy=False)
#             if read:
#                 number_to_check = read[0]['__count']
#                 to_check_balance = read[0]['amount_total']
#         elif self.type == 'general':
#             read = self.env['account.move'].read_group([('journal_id', '=', self.id), ('to_check', '=', True)], ['amount_total'], 'journal_id', lazy=False)
#             if read:
#                 number_to_check = read[0]['__count']
#                 to_check_balance = read[0]['amount_total']
# 
#         difference = currency.round(last_balance-account_sum) + 0.0
# 
#         is_sample_data = self.kanban_dashboard_graph and any(data.get('is_sample_data', False) for data in json.loads(self.kanban_dashboard_graph))
# 
#         return {
#             'number_to_check': number_to_check,
#             'to_check_balance': formatLang(self.env, to_check_balance, currency_obj=currency),
#             'number_to_reconcile': number_to_reconcile,
#             'account_balance': formatLang(self.env, currency.round(account_sum) + 0.0, currency_obj=currency),
#             'last_balance': formatLang(self.env, currency.round(last_balance) + 0.0, currency_obj=currency),
#             'difference': formatLang(self.env, difference, currency_obj=currency) if difference else False,
#             'number_draft': number_draft,
#             'number_waiting': number_waiting,
#             'number_late': number_late,
#             'sum_draft': formatLang(self.env, currency.round(sum_draft) + 0.0, currency_obj=currency),
#             'sum_waiting': formatLang(self.env, currency.round(sum_waiting) + 0.0, currency_obj=currency),
#             'sum_late': formatLang(self.env, currency.round(sum_late) + 0.0, currency_obj=currency),
#             'currency_id': currency.id,
#             'bank_statements_source': self.bank_statements_source,
#             'title': title,
#             'is_sample_data': is_sample_data,
#         }
    
class AccountMove(models.Model):
    _inherit = "account.move"
    
    attn = fields.Char('Attention',size=64)
    signature = fields.Char('Signature', size=64)
    journal_bank_id = fields.Many2one('account.journal', string='Payment Method', domain=[('type', 'in', ('cash','bank'))])
    
    def action_unlink(self):
        for move in self:
            move.unlink()
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['context'] = dict(self.env.context)
        action['context']['default_type'] = 'entry'
        action['context']['search_default_misc_filter'] = 1
        action['context']['view_no_maturity'] = True
        action['views'] = [(self.env.ref('account.view_invoice_tree').id, 'tree')]
        return action
    
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    def _get_price_tax(self):
        for l in self:
            l.price_tax = l.price_total - l.price_subtotal
            
    price_tax = fields.Monetary(string='Tax Amount', compute='_get_price_tax', currency_field='currency_id')
    
    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type):
        res = super(AccountMoveLine, self)._get_price_total_and_subtotal_model(price_unit=price_unit, quantity=quantity, discount=discount, currency=currency, product=product, partner=partner, taxes=taxes, move_type=move_type)
        if taxes:
            res['price_tax'] = res['price_total'] - res['price_subtotal']
        else:
            res['price_tax'] = 0.0
        return res
    
    @api.model
    def _compute_amount_fields(self, amount, src_currency, company_currency):
        """ Helper function to compute value for fields debit/credit/amount_currency based on an amount and the currencies given in parameter"""
        amount_currency = False
        currency_id = False
        date = self.env.context.get('date') or fields.Date.today()
        company = self.env.context.get('company_id')
        company = self.env['res.company'].browse(company) if company else self.env.user.company_id
        if src_currency and src_currency != company_currency:
            amount_currency = amount
            amount = src_currency._convert(amount, company_currency, company, date)
            currency_id = src_currency.id
        debit = amount > 0 and amount or 0.0
        credit = amount < 0 and -amount or 0.0
        return debit, credit, amount_currency, currency_id