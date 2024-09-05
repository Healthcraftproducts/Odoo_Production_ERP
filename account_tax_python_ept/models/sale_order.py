from odoo import models, fields, api
import json

class sale_order(models.Model):
    _inherit = "sale.order"

    @api.depends('order_line.tax_id', 'order_line.price_unit', 'amount_total', 'amount_untaxed',
                 'order_line.line_tax_amount_percent')
    def _compute_tax_totals(self):
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type)

            # Ensure currency_id is evaluated as a singleton
            currency = order.currency_id or order.company_id.currency_id
            currency.ensure_one()  # Ensure it's a singleton

            order.tax_totals = self.env['account.tax']._prepare_tax_totals(
                [x.with_context({'tax_computation_context': {
                    'line_tax_amount_percent': x.line_tax_amount_percent
                }})._convert_to_tax_base_line_dict() for x in order_lines],
                currency
            )

