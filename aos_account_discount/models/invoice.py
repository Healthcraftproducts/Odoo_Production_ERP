# -*- coding: utf-8 -*- 
# Part of Odoo. See LICENSE file for full copyright and licensing details. 
import math
from odoo import api, fields, models, _
from datetime import datetime
from odoo.exceptions import UserError, RedirectWarning, ValidationError

def round_down(n, decimals=0):
    multiplier = 10 ** decimals
    return math.floor(n * multiplier) / multiplier

class AccountMove(models.Model):
    _inherit = 'account.move'

    # def action_post(self):
    #     # OVERRIDE
    #     self.env['account.move.line'].create(self._discount_prepare_lines_vals())
    #
    #     # Post entries.
    #     res = super(AccountMove, self).action_post()
    #     return res
    
    def _post(self, soft=True):
        # OVERRIDE

        # Don't change anything on moves used to cancel another ones.
        if self._context.get('move_reverse_cancel'):
            return super()._post(soft)

        # Create additional COGS lines for customer invoices.
        self.env['account.move.line'].create(self._discount_prepare_lines_vals())

        # Post entries.
        posted = super()._post(soft=soft)

        # Reconcile COGS lines in case of anglo-saxon accounting with perpetual valuation.
        #posted._stock_account_anglo_saxon_reconcile_valuation()
        return posted


    def button_draft(self):
        res = super(AccountMove, self).button_draft()

        # Unlink the DISC lines generated during the 'post' method.
        self.mapped('line_ids').filtered(lambda line: line.is_discount_line).unlink()
        return res

    def button_cancel(self):
        # OVERRIDE
        res = super(AccountMove, self).button_cancel()

        # Unlink the DISC lines generated during the 'post' method.
        # In most cases it shouldn't be necessary since they should be unlinked with 'button_draft'.
        # However, since it can be called in RPC, better be safe.
        self.mapped('line_ids').filtered(lambda line: line.is_discount_line).unlink()
        return res
    
    def _discount_prepare_lines_vals(self):
        lines_vals_list = []
        for move in self:
            # move = move.with_company(move.company_id)
            #
            # if not move.is_sale_document(include_receipts=True) or not move.company_id.anglo_saxon_accounting:
            #     continue
            for line in move.invoice_line_ids:
                # Retrieve accounts needed to generate the COGS.
                accounts = (
                    line.product_id.product_tmpl_id
                    #.with_context(force_company=line.company_id.id)
                    .get_product_accounts(fiscal_pos=move.fiscal_position_id)
                )
                debit_account = accounts['discount_output']
                credit_account = accounts['discount_input']
                #move_line_income = move.line_ids.filtered(lambda x: x.account_id == line.account_id)
                #print ('---',move_line_income.debit,move_line_income.credit)
                #print ('==debit_account==',debit_account,credit_account)
                #if not debit_account or not credit_account:
                #    continue

                # Compute accounting fields.
                #sign = -1 if move.move_type == 'out_refund' else 1
                price_unit = line.price_discount_untaxed
                #balance = price_unit
                #balance = sign * price_unit
                #print ('====debit_account====',price_unit,debit_account,move.move_type)
                if price_unit and debit_account and move.move_type in ('out_invoice','out_refund'):
                    sign = -1 if move.move_type == 'out_refund' else 1
                    balance = sign * price_unit
                    # Add expense account line.
                    lines_vals_list.append({
                        'name': 'Disc Sales: %s'%line.name[:64],
                        'move_id': move.id,
                        'product_id': line.product_id.id,
                        'product_uom_id': line.product_uom_id.id,
                        'quantity': 1,
                        'price_unit': price_unit * sign,
                        'debit': balance > 0.0 and balance or 0.0,
                        'credit': balance < 0.0 and -balance or 0.0,
                        'account_id': debit_account,
                        'analytic_distribution': line.analytic_distribution,
                        #'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                        'is_discount_line': True,
                        'display_type': 'cogs',
                        #'exclude_from_invoice_tab': True,
                    })
                    lines_vals_list.append({
                        'name': 'Disc Sales: %s'%line.name[:64],
                        'move_id': move.id,
                        'product_id': line.product_id.id,
                        'product_uom_id': line.product_uom_id.id,
                        'quantity': 1,
                        'price_unit': price_unit * sign,
                        'debit': balance < 0.0 and -balance or 0.0,
                        'credit': balance > 0.0 and balance or 0.0,
                        'account_id': line.account_id.id,
                        'analytic_distribution': line.analytic_distribution,
                        #'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                        'is_discount_line': True,
                        'display_type': 'cogs',
                        #'exclude_from_invoice_tab': True,
                    })
                    
                elif price_unit and credit_account and move.move_type in ('in_invoice','in_refund'):
                    sign = -1 if move.move_type == 'in_invoice' else 1
                    balance = sign * price_unit
                    # Add interim account line.
                    lines_vals_list.append({
                        'name': 'Disc Purchase: %s'%line.name[:64],
                        'move_id': move.id,
                        'product_id': line.product_id.id,
                        'product_uom_id': line.product_uom_id.id,
                        'quantity': 1,
                        'price_unit': price_unit * sign,
                        'debit': balance < 0.0 and -balance or 0.0,
                        'credit': balance > 0.0 and balance or 0.0,
                        'account_id': credit_account,
                        'analytic_distribution': line.analytic_distribution,
                        #'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                        'is_discount_line': True,
                        'display_type': 'cogs',
                        #'exclude_from_invoice_tab': True,
                    })
                    
                    # Add expense account line.
                    lines_vals_list.append({
                        'name': 'Disc Purchase: %s'%line.name[:64],
                        'move_id': move.id,
                        'product_id': line.product_id.id,
                        'product_uom_id': line.product_uom_id.id,
                        'quantity': 1,
                        'price_unit': price_unit * sign,
                        'debit': balance > 0.0 and balance or 0.0,
                        'credit': balance < 0.0 and -balance or 0.0,
                        'account_id': line.account_id.id,
                        'analytic_distribution': line.analytic_distribution,
                        #'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                        'is_discount_line': True,
                        'display_type': 'cogs',
                        #'exclude_from_invoice_tab': True,
                    })
        #print ('===lines_vals_list==',lines_vals_list)
        return lines_vals_list
    
    # def _discount_move_lines(self, i_line, move):
    #     """Return the additional move lines for sales invoices and refunds.
 
    #     i_line: An account.invoice.line object.
    #     res: The move line entries produced so far by the parent move_line_get.
    #     """
    #     inv = i_line.move_id
    #     company_currency = inv.company_id.currency_id
    #     price_discount_untaxed = i_line.price_discount_untaxed
        
    #     if inv.currency_id != company_currency:
    #         currency = inv.currency_id
    #         amount_currency = i_line._get_price(company_currency, price_discount_untaxed)
    #     else:
    #         currency = False
    #         amount_currency = False
 
    #     return self.env['product.product']._discount_move_lines(move, i_line.name, i_line.product_id, i_line.product_uom_id, 1, price_discount_untaxed, currency=currency, amount_currency=amount_currency, fiscal_position=inv.fiscal_position_id, account_analytic=i_line.analytic_account_id, analytic_tags=i_line.analytic_tag_ids)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
