# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class to config the Amazon seller details
"""

from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError

from ..endpoint import REGISTER_ENDPOINT, VERIFY_ENDPOINT


class AmazonSellerConfig(models.TransientModel):
    """
    Added class to configure the seller details.
    """
    _name = 'res.config.amazon.seller'
    _description = 'Amazon Seller Configurations'

    name = fields.Char("Seller Name", help="Name of Seller to identify unique seller in the ERP")
    country_id = fields.Many2one('res.country', string="Country",
                                 help="Country name in which seller is registered")
    company_id = fields.Many2one('res.company', string='Company',
                                 help="Company of this seller All transactions which do based on "
                                      "seller country")
    merchant_id = fields.Char(help="Seller's Merchant ID")
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')],
                                      string='Fulfillment By ?', default='Both',
                                      help="Select FBA for Fulfillment by Amazon, FBM for "
                                           "Fulfillment by Merchant, "
                                           "FBA & FBM for those sellers who are doing both.")
    amz_video_url = fields.Html('video_link')
    """
        Modified: updated code to create iap account if not exist and if exist iap account than
        verify to check if credit exist for that account than it will allow to create seller
        if credit not exist than it will raise popup to purchase credits for that account.
    """

    def prepare_marketplace_kwargs(self, account):
        """
        Prepare Arguments for Load Marketplace.
        :return: dict{}
        """
        ir_config_parameter_obj = self.env['ir.config_parameter']
        dbuuid = ir_config_parameter_obj.sudo().get_param('database.uuid')
        return {'merchant_id': self.merchant_id and str(self.merchant_id) or False,
                'app_name': 'amazon_ept_spapi',
                'account_token': account.account_token,
                'emipro_api': 'load_marketplace_sp_api',
                'dbuuid': dbuuid,
                'amazon_selling': self.amazon_selling,
                'amazon_marketplace_code': self.country_id.amazon_marketplace_code or self.country_id.code,
                'odoo_version': 'v16'
            }

    def prepare_amazon_seller_vals(self, company_id):
        """
        Prepare Amazon Seller values
        :param company_id: res.company()
        :return: dict
        """
        return {
            'name': self.name,
            'country_id': self.country_id.id,
            'company_id': company_id.id,
            'amazon_selling': self.amazon_selling,
            'merchant_id': self.merchant_id
        }

    def create_transaction_type(self, seller):
        """
        This is used to create amazon transaction type of seller
        """
        trans_line_obj = self.env['amazon.transaction.line.ept']
        trans_type_ids = self.env['amazon.transaction.type'].search([])
        for trans_id in trans_type_ids:
            trans_line_vals = {
                'transaction_type_id': trans_id.id,
                'seller_id': seller.id,
                'amazon_code': trans_id.amazon_code,
            }
            trans_line_obj.create(trans_line_vals)

    def amz_create_sales_team(self, seller):
        """
        Define this method for create sales team for amazon seller.
        :param: seller: amazon.seller.ept()
        :return: crm.team()
        """
        crm_team_obj = self.env['crm.team']
        team_name = "Amazon-" + seller.name
        amz_sales_team = crm_team_obj.search([('name', '=', team_name)], limit=1)
        if not amz_sales_team:
            amz_sales_team = crm_team_obj.create({'name': team_name})
        return amz_sales_team

    def update_reimbursement_details(self, seller):
        """
        This is used to update the Reimbursement details in seller.
        """
        prod_obj = self.env['product.product']
        partner_obj = self.env['res.partner']
        product = prod_obj.search([('default_code', '=', 'REIMBURSEMENT'), ('type', '=', 'service')], limit=1)
        vals = {'name': 'Amazon Reimbursement'}
        partner_id = partner_obj.create(vals)
        journal_id = self.env['account.journal'].search([('type', '=', 'sale'),
                                                         ('company_id', '=', seller.company_id.id)],
                                                        order="id", limit=1)

        seller.write({'reimbursement_customer_id': partner_id.id,
                      'reimbursement_product_id': product.id if product else False,
                      'sale_journal_id': journal_id and journal_id.id})
        return True

    def test_amazon_connection(self):
        """
        Create Seller account in ERP if not created before.
        If merchant_id found in ERP then raise UserError.
        If Amazon Seller Account is registered in IAP raise UserError.
        IF Amazon Seller Account is not registered in IAP then create it.
        This function will load Marketplaces automatically based on seller region.
        :return:
        """
        amazon_seller_obj = self.env['amazon.seller.ept']
        iap_account_obj = self.env['iap.account']
        seller_exist = amazon_seller_obj.search([('merchant_id', '=', self.merchant_id)])

        if seller_exist:
            raise UserError(_('Seller already exist with given Credential.'))

        account = iap_account_obj.search([('service_name', '=', 'amazon_ept')])
        if account:
            kwargs = self.prepare_marketplace_kwargs(account)
            response = iap_tools.iap_jsonrpc(VERIFY_ENDPOINT, params=kwargs, timeout=1000)
        else:
            account = iap_account_obj.create({'service_name': 'amazon_ept'})
            account._cr.commit()
            kwargs = self.prepare_marketplace_kwargs(account)
            response = iap_tools.iap_jsonrpc(REGISTER_ENDPOINT, params=kwargs, timeout=1000)

        if response.get('error', {}):
            raise UserError(_(response.get('error', {})))

        flag = response.get('result', {})
        if flag:
            company_id = self.company_id or self.env.user.company_id or False
            vals = self.prepare_amazon_seller_vals(company_id)
            if self.country_id.code in ['AE', 'DE', 'EG', 'ES', 'FR', 'GB', 'IN', 'IT', 'SA', 'TR', 'NL',
                                        'SE', 'BE', 'PL', 'ZA']:
                vals.update({'is_european_region': True})
            else:
                vals.update({'is_european_region': False})

            vals.update({'is_sp_api_amz_seller': True})
            try:
                seller = amazon_seller_obj.create(vals)
                # create amazon sales team for the seller
                self.amz_create_sales_team(seller)
                if self.env.user.has_group('analytic.group_analytic_accounting'):
                    seller.amz_create_analytic_account_for_seller(seller)
                seller.load_marketplace()
                self.create_transaction_type(seller)

            except Exception as ex:
                raise UserError(_('Exception during instance creation.\n %s' % (str(ex))))
            action = self.env.ref(
                'amazon_ept.action_amazon_configuration', False)
            result = action.read()[0] if action else {}
            result.update({'seller_id': seller.id})
            if seller.amazon_selling in ['FBA', 'Both']:
                self.update_reimbursement_details(seller)
                seller.auto_create_stock_adjustment_configuration()
            seller.update_user_groups()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @staticmethod
    def confirm_archive_un_archive(self):
        """
        Send confirmation for archiving the seller
        Send confirmation for un-archiving the seller
        :return:  True
        """
        sellers = self._context.get('active_ids')
        AMZ_SELLER = 'amazon.seller.ept'
        for seller in sellers:
            try:
                if self._context.get('active_seller'):
                    self.env[AMZ_SELLER].browse(seller).with_context({'confirm_archive': True}).archive_seller()
                else:
                    self.env[AMZ_SELLER].browse(seller).with_context({'confirm_un_archive': True}).unarchive_seller()
            except Exception as ex:
                raise UserError(_(ex))
