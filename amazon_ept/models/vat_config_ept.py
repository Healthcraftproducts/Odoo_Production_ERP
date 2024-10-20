# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Vat Configuration Class.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VatConfigEpt(models.Model):
    """
    For Setting VAT number in warehouse partner.
    @author: Maulik Barad on Date 11-Jan-2020.
    updated by : Kishan Sorani on Date 10-Jun-2021
    """
    _name = "vat.config.ept"
    _description = "VAT Configuration EPT"
    _rec_name = "company_id"

    def _get_company_domain(self):
        """
        Creates domain to only allow to select company from allowed companies in switchboard.
        @author: Maulik Barad on Date 11-Jan-2020.
        """
        return [("id", "in", self.env.context.get('allowed_company_ids'))]

    company_id = fields.Many2one("res.company", domain=_get_company_domain)
    vat_config_line_ids = fields.One2many("vat.config.line.ept", "vat_config_id")
    _sql_constraints = [("unique_company_vat_config", "UNIQUE(company_id)",
                         "VAT configuration is already added for the company.")]

    def action_eu_tax_mapping(self):
        """
        Will return invoice action to map the EU taxes if participated in OSS
        """
        action = self.env.ref('account.action_account_config').read()[0]
        return action

    def amazon_eu_tax_mapping(self):
        """
        Will find the vat configurations of current company and map the EU FPOS and Taxes
        """
        vat_config_line_ids = self.vat_config_line_ids
        for vat_config_line in vat_config_line_ids:
            vat_config_line.amazon_map_eu_fpos_and_taxes()