#     @api.model
#     def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type):
#         ''' This method is used to compute 'price_total' & 'price_subtotal'.
 
#         :param price_unit:  The current price unit.
#         :param quantity:    The current quantity.
#         :param discount:    The current discount.
#         :param currency:    The line's currency.
#         :param product:     The line's product.
#         :param partner:     The line's partner.
#         :param taxes:       The applied taxes.
#         :param move_type:   The type of the move.
#         :return:            A dictionary containing 'price_subtotal' & 'price_total'.
#         '''
#         res = {}     
#         # Compute 'price_subtotal'.
#         price_unit_wo_discount = price_unit * (1 - (discount / 100.0))
#         subtotal = quantity * price_unit_wo_discount
         
#         subtotal_undiscount = quantity * price_unit
         
#         # Compute 'price_total'.
#         res['price_undiscount'] = subtotal_undiscount
#         res['price_discount_untaxed'] = subtotal_undiscount * ((discount or 0.0) / 100.0)
#         #print ('---taxes---',taxes)
#         if taxes:
#             taxes_res = taxes._origin.compute_all(price_unit_wo_discount,
#                 quantity=quantity, currency=currency, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))
# #             taxes = taxes._origin.compute_all(res['price_discount_untaxed'],
# #                 quantity=quantity, currency=currency, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))
#             taxes_unit = taxes._origin.compute_all(price_unit,
#                 quantity=quantity, currency=currency, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))
#             res['price_subtotal'] = res['price_untaxed'] = taxes_res['total_excluded']
#             res['price_total'] = taxes_res['total_included']
#             res['price_unit_undiscount_untaxed'] = taxes_unit['total_excluded'] if taxes_unit else price_unit
#             res['price_undiscount_untaxed'] = quantity * res['price_unit_undiscount_untaxed']
#         else:
#             res['price_total'] = res['price_subtotal'] = res['price_untaxed'] = subtotal
#             res['price_unit_undiscount_untaxed'] = price_unit
#             res['price_undiscount_untaxed'] = quantity * res['price_unit_undiscount_untaxed']
#         res['price_undiscount_signed'] = res['price_undiscount_untaxed']
#         #In case of multi currency, round before it's use for computing debit credit
#         if currency:
#             res = {k: currency.round(v) for k, v in res.items()}
#         #print ('---res---',res)
#         #self.recompute_tax_line = True
#         return res
    
    @api.depends('quantity', 'discount', 'price_unit', 'tax_ids', 'currency_id')
    def _compute_undiscount_totals(self):
        for line in self:
            if line.display_type != 'product':
                line.price_undiscount = line.price_unit_undiscount_untaxed = line.price_undiscount_untaxed = line.price_untaxed = line.price_undiscount_signed = line.price_discount_untaxed = False
            # Compute 'price_subtotal'.
            line_discount_price_unit = line.price_unit * (1 - (line.discount / 100.0))
            #subtotal = line.quantity * line_discount_price_unit
            
            subtotal_undiscount = line.quantity * line.price_unit
            line.price_undiscount = subtotal_undiscount
            line.price_discount_untaxed = subtotal_undiscount * ((line.discount or 0.0) / 100.0)

            # Compute 'price_total'.
            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.price_unit_undiscount_untaxed = taxes_res['total_excluded'] if taxes_res else line.price_unit
                line.price_undiscount_untaxed = line.quantity * line.price_unit_undiscount_untaxed
            else:
                line.price_unit_undiscount_untaxed = line.price_unit
                line.price_undiscount_untaxed = line.quantity * line.price_unit_undiscount_untaxed
    
    is_discount_line = fields.Boolean('Is Discount Line')
    price_undiscount = fields.Monetary(string='Undiscount', compute='_compute_undiscount_totals', readonly=True,
        currency_field='currency_id')
    price_unit_undiscount_untaxed = fields.Monetary(string='Price Untaxed', compute='_compute_undiscount_totals', readonly=True,
        currency_field='currency_id')
    price_undiscount_untaxed = fields.Monetary(string='Undiscount Tax Basis', compute='_compute_undiscount_totals',  readonly=True,
        currency_field='currency_id')
    price_untaxed = fields.Monetary(string='Tax Basis', compute='_compute_undiscount_totals', readonly=True,
        currency_field='currency_id')
    price_undiscount_signed = fields.Monetary(string='Undiscount Amount Signed', compute='_compute_undiscount_totals', readonly=True,
        currency_field='currency_id')
    price_discount_untaxed = fields.Monetary(string='Disc Untaxed', compute='_compute_undiscount_totals', readonly=True,
        currency_field='currency_id')

        
    
