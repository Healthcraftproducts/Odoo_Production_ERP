# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Inherited class, fields and methods for amazon configurations.
"""

import requests
from datetime import datetime
from odoo import SUPERUSER_ID
from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError
from odoo.http import request

AMAZON_SELLER_EPT = 'amazon.seller.ept'
AMAZON_INSTANCE_EPT = 'amazon.instance.ept'
STOCK_WAREHOUSE = 'stock.warehouse'
ACCOUNT_ACCOUNT = 'account.account'
PRODUCT_PRODUCT = 'product.product'
URL_ACTION = 'ir.actions.act_url'


class AmazonConfigSettings(models.TransientModel):
    """
    Inherited class to config the amazon details.
    """

    _inherit = 'res.config.settings'

    amz_seller_id = fields.Many2one(AMAZON_SELLER_EPT, string='Amazon Seller',
                                    help="Unique Amazon Seller name")
    amz_instance_id = fields.Many2one(AMAZON_INSTANCE_EPT, string='Amazon Marketplace',
                                      help="Select Amazon Instance")
    amz_instance_removal_order = fields.Many2one(AMAZON_INSTANCE_EPT, string='Removal Order Marketplace',
                                                 help="Select Amazon Instance For Removal Order")
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')],
                                      string='Fulfillment By ?', default='FBM',
                                      help="Select FBA for Fulfillment by Amazon, FBM for "
                                           "Fulfillment by Merchant FBA & FBM for those sellers "
                                           "who are doing both.")
    is_default_odoo_sequence_in_sales_order_fbm = fields.Boolean(
        "Is default Odoo Sequence in Sales Orders (FBM) ?")
    amz_order_prefix = fields.Char(size=10, string='Amazon Order Prefix')
    amz_auto_workflow_id = fields.Many2one('sale.workflow.process.ept',
                                           string='Amazon Auto Workflow')

    amz_country_id = fields.Many2one('res.country', string="Country Name")
    amz_warehouse_id = fields.Many2one(STOCK_WAREHOUSE, string="Amazon Warehouse")
    company_for_amazon_id = fields.Many2one('res.company', string='Amazon Company Name',
                                            related="amz_seller_id.company_id", store=False)
    amz_payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')
    amz_partner_id = fields.Many2one('res.partner', string='Default Customer')
    amz_lang_id = fields.Many2one('res.lang', string='Language Name')
    amz_team_id = fields.Many2one('crm.team', 'Amazon Sales Team')
    amz_instance_pricelist_id = fields.Many2one('product.pricelist', string='Pricelist Name')
    amz_create_new_product = fields.Boolean('Allow to create new product if not found in odoo ?', default=False)
    amazon_property_account_payable_id = fields.Many2one(ACCOUNT_ACCOUNT, \
                                                         string="Account Payable",
                                                         help='This account will be used instead '
                                                              'of the default one as the payable '
                                                              'account for the current partner')
    amazon_property_account_receivable_id = fields.Many2one(
        ACCOUNT_ACCOUNT, string="Account Receivable", \
        help='This account will be used instead of the default one as the receivable account for '
             'the current partner')

    amz_shipment_charge_product_id = fields.Many2one(PRODUCT_PRODUCT, "Amazon Shipment Fee",
                                                     domain=[('type', '=', 'service')])
    amz_gift_wrapper_product_id = fields.Many2one(PRODUCT_PRODUCT, "Amazon Gift Wrapper Fee",
                                                  domain=[('type', '=', 'service')])
    amz_promotion_discount_product_id = fields.Many2one(PRODUCT_PRODUCT,
                                                        "Amazon Promotion Discount",
                                                        domain=[('type', '=', 'service')])
    amz_ship_discount_product_id = fields.Many2one(PRODUCT_PRODUCT, "Amazon Shipment Discount",
                                                   domain=[('type', '=', 'service')])
    amz_fba_auto_workflow_id = fields.Many2one('sale.workflow.process.ept', string='Auto Workflow (FBA)')
    amz_fba_warehouse_id = fields.Many2one(STOCK_WAREHOUSE, string='FBA Warehouse')
    amz_is_another_soft_create_fba_shipment = fields.Boolean(
        string="Does another software create the FBA shipment reports?", default=False)
    amz_is_another_soft_create_fba_inventory = fields.Boolean(
        string="Does another software create the FBA Inventory reports?", default=False)
    is_allow_to_create_removal_order = fields.Boolean('Allow Create Removal Order In FBA?',
                                                      help="Allow to create removal order in FBA.")
    removal_warehouse_id = fields.Many2one(STOCK_WAREHOUSE, string="Removal Warehouse", help="Removal Warehouse")
    amz_fba_liquidation_partner = fields.Many2one("res.partner", string="FBA Liquidation Partner",
                                                  help="This Partner will be used as delivery partner for "
                                                       "FBA Liquidation Removal Order.")
    amz_validate_stock_inventory_for_report = fields.Boolean(
        "Auto Validate Amazon FBA Live Stock Report")
    amz_is_reserved_qty_included_inventory_report = fields.Boolean(
        string='Is Reserved Quantity to be included FBA Live Inventory Report?')
    amz_is_default_odoo_sequence_in_sales_order_fba = fields.Boolean(
        "Is default Odoo Sequence In Sales Orders (FBA) ?")
    amz_fba_order_prefix = fields.Char(size=10, string='Amazon FBA Order Prefix')
    amz_def_fba_partner_id = fields.Many2one('res.partner',
                                             string='Default Customer for FBA pending order')
    amz_instance_stock_field = fields.Selection(
        [('free_qty', 'Free Quantity'), ('virtual_available', 'Forecast Quantity')],
        string="Stock Type", default='free_qty')
    amz_instance_settlement_report_journal_id = fields.Many2one('account.journal',
                                                                string='Settlement Report Journal')
    amz_instance_ending_balance_account_id = fields.Many2one(ACCOUNT_ACCOUNT,
                                                             string="Ending Balance Account")
    amz_instance_ending_balance_description = fields.Char(
        "Ending Balance Description")
    amz_unsellable_location_id = fields.Many2one('stock.location', string="Unsellable Location",
                                                 help="Select instance wise amazon unsellable "
                                                      "location")
    amz_reimbursement_customer_id = fields.Many2one("res.partner", string="Reimbursement Customer")
    amz_reimbursement_product_id = fields.Many2one(PRODUCT_PRODUCT,
                                                   string="Reimbursement Product")
    amz_sales_journal_id = fields.Many2one('account.journal', string='Sales Journal',
                                           domain=[('type', '=', 'sale')])
    amz_fulfillment_latency = fields.Integer('Fulfillment Latency', default=3)
    amz_outbound_instance_id = fields.Many2one(AMAZON_INSTANCE_EPT,
                                               string='Default Outbound Marketplace',
                                               help="Select Amazon Instance for Outbound Orders.")
    amz_tax_id = fields.Many2one('account.tax', string="Tax Account")
    amz_is_usa_marketplace = fields.Boolean(string="Is USA Marketplace", store=False, default=False)

    stock_update_warehouse_ids = fields.Many2many(STOCK_WAREHOUSE, string="Stock Update Warehouses", \
                                                  help="Warehouses which will fulfill the orders")
    removal_order_report_days = fields.Integer("Removal Order Report Days", default=3,
                                               help="Days of report to import Removal Order Report")

    def switch_amazon_fulfillment_by(self):
        """
        Used to switch the amazon selling option.
        """
        action = self.env.ref('amazon_ept.res_config_action_amazon_marketplace', False)
        result = action.read()[0] if action else {}
        ctx = result.get('context', {}) and eval(result.get('context', {}))
        active_seller = request.session['amz_seller_id']
        if active_seller:
            marketplace_obj = self.env['amazon.marketplace.ept']
            amazon_active_seller = self.env[AMAZON_SELLER_EPT].browse(active_seller)
            amazon_active_seller.load_marketplace()
            market_place_id = amazon_active_seller.instance_ids.filtered(
                lambda x: x.market_place_id).mapped('market_place_id')
            marketplace_id = marketplace_obj.search(
                [('seller_id', '=', active_seller), ('market_place_id', 'not in', market_place_id)])
            other_marketplace_ids = marketplace_obj.search([('market_place_id', 'in', ['A1F83G8C2ARO7P']),
                                                            ('seller_id', '=', active_seller)])
            ctx.update({'default_seller_id': active_seller,
                        'deactivate_marketplace': marketplace_id.ids,
                        'default_other_marketplace_ids': other_marketplace_ids.ids})

        result['context'] = ctx
        return result

    is_vcs_activated = fields.Boolean(string="Is Vat calculation Service Activated ?")
    is_european_region = fields.Boolean(related='amz_seller_id.is_european_region')
    is_any_european_seller = fields.Boolean()
    allow_auto_create_outbound_orders = fields.Boolean()
    fulfillment_action = fields.Selection([("Ship", "Ship"), ("Hold", "Hold")], default="Ship")
    shipment_category = fields.Selection([("Expedited", "Expedited"),
                                          ("Standard", "Standard"),
                                          ("Priority", "Priority"),
                                          ("ScheduledDelivery", "ScheduledDelivery")],
                                         default="Standard")
    fulfillment_policy = fields.Selection([("FillOrKill", "FillOrKill"), ("FillAll", "FillAll"),
                                           ("FillAllAvailable", "FillAllAvailable")],
                                          default="FillOrKill")
    invoice_upload_policy = fields.Selection(
        [("amazon", "Amazon Create invoices"), ("custom", "Upload Invoice from Odoo")])
    amz_upload_refund_invoice = fields.Boolean(string='Export Customer Refunds to Amazon via API?', default=False)
    amz_invoice_report = fields.Many2one("ir.actions.report", string="Invoice Report")
    is_fulfilment_center_configured = fields.Boolean(string='Are Fulfillment Centers Required to Import FBA Orders?',
                                                     help='If True, then Orders will not be imported if the fulfillment'
                                                          ' center is not configured in an appropriate warehouse.')
    amz_seller_analytic_account_id = fields.Many2one('account.analytic.account',
                                                     string='Analytic Account (Seller)',
                                                     help='Analytic Account for Amazon Seller.')
    fba_analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account (FBA)',
                                              help='Analytic Account for Amazon FBA Seller.')
    fbm_analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account (FBM)',
                                              help='Analytic Account for Amazon FBM Seller.')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account (Marketplace)',
                                          help='Analytic Account for Amazon Marketplace.')
    amz_create_outbound_on_confirmation = fields.Boolean("Create Outbound On Order Confirmation",
                                                         help="This will allow to create outbound order when order is "
                                                              "confirmed.")
    amz_default_outbound_instance = fields.Many2one(AMAZON_INSTANCE_EPT, string='Default Instance for Outbound Orders')
    is_amz_create_schedule_activity = fields.Boolean("Create Schedule Activity ? ", default=False,
                                                     help="If checked, Then Schedule Activity create for "
                                                          "import orders if any products missing.")
    amz_activity_user_ids = fields.Many2many('res.users', string='Responsible User')
    amz_activity_type_id = fields.Many2one('mail.activity.type', string="Activity Type")
    amz_activity_date_deadline = fields.Integer('Deadline lead days',
                                                help="its add number of days in schedule activity deadline date ")

    def set_values(self):
        """
        will added the amazon access group based on selling option.
        """
        super(AmazonConfigSettings, self).set_values()
        amazon_seller_obj = self.env[AMAZON_SELLER_EPT]
        amazon_selling = self.amz_seller_id.amazon_selling
        seller = self.amz_seller_id
        if amazon_selling == 'FBA':
            other_seller = amazon_seller_obj.search(
                [('id', '!=', seller.id), ('amazon_selling', '=', 'Both')])
            seller_company = other_seller.filtered(
                lambda x: x.company_id.id in self.env.user.company_ids.ids)
            if other_seller and seller_company:
                return True
            other_seller = amazon_seller_obj.search(
                [('id', '!=', seller.id), ('amazon_selling', '=', 'FBM')])
            seller_company = other_seller.filtered(
                lambda x: x.company_id.id in self.env.user.company_ids.ids)
            if other_seller and seller_company:
                amazon_selling = 'Both'
        elif amazon_selling == 'FBM':
            other_seller = amazon_seller_obj.search(
                [('id', '!=', seller.id), ('amazon_selling', '=', 'Both')])
            seller_company = other_seller.filtered(
                lambda x: x.company_id.id in self.env.user.company_ids.ids)
            if other_seller and seller_company:
                return True
            other_seller = amazon_seller_obj.search(
                [('id', '!=', seller.id), ('amazon_selling', '=', 'FBA')])
            seller_company = other_seller.filtered(
                lambda x: x.company_id.id in self.env.user.company_ids.ids)
            if other_seller and seller_company:
                amazon_selling = 'Both'

        self = self.with_user(SUPERUSER_ID)
        amazon_fba_group = self.env.ref('amazon_ept.group_amazon_fba_ept')
        amazon_fbm_group = self.env.ref('amazon_ept.group_amazon_fbm_ept')
        amazon_fba_fbm_group = self.env.ref('amazon_ept.group_amazon_fba_and_fbm_ept')
        amazon_user_group = self.env.ref('amazon_ept.group_amazon_user_ept')
        amazon_manager_group = self.env.ref('amazon_ept.group_amazon_manager_ept')
        user_list = list(set(amazon_user_group.users.ids + amazon_manager_group.users.ids))

        if amazon_selling == 'FBM':
            amazon_fbm_group.write({'users': [(6, 0, user_list)]})
            amazon_fba_group.write({'users': [(6, 0, [])]})
            amazon_fba_fbm_group.write({'users': [(6, 0, [])]})
        elif amazon_selling == 'FBA':
            amazon_fba_group.write({'users': [(6, 0, user_list)]})
            amazon_fbm_group.write({'users': [(6, 0, [])]})
            amazon_fba_fbm_group.write({'users': [(6, 0, [])]})
        elif amazon_selling == 'Both':
            amazon_fba_fbm_group.write({'users': [(6, 0, user_list)]})
            amazon_fba_group.write({'users': [(6, 0, user_list)]})
            amazon_fbm_group.write({'users': [(6, 0, user_list)]})
        return True

    @api.onchange('amz_seller_id')
    def onchange_amz_seller_id(self):
        """
        based on seller's onchange it will update the values
        """
        vals = {}
        domain = {}
        if self.amz_seller_id:
            request.session['amz_seller_id'] = self.amz_seller_id.id
            seller = self.amz_seller_id
            self.env[AMAZON_INSTANCE_EPT].search([('seller_id', '=', self.amz_seller_id.id)])
            vals = self.onchange_amz_instance_id()
            vals['value'][
                'is_default_odoo_sequence_in_sales_order_fbm'] = \
                seller.is_default_odoo_sequence_in_sales_order or False
            vals['value']['amazon_selling'] = seller.amazon_selling
            vals['value']['amz_order_prefix'] = seller.order_prefix
            vals['value'][
                'amz_fba_order_prefix'] = seller.fba_order_prefix

            vals['value'][
                'amz_auto_workflow_id'] = seller.fbm_auto_workflow_id.id if \
                seller.fbm_auto_workflow_id else False
            vals['value']['amz_create_new_product'] = seller.create_new_product or False

            vals['value'][
                'amz_shipment_charge_product_id'] = seller.shipment_charge_product_id.id if \
                seller.shipment_charge_product_id else False
            vals['value'][
                'amz_gift_wrapper_product_id'] = seller.gift_wrapper_product_id.id if \
                seller.gift_wrapper_product_id else False
            vals['value'][
                'amz_promotion_discount_product_id'] = seller.promotion_discount_product_id.id if \
                seller.promotion_discount_product_id else False
            vals['value'][
                'amz_ship_discount_product_id'] = seller.ship_discount_product_id.id \
                if seller.ship_discount_product_id else False
            vals['value'][
                'amz_fba_auto_workflow_id'] = seller.fba_auto_workflow_id.id if \
                seller.fba_auto_workflow_id else False
            vals['value'][
                'amz_is_another_soft_create_fba_shipment'] = \
                seller.is_another_soft_create_fba_shipment or False
            vals['value'][
                'amz_is_another_soft_create_fba_inventory'] = \
                seller.is_another_soft_create_fba_inventory or False
            vals['value'][
                'amz_validate_stock_inventory_for_report'] = \
                seller.validate_stock_inventory_for_report or False
            vals['value'][
                'amz_is_reserved_qty_included_inventory_report'] = \
                seller.amz_is_reserved_qty_included_inventory_report or False
            vals['value'][
                'amz_is_default_odoo_sequence_in_sales_order_fba'] = \
                seller.is_default_odoo_sequence_in_sales_order_fba or False
            vals['value'][
                'amz_def_fba_partner_id'] = seller.def_fba_partner_id.id if \
                seller.def_fba_partner_id else False
            vals['value'][
                'amz_payment_term_id'] = seller.payment_term_id.id if \
                seller.payment_term_id else False
            vals['value'][
                'amz_reimbursement_customer_id'] = seller.reimbursement_customer_id.id if \
                seller.reimbursement_customer_id else False
            vals['value'][
                'amz_reimbursement_product_id'] = seller.reimbursement_product_id.id if \
                seller.reimbursement_product_id else False
            vals['value'][
                'amz_sales_journal_id'] = seller.sale_journal_id.id if \
                seller.sale_journal_id else False
            vals['value'][
                'amz_fulfillment_latency'] = seller.fulfillment_latency or 0
            vals['value']['invoice_upload_policy'] = seller.invoice_upload_policy
            vals['value']['amz_upload_refund_invoice'] = seller.amz_upload_refund_invoice
            vals['value']['amz_invoice_report'] = seller.amz_invoice_report.id or False
            vals['value']['is_vcs_activated'] = seller.is_vcs_activated
            vals['value']['amz_seller_analytic_account_id'] = seller.amz_seller_analytic_account_id.id if\
                seller.amz_seller_analytic_account_id else False
            vals['value']['fba_analytic_account_id'] = seller.fba_analytic_account_id.id if\
                seller.fba_analytic_account_id else False
            vals['value']['fbm_analytic_account_id'] = seller.fbm_analytic_account_id.id if\
                seller.fbm_analytic_account_id else False
            vals['value'][
                'amz_outbound_instance_id'] = seller.amz_outbound_instance_id.id if \
                seller.amz_outbound_instance_id else False
            vals['value']['is_fulfilment_center_configured'] = seller.is_fulfilment_center_configured or False

            vals['value']['is_amz_create_schedule_activity'] = seller.is_amz_create_schedule_activity or False
            vals['value']['amz_activity_user_ids'] = seller.amz_activity_user_ids or False
            vals['value']['amz_activity_type_id'] = seller.amz_activity_type_id or False
            vals['value']['amz_activity_date_deadline'] = seller.amz_activity_date_deadline or False

            removal_instance_id = seller.instance_ids.filtered(lambda r: r.is_allow_to_create_removal_order)
            if removal_instance_id:
                vals['value'][
                    'is_allow_to_create_removal_order'] = \
                    removal_instance_id.is_allow_to_create_removal_order or False
                vals['value']['amz_instance_removal_order'] = removal_instance_id.id or False
                vals['value'][
                    'removal_warehouse_id'] = removal_instance_id.removal_warehouse_id.id if \
                    removal_instance_id.removal_warehouse_id else False
                vals["value"]['amz_fba_liquidation_partner'] = seller.amz_fba_liquidation_partner or False
            vals["value"]['removal_order_report_days'] = seller.removal_order_report_days or 3
            vals["value"]["allow_auto_create_outbound_orders"] = seller.allow_auto_create_outbound_orders
            vals["value"]["fulfillment_action"] = seller.fulfillment_action
            vals["value"]["shipment_category"] = seller.shipment_category
            vals["value"]["fulfillment_policy"] = seller.fulfillment_policy
            vals['value']["amz_create_outbound_on_confirmation"] = seller.create_outbound_on_confirmation
            vals['value']["amz_default_outbound_instance"] = seller.default_outbound_instance
        else:
            """
            Checks if any seller is there of european region for configuration of VAT.
            @author: Maulik Barad on Date 11-Jan-2020.
            """
            sellers = self.env["amazon.seller.ept"].search_read([("is_european_region", "=", True)],
                                                                ["id"])
            if sellers:
                self.is_any_european_seller = True
        vals.update({'domain': domain})
        return vals

    @api.constrains('amz_fba_warehouse_id')
    def onchange_company_fba_warehouse_id(self):
        """
        Added to check Selected Company and Company in FBA Warehouse is same or not.
        """
        if self.amz_fba_warehouse_id and \
                self.amz_fba_warehouse_id.company_id.id != self.company_for_amazon_id.id:
            raise UserError(_(
                "Company in FBA warehouse is different than the selected company. "
                "Selected Company and Company in FBA Warehouse must be same."))

    @api.constrains('amz_warehouse_id')
    def onchange_company_warehouse_id(self):
        """
        Added to check Selected Company and Company in Warehouse is same or not.
        """
        if self.amz_warehouse_id and \
                self.amz_warehouse_id.company_id.id != self.company_for_amazon_id.id:
            raise UserError(_(
                "Company in warehouse is different than the selected company. "
                "Selected Company and Company in Warehouse must be same."))

    @api.onchange('amz_instance_id')
    def onchange_amz_instance_id(self):
        """
        Added to update the vals based on amazon instance
        """
        values = {}

        instance = self.amz_instance_id
        if instance:
            values['amz_instance_id'] = instance.id or False
            values['amz_partner_id'] = instance.partner_id.id if instance.partner_id else False
            values[
                'amz_warehouse_id'] = instance.warehouse_id.id if instance.warehouse_id else False
            values['amz_country_id'] = instance.country_id.id if instance.country_id else False
            values['amz_team_id'] = instance.team_id.id if instance.team_id else False
            values['amz_lang_id'] = instance.lang_id.id if instance.lang_id else False
            values['amz_instance_pricelist_id'] = instance.pricelist_id.id if \
                instance.pricelist_id else False
            values[
                'amazon_property_account_payable_id'] = \
                instance.amazon_property_account_payable_id \
                    if instance.amazon_property_account_payable_id else False
            values[
                'amazon_property_account_receivable_id'] = \
                instance.amazon_property_account_receivable_id.id \
                    if instance.amazon_property_account_receivable_id else False

            values['amz_instance_stock_field'] = instance.stock_field or False
            values[
                'amz_instance_settlement_report_journal_id'] = \
                instance.settlement_report_journal_id or False
            values[
                'amz_instance_ending_balance_account_id'] = instance.ending_balance_account_id.id \
                if instance.ending_balance_account_id else False
            values[
                'amz_instance_ending_balance_description'] = \
                instance.ending_balance_description or False
            values[
                'amz_unsellable_location_id'] = instance.fba_warehouse_id.unsellable_location_id.id \
                if instance.fba_warehouse_id.unsellable_location_id else False
            values[
                'amz_fba_warehouse_id'] = instance.fba_warehouse_id.id \
                if instance.fba_warehouse_id else False
            values['amz_tax_id'] = instance.amz_tax_id.id if instance.amz_tax_id else False
            values[
                'amz_is_usa_marketplace'] = True if \
                instance.market_place_id in ['ATVPDKIKX0DER', 'A2EUQ1WTGCTBG2', 'A1AM78C64UM0Y8'] else False
            values[
                'stock_update_warehouse_ids'] = instance.stock_update_warehouse_ids.ids if \
                instance.stock_update_warehouse_ids else False
            values['analytic_account_id'] = instance.analytic_account_id.id if \
                instance.analytic_account_id else False
        else:
            values = {'amz_instance_id': False, 'amz_instance_stock_field': False,
                      'amz_country_id': False, 'stock_update_warehouse_ids': False,
                      'amz_lang_id': False, 'amz_warehouse_id': False,
                      'amz_instance_pricelist_id': False, 'amz_partner_id': False}
        return {'value': values}

    def execute(self):
        """
        this is used to save the amazon configurations.
        """
        instance = self.amz_instance_id
        values, vals = {}, {}
        res = super(AmazonConfigSettings, self).execute()
        if self.env.user.has_group('analytic.group_analytic_accounting'):
            self.amz_seller_id.amz_create_analytic_account()
        ctx = {}
        if instance:
            ctx.update({'default_instance_id': instance.id})
            values['warehouse_id'] = self.amz_warehouse_id.id if self.amz_warehouse_id else False
            values['country_id'] = self.amz_country_id.id if self.amz_country_id else False
            values['lang_id'] = self.amz_lang_id.id if self.amz_lang_id else False
            values[
                'pricelist_id'] = self.amz_instance_pricelist_id.id if \
                self.amz_instance_pricelist_id else False
            values['partner_id'] = self.amz_partner_id.id if self.amz_partner_id else False
            values['team_id'] = self.amz_team_id.id if self.amz_team_id else False
            values[
                'amazon_property_account_payable_id'] = \
                self.amazon_property_account_payable_id.id or False
            values[
                'amazon_property_account_receivable_id'] = \
                self.amazon_property_account_receivable_id.id or False
            values['stock_field'] = self.amz_instance_stock_field or False
            values[
                'settlement_report_journal_id'] = \
                self.amz_instance_settlement_report_journal_id.id \
                    if self.amz_instance_settlement_report_journal_id else False
            values[
                'ending_balance_account_id'] = self.amz_instance_ending_balance_account_id.id if \
                self.amz_instance_ending_balance_account_id else False
            values[
                'ending_balance_description'] = self.amz_instance_ending_balance_description or False
            values[
                'fba_warehouse_id'] = self.amz_fba_warehouse_id.id if self.amz_fba_warehouse_id else False
            values['amz_tax_id'] = self.amz_tax_id.id if self.amz_tax_id else False
            values['is_use_percent_tax'] = True if self.amz_tax_id else False
            values['stock_update_warehouse_ids'] = [(6, 0,
                                                     self.stock_update_warehouse_ids and
                                                     self.stock_update_warehouse_ids.ids or [])]
            values['analytic_account_id'] = self.analytic_account_id.id if self.analytic_account_id else False
            instance.write(values)
        if self.amz_seller_id:
            vals['amazon_selling'] = self.amz_seller_id.amazon_selling or False
            vals[
                'is_default_odoo_sequence_in_sales_order'] = \
                self.is_default_odoo_sequence_in_sales_order_fbm or False
            vals['order_prefix'] = self.amz_order_prefix if self.amz_order_prefix else False
            vals[
                'fba_order_prefix'] = self.amz_fba_order_prefix if self.amz_fba_order_prefix else False

            vals[
                'fbm_auto_workflow_id'] = self.amz_auto_workflow_id.id if \
                self.amz_auto_workflow_id else False
            vals[
                'create_new_product'] = self.amz_create_new_product if \
                self.amz_create_new_product else False
            vals[
                'shipment_charge_product_id'] = self.amz_shipment_charge_product_id.id if \
                self.amz_shipment_charge_product_id else False
            vals[
                'gift_wrapper_product_id'] = self.amz_gift_wrapper_product_id.id if \
                self.amz_gift_wrapper_product_id else False
            vals[
                'promotion_discount_product_id'] = self.amz_promotion_discount_product_id.id if \
                self.amz_promotion_discount_product_id else False
            vals[
                'ship_discount_product_id'] = self.amz_ship_discount_product_id.id if \
                self.amz_ship_discount_product_id else False
            vals[
                'fba_auto_workflow_id'] = self.amz_fba_auto_workflow_id.id if \
                self.amz_fba_auto_workflow_id else False
            vals[
                'is_another_soft_create_fba_shipment'] = \
                self.amz_is_another_soft_create_fba_shipment or False
            vals[
                'is_another_soft_create_fba_inventory'] = \
                self.amz_is_another_soft_create_fba_inventory or False
            vals[
                'validate_stock_inventory_for_report'] = \
                self.amz_validate_stock_inventory_for_report or False
            vals[
                'amz_is_reserved_qty_included_inventory_report'] = \
                self.amz_is_reserved_qty_included_inventory_report or False
            vals[
                'is_default_odoo_sequence_in_sales_order_fba'] = \
                self.amz_is_default_odoo_sequence_in_sales_order_fba or False
            vals[
                'def_fba_partner_id'] = self.amz_def_fba_partner_id.id \
                if self.amz_def_fba_partner_id else False
            vals[
                'payment_term_id'] = self.amz_payment_term_id.id if self.amz_payment_term_id \
                else False
            vals[
                'reimbursement_customer_id'] = self.amz_reimbursement_customer_id.id if \
                self.amz_reimbursement_customer_id else False
            vals[
                'reimbursement_product_id'] = self.amz_reimbursement_product_id.id if \
                self.amz_reimbursement_product_id else False
            vals[
                'sale_journal_id'] = self.amz_sales_journal_id.id if \
                self.amz_sales_journal_id else False
            vals['fulfillment_latency'] = self.amz_fulfillment_latency or 0
            vals['invoice_upload_policy'] = self.invoice_upload_policy
            vals['amz_upload_refund_invoice'] = self.amz_upload_refund_invoice
            vals['amz_invoice_report'] = self.amz_invoice_report.id or False
            vals['is_vcs_activated'] = True if self.invoice_upload_policy else False
            vals['amz_seller_analytic_account_id'] = self.amz_seller_analytic_account_id.id or False
            vals['fba_analytic_account_id'] = self.fba_analytic_account_id.id or False
            vals['fbm_analytic_account_id'] = self.fbm_analytic_account_id.id or False
            vals['is_amz_create_schedule_activity'] = self.is_amz_create_schedule_activity
            vals['amz_activity_user_ids'] = self.amz_activity_user_ids
            vals['amz_activity_type_id'] = self.amz_activity_type_id
            vals['amz_activity_date_deadline'] = self.amz_activity_date_deadline
            vals[
                'amz_outbound_instance_id'] = self.amz_outbound_instance_id.id if \
                self.amz_outbound_instance_id else False
            vals['is_fulfilment_center_configured'] = self.is_fulfilment_center_configured or False

            cron_id = self.env.ref('amazon_ept.ir_cron_auto_import_amazon_fulfillment_centers',
                                   raise_if_not_found=False).id
            if self.is_fulfilment_center_configured:
                self.env['ir.cron'].browse(cron_id).active = self.is_fulfilment_center_configured
            elif not any(self.env['amazon.seller.ept'].search([('id', '!=', self.amz_seller_id.id),
                                                               ('is_fulfilment_center_configured', '=', True)])):
                self.env['ir.cron'].browse(cron_id).active = False

            if self.is_allow_to_create_removal_order:
                vals['amz_fba_liquidation_partner'] = self.amz_fba_liquidation_partner or False
                vals['removal_order_report_days'] = self.removal_order_report_days or 3
                instance_for_removal_order = self.amz_seller_id.instance_ids.filtered( \
                    lambda r: r.id == self.amz_instance_removal_order.id)
                if instance_for_removal_order:
                    instance_for_removal_order.write({
                        'is_allow_to_create_removal_order': self.is_allow_to_create_removal_order
                                                            or False,
                        'removal_warehouse_id': self.removal_warehouse_id and
                                                self.removal_warehouse_id.id or False,
                    })
                    if not instance_for_removal_order.removal_order_config_ids. \
                            filtered(lambda l: l.removal_disposition == 'Liquidations'):
                        instance_for_removal_order.configure_amazon_removal_order_routes()
            else:
                if self.amz_seller_id.instance_ids:
                    self.amz_seller_id.instance_ids.write(
                        {'is_allow_to_create_removal_order': self.is_allow_to_create_removal_order or False,
                         'removal_warehouse_id': self.removal_warehouse_id.id if self.removal_warehouse_id else False})

            vals["allow_auto_create_outbound_orders"] = self.allow_auto_create_outbound_orders
            vals["create_outbound_on_confirmation"] = self.amz_create_outbound_on_confirmation
            vals["default_outbound_instance"] = self.amz_default_outbound_instance

            vals["fulfillment_action"] = self.fulfillment_action
            vals["shipment_category"] = self.shipment_category
            vals["fulfillment_policy"] = self.fulfillment_policy
            self.auto_create_outbound_scheduler()
            self.amz_seller_id.write(vals)
        if res and ctx:
            res['context'] = ctx
            res['params'] = {'seller_id': self.amz_seller_id and self.amz_seller_id.id,
                             'instance_id': instance and instance.id or False}
        return res

    def create_more_amazon_marketplace(self):
        """
        Create Other Amazon Marketplaces instance in ERP.
        :return:
        """
        action = self.env.ref('amazon_ept.res_config_action_amazon_marketplace', False)
        result = action.read()[0] if action else {}
        ctx = result.get('context', {}) and eval(result.get('context', {}))
        active_seller = request.session['amz_seller_id']
        if active_seller:
            marketplace_obj = self.env['amazon.marketplace.ept']
            amazon_active_seller = self.env[AMAZON_SELLER_EPT].browse(active_seller)
            amazon_active_seller.load_marketplace()
            market_place_id = amazon_active_seller.instance_ids.filtered(lambda x: x.market_place_id).mapped(
                'market_place_id')
            marketplace_id = marketplace_obj.search(
                [('seller_id', '=', active_seller), ('market_place_id', 'not in', market_place_id)])
            other_marketplace_ids = marketplace_obj.search([('market_place_id', 'in', ['A1F83G8C2ARO7P']),
                                                            ('seller_id', '=', active_seller)])
            ctx.update({'default_seller_id': active_seller,
                        'deactive_marketplace': marketplace_id.ids,
                        'default_other_marketplace_ids': other_marketplace_ids.ids})
        # ctx.update({'default_seller_id':request.session['amz_seller_id']})
        result['context'] = ctx
        return result

    def generate_buy_pack_url(self):
        """
        Generate Buy Pack URL while registering Seller ID
        :return: {}
        """
        url = 'https://iap.odoo.com/iap/1/credit?dbuuid='
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        service_name = 'amazon_ept'
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        if not account:
            account = self.env['iap.account'].create({'service_name': 'amazon_ept'})
        account_token = account.account_token
        if not account_token:
            account_token = self.get_account_token_ept(dbuuid)
        url = ('%s%s&service_name=%s&account_token=%s&credit=1') % (
            url, dbuuid, service_name, account_token)
        return {
            'type': URL_ACTION,
            'url': url,
            'target': 'new'
        }

    @staticmethod
    def get_account_token_ept(database_uid):
        """
        This method will help to find account_token from IAP for buy amazon connector IAP pack.
        :param database_uid: database id
        :return str: IAP Account token
        """
        kwargs = {'database_uid': database_uid}
        response = iap_tools.iap_jsonrpc('https://iap.odoo.emiprotechnologies.com/get_amz_iap_token', params=kwargs,
                                         timeout=1000)
        if response.get('error', False):
            raise UserError(_(response.get('error', False)))
        return response.get('amz_iap_token', '')

    def register_seller(self):
        """
        Registration of seller with IAP
        :return: dict
        """
        payload = {'key1': 'value1'}
        url = "https://iap.odoo.emiprotechnologies.com/amazon-seller-registration-sp-api"
        requests.post(url, data=payload)
        return {
            'type': URL_ACTION,
            'url': url,
            'target': 'new'
        }

    def create_amazon_seller_transaction_type(self):
        """
        Create Other Amazon Marketplaces instance in ERP.
        :return:
        """
        action = self.env.ref('amazon_ept.res_config_action_amazon_transaction_type', False)
        result = action.read()[0] if action else {}
        result.update({'domain': [('seller_id', '=', request.session['amz_seller_id'])]})
        return result

    def create_vcs_tax(self):
        """
        Used to configure the VCS tax
        """
        action = self.env.ref('amazon_ept.res_config_action_amazon_tax_configuration', False)
        result = action.read()[0] if action else {}
        result.update({'res_id': request.session['amz_seller_id']})
        return result

    def download_attached_module(self):
        """
        This Method relocates download sample file of amazon.
        :return: This Method return file download file.
        """
        attachment = self.env['ir.attachment'].search([('name', '=', 'account_tax_python_ept.zip'),
                                                       ('res_model', '=', 'res.config')])
        return {
            'type': URL_ACTION,
            'url': '/web/content/%s?download=true' % (attachment.id),
            'target': 'new',
            'nodestroy': False,
        }

    def auto_create_outbound_scheduler(self):
        """
        Auto Enable outbound orders scheduler on Configurations
        :return:
        """
        auto_create_outbound_order_cron = self.env.ref('amazon_ept.auto_create_outbound_order',
                                                       raise_if_not_found=False)
        if auto_create_outbound_order_cron and self.allow_auto_create_outbound_orders:
            vals = {
                'active': self.allow_auto_create_outbound_orders,
                'nextcall': datetime.now(),
                'doall': True
            }
            auto_create_outbound_order_cron.write(vals)
        elif auto_create_outbound_order_cron:
            auto_create_outbound_order_cron.write({'active': self.allow_auto_create_outbound_orders})

    def refresh_eu_tax_mapping(self):
        """
        test
        """
        result = super(AmazonConfigSettings, self).refresh_eu_tax_mapping()
        vat_config_obj = self.env['vat.config.ept']
        eu_countries = self.env.ref('base.europe').country_ids
        company = self.env.company
        multi_tax_reports_countries_fpos = self.env['account.fiscal.position'].search([
            ('company_id', '=', company.id),
            ('foreign_vat', '!=', False),
        ])
        oss_countries = eu_countries - company.account_fiscal_country_id - multi_tax_reports_countries_fpos.country_id
        fpos = self.env['account.fiscal.position'].search([
            ('country_id', 'in', oss_countries.ids),
            ('company_id', '=', company.id),
            ('auto_apply', '=', True),
            ('vat_required', '=', False),
            ('foreign_vat', '=', False),
            ('is_amazon_fpos', '=', False)])
        fpos.write({'is_amazon_fpos': True})
        vat_config_ids = vat_config_obj.search([('company_id', '=', company.id)])
        for vat_config in vat_config_ids:
            vat_config.amazon_eu_tax_mapping()
        return result

    def sync_fba_fulfilment_centers(self, sellers_id=[]):
        """
        when 'sync fulfilment center' button clicked form amazon configuration settings
        this method will call the method request_fba_fulfilment_centers of amazon seller
        which will sync the new fulfilment centers to the warehouse
        """
        active_seller = request.session['amz_seller_id']
        self.env['amazon.seller.ept'].request_fba_fulfilment_centers([active_seller])

    def open_operations_tutorial(self):
        """
        Prepare the iframe code for Amazon settings operations.
        :return: action to open the wizard with the video.
        """
        video_tutorial = {'Register Your Seller ID': 'gVFmsV8UsC0',
                          'Connect Your Seller Central Account': 'NHy4dXDf7E8'}
        if not self._context.get('tutorial_type'):
            return
        action = self.env["ir.actions.actions"]._for_xml_id("amazon_ept.action_amz_video_tutorial")
        url = f'<iframe width="920px" height="520px" ' \
              f'src="https://www.youtube.com/embed/' \
              f'{video_tutorial.get(self._context.get("tutorial_type"))}?autoplay=1" ' \
              f'title="YouTube video player" frameborder="0" ' \
              f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" ' \
              f'allowfullscreen></iframe>'
        action['context'] = str({'default_amz_video_url': url})
        action['name'] = self._context.get('tutorial_type')
        return action

    def document_open(self):
        document_url = {'register_seller':
                            "https://docs.emiprotechnologies.com/amazon-odoo-connector/v16/seller-registration.html",
                        'connect_your_seller':
                            "https://docs.emiprotechnologies.com/amazon-odoo-connector/v16/seller-registration.html",
                        'vat_number_configuration':
                            "https://docs.emiprotechnologies.com/amazon-odoo-connector/v16/vat-number-registration.html"
                        }
        if not self._context.get('document_to_open'):
            return
        return {
            'name': _("Document"),
            'type': 'ir.actions.act_url',
            'url': document_url.get(self._context.get('document_to_open')),
            'target': 'new',
        }
