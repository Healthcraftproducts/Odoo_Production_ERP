# -*- coding: utf-8 -*-pack
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class SaleOrderLine(models.Model):
    """
    Use: Add Line tax amount in Sale Order line
    Added by: Dhaval Sanghani @Emipro Technologies
    Added on: 05-Oct-2019
    """
    _inherit = 'sale.order.line'

    line_tax_amount_percent = fields.Float(digits='Line Tax Amount',
                                           default=0.00,
                                           string="Tax Amount In Percentage(%)",
                                           help="Order line Tax")

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id',
                 'line_tax_amount_percent')
    def _compute_amount(self):
        """
        Use: Override method for Compute Line tax amount in sale order line
        Params: self => sale.order.line
        Return: {}
        Migration done by twinkalc August 2020
        """
        if sum(self.mapped('line_tax_amount_percent')) > 0:
            for line in self:
                line_tax = line.line_tax_amount_percent or 0.0
                super(SaleOrderLine, line.with_context(
                    {'tax_computation_context': {
                        'line_tax_amount_percent': line_tax}}))._compute_amount()
        else:
            return super(SaleOrderLine, self)._compute_amount()

    def _prepare_invoice_line(self, **optional_values):
        """
        Use: Inherited method for set Line tax amount in Invoice line (Account Move Line)
        from sale order line
        Params: self => sale.order.line
        Return: res => {vals}
        Migration done by twinkalc August 2020
        """
        res = super(SaleOrderLine, self)._prepare_invoice_line(
            **optional_values)
        if self.invoice_lines:
            res.update({'line_tax_amount_percent': self.invoice_lines[
                0].line_tax_amount_percent})

        if self.line_tax_amount_percent:
            res.update(
                {'line_tax_amount_percent': self.line_tax_amount_percent})
        return res
