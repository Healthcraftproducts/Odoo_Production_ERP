# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.


"""
Main Model for Vat Configuration.
"""
import logging
from odoo import api, fields, models, Command

_logger = logging.getLogger("Amazon")

EXCLUDED_VAT_REGISTERED_EUROPE_GROUP = "amazon_ept.excluded_vat_registered_europe"


class VatConfigLineEpt(models.Model):
    """
    For Setting VAT number for Country.
    @author: Maulik Barad on Date 11-Jan-2020.
    """
    _name = "vat.config.line.ept"
    _description = "VAT Configuration Line EPT"

    @api.model_create_multi
    def create(self, vals_list):
        """
        Inherited the create method for updating the VAT number and creating Fiscal positions.
        MOD : Create an VCS FPOS based on VAT number configurations.
        MOD : update data dict
        """
        results = super(VatConfigLineEpt, self).create(vals_list)
        for result in results:
            country_id = result.country_id
            excluded_vat_registered_europe_group = self.env.ref("amazon_ept.excluded_vat_registered_europe")
            if country_id.id in excluded_vat_registered_europe_group.country_ids.ids:
                excluded_vat_registered_europe_group.country_ids = [(3, country_id.id, 0)]
                _logger.info("COUNTRY REMOVED FROM THE EUROPE GROUP ")
            result.update_warehouse_partner_and_map_vat_units()
        return results

    def update_warehouse_partner_and_map_vat_units(self):
        """
        Updating the VAT number into warehouse's partner of the same country.
        Will create or update the vat units
        """
        warehouse_obj = self.env["stock.warehouse"]
        module_obj = self.env['ir.module.module']
        account_accountant_module = module_obj.sudo().search([('name', '=', 'account_accountant'),
                                                              ('state', '=', 'installed')])
        country_id = self.country_id
        company_id = self.vat_config_id.company_id
        warehouses = warehouse_obj.search([("company_id", "=", company_id.id)])
        warehouse_partners = warehouses.partner_id.filtered(
            lambda x: x.country_id.id == country_id.id and x.vat != self.vat)
        if warehouse_partners:
            warehouse_partners.write({"vat": self.vat})
            _logger.info("VAT Number Updated OF Warehouse's Partner Which Belongs To Country %s." % (country_id.id))

        if bool(account_accountant_module):
            self.map_amazon_vat_units()

    def write(self, vals):
        """
        Inherited write method for creating excluded_vat_group
        countries country to country[B2C] fiscal position based on VAT number configuration
        :param: vals: data dict for update record
        @author: Kishan Sorani on Date 25-Jun-2020.
        """
        res = super(VatConfigLineEpt, self).write(vals)
        if 'vat' in vals:
            self.update_warehouse_partner_and_map_vat_units()
        return res

    def _get_country_domain(self):
        """
        Creates domain to only allow to select company from allowed companies in switchboard.
        @author: Maulik Barad on Date 11-Jan-2020.
        """
        country_list = []
        europe_group = self.env.ref("base.europe", raise_if_not_found=False)
        uk_ref = self.env.ref("base.uk", raise_if_not_found=False)
        if europe_group:
            country_list = europe_group.country_ids.ids
        if uk_ref:
            country_list += uk_ref.ids
        return [("id", "in", country_list)]

    vat_config_id = fields.Many2one("vat.config.ept", ondelete="cascade")
    vat = fields.Char("VAT Number")
    country_id = fields.Many2one("res.country", domain=_get_country_domain)

    _sql_constraints = [
        ("unique_country_vat_config", "UNIQUE(vat_config_id,country_id)",
         "VAT configuration is already added for the country.")]

    def map_amazon_vat_units(self):
        """
        Will used to map the vat units into the company
        """
        account_tax_unit_obj = self.env['account.tax.unit']
        company = self.vat_config_id.company_id
        country = self.country_id
        vat_unit = account_tax_unit_obj.search([('country_id', '=', country.id), ('main_company_id', '=', company.id)], limit=1)
        if vat_unit and vat_unit.vat != self.vat:
            vat_unit.write({'vat': self.vat})
        elif vat_unit and vat_unit.id not in company.account_tax_unit_ids.ids:
            company.write({'account_tax_unit_ids': [(4, vat_unit.id)]})
        elif not vat_unit:
            account_tax_unit_obj.create({
                'name': country.name + ' VAT Unit',
                'country_id': country.id,
                'vat': self.vat,
                'company_ids': [Command.set([company.id])],
                'main_company_id': company.id,
            })

    def amazon_map_eu_fpos_and_taxes(self):
        """
        Create Fiscal Positions Automatically as per VAT number Configurations.
        For Ex. France VAT
            - Deliver to France(B2C)
            - VCS - Deliver to France(VAT Required)(B2B)
            - Deliver from France to Europe(Exclude VAT registered country)(B2C)
            - VCS - Deliver from France to Europe(VAT Required)(B2B)
            - VCS - Deliver from France to Outside Europe (B2C)
            - VCS - Deliver from France to Outside Europe (VAT Required)(B2B)

        updated by : Kishan Sorani on Date 10-JUN-2021
        MOD : if is_union_oss_vat_declaration true the no need
              to create Delivered Country to EU(Exclude VAT registered country)
              fiscal position for VAT number configure country
        """
        fiscal_position_obj = self.env["account.fiscal.position"]
        module_obj = self.env['ir.module.module']
        data = {"company_id": self.vat_config_id.company_id.id,
                "vat_config_id": self.vat_config_id.id, "is_amazon_fpos": True}
        excluded_vat_registered_europe_group = self.env.ref(EXCLUDED_VAT_REGISTERED_EUROPE_GROUP,
                                                            raise_if_not_found=False)
        europe_group = self.env.ref('base.europe', raise_if_not_found=False)
        country_id = self.country_id
        country_name = country_id.name
        is_union_oss_vat_declaration = module_obj.sudo().search(
            [('name', '=', 'l10n_eu_oss'), ('state', '=', 'installed')])
        union_oss_vat_declaration = bool(is_union_oss_vat_declaration)

        # Delivered Country to Country
        country_to_country_fpos = fiscal_position_obj.search([("company_id", "=", data["company_id"]),
                                                              ('vat_required', '=', False),
                                                              ("country_id", "=", country_id.id)], limit=1)
        if not country_to_country_fpos:
            data.update({'name': "Deliver to %s[B2C]" % country_name, 'country_id': country_id.id})
            country_to_country_fpos = fiscal_position_obj.create(data)
            _logger.info("Fiscal Position Created For Country %s[B2C]." % country_name)
        elif not country_to_country_fpos.is_amazon_fpos:
            country_to_country_fpos.is_amazon_fpos = True
        # create automatic tax record for fiscal position.
        country_to_country_fpos.map_amazon_eu_taxes()

        # VCS - Vat Required - Delivered Country to Country
        vat_country_to_country_fpos = fiscal_position_obj.search([("company_id", "=", data["company_id"]),
                                                                  ("country_id", "=", country_id.id),
                                                                  ('vat_required', '=', True)], limit=1)
        if not vat_country_to_country_fpos:
            data.update({'name': "Deliver to %s[B2B]" % country_name, 'country_id': country_id.id,
                         'vat_required': True, 'foreign_vat': self.vat})
            vat_country_to_country_fpos = fiscal_position_obj.create(data)
            _logger.info("Fiscal Position Created For Country %s[B2B]." % country_name)
        elif not vat_country_to_country_fpos.is_amazon_fpos:
            vat_country_to_country_fpos.is_amazon_fpos = True
        # create automatic tax record for fiscal position.
        vat_country_to_country_fpos.map_amazon_eu_taxes()

        if not union_oss_vat_declaration:
            # VAT Required False - Delivered Country to EU(Exclude VAT registered country)
            existing_excluded_fiscal_position = fiscal_position_obj.search(
                [("company_id", "=", data["company_id"]), ("origin_country_ept", "=", country_id.id),
                 ('vat_required', '=', False), ("country_group_id", "=", excluded_vat_registered_europe_group.id if
                excluded_vat_registered_europe_group else False)], limit=1)
            if not existing_excluded_fiscal_position:
                data.update({"name": "Deliver from %s to Europe(Exclude VAT registered country)[B2C]" % country_name,
                             "origin_country_ept": country_id.id, 'vat_required': False,
                             "country_group_id": excluded_vat_registered_europe_group.id if
                             excluded_vat_registered_europe_group else False})
                if 'country_id' in data.keys():
                    del data['country_id']
                if 'foreign_vat' in data.keys():
                    del data['foreign_vat']
                existing_excluded_fiscal_position = fiscal_position_obj.create(data)
                _logger.info("Fiscal Position Created From %s To Excluded Country Group[B2C]." % country_name)
            elif not existing_excluded_fiscal_position.is_amazon_fpos:
                existing_excluded_fiscal_position.is_amazon_fpos = True
            # create automatic tax record for fiscal position
            existing_excluded_fiscal_position.map_amazon_eu_taxes()

        # VAT Required - VCS Delivered Country to EU
        existing_europe_vat_fpos = fiscal_position_obj.search([
            ("company_id", "=", data["company_id"]), ('vat_required', '=', True),
            ("origin_country_ept", "=", country_id.id),
            ("country_group_id", "=", europe_group.id if europe_group else False)], limit=1)
        if not existing_europe_vat_fpos:
            data.update({"name": "Deliver from %s to Europe[B2B]" % country_name,
                         "origin_country_ept": country_id.id, "vat_required": True,
                         "country_group_id": europe_group.id if europe_group else False})
            if 'country_id' in data.keys():
                del data['country_id']
            if 'foreign_vat' in data.keys():
                del data['foreign_vat']
            existing_europe_vat_fpos = fiscal_position_obj.create(data)
            _logger.info("Fiscal Position Created From %s To Europe Country Group[B2B]." % country_name)
        elif not existing_europe_vat_fpos.is_amazon_fpos:
            existing_europe_vat_fpos.is_amazon_fpos = True
        # create automatic tax record for fiscal position
        existing_europe_vat_fpos.map_amazon_eu_taxes()

        # VCS - Delivered Country to Outside EU
        outside_eu_fiscal_position = fiscal_position_obj.search([("company_id", "=", data["company_id"]),
                                                                 ("origin_country_ept", "=", country_id.id),
                                                                 ('vat_required', '=', False),
                                                                 ('country_group_id', '=', False)], limit=1)
        if not outside_eu_fiscal_position:
            data.update({"name": "Deliver from %s to Outside Europe[B2C]" % country_name,
                         'origin_country_ept': country_id.id, "vat_required": False})
            if 'country_group_id' in data.keys():
                del data['country_group_id']
            if 'country_id' in data.keys():
                del data['country_id']
            if 'foreign_vat' in data.keys():
                del data['foreign_vat']
            outside_eu_fiscal_position = fiscal_position_obj.create(data)
            _logger.info("Fiscal Position Created From %s To Outside EU[B2C]." % country_name)
        elif not outside_eu_fiscal_position.is_amazon_fpos:
            outside_eu_fiscal_position.is_amazon_fpos = True
        # create automatic tax record for fiscal position
        outside_eu_fiscal_position.map_amazon_eu_taxes()

        # VCS - Delivered Country to Outside EU(VAT Required)
        vcs_outside_eu_fiscal_position = fiscal_position_obj.search([("company_id", "=", data["company_id"]),
                                                                     ("origin_country_ept", "=", country_id.id),
                                                                     ('vat_required', '=', True),
                                                                     ('country_group_id', '=', False)], limit=1)
        if not vcs_outside_eu_fiscal_position:
            data.update({"name": "Deliver from %s to Outside Europe(VAT Required)[B2B]" % country_name,
                         'origin_country_ept': country_id.id, "vat_required": True})
            if 'country_group_id' in data.keys():
                del data['country_group_id']
            if 'country_id' in data.keys():
                del data['country_id']
            if 'foreign_vat' in data.keys():
                del data['foreign_vat']
            vcs_outside_eu_fiscal_position = fiscal_position_obj.create(data)
            _logger.info("Fiscal Position Created From %s To Outside EU(VAT Required)[B2B]." % country_name)
        elif not vcs_outside_eu_fiscal_position.is_amazon_fpos:
            vcs_outside_eu_fiscal_position.is_amazon_fpos = True

        # create automatic tax record for fiscal position
        vcs_outside_eu_fiscal_position.map_amazon_eu_taxes()
        return True
