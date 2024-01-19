"""
Added fields in AccountFiscalPosition related to vat config and amazon fiscal position
configuration.
"""

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.addons.l10n_eu_oss.models.eu_tax_map import EU_TAX_MAP


class AccountFiscalPosition(models.Model):
    """
    Inherited this model for relating with vat configuration and added
    amazon configurations.
    @author: Maulik Barad on Date 15-Jan-2020.
    """
    _inherit = "account.fiscal.position"

    vat_config_id = fields.Many2one("vat.config.ept", "VAT Configuration", readonly=True)
    is_amazon_fpos = fields.Boolean(string="Is Amazon Fiscal Position", default=False)

    def unlink(self):
        """
        This Method if report is processed then raise UserError.
        """
        for fpos in self:
            if fpos.is_amazon_fpos:
                raise UserError(_('You cannot delete Amazon fiscal position. However, you can archive it.'))
        return super(AccountFiscalPosition, self).unlink()

    def map_amazon_eu_taxes(self):
        """
        Will auto create and map the amazon taxes for B2B and B2C Fiscal position
        """
        tax_group_fid = self.env['account.tax.group'].search([], limit=1)
        tax_obj = self.env['account.tax']
        company = self.vat_config_id.company_id
        country = self.country_id if self.country_id else self.origin_country_ept

        taxes = tax_obj.search([
            ('type_tax_use', '=', 'sale'),
            ('amount_type', '=', 'percent'),
            ('company_id', '=', company.id),
            ('country_id', '=', company.account_fiscal_country_id.id)])
        mapping = []
        foreign_taxes = {tax.amount: tax for tax in self.tax_ids.tax_dest_id if tax.amount_type == 'percent'}
        for domestic_tax in taxes:
            tax_amount = EU_TAX_MAP.get((company.account_fiscal_country_id.code, domestic_tax.amount, country.code),
                                        False)
            if tax_amount and domestic_tax not in self.tax_ids.tax_src_id:
                if not foreign_taxes.get(tax_amount, False):
                    tax_name = '%(rate)s%% %(country)s %(label)s' % {'rate': tax_amount, 'country': country.code,
                                                                     'label': country.vat_label}
                    tax_search_domain = [('amount_type', '=', 'percent'), ('type_tax_use', '=', 'sale'),
                                         ('company_id', '=', company.id), ('price_include', '=', True),
                                         ('name', '=', tax_name), ('amount', '=', tax_amount),
                                         ('country_id', '=', country.id)]
                    tax = tax_obj.search(tax_search_domain)
                    if not tax:
                        tax = tax_obj.create({'name': tax_name,
                                              'amount': tax_amount,
                                              'type_tax_use': 'sale',
                                              'description': "%s%%" % tax_amount,
                                              'tax_group_id': tax_group_fid.id,
                                              'country_id': country.id,
                                              'sequence': 1000,
                                              'company_id': company.id,
                                              'price_include': True
                                              })
                    foreign_taxes[tax_amount] = tax
                    self.map_tax_and_set_account(tax, company.id)
                mapping.append((0, 0, {'tax_src_id': domestic_tax.id, 'tax_dest_id': foreign_taxes[tax_amount].id}))
        if mapping:
            self.write({
                'tax_ids': mapping
            })

    def map_tax_and_set_account(self, tax_record, company_id):
        """
        Define method which map created tax record with default product
        taxes in fiscal position and set account record in tax
        invoice and refund lines
        :param tax_record: created tax record
        :param fiscal_position: created fiscal position record
        :return: True
        """
        sales_tax_accounts = self.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', company_id)
        ]).invoice_repartition_line_ids.mapped('account_id')
        if sales_tax_accounts:
            # set account record in invoice lines of tax record
            invoice_lines = tax_record.invoice_repartition_line_ids.filtered(lambda line: line.repartition_type == 'tax')
            for invoice_line in invoice_lines:
                if not invoice_line.account_id or invoice_line.account_id.id != sales_tax_accounts[0].id:
                    invoice_line.write({'account_id': sales_tax_accounts[0].id})
            # set account record in refund lines of tax record
            refund_lines = tax_record.refund_repartition_line_ids.filtered(lambda line: line.repartition_type == 'tax')
            for refund_line in refund_lines:
                if not refund_line.account_id or refund_line.account_id.id != sales_tax_accounts[0].id:
                    refund_line.write({'account_id': sales_tax_accounts[0].id})
        return True
