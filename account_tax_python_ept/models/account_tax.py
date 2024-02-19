# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval


class AccountTax(models.Model):
    """
    Use: Override Field and Methods for Compute Tax
    """
    _inherit = 'account.tax'

    python_compute = fields.Text(
        help="Compute the amount of the tax by setting the variable "
             "'result'.\n\n"
             ":param base_amount: float, actual amount on which the "
             "tax is applied\n"
             ":param price_unit: float\n"
             ":param line_tax_amount_percent: float\n"
             ":param quantity: float\n"
             ":param company: res.company recordset singleton\n"
             ":param product: product.product recordset singleton"
             " or None\n"
             ":param partner: res.partner recordset singleton or None")

    def _compute_amount(self, base_amount, price_unit, quantity=1.0, product=None, partner=None, fixed_multiplicator=1):
        self.ensure_one()
        if self.amount_type != 'code':
            return super(AccountTax, self)._compute_amount(base_amount,
                                                           price_unit, quantity,
                                                           product, partner, fixed_multiplicator)
        if product and product._name == 'product.template':
            product = product.product_variant_id
        company = self.env.company
        localdict = self._context.get('tax_computation_context',
                                      {'line_tax_amount_percent': 0.00})
        localdict.update(
            {'base_amount': base_amount, 'price_unit': price_unit,
             'quantity': quantity, 'product': product,
             'partner': partner, 'company': company})
        safe_eval(self.python_compute, localdict, mode="exec", nocopy=True)
        return localdict['result']

    @api.model
    def _create_amazon_python_tax(self):
        """
        Create Tax configuration for calculate tax based on calculation.
        :return:  boolean
        @author: Keyur Kanani
        """
        amz_tax_id = self.search(
                    [('python_compute', '=', 'result = (price_unit * quantity * line_tax_amount_percent) / 100')])
        country = self.env.ref('base.us',raise_if_not_found=False)           
        if not amz_tax_id and country:
            tax_vals = {
                'name': 'Amazon Tax',
                'amount_type': 'code',
                'type_tax_use': 'sale',
                'country_id':country.id,
                'amount': 0.00,
                'price_include': False,
                'python_compute': 'result = (price_unit * quantity * line_tax_amount_percent) / 100'
            }
            amz_tax_id = self.create(tax_vals)
            amz_tax_id.onchange_price_include()
        return True
