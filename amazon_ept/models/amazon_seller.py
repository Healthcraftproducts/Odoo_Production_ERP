# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class to store the seller information
"""
import requests
import time
from datetime import datetime, timedelta
from odoo import SUPERUSER_ID
from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError
from ..endpoint import DEFAULT_ENDPOINT
from ..endpoint import FULFILLMENT_ENDPOINT

TYPE2JOURNAL = {
    'entry': 'Journal Entry',
    'out_invoice': 'Customer Invoice',
    'out_refund': 'Customer Credit Note',
    'in_invoice': 'Vendor Bill',
    'in_refund': 'Vendor Credit Note',
    'out_receipt': 'Sales Receipt',
    'in_receipt': 'Purchase Receipt'
}
LAST_SYNC_FIELDS = ['removal_order_report_last_sync_on', 'shipping_report_last_sync_on',
                    'inventory_report_last_sync_on', 'settlement_report_last_sync_on',
                    'fba_recommended_removal_report_last_sync_on', 'fba_order_last_sync_on',
                    'fba_pending_order_last_sync_on', 'return_report_last_sync_on',
                    'last_inbound_shipment_status_sync', 'vcs_report_last_sync_on', 'inventory_last_sync_on',
                    'rating_report_last_sync_on', 'stock_adjustment_report_last_sync_on', 'order_last_sync_on',
                    'update_shipment_last_sync_on']
AMZ_SELLER_EPT = 'amazon.seller.ept'
PRODUCT_PRODUCT = 'product.product'
AMZ_INSTANCE_EPT = 'amazon.instance.ept'
IR_CRON = 'ir.cron'
SALE_ORDER = 'sale.order'
RES_COUNTRY = 'res.country'
STOCK_LOCATION = 'stock.location'
IAP_ACCOUNT = 'iap.account'
DATABASE_UUID = 'database.uuid'
IR_CONFIG_PARAMETER = 'ir.config_parameter'


class AmazonSellerEpt(models.Model):
    """
    Added this class to store the amazon seller information.
    """
    _name = 'amazon.seller.ept'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Amazon Seller Details'

    @api.model
    def _get_default_shipment_amazon_fee(self):
        return self.env.ref('amazon_ept.product_product_amazon_shipping_ept', raise_if_not_found=False)

    @api.model
    def _get_default_gift_wrapper_fee(self):
        return self.env.ref('amazon_ept.product_product_amazon_giftwrapper_fee', raise_if_not_found=False)

    @api.model
    def _get_default_promotion_discount(self):
        return self.env.ref('amazon_ept.product_product_amazon_promotion_discount', raise_if_not_found=False)

    @api.model
    def _get_default_shipment_discount(self):
        return self.env.ref('amazon_ept.product_product_amazon_shipment_discount', raise_if_not_found=False)

    @api.model
    def _get_default_payment_term(self):
        return self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)

    @api.model
    def _get_default_auto_workflow(self):
        return self.env.ref('common_connector_library.automatic_validation_ept', raise_if_not_found=False)

    @api.model
    def _get_default_fba_partner_id(self):
        return self.env.ref('amazon_ept.amazon_fba_pending_order', raise_if_not_found=False)

    @api.model
    def _get_default_fba_auto_workflow(self):
        return self.env.ref('common_connector_library.automatic_validation_ept', raise_if_not_found=False)

    def _default_journal(self):
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', list(filter(None, list(map(TYPE2JOURNAL.get, inv_types))))),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)

    def _compute_scheduler_list(self):
        seller_cron = self.env[IR_CRON].sudo().search([('amazon_seller_cron_id', '=', self.id)])
        for record in self:
            record.cron_count = len(seller_cron.ids)

    def _compute_region(self):
        """
        This method will set is_european_region based on country code.
        """
        if self.country_id.code in ['AE', 'DE', 'EG', 'ES', 'FR', 'GB', 'IN', 'IT', 'SA', 'TR', 'NL', 'ZA']:
            self.is_european_region = True
        else:
            self.is_european_region = False

    @api.constrains('invoice_upload_policy')
    def _hide_show_vcs_vidr_menu(self):
        """
        This method will Hide and Show VCS Report and VIDR Report Menu In the Statement Menu.
        :return:
        """
        vcs_menu_id = self.env.ref('amazon_ept.menu_amazon_vcs_tax_report_ept')
        if not self.invoice_upload_policy:
            vcs_menu_id.write({'active': False})
        elif self.invoice_upload_policy == 'amazon':
            vcs_menu_id.write({'active': True})
        elif self.invoice_upload_policy == 'custom':
            vcs_menu_id.write({'active': False})

    name = fields.Char(size=120, required=True, help="Amazon Seller Name for ERP")
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')],
                                      string='Fulfillment By ?', default='FBM')
    merchant_id = fields.Char("Merchant ID")
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    country_id = fields.Many2one(RES_COUNTRY, string="Region",
                                 domain="[('amazon_marketplace_code','!=',False)]")
    instance_ids = fields.One2many(AMZ_INSTANCE_EPT, "seller_id", "Marketplaces",
                                   help="Amazon Instance id.")
    auth_token = fields.Char(help="Authentication Token created from Amazon seller central account")

    marketplace_ids = fields.One2many('amazon.marketplace.ept', 'seller_id', string='Amazon Marketplaces')
    is_default_odoo_sequence_in_sales_order = fields.Boolean(
        "Is default Odoo Sequence in Sales Orders ?")
    is_default_odoo_sequence_in_sales_order_fba = fields.Boolean(
        "Is default Odoo Sequence In Sales Orders (FBA) ?")
    order_prefix = fields.Char(size=10)
    fba_order_prefix = fields.Char(size=10, string='FBA Order Prefix')
    allow_to_process_shipped_order = fields.Boolean(
        'Allow to process shipped order (FBM) in odoo ?',
        default=False)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term',
                                      default=_get_default_payment_term)
    fbm_auto_workflow_id = fields.Many2one('sale.workflow.process.ept',
                                           string='Auto Workflow (FBM)',
                                           default=_get_default_auto_workflow)
    create_new_product = fields.Boolean('Allow to create new product if not found in odoo ?',
                                        default=False)
    fba_auto_workflow_id = fields.Many2one('sale.workflow.process.ept',
                                           string='Auto Workflow (FBA)',
                                           default=_get_default_fba_auto_workflow)
    fulfillment_latency = fields.Integer('Fullfillment Latency', default=3)
    shipment_charge_product_id = fields.Many2one(PRODUCT_PRODUCT, "Shipment Fee",
                                                 domain=[('type', '=', 'service')],
                                                 default=_get_default_shipment_amazon_fee)
    gift_wrapper_product_id = fields.Many2one(PRODUCT_PRODUCT, "Gift Wrapper Fee",
                                              domain=[('type', '=', 'service')],
                                              default=_get_default_gift_wrapper_fee)
    promotion_discount_product_id = fields.Many2one(PRODUCT_PRODUCT, "Promotion Discount",
                                                    domain=[('type', '=', 'service')],
                                                    default=_get_default_promotion_discount)
    ship_discount_product_id = fields.Many2one(PRODUCT_PRODUCT, "Shipment Discount",
                                               domain=[('type', '=', 'service')],
                                               default=_get_default_shipment_discount)
    transaction_line_ids = fields.One2many('amazon.transaction.line.ept', 'seller_id',
                                           'Transactions')
    reimbursement_customer_id = fields.Many2one("res.partner", string="Reimbursement Customer")
    reimbursement_product_id = fields.Many2one(PRODUCT_PRODUCT, string="Product")
    sale_journal_id = fields.Many2one('account.journal', string='Sales Journal',
                                      default=_default_journal, domain=[('type', '=', 'sale')])
    removal_order_report_last_sync_on = fields.Datetime("Last Removal Order Report Request Time")
    return_report_last_sync_on = fields.Datetime("Last Return Report Request Time")
    def_fba_partner_id = fields.Many2one('res.partner',
                                         string='Default Customer for FBA pending order',
                                         default=_get_default_fba_partner_id)
    is_another_soft_create_fba_shipment = fields.Boolean(
        string="Does another software create the FBA shipment reports?", default=False)
    amz_is_reserved_qty_included_inventory_report = fields.Boolean(
        string='Is Reserved Quantity to be included FBA Live Inventory Report?',
        help="Is Reserved Quantity to be included FBA Live Inventory Report")

    is_another_soft_create_fba_inventory = fields.Boolean(
        string="Does another software create the FBA Inventory reports?",
        default=False,
        help="Does another software create the FBA Inventory reports")

    validate_stock_inventory_for_report = fields.Boolean(
        "Auto Validate Amazon FBA Live Stock Report",
        help="Auto Validate Amazon FBA Live Stock Report")
    amz_warehouse_ids = fields.One2many('stock.warehouse', 'seller_id',
                                        string='Warehouses')

    inv_adjustment_report_days = fields.Integer("Inventory Adjustment Report Days", default=3,
                                                help="Days of report to import inventory Report")
    shipping_report_days = fields.Integer("Shipping Report Report Days", default=3,
                                          help="Days of report to import Shipping Report")
    customer_return_report_days = fields.Integer(default=3,
                                                 help="Days of report to import Customer Return Report")
    removal_order_report_days = fields.Integer("Removal Order Report Days", default=3,
                                               help="Days of report to import Removal ORder Report")
    live_inv_adjustment_report_days = fields.Integer("Live Inventory Adjustment Report Days", default=3,
                                                     help="Days of report to import Live inventory Report")
    # for cron
    order_auto_import = fields.Boolean(string='Auto Order Import?')
    order_last_sync_on = fields.Datetime("Last FBM Order Sync Time")
    update_shipment_last_sync_on = fields.Datetime("Last Shipment update status Sync Time")
    amz_order_auto_update = fields.Boolean("Auto Update Order Shipment ?")
    amz_stock_auto_export = fields.Boolean(string="Stock Auto Export?")
    # For Cron FBA
    auto_import_fba_pending_order = fields.Boolean(string='Auto Import FBA Pending Order?')
    fba_pending_order_last_sync_on = fields.Datetime("FBA Pending Order Last Sync Time")
    auto_import_shipment_report = fields.Boolean(string='Auto Import Shipment Report?')
    shipping_report_last_sync_on = fields.Datetime("Last Shipping Report Request Time")

    auto_create_removal_order_report = fields.Boolean(string="Auto Create Removal Order Report ?")
    auto_import_return_report = fields.Boolean(string='Auto Import Return Report?')
    auto_import_product_stock = fields.Boolean("Auto Import Amazon FBA Live Stock Report")
    auto_create_fba_stock_adj_report = fields.Boolean(string="Auto Create FBA Stock Adjustment Report ?")
    stock_adjustment_report_last_sync_on = fields.Datetime("Last Stock Adjustment Report Request Time")
    auto_send_refund = fields.Boolean("Auto Send Refund Via Email ?", default=False)
    auto_send_invoice = fields.Boolean("Auto Send Invoice Via Email ?", default=False)
    auto_check_cancel_order = fields.Boolean("Auto Check Cancel Order ?", default=False)
    settlement_report_auto_create = fields.Boolean("Auto Create Settlement Report ?", default=False)
    cron_count = fields.Integer("Scheduler Count",
                                compute="_compute_scheduler_list",
                                help="This Field relocates Scheduler Count.")

    fba_recommended_removal_report_last_sync_on = fields.Datetime("Last FBA Recommended  Report Request Time")
    inventory_report_last_sync_on = fields.Datetime("Last Inventory Report Request Time")
    settlement_report_last_sync_on = fields.Datetime("Settlement Report Last Sync Time")
    fba_order_last_sync_on = fields.Datetime("Last FBA Order Sync Time")
    is_european_region = fields.Boolean('Is European Region ?')
    is_north_america_region = fields.Boolean('Is North America Region ?', default=False)
    other_pan_europe_country_ids = fields.Many2many(RES_COUNTRY, 'other_pan_europe_country_seller_rel',
                                                    'res_marketplace_id',
                                                    'country_id', "Other Pan Europe Countries")
    last_inbound_shipment_status_sync = fields.Datetime()
    amz_auto_import_inbound_shipment_status = fields.Boolean(string='Auto Import Inbound Shipment '
                                                                    'Status ?')
    auto_import_rating_report = fields.Boolean(string='Auto Import Rating Report?')
    auto_process_rating_report = fields.Boolean(string='Auto Process Rating Report?')
    rating_report_days = fields.Integer(default=3,
                                        help="Days of report to import rating Report")
    rating_report_last_sync_on = fields.Datetime("Last Rating Report Request Time")

    b2b_amazon_tax_ids = fields.One2many('amazon.tax.configuration.ept', 'seller_id', string="B2B VCS Tax")
    is_vcs_activated = fields.Boolean(string="Is VCS Activated ?")
    fba_vcs_report_days = fields.Integer("Default VCS Request Report Days", default=3)
    amz_auto_import_vcs_tax_report = fields.Boolean(string='Auto import VCS Tax report ?')
    amz_auto_upload_tax_invoices = fields.Boolean(string='Auto Upload Tax Invoices to Amazon ?')
    amz_auto_process_vcs_tax_report = fields.Boolean(string='Download and Process VCS Tax Report ?')
    vcs_report_last_sync_on = fields.Datetime("Last VCS Report Request Time")
    vidr_report_last_sync_on = fields.Datetime("Last VIDR Report Request Time")

    amazon_program = fields.Selection([('pan_eu', 'PAN EU'),
                                       ('efn', 'EFN'),
                                       ('mci', 'MCI'),
                                       ('cep', 'CEP'),
                                       ('efn+mci', 'EFN+MCI')])
    amz_fba_us_program = fields.Selection([('narf', 'NARF')])
    store_inv_wh_efn = fields.Many2one(RES_COUNTRY, string="Store Inv. Country")
    active = fields.Boolean(default=True)
    allow_auto_create_outbound_orders = fields.Boolean()
    fulfillment_action = fields.Selection([("Ship", "Ship"), ("Hold", "Hold")])
    shipment_category = fields.Selection([("Expedited", "Expedited"),
                                          ("Standard", "Standard"),
                                          ("Priority", "Priority"),
                                          ("ScheduledDelivery", "ScheduledDelivery")],
                                         default="Standard")
    fulfillment_policy = fields.Selection([("FillOrKill", "FillOrKill"), ("FillAll", "FillAll"),
                                           ("FillAllAvailable", "FillAllAvailable")],
                                          default="FillOrKill")
    invoice_upload_policy = fields.Selection([("amazon", "Amazon Create invoices"),
                                              ("custom", "Upload Invoice from Odoo")])
    amz_outbound_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, string='Default Outbound Marketplace',
                                               help="Select Amazon Instance for Outbound Orders.")
    amz_upload_refund_invoice = fields.Boolean(string='Export Customer Refunds to Amazon via API?', default=False)
    amz_invoice_report = fields.Many2one("ir.actions.report", string="Invoice Report")
    is_fulfilment_center_configured = fields.Boolean(string='Are Fulfillment Centers Required to Import FBA Orders?',
                                                     help='If True, then Orders will not be imported if the fulfillment'
                                                          ' center is not configured in an appropriate warehouse.',
                                                     default=False)
    amz_auto_import_shipped_orders = fields.Boolean(string="Auto Import Shipped Orders?",
                                                    help="If checked, then system auto import shipped "
                                                         "orders from amazon", default=False)
    amz_fba_liquidation_partner = fields.Many2one("res.partner", string="FBA Liquidation Partner",
                                                  help="This Partner will be used as delivery partner for "
                                                       "FBA Liquidation Removal Order.")
    is_sp_api_amz_seller = fields.Boolean(string="Is SPAPI Seller?",
                                          help="This is used to identify is seller registered in SPAPI?")
    create_outbound_on_confirmation = fields.Boolean("Create Outbound On Order Confirmation",
                                                     help="This will allow to create outbound order when order is "
                                                          "confirmed.")
    default_outbound_instance = fields.Many2one(AMZ_INSTANCE_EPT, string='Default Instance for Outbound Orders')
    amz_seller_analytic_account_id = fields.Many2one('account.analytic.account',
                                                     string='Analytic Account (Seller)',
                                                     help='Analytic Account for Amazon Seller.')
    fba_analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account (FBA)',
                                              help='Analytic Account for Amazon FBA Seller.')
    fbm_analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account (FBM)',
                                              help='Analytic Account for Amazon FBM Seller.')
    is_amz_create_schedule_activity = fields.Boolean("Create Schedule Activity ? ", default=False,
                                                     help="If checked, Then Schedule Activity create for "
                                                          "import orders if any products missing.")
    amz_activity_user_ids = fields.Many2many('res.users', 'res_users_amazon_seller_rel',
                                             'seller_id', 'res_users_id', string='Responsible User')
    amz_activity_type_id = fields.Many2one('mail.activity.type', string="Activity Type")
    amz_activity_date_deadline = fields.Integer('Deadline lead days',
                                                help="its add number of days in schedule activity deadline date ")

    def write(self, vals):
        """
        This method is Overridden with super call
        to make a Logger Note about the changes that user have made in the current model
        :return super()
        """
        for amz_seller in self:
            msg = ""
            new = amz_seller.new(vals)
            for key, value in vals.items():
                if getattr(amz_seller, key) != getattr(new, key):
                    if isinstance(getattr(amz_seller, key), models.BaseModel) and \
                            getattr(amz_seller, key).ids == getattr(new, key).ids:
                        continue
                    if amz_seller.amz_check_last_sync_field(key):
                        continue
                    msg += "<li><b>%s:  </b> %s  ->  %s</li>" % \
                           (amz_seller._fields.get(key).string,
                            amz_seller.env['ir.qweb']._get_field(amz_seller, key, '', '', {}, {})[1],
                            amz_seller.env['ir.qweb']._get_field(new, key, '', '', {}, {})[1])
            if msg and msg != "":
                amz_seller.message_post(body=msg)
        return super(AmazonSellerEpt, self).write(vals)

    @staticmethod
    def amz_check_last_sync_field(key):
        """
        Define this method for skip to creating a tracking log note for the last sync fields of the Amazon schedulers
        for the amazon sellers.
        :param: key : str (field name)
        :return: boolean (TRUE/FALSE)
        """
        if str(key) in LAST_SYNC_FIELDS:
            return True
        return False

    def deactivate_fba_warehouse(self):
        """
        Define method which help to deactivate FBA warehouse of Amazon seller.
        """
        for seller in self:
            if seller.amazon_program in ('pan_eu', 'cep'):
                location = seller.amz_warehouse_ids.mapped('lot_stock_id')
                warehouses = tuple(seller.amz_warehouse_ids.ids)
                for warehouse in seller.amz_warehouse_ids:
                    name = warehouse.name + 'archived' + (seller.amazon_program)
                    warehouse.name = name + str(time.time())[-2:]
                    warehouse.code = warehouse.code + str(time.time())[-2:]
                    warehouse.fulfillment_center_ids.unlink()
                unsellable_location = seller.amz_warehouse_ids.mapped('unsellable_location_id')
                picking_types = self.env['stock.picking.type'].search(
                    [('warehouse_id', 'in', seller.amz_warehouse_ids.ids)])
                rule_ids = self.env['stock.rule'].search([('warehouse_id', 'in', seller.amz_warehouse_ids.ids)])
                rule_ids.write({'active': False})
                route_ids = seller.amz_warehouse_ids.mapped('route_ids')
                route_ids.write({'active': False})

                if location:
                    if len(location) > 1:
                        self._cr.execute(
                            'update stock_location set active=False where id in %s' % (str(tuple(location.ids, ))))
                    else:
                        self._cr.execute(
                            'update stock_location set active=False where id = %s' % (location.id))
                if picking_types:
                    self._cr.execute('update stock_picking_type set active=False where id in %s' % (
                        str(tuple(picking_types.ids))))
                if warehouses:
                    qry = '''update stock_warehouse set active=False where id in %s''' % (
                        str(warehouses))
                    self._cr.execute(qry)
                unsellable_location and unsellable_location.write({'active': False})

            if (seller.amazon_program in ('efn', 'mci', 'efn+mci')) or (not seller.amazon_program):
                warehouses = seller.amz_warehouse_ids
                unsellable_location = seller.amz_warehouse_ids.mapped('unsellable_location_id')
                for wh in warehouses:
                    if not seller.amazon_program:
                        name = wh.name + 'archived'
                    else:
                        name = wh.name + 'archived' + (seller.amazon_program)
                    wh.write({'active': False, 'name': name + str(time.time())[-2:],
                              'code': wh.code + str(time.time())[-2:]})
                    wh.fulfillment_center_ids.unlink()
                unsellable_location and unsellable_location.write({'active': False})

    def process_schedulers(self):
        """
        This method deactivate the schedulers created for the particular seller
        and add archived_<seller_id> in the name of scheduler while archiving seller
        and while activating seller the method will remove archived message form the name of schedulers
        """
        schedulers = self.env['ir.cron'].search([('amazon_seller_cron_id', '=', self.id),
                                                 ('active', 'in', [True, False])])
        if self.active:
            for scheduler in schedulers:
                name = f"{scheduler.name}(archived_{self.id})"
                scheduler.write({'name': name,
                                 'active': False})
        else:
            for scheduler in schedulers:
                name = scheduler.name.split('(')[0]
                scheduler.write({'name': name})

    def toggle_active(self):
        """
        This method will check the active status of seller.
        If active the method will open a for un-archiving the seller
        """
        archive = self.filtered('active')
        unarchive = self.filtered(lambda seller: seller.active == False)
        if archive:
            action = self.env["ir.actions.actions"]._for_xml_id("amazon_ept.action_archive_seller_confirmation")
            action['context'] = {'active_seller': True, 'active_ids': archive.ids}
            return action
        elif unarchive:
            action = self.env["ir.actions.actions"]._for_xml_id("amazon_ept.action_un_archive_seller_confirmation")
            action['context'] = {'active_seller': False, 'active_ids': unarchive.ids}
            return action

    def archive_seller(self):
        """
        This method will archive the seller, if the user confirm form the confirmation wizard
        :return: Boolean
        """
        if self._context.get('confirm_archive', False):
            self.process_schedulers()
            self.env['amazon.product.ept'].search([('instance_id', '=', self.instance_ids.ids)]).unlink()
            self.deactivate_fba_warehouse()
            for seller in self:
                seller.with_context(deactive_seller=True).update_user_groups()
            if self.instance_ids:
                self.instance_ids.write({'active': False})
            self.active = False
            return True

    def unarchive_seller(self):
        """
        This method will un-archive the seller
        """
        if not self._context.get('confirm_un_archive'):
            return False
        seller_exist = self.env[AMZ_SELLER_EPT].search([('auth_token', '=', self.auth_token),
                                                        ('merchant_id', '=', self.merchant_id)])

        if seller_exist:
            raise UserError(_(
                'You can not active this seller due to other seller already created with same '
                'credential.'))

        instance_ids = self.with_context({'active_test': False}).instance_ids
        instance_ids and instance_ids.write({'active': True})
        fba_warehouse_ids = self.with_context({'active_test': False}).amz_warehouse_ids
        if fba_warehouse_ids:
            picking_types = self.env['stock.picking.type'].search(
                [('warehouse_id', 'in', fba_warehouse_ids.ids), ('active', '=', False)])
            picking_types and picking_types.write({'active': True})
            unsellable_location = fba_warehouse_ids.mapped('unsellable_location_id')
            unsellable_location and unsellable_location.write({'active': True})
            rule_ids = self.env['stock.rule'].search(
                [('warehouse_id', 'in', fba_warehouse_ids.ids), ('active', '=', False)])
            rule_ids and rule_ids.write({'active': True})
            route_ids = fba_warehouse_ids.with_context({'active_test': False}).mapped(
                'route_ids')
            route_ids and route_ids.write({'active': True})
            location = fba_warehouse_ids.with_context({'active_test': False}).mapped('lot_stock_id')
            if len(location) == 1:
                self._cr.execute(
                    'update stock_location set active=True where id =%s' % (location.id))
            else:
                location = tuple(location.ids)
                self._cr.execute('update stock_location set active=True where id in %s' % str(location))

            if len(fba_warehouse_ids) > 1:
                fba_warehouse_ids = tuple(fba_warehouse_ids.ids)
                qry = '''update stock_warehouse set active=True where id in %s''' % (str(fba_warehouse_ids))
                self._cr.execute(qry)
            else:
                qry = '''update stock_warehouse set active=True where id = %s''' % (fba_warehouse_ids.id)
                self._cr.execute(qry)
            for fba_warehouse in self.with_context({'active_test': False}).amz_warehouse_ids:
                name = fba_warehouse.name.split(')')[0]
                name = name + ')'
                fba_warehouse.write({'name': name})
        self.process_schedulers()
        for seller in self:
            seller.update_user_groups()
        self.active = True
        self._cr.commit()
        self.request_fba_fulfilment_centers(self.id)

    def amz_assign_sales_team_in_marketplaces(self, amazon_seller):
        """
        Define this method for set amazon seller sales team in the marketplaces.
        :param: amazon_seller: amazon.seller.ept()
        :return: boolean
        """
        crm_team_obj = self.env['crm.team']
        team_name = "Amazon-" + amazon_seller.name
        amz_sales_team = crm_team_obj.search([('name', '=', team_name)], limit=1)
        if amz_sales_team:
            for amazon_marketplace in amazon_seller.instance_ids:
                if not amazon_marketplace.team_id:
                    amazon_marketplace.write({'team_id': amz_sales_team.id})
        return True

    def amz_create_analytic_account(self):
        """
        Define method for create Analytic Account and Plan records for Amazon seller
        and marketplaces.
        :return: boolean (TRUE)
        """
        amazon_sellers = self.search([])
        if self.env.user.has_group('analytic.group_analytic_accounting') and amazon_sellers:
            self.amz_create_analytic_account_for_seller(amazon_sellers)
            if amazon_sellers.instance_ids and amazon_sellers.instance_ids.filtered(
                    lambda instance: not instance.analytic_account_id):
                account_required_marketplaces = amazon_sellers.instance_ids.filtered(
                    lambda instance: not instance.analytic_account_id)
                self.amz_create_analytic_account_for_marketplaces(account_required_marketplaces)
        return True

    def amz_search_or_create_analytic_account_plan(self):
        """
        Define this method for search or create Amazon analytic plan.
        :return: account.analytic.plan()
        """
        analytic_account_plan_obj = self.env['account.analytic.plan']
        analytic_account_plan = analytic_account_plan_obj.search(
            [('name', '=', 'Amazon'), ('company_id', '=', self.env.user.company_id.id)], limit=1)
        if not analytic_account_plan:
            analytic_account_plan = analytic_account_plan_obj.create({'name': 'Amazon'})
        return analytic_account_plan

    def amz_search_or_create_analytic_account(self, account_name, analytic_account_plan):
        """
        Define this method for search or create analytic account.
        :param: account_name: str
        :param: analytic_account_plan: account.analytic.plan()
        :return: account.analytic.account()
        """
        analytic_account_obj = self.env['account.analytic.account']
        analytic_account = analytic_account_obj.search([('name', '=', account_name),
                                                        ('plan_id', '=', analytic_account_plan.id),
                                                        ('company_id', '=', self.env.user.company_id.id)], limit=1)
        if not analytic_account:
            analytic_account = analytic_account_obj.create({'name': account_name, 'plan_id': analytic_account_plan.id})
        return analytic_account

    def amz_create_analytic_account_for_seller(self, amazon_sellers):
        """
        Define method for create analytic account and plan records for Amazon Sellers.
        :param: amazon_sellers: list of amazon.seller.ept() objects
        :return: boolean (TRUE)
        """
        analytic_account_plan = self.amz_search_or_create_analytic_account_plan()
        for amazon_seller in amazon_sellers:
            if not amazon_seller.amz_seller_analytic_account_id:
                seller_analytic_account = self.amz_search_or_create_analytic_account(amazon_seller.name,
                                                                                     analytic_account_plan)
                amazon_seller.write({'amz_seller_analytic_account_id': seller_analytic_account.id})
            fba_account_name = ''
            fbm_account_name = ''
            if amazon_seller.amazon_selling == 'FBA':
                fba_account_name = amazon_seller.name + '_FBA'
            elif amazon_seller.amazon_selling == 'FBM':
                fbm_account_name = amazon_seller.name + '_FBM'
            elif amazon_seller.amazon_selling == 'Both':
                fba_account_name = amazon_seller.name + '_FBA'
                fbm_account_name = amazon_seller.name + '_FBM'
            if fba_account_name and not amazon_seller.fba_analytic_account_id:
                fba_analytic_account = self.amz_search_or_create_analytic_account(fba_account_name,
                                                                                  analytic_account_plan)
                amazon_seller.write({'fba_analytic_account_id': fba_analytic_account.id})
            if fbm_account_name and not amazon_seller.fbm_analytic_account_id:
                fbm_analytic_account = self.amz_search_or_create_analytic_account(fbm_account_name,
                                                                                  analytic_account_plan)
                amazon_seller.write({'fbm_analytic_account_id': fbm_analytic_account.id})
        return True

    def amz_create_analytic_account_for_marketplaces(self, amazon_marketplaces):
        """
        Define method for create Analytic Account for marketplaces.
        :param: amazon_sellers: list of amazon.instance.ept() objects
        :return: boolean (TRUE)
        """
        analytic_account_plan = self.amz_search_or_create_analytic_account_plan()
        for amazon_marketplace in amazon_marketplaces:
            if not amazon_marketplace.analytic_account_id:
                account_name = amazon_marketplace.seller_id.name + amazon_marketplace.name
                marketplace_analytic_account = self.amz_search_or_create_analytic_account(account_name,
                                                                                          analytic_account_plan)
                amazon_marketplace.write({'analytic_account_id': marketplace_analytic_account.id})
        return True

    def list_of_seller_cron(self):
        """
        This method return action which list out seller scheduler.
        """
        seller_cron = self.env[IR_CRON].sudo().search([('amazon_seller_cron_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(seller_cron.ids) + " )]",
            'name': 'Cron Scheduler',
            'view_mode': 'tree,form',
            'res_model': IR_CRON,
            'type': 'ir.actions.act_window',
        }
        return action

    def fbm_cron_configuration_action(self):
        """
        This method will return the FBM cron config action.
        """
        action = self.env.ref('amazon_ept.action_wizard_fbm_cron_configuration_ept').read()[0]
        context = {'amz_seller_id': self.id, 'amazon_selling': self.amazon_selling}
        action['context'] = context
        return action

    def fba_cron_configuration_action(self):
        """
        This method will return the FBA cron config action.
        """
        action = self.env.ref('amazon_ept.action_wizard_fba_cron_configuration_ept').read()[0]
        context = {'amz_seller_id': self.id, 'amazon_selling': self.amazon_selling}
        action['context'] = context
        return action

    def global_cron_configuration_action(self):
        """
        This method will return the GLOBAL cron config action.
        """
        action = self.env.ref('amazon_ept.action_wizard_global_cron_configuration_ept').read()[0]
        context = {'amz_seller_id': self.id, 'amazon_selling': self.amazon_selling}
        action['context'] = context
        return action

    def amazon_instance_list(self):
        """
        This method will return the amazon instance list.
        """
        instance_obj = self.env[AMZ_INSTANCE_EPT].search([('seller_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(instance_obj.ids) + " )]",
            'name': 'Active Instance',
            'view_mode': 'tree,form',
            'res_model': AMZ_INSTANCE_EPT,
            'type': 'ir.actions.act_window',
        }
        return action

    def auto_import_sale_order_ept(self, args={}):
        """
        This method will auto process import sale order.
        """
        fbm_sale_order_obj = self.env['fbm.sale.order.report.ept']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            fbm_sale_order_obj.with_context(is_auto_process=True).auto_import_unshipped_order_report(seller)
            seller.write({'order_last_sync_on': datetime.now()})
        return True

    @api.model
    def auto_process_unshipped_sale_order_ept(self, args={}):
        """
        This method will auto process unshipped sale order.
        """
        fbm_sale_order_obj = self.env['fbm.sale.order.report.ept']
        seller_id = args.get('seller_id', False)
        is_skip = False
        if seller_id:
            seller = self.browse(int(seller_id))
            cron_id = self.env.ref('amazon_ept.%s%d' % ("ir_cron_import_missing_unshipped_orders_seller_", seller_id),
                                   raise_if_not_found=False)
            if cron_id and cron_id.sudo().active:
                res = cron_id.sudo().try_cron_lock()
                if res and res.get('reason', {}):
                    is_skip = True
            cron_id = self.env.ref('amazon_ept.%s' % ("ir_cron_child_to_process_shipped_order_queue_line"),
                                   raise_if_not_found=False)
            if cron_id and cron_id.sudo().active:
                res = cron_id.sudo().try_cron_lock()
                if res and res.get('reason', {}):
                    is_skip = True
            if not is_skip:
                fbm_sale_order_obj.with_context(is_auto_process=True).auto_process_unshipped_order_report(seller)
        return True

    @api.model
    def auto_process_missing_unshipped_sale_order_ept(self, args={}):
        """
        Auto process Missing Unshipped Sale Orders.
        """
        sale_order_obj = self.env[SALE_ORDER]
        seller_id = args.get('seller_id', False)
        is_skip = False
        if seller_id:
            seller = self.browse(int(seller_id))
            cron_id = self.env.ref('amazon_ept.%s%d' % ("ir_cron_process_amazon_unshipped_orders_seller_", seller_id),
                                   raise_if_not_found=False)
            if cron_id and cron_id.sudo().active:
                res = cron_id.sudo().try_cron_lock()
                if res and res.get('reason', {}):
                    is_skip = True
            if not is_skip:
                sale_order_obj.import_fbm_shipped_or_missing_unshipped_orders(seller, False, False,
                                                                              ['Unshipped', 'PartiallyShipped'])
        return True

    @api.model
    def auto_update_order_status_ept(self, args={}):
        """
        This method will auto update order status.
        """
        sale_order_obj = self.env[SALE_ORDER]
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            sale_order_obj.with_context({'auto_process': True}).amz_update_tracking_number(seller)
            seller.write({'update_shipment_last_sync_on': datetime.now()})
        return True

    @api.model
    def fbm_auto_check_cancel_order_in_amazon(self, args={}):
        """
        This method will auto check cancel order in amazon.
        """
        sale_order_obj = self.env[SALE_ORDER]
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            marketplaceids = tuple([x.market_place_id for x in seller.instance_ids])
            sale_order_obj.with_context(is_auto_process=True).cancel_amazon_fbm_pending_sale_orders(
                seller, marketplaceids, seller.instance_ids.ids)
        return True

    @api.model
    def auto_export_inventory_ept(self, args={}):
        """
        Auto export product stock in Amazon.
        """
        amazon_product_obj = self.env['amazon.product.ept']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            if seller:
                for instance in seller.instance_ids:
                    amazon_product_obj.export_amazon_stock_levels_operation(instance)
                    instance.write({'inventory_last_sync_on': datetime.now()})
        return True

    # FBA Pending Order
    @api.model
    def auto_import_fba_pending_sale_order_ept(self, args={}):
        """
        Auto process of import FBA pending orders.
        """
        sale_order_obj = self.env[SALE_ORDER]
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            marketplaceids = tuple([x.market_place_id for x in seller.instance_ids])
            last_sync = seller.fba_pending_order_last_sync_on
            sale_order_obj.with_context(is_auto_process=True).import_fba_pending_sales_order(
                seller, marketplaceids, last_sync)
            seller.write({'fba_pending_order_last_sync_on': datetime.now()})
            sale_order_obj.with_context(is_auto_process=True).cancel_amazon_fba_pending_sale_orders(
                seller, marketplaceids, seller.instance_ids.ids)
        return True

    @api.model
    def auto_import_fba_shipment_status_ept(self, args={}):
        """
        Auto process of FBA import status from Amazon.
        Purpose: Action Back Orders Pickings and Create Return Picking
        :param args:
        :return:
        """
        inbound_shipment_obj = self.env['amazon.inbound.shipment.ept']
        common_log_line_obj = self.env['common.log.lines.ept']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(seller_id)
            current_date = datetime.utcnow()
            last_updated_before = current_date
            if seller.last_inbound_shipment_status_sync:
                last_sync_time = seller.last_inbound_shipment_status_sync
            else:
                last_sync_time = datetime.utcnow()
            last_updated_after = (last_sync_time - timedelta(days=1))
            # preparing request kwargs
            kwargs = self.prepare_fba_shipment_status_request_kwargs(seller)
            kwargs.update({'emipro_api': 'check_amazon_shipment_status_spapi',
                           'last_updated_after': last_updated_after.isoformat(),
                           'last_updated_before': last_updated_before.isoformat()})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                raise UserError(_(response.get('error', {})))
            items = response.get('items', {})
            amazon_inbound_shipments = {}
            for amazon_result in items:
                shipment_id = amazon_result.get('ShipmentId', '')
                seller_sku = amazon_result.get('SellerSKU', '')
                if amazon_inbound_shipments:
                    keys = amazon_inbound_shipments.keys()
                    if shipment_id in keys:
                        ship_members = amazon_inbound_shipments.get(shipment_id)
                        flag = 1
                        for ship_member in ship_members:
                            if seller_sku == ship_member.get('SellerSKU', ''):
                                new_received_quantity = amazon_result.get('QuantityReceived', 0.0)
                                old_quantity = ship_member.get('QuantityReceived', 0.0)
                                qty = float(old_quantity) + (float(new_received_quantity))
                                ship_member.update({'QuantityReceived': str(qty)})
                                flag = 0
                        if flag:
                            ship_members.append(amazon_result)
                            amazon_inbound_shipments.update({shipment_id: ship_members})
                    else:
                        amazon_inbound_shipments.update({shipment_id: [amazon_result]})
                else:
                    amazon_inbound_shipments.update({shipment_id: [amazon_result]})
            if amazon_inbound_shipments:
                inbound_shipment_obj.check_status_ept(amazon_inbound_shipments, seller)
                max_range = 0
                ship_id_list = amazon_inbound_shipments.keys()
                while max_range < len(ship_id_list):
                    ship_id_list = list(ship_id_list)
                    kwargs = self.prepare_fba_shipment_status_request_kwargs(seller)
                    kwargs.update({'emipro_api': 'check_status_by_shipment_ids',
                                   'shipment_ids': ','.join(ship_id_list[max_range:max_range + 50])})
                    max_range += 50
                    response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
                    if response.get('error', False):
                        raise UserError(_(response.get('error', {})))
                    items = response.get('amazon_shipments', {})
                    shipment_status = {}
                    for ship_member in items:
                        shipmentid = ship_member.get('ShipmentId', '')
                        status = ship_member.get('ShipmentStatus', '')
                        shipment_status[shipmentid] = status
                    inbound_shipment_ids = shipment_status.keys()
                    inbound_shipments = inbound_shipment_obj.search(
                        [('shipment_id', 'in', list(inbound_shipment_ids))])
                    for inbound_shipment in inbound_shipments:
                        ship_status = shipment_status.get(inbound_shipment.shipment_id)
                        inbound_shipment.write({'state': ship_status})
                        if ship_status == 'CLOSED':
                            if not inbound_shipment.closed_date:
                                inbound_shipment.write({'closed_date': time.strftime("%Y-%m-%d")})
                            pickings = inbound_shipment.mapped('picking_ids').filtered(
                                lambda r: r.state not in ['done', 'cancel'] and r.is_fba_wh_picking)
                            pickings and pickings.action_cancel()
                            # create qty difference return for inbound shipment
                            self.amz_return_shipment_qty_difference(inbound_shipment)
                message = "%s inbound shipment is successfully processed" % (len(amazon_inbound_shipments))
                common_log_line_obj.create_common_log_line_ept(message=message,
                                                               model_name='amazon.inbound.shipment.ept',
                                                               module='amazon_ept', operation_type='import',
                                                               amz_seller_ept=seller.id)
            seller.last_inbound_shipment_status_sync = last_updated_before
        return True

    @api.model
    def auto_all_inbound_shipment_check_status_ept(self, args={}):
        """
        Define this method for auto check status of all inbound shipment which check status
        are not done via main scheduler of check status.
        :param args: dict {}
        :return: True
        """
        inbound_shipment_obj = self.env['amazon.inbound.shipment.ept']
        common_log_line_obj = self.env['common.log.lines.ept']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(seller_id)
            instances = seller.instance_ids
            shipments = inbound_shipment_obj.search([('instance_id_ept', 'in', instances.ids),
                                                     ('state', 'not in', ('CLOSED', 'CANCELLED',
                                                                          'DELETED', 'ERROR', 'draft'))])
            for shipment in shipments:
                try:
                    shipment.check_status()
                except Exception as ex:
                    common_log_line_obj.create_common_log_line_ept(
                        message=str(ex), model_name='amazon.inbound.shipment.ept',
                        module='amazon_ept', operation_type='import', res_id=shipment.id,
                        order_ref=shipment.shipment_id, amz_seller_ept=seller_id)
                self._cr.commit()
        return True

    def amz_return_shipment_qty_difference(self, inbound_shipment):
        """
        Define this method for create return picking for qty difference for shipment.
        :param: inbound_shipment : amazon.inbound.shipment.ept()
        :return: True
        """
        common_log_line_obj = self.env['common.log.lines.ept']
        inbound_shipment_obj = self.env['amazon.inbound.shipment.ept']
        stock_picking_obj = self.env['stock.picking']
        instance = inbound_shipment_obj.get_instance(inbound_shipment)
        kwargs = inbound_shipment_obj.amz_prepare_inbound_shipment_kwargs_vals(instance)
        kwargs.update({'emipro_api': 'check_amazon_shipment_status_spapi',
                       'amazon_shipment_id': inbound_shipment.shipment_id})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            common_log_line_obj.create_common_log_line_ept(
                message=response.get('error', ''), model_name='amazon.inbound.shipment.ept',
                module='amazon_ept', operation_type='import',
                amz_seller_ept=instance.seller_id and instance.seller_id.id or False,
                amz_instance_ept=instance and instance.id or False)
        else:
            inbound_shipment_obj.get_remaining_qty_ept(
                inbound_shipment.instance_id_ept, inbound_shipment.shipment_id, inbound_shipment,
                response.get('items', []))
            stock_picking_obj.check_qty_difference_and_create_return_picking_ept(
                inbound_shipment.shipment_id, inbound_shipment, inbound_shipment.instance_id_ept,
                response.get('items', []))
        return True

    def prepare_fba_shipment_status_request_kwargs(self, seller):
        """
        Prepare Arguments for FBA Shipment Status Request.
        :param : seller : Amazon Seller reference
        :return : dict{}
        """
        account_obj = self.env[IAP_ACCOUNT]
        ir_config_parameter_obj = self.env[IR_CONFIG_PARAMETER]
        account = account_obj.search([('service_name', '=', 'amazon_ept')])
        dbuuid = ir_config_parameter_obj.sudo().get_param(DATABASE_UUID)
        return {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                'app_name': 'amazon_ept_spapi',
                'account_token': account.account_token,
                'dbuuid': dbuuid,
                'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                           seller.country_id.code
                }

    def prepare_marketplace_kwargs(self):
        """
        Prepare Arguments for Load Marketplace.
        :return: dict{}
        """
        account_obj = self.env[IAP_ACCOUNT]
        ir_config_parameter_obj = self.env[IR_CONFIG_PARAMETER]
        account = account_obj.search([('service_name', '=', 'amazon_ept')])
        dbuuid = ir_config_parameter_obj.sudo().get_param(DATABASE_UUID)
        return {'merchant_id': self.merchant_id and str(self.merchant_id) or False,
                'app_name': 'amazon_ept_spapi',
                'account_token': account.account_token,
                'emipro_api': 'load_marketplace_sp_api',
                'dbuuid': dbuuid,
                'amazon_selling': self.amazon_selling,
                'amazon_marketplace_code': self.country_id.amazon_marketplace_code or
                                           self.country_id.code
                }

    def prepare_marketplace_vals(self, marketplace, participation_dict):
        """
        Prepatation of values of marketplaces to create in odoo
        :param marketplace: dict{}
        :param participation_dict: dict{}
        :return: {}
        """
        currency_obj = self.env['res.currency']
        lang_obj = self.env['res.lang']
        country_obj = self.env[RES_COUNTRY]
        country_code = marketplace.get('countryCode', '')
        name = marketplace.get('name', '')
        domain = marketplace.get('domainName', '')
        lang_code = marketplace.get('defaultLanguageCode', '')
        currency_code = marketplace.get('defaultCurrencyCode', '')
        marketplace_id = marketplace.get('id', '')
        currency_id = currency_obj.search([('name', '=', currency_code)])
        if not currency_id:
            currency_id = currency_id.search([('name', '=', currency_code), ('active', '=', False)])
            currency_id.write({'active': True})
        lang_id = lang_obj.search([('code', '=', lang_code)])
        country_id = country_obj.search([('code', '=', country_code)])
        return {
            'seller_id': self.id,
            'name': name,
            'market_place_id': marketplace_id,
            'is_participated': participation_dict.get('isParticipating', False),
            'domain': domain,
            'currency_id': currency_id and currency_id[0].id or False,
            'lang_id': lang_id and lang_id[0].id or False,
            'country_id': country_id and country_id[0].id or self.country_id and self.country_id.id or False,
        }

    def load_marketplace(self):
        """
        Load Amazon Marketplaces based on seller regions.
        :return: True
        """
        marketplace_list = ['A2Q3Y263D00KWC', 'A2EUQ1WTGCTBG2', 'A1AM78C64UM0Y8', 'ATVPDKIKX0DER', 'A2VIGQ35RCS4UG',
                            'A1PA6795UKMFR9', 'ARBP9OOSHTCHU', 'A1RKKUPIHCS9HS', 'A13V1IB3VIYZZH', 'A1F83G8C2ARO7P',
                            'A21TJRUUN4KGV', 'APJ6JRA9NG5V4', 'A33AVAJ2PDY3EV', 'A19VAU5U5O7RUS', 'A39IBJ37TRP1C6',
                            'A1VC38T7YXB528', 'A17E79C6D8DWNP', 'A1805IZSGTT6HS', 'A2NODRKZP88ZB9', 'A1C3SOZRARQ6R3',
                            'AMEN7PMS3EDWL', 'AE08WJ6YKNBMC']
        marketplace_obj = self.env['amazon.marketplace.ept']
        kwargs = self.prepare_marketplace_kwargs()
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False) or response.get('reason', False):
            raise UserError(_(response.get('error', {}) or response.get('reason', {})))
        values = response.get('result', {})
        for value in values:
            participation_dict = value.get('participation', {})
            marketplace = value.get('marketplace', {})
            marketplace_id = marketplace.get('id', '')
            if marketplace_id in marketplace_list:
                marketplace_value = self.prepare_marketplace_vals(marketplace, participation_dict)
                marketplace_rec = marketplace_obj.search(
                    [('seller_id', '=', self.id), ('market_place_id', '=', marketplace_id)])
                if marketplace_rec:
                    marketplace_rec.write(marketplace_value)
                else:
                    marketplace_obj.create(marketplace_value)
        return True

    def update_user_groups(self):
        """
        This mwthod will update the user groups as per the amazon fulfillment by
        :return:
        """
        amazon_selling = self.amazon_selling
        if self._context.get('deactive_seller', False):
            amazon_selling = self.update_user_group_deactive_seller(amazon_selling)
        else:
            amazon_selling = self.update_user_group_active_seller(amazon_selling)

        self = self.with_user(SUPERUSER_ID)
        amazon_fba_group = self.env.ref('amazon_ept.group_amazon_fba_ept')
        amazon_fbm_group = self.env.ref('amazon_ept.group_amazon_fbm_ept')
        amazon_fba_fbm_group = self.env.ref(
            'amazon_ept.group_amazon_fba_and_fbm_ept')
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

    def update_user_group_active_seller(self, amazon_selling):
        """
        This method will update the user group for active seller, it's call when create the seller
        and change fulfilment by.
        :return: fulfilment by
        """
        other_seller, seller_company = self.search_amazon_seller_and_seller_company('Both')
        if other_seller and seller_company:
            return True
        if amazon_selling == 'FBA':
            other_seller, seller_company = self.search_amazon_seller_and_seller_company('FBM')
            if other_seller and seller_company:
                amazon_selling = 'Both'
        elif amazon_selling == 'FBM':
            other_seller, seller_company = self.search_amazon_seller_and_seller_company('FBA')
            if other_seller and seller_company:
                amazon_selling = 'Both'
        return amazon_selling

    def update_user_group_deactive_seller(self, amazon_selling):
        """
        This method will update user group when deactivate the seller.
        :return: fulfilment by
        """
        other_seller, seller_company = self.search_amazon_seller_and_seller_company('Both')
        if other_seller and seller_company:
            return True
        if amazon_selling == 'FBA':
            other_seller, seller_company = self.search_amazon_seller_and_seller_company('FBM')
            other_fba_seller, other_fba_seller_company = self.search_amazon_seller_and_seller_company('FBA')
            amazon_selling = self.manage_amazon_selling_ept(other_seller, seller_company, other_fba_seller,
                                                            other_fba_seller_company, 'FBM')
        elif amazon_selling == 'FBM':
            other_seller, seller_company = self.search_amazon_seller_and_seller_company('FBA')
            other_fbm_seller, other_seller_fbm_company = self.search_amazon_seller_and_seller_company('FBM')
            amazon_selling = self.manage_amazon_selling_ept(other_seller, seller_company, other_fbm_seller,
                                                            other_seller_fbm_company, 'FBA')
        elif amazon_selling == 'Both':
            other_seller, seller_company = self.search_amazon_seller_and_seller_company('FBA')
            other_fbm_seller, other_seller_fbm_company = self.search_amazon_seller_and_seller_company('FBM')
            if not other_seller and other_fbm_seller and other_seller_fbm_company:
                amazon_selling = 'FBM'
            else:
                amazon_selling = self.manage_amazon_selling_ept(other_seller, seller_company, other_fbm_seller,
                                                                other_seller_fbm_company, 'FBA')
        return amazon_selling

    def manage_amazon_selling_ept(self, other_seller, seller_company, seller_program,
                                  other_program_company, program):
        """
        Set Amazon selling in seller record.
        :param : other_seller : seller program
        :param : seller_company seller program company
        :param : seller_program : seller another program
        :param : other_program_company : seller another program company
        :param : program : amazon program
        :return : amazon selling
        """
        amazon_selling = False
        if (other_seller and seller_program and seller_company and other_program_company) or (
                not other_seller and not seller_program and not seller_company and not other_program_company):
            amazon_selling = 'Both'
        elif other_seller and not seller_program and seller_company:
            amazon_selling = program
        return amazon_selling

    def search_amazon_seller_and_seller_company(self, amazon_selling):
        """
        Find Amazon Seller and Seller Company based on Amazon Selling.
        :param : amazon_selling : Amazon Selling type
        :return : amazon seller, seller company
        """
        amazon_seller_obj = self.env[AMZ_SELLER_EPT]
        amazon_seller = amazon_seller_obj.search([('id', '!=', self.id), ('amazon_selling', '=', amazon_selling)])
        seller_company = amazon_seller.filtered(lambda x: x.company_id.id in self.env.user.company_ids.ids)
        return amazon_seller, seller_company

    def auto_create_stock_adjustment_configuration(self):
        """
        This method will generate the stock adjustment configuration
        :return: True
        """
        reason_group_ids = self.env['amazon.adjustment.reason.group'].search([])
        customer_location, inventory_location, \
        misplace_location_id, inbound_shipment_id = self.find_stock_adjustment_config_location()
        prepare_config_vals = list()
        stock_adjustment_configuration_obj = self.env['amazon.stock.adjustment.config']
        for group_id in reason_group_ids:
            exist_configuration = stock_adjustment_configuration_obj.search(
                [('seller_id', '=', self.id), ('group_id', '=', group_id.id)])
            if exist_configuration:
                continue
            if group_id.id == self.env.ref('amazon_ept.amazon_misplaced_and_found_ept').id:
                prepare_config_vals.append(
                    {'seller_id': self.id, 'location_id': misplace_location_id.id, 'group_id': group_id.id})
            elif group_id.id in [self.env.ref('amazon_ept.amazon_unrecoverable_inventory_ept').id, self.env.ref(
                    'amazon_ept.amazon_transferring_ownership_ept').id]:
                prepare_config_vals.append(
                    {'seller_id': self.id, 'group_id': group_id.id, 'location_id': customer_location.id})
            elif group_id.id == self.env.ref('amazon_ept.amazon_inbound_shipement_receive_adjustment_ept').id:
                prepare_config_vals.append(
                    {'seller_id': self.id, 'group_id': group_id.id, 'location_id': inbound_shipment_id.id})
            elif group_id.id in [self.env.ref('amazon_ept.amazon_software_corrections_ept').id, self.env.ref(
                    'amazon_ept.amazon_catalogue_management_ept').id]:
                prepare_config_vals.append(
                    {'seller_id': self.id, 'group_id': group_id.id, 'location_id': inventory_location.id})
            elif group_id.id == self.env.ref('amazon_ept.amazon_damaged_inventory_ept').id:
                prepare_config_vals.append({'seller_id': self.id, 'group_id': group_id.id, 'location_id': False})

        if prepare_config_vals:
            stock_adjustment_configuration_obj.create(prepare_config_vals)
        return True

    def find_stock_adjustment_config_location(self):
        """
        This method will find the location if not exist location then create new location.
        :return: customer_location, inventory_location, misplace_location_id, inbound_shipment_id locations
        """
        stock_location_obj = self.env[STOCK_LOCATION]
        physical_view_location = self.env.ref('stock.stock_location_locations')
        partner_view_location = self.env.ref('stock.stock_location_locations_partner')
        virtual_location = self.env.ref('stock.stock_location_locations_virtual')
        customer_location = self.env.ref('stock.stock_location_customers')
        if not customer_location:
            customer_location = stock_location_obj.search([('location_id', '=', partner_view_location.id),
                                                           ('company_id', '=', self.company_id.id),
                                                           ('usage', '=', 'customer')], limit=1)
            if not customer_location:
                customer_location = stock_location_obj.search([('location_id', '=', partner_view_location.id),
                                                               ('company_id', '=', False),
                                                               ('usage', '=', 'customer')], limit=1)
            if not customer_location:
                location_vals = {'name': 'Customer',
                                 'active': True,
                                 'usage': 'customer',
                                 'company_id': self.company_id.id,
                                 'location_id': partner_view_location.id}
                customer_location = self.env[STOCK_LOCATION].create(location_vals)

        inventory_location = stock_location_obj.search([('location_id', '=', virtual_location.id),
                                                        ('company_id', '=', self.company_id.id),
                                                        ('usage', '=', 'inventory')], limit=1)
        if not inventory_location:
            inventory_location = stock_location_obj.search([('location_id', '=', virtual_location.id),
                                                            ('company_id', '=', False),
                                                            ('usage', '=', 'inventory')], limit=1)
        if not inventory_location:
            location_vals = {'name': 'Inventory adjustment',
                             'active': True,
                             'usage': 'inventory',
                             'company_id': self.company_id.id,
                             'location_id': virtual_location.id}
            inventory_location = stock_location_obj.create(location_vals)

        loss_by_amazon = 'Loss by amazon'
        misplace_location_id = stock_location_obj.search([('location_id', '=', physical_view_location.id),
                                                          ('company_id', '=', self.company_id.id),
                                                          ('usage', '=', 'internal'),
                                                          ('name', '=', self.name + ' ' + loss_by_amazon)], limit=1)
        if not misplace_location_id:
            misplace_location_id = stock_location_obj.search([('location_id', '=', physical_view_location.id),
                                                              ('company_id', '=', False),
                                                              ('usage', '=', 'internal'),
                                                              ('name', '=', self.name + ' ' + loss_by_amazon)], limit=1)
        if not misplace_location_id:
            location_vals = {'name': self.name + ' ' + loss_by_amazon,
                             'active': True,
                             'usage': 'internal',
                             'company_id': self.company_id.id,
                             'location_id': physical_view_location.id}
            misplace_location_id = stock_location_obj.create(location_vals)

        inbound_shipment_id = stock_location_obj.search([('location_id', '=', physical_view_location.id),
                                                         ('company_id', '=', self.company_id.id),
                                                         ('usage', '=', 'transit')], limit=1)
        if not inbound_shipment_id:
            inbound_shipment_id = stock_location_obj.search([('location_id', '=', physical_view_location.id),
                                                             ('company_id', '=', False),
                                                             ('usage', '=', 'transit')], limit=1)
        if not inbound_shipment_id:
            location_vals = {'name': self.company_id.name + ': Transit Location',
                             'active': True,
                             'usage': 'transit',
                             'company_id': self.company_id.id,
                             'location_id': physical_view_location.id}
            inbound_shipment_id = self.env[STOCK_LOCATION].create(location_vals)
        return customer_location, inventory_location, misplace_location_id, inbound_shipment_id

    @api.model
    def auto_process_shipped_sale_order_ept(self, args={}):
        """
        This method will auto process FBM shipped sale order.
        :param args:
        :return: True
        """
        sale_order_obj = self.env[SALE_ORDER]
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.browse(int(seller_id))
            sale_order_obj.with_context(is_auto_process=True).import_fbm_shipped_or_missing_unshipped_orders(
                seller, False, False, ['Shipped'])
        return True

    @api.model
    def auto_sync_amazon_fulfillment_center_ept(self):
        """
        This method will Sync Amazon fulfillment centers from IAP
        and create fulfillment center records in appropriate seller warehouse.
        """
        seller_ids = self.search([])
        if seller_ids:
            self.request_fba_fulfilment_centers(seller_ids.ids)
        return True

    def request_fba_fulfilment_centers(self, sellers_ids=[]):
        """
        when 'sync fulfilment center' button clicked form amazon configuration settings
        this method will request IAP for all fulfillment centers associated to the country codes
        of all the fba warehouse associated to the seller clicked the button
        :return:
        """
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        sellers = self.env[AMZ_SELLER_EPT].browse(sellers_ids)
        if not sellers:
            return False

        if not self._context.get('for_stock_adjustment', False):
            sellers = sellers.filtered(lambda l: l.is_fulfilment_center_configured)

        fba_warehouses = sellers.amz_warehouse_ids.filtered(lambda l: l.is_fba_warehouse)
        sellers.check_fba_warehouse_partner_and_country_configured()
        country_code = fba_warehouses.mapped('partner_id').mapped('country_id').mapped('code')
        kwargs = {'country_code': country_code}
        response = iap_tools.iap_jsonrpc(FULFILLMENT_ENDPOINT, params=kwargs,
                                         timeout=1000)
        if response.get('error'):
            raise UserError(_("Something went wrong during fetch fulfilment centers details!"))
        fulfillment_centers = response.get('fulfillment_centers', {})
        if fulfillment_centers:
            for seller in sellers:
                fulfillment_center_obj._map_amazon_fulfillment_centers_warehouse(seller, fulfillment_centers)

    def check_fba_warehouse_partner_and_country_configured(self):
        """
        Define method for check partner and country set in Amazon FBA warehouses.
        :return:
        """
        for seller in self:
            if not seller.amz_warehouse_ids:
                UserError(_("Please Set Amazon FBA Warehouses in Seller [%s]" % (seller.name)))
            missing_partners = seller.amz_warehouse_ids.filtered(lambda warehouse: not warehouse.partner_id)
            if missing_partners:
                raise UserError(_("Please Configure Partner in following Amazon FBA Warehouses: %s" %
                                  (missing_partners.mapped('name'))))
            missing_warehouses = seller.amz_warehouse_ids.filtered(
                lambda warehouse: not warehouse.partner_id.country_id)
            if missing_warehouses:
                missing_country_instance = seller.instance_ids.filtered(
                    lambda wh, missing_warehouses=missing_warehouses: wh.fba_warehouse_id in missing_warehouses and
                                                                      wh.country_id.code not in ['NL', 'SE'])
                message = ""
                for inst in missing_country_instance:
                    message += "Country [%s] must be required in Amazon FBA Warehouse [%s] in Partner [%s] " % (
                        inst.country_id.code, inst.fba_warehouse_id.name, inst.fba_warehouse_id.partner_id.name)
                raise UserError(_(message))

    def migrate_to_sp_api(self):
        """
        Request to get authorization code based on the developer id, auth token and seller id
        :return: mark seller as sp-api to True
        """
        account_obj = self.env[IAP_ACCOUNT]
        ir_config_parameter_obj = self.env[IR_CONFIG_PARAMETER]
        account = account_obj.search([('service_name', '=', 'amazon_ept')])
        dbuuid = ir_config_parameter_obj.sudo().get_param(DATABASE_UUID)

        kwargs = {'merchant_id': self.merchant_id and str(self.merchant_id) or False,
                  'app_name': 'amazon_ept_spapi',
                  'account_token': account.account_token,
                  'emipro_api': 'get_authorization_code_spapi',
                  'dbuuid': dbuuid,
                  'amazon_selling': self.amazon_selling,
                  'mws_auth_token': self.auth_token,
                  'amazon_marketplace_code': self.country_id.amazon_marketplace_code or
                                             self.country_id.code}
        response = iap_tools.iap_jsonrpc('https://iap.odoo.emiprotechnologies.com/sp_api_authorisation',
                                         params=kwargs, timeout=1000)
        if response.get('error', {}) or response.get('reason', {}):
            message = response.get('error', {}) or response.get('reason', {})
            raise UserError(_(message))
        self.write({'is_sp_api_amz_seller': True})

    def re_authorisation_to_sp_api(self):
        """
        Request to re-authorization of seller into the SP API.
        :return: User warning
        """
        amz_marketplace_code = self.country_id.amazon_marketplace_code or self.country_id.code
        if amz_marketplace_code.upper() == 'GB':
            amz_marketplace_code = 'UK'
        kwargs = {'merchant_id': self.merchant_id if self.merchant_id else False,
                  'amazon_marketplace_code': amz_marketplace_code}
        response = iap_tools.iap_jsonrpc('https://iap.odoo.emiprotechnologies.com/sp_api_re_authorisation',
                                         params=kwargs, timeout=1000)
        if response.get('error', {}):
            user_message = response.get('error', {})
        elif response.get('result', {}):
            user_message = ("An email has been sent to you at %s."
                            " Please click on the Authenticate SP-API button to complete the re-authorization process." %
                            response.get('result', {}).get('email', ''))
        else:
            user_message = 'There is no need to reauthorize your SP API credential at the moment.'
        raise UserError(_(user_message))

    def active_iap_database(self):
        """
        Used to request iap_database endpoint to get the response containing databases related to the seller.
        can be called from the button 'Active IAP Databases' in the seller view
        :return: action to open the wizard
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        seller = self.merchant_id
        if not seller:
            return False

        kwargs = {'seller': seller, 'database': 'get', 'account_token': account.account_token, 'dbuuid': dbuuid}
        response = iap_tools.iap_jsonrpc('https://iap.odoo.emiprotechnologies.com/iap_databases', params=kwargs,
                                         timeout=1000)
        if response.get('error'):
            raise UserError(_(response.get('error')))
        context = dict(self._context)
        context.update(response)
        context.update({'seller': seller, 'account_token': account.account_token, 'dbuuid': dbuuid})
        view = self.env.ref('amazon_ept.view_amazon_iap_seller_databases')
        action = {
            'name': _('Activate / Deactivate Staging Database'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'amazon.seller.iap.database',
            'target': 'new',
            'context': context,
            'view_id': view.id
        }
        return action
