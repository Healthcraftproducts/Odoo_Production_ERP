# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added to perform the amazon import, export operations and added onchange and methods
to process for different amazon operations.
"""

import base64
import csv
import xlrd
import time
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO
import os
import logging
from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError, ValidationError
from ..endpoint import DEFAULT_ENDPOINT
from .. reportTypes import ReportType

_logger = logging.getLogger(__name__)
DATE_VALIDATION_MESSAGE = 'Please select Date Range.'
AMZ_SHIPPING_REPORT_REQUEST_HISTORY = 'shipping.report.request.history'
AMZ_INSTANCE_EPT = 'amazon.instance.ept'
AMZ_PRODUCT_EPT = 'amazon.product.ept'
AMZ_FBA_LIVE_STOCK_REPORT_EPT = 'amazon.fba.live.stock.report.ept'
IT_ACTIONS_ACT_WINDOW = 'ir.actions.act_window'
PRODUCT_PRODUCT = 'product.product'
AMZ_SELLER_SKU = 'Seller SKU'
INTERNAL_REFERENCE = 'Internal Reference'
SETTLEMENT_REPORT_EPT = 'settlement.report.ept'
SALE_ORDER = 'sale.order'
COMMON_LOG_LINES_EPT = 'common.log.lines.ept'
video_url_dict = {'amz_sync_active_products': 'eBydTcibHgA',
                   'amz_fbm_export_stock_from_odoo_to_amazon': 'k0pllAQSpH0',
                   'amz_export_price_from_odoo_to_amazon': 'RMY0EfCNTEc',
                   'amz_import_fbm_unshipped_orders': 'joeN0WsQFQA',
                   'amz_check_cancel_orders_fbm': 'aIM7CetWJnA',
                   'amz_fbm_update_track_number_and_ship_status': 'O9owZ44-rvY',
                   'amz_import_fba_pending_orders': 'pHCLQLTdREY',
                   'amz_customer_return_report': 'Y3PKS9Nxpb0',
                   'amz_fba_live_inventory_report': 'VgZQ_C8maLk',
                   'amz_stock_adjustment_report': 'i_0FKLihNWw',
                   'amz_removal_order_report': 'x85Bdvpj9Yg',
                   'amz_removal_order_request': 'x85Bdvpj9Yg',
                   'amz_import_fbm_shipped_orders': '_3LiuB8MsUk',
                   'amz_list_settlement_report': 'MPjd96nC9Rc',
                   'amz_import_products': 'K6fh24cbSGQ',
                   'amz_shipment_report': 'uS2WtnRkd0c',
                   'amz_import_inbound_shipment': '-xHBNN_VPxU',
                   'amz_create_inbound_shipment_plan': 'vg86Ck0dvkQ'
                   }
SHIPPED_ORDER_DATA_QUEUE_EPT = 'shipped.order.data.queue.ept'
SHIPPED_ORDER_DATA_QUEUE = 'Shipped Order Data Queue'


class AmazonProcessImportExport(models.TransientModel):
    """
    Added class to perform amazon import and export operations.
    """
    _name = 'amazon.process.import.export'
    _description = 'Amazon Import Export Process'

    seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller',
                                help="Select Amazon Seller Account")

    amazon_program = fields.Selection(related="seller_id.amazon_program")
    amazon_selling = fields.Selection(related="seller_id.amazon_selling")

    us_amazon_program = fields.Selection(related="seller_id.amz_fba_us_program")
    instance_id = fields.Many2one(AMZ_INSTANCE_EPT, string='Marketplace',
                                  help="This Field relocates amazon instance.")
    order_removal_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, string='Removal Marketplace',
                                                help="This instance is used for the Removal order.")
    is_another_soft_create_fba_inventory = fields.Boolean(
        related="seller_id.is_another_soft_create_fba_inventory",
        string="Does another software create the FBA Inventory reports?",
        help="Does another software create the FBA Inventory reports")
    instance_ids = fields.Many2many("amazon.instance.ept", 'amazon_instance_import_export_rel',
                                    'process_id', 'instance_id', "Marketplaces",
                                    help="Select Amazon Marketplaces where you want to perform "
                                         "opetations.")
    list_settlement_report = fields.Boolean("List settlement report?")
    report_start_date = fields.Datetime("Start Date", help="Start date of report.")
    report_end_date = fields.Datetime("End Date", help="End date of report.")
    selling_on = fields.Selection([
        ('FBM', 'FBM'),
        ('FBA', 'FBA'),
        ('fba_fbm', 'FBA & FBM')
    ], 'Operation For')
    operations = fields.Selection([
        ('amz_fbm_export_stock_from_odoo_to_amazon', 'Export Stock'),
        ('amz_fbm_update_track_number_and_ship_status', 'Export Shipment Info/Update Order Status'),
        ('amz_check_cancel_orders_fbm', 'Mark Cancel Orders'),
        ('amz_import_fbm_shipped_orders', 'Import FBM Shipped Orders'),
        ('amz_import_fbm_missing_unshipped_orders', 'Import Missing UnShipped Orders'),
        ('amz_import_fbm_unshipped_orders', 'Import Unshipped Orders')
    ], 'FBM Operations')
    fba_operations = fields.Selection([
        ('amz_import_fba_pending_orders', 'Import FBA Pending Orders'),
        ('amz_check_cancel_orders_fba', 'Mark Cancel Orders'),
        ('amz_shipment_report', 'Import FBA Shipped Orders'),
        ('amz_stock_adjustment_report', 'Import FBA Stock Adjustment'),
        ('amz_removal_order_report', 'Import FBA Removal Orders'),
        ('amz_customer_return_report', 'Import FBA Customer Returns'),
        ('amz_removal_order_request', 'Create Removal Order Plan'),
        ('amz_import_inbound_shipment', 'Import Inbound Shipment'),
        ('amz_create_inbound_shipment_plan', 'Create Inbound Shipment Plan'),
        ('amz_fba_live_inventory_report', 'Import FBA Inventory')
    ], 'Operations')

    both_operations = fields.Selection([
        ('amz_import_products', 'Map Products'),
        ('amz_sync_active_products', 'Import Products'),
        ('amz_export_price_from_odoo_to_amazon', 'Export Prices'),
        ('amz_list_settlement_report', 'Download Settlement Reports'),
        ('amz_request_rating_report', 'Import Rating Report'),
        ('amz_vcs_tax_report', 'Import VCS(VAT Calculation Service) Report'),
        ('amz_manually_create_settlement_report', 'Manually Create Settlement Report')
    ], 'FBA & FBM Operations')
    is_vcs_enabled = fields.Boolean('Is VCS Report Enabled ?', default=False, store=False)
    is_split_report = fields.Boolean('Is Split Report ?', default=False)
    split_report_by_days = fields.Selection([
        ('3', '3'),
        ('7', '7'),
        ('15', '15')
    ])
    fbm_order_updated_after_date = fields.Datetime('Updates After')
    import_fba_pending_sale_order = fields.Boolean('Sale order(Only Pending Orders)',
                                                   help="System will import pending FBA orders "
                                                        "from Amazon")
    check_order_status = fields.Boolean("Check Cancelled Order in Amazon",
                                        help="If ticked, system will check the orders status in "
                                             "canceled in Amazon, then system will cancel that "
                                             "order "
                                             "is Odoo too.")
    export_inventory = fields.Boolean()
    export_product_price = fields.Boolean('Update Product Price')
    updated_after_date = fields.Datetime('Updated After')
    shipment_id = fields.Char()
    from_warehouse_id = fields.Many2one('stock.warehouse', string="From Warehouse")
    update_price_in_pricelist = fields.Boolean(string='Update price in pricelist?', default=False,
                                               help='Update or create product line in pricelist '
                                                    'if ticked.')
    auto_create_product = fields.Boolean(string='Auto create product?', default=False,
                                         help='Create product in ERP if not found.')
    file_name = fields.Char(string='Name')
    choose_file = fields.Binary(string="Select File")
    delimiter = fields.Selection([('tab', 'Tab'), ('semicolon', 'Semicolon'), ('comma', 'Comma')],
                                 string="Separator", default='comma')
    user_warning = fields.Text(string="Note: ", store=False)
    pan_eu_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, string='Marketplace(UK)',
                                         help="This Field relocates amazon UK instance.")
    efn_eu_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, string='EFN Marketplace(UK)',
                                         help="This Field relocates amazon UK instance.")
    us_region_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, string='Marketplace(US)',
                                            help="This Field relocates amazon North America Region instance.")
    country_code = fields.Char(related='seller_id.country_id.code', string='Country Code')
    mci_efn_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, string='Marketplace(EU)',
                                          help="This Field relocates amazon MCI or MCI+EFN instance.")
    ship_to_address = fields.Many2one('res.partner', string='Ship To Address',
                                      help='Destination Address for Inbound Shipment')
    amz_video_url = fields.Html(compute='_set_video_url', sanitize=False)
    fbm_order_updated_before_date = fields.Datetime('Updates Before')

    @api.depends('both_operations', 'fba_operations', 'operations', 'selling_on')
    def _set_video_url(self):
        """
        Compute method which will set the iframe to the video_url HTML field.
        :return: True
        """
        selling = self.selling_on
        if selling == 'FBM':
            self.amz_video_url = self.prepare_embed_code(self.operations)
        elif selling == 'FBA':
            self.amz_video_url = self.prepare_embed_code(self.fba_operations)
        elif selling == 'fba_fbm':
            self.amz_video_url = self.prepare_embed_code(self.both_operations)
        else:
            self.amz_video_url = False
        return True

    @api.constrains('fbm_order_updated_after_date', 'fbm_order_updated_before_date')
    def _check_duration(self):
        """
        Compare updated after date and updated before date, If updated before date is before updated after date
         then raise warning.
        :return: True
        """
        if self.fbm_order_updated_after_date and self.fbm_order_updated_before_date \
                and self.fbm_order_updated_before_date < self.fbm_order_updated_after_date:
            raise UserError(_('The updated after date must be precede its updated before date.'))
        return True

    @staticmethod
    def prepare_embed_code(operation):
        """
        Prepare the iframe for different operations
        :param operation: for which operation iframe need to be created
        :return: iframe code
        """
        if operation and video_url_dict.get(operation):
            embed_code = f'<iframe width="410px" height="232px" ' \
                  f'src="https://www.youtube.com/embed/' \
                  f'{video_url_dict.get(operation)}" ' \
                  f'title="YouTube video player" frameborder="0" ' \
                  f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" ' \
                  f'allowfullscreen></iframe>'
        else:
            embed_code = False
        return embed_code

    @api.onchange('report_start_date', 'report_end_date')
    def onchange_shipment_report_date(self):
        """
        Added onchange to allow option to split report based on selected date range difference is
        more than 7 days.
        """
        if self.report_start_date and self.report_end_date:
            count = self.report_end_date.date() - self.report_start_date.date()
            if count.days > 7 and not self.seller_id.is_another_soft_create_fba_shipment:
                self.is_split_report = True
            else:
                self.is_split_report = False

    @api.onchange('selling_on')
    def onchange_selling_on(self):
        """
        Added set operations vals false based on selling on.
        """
        self.operations = False
        self.fba_operations = False
        self.both_operations = False

    @api.onchange('operations')
    def onchange_operations(self):
        """
        On change of operations field it will check the active scheduler or scheduler
        exist then it's next run time.
        """
        self.export_inventory = False
        self.export_product_price = False
        self.list_settlement_report = False
        self.fbm_order_updated_after_date = False
        self.fbm_order_updated_before_date = False
        self.updated_after_date = False
        self.report_start_date = False
        self.report_end_date = False

        self.user_warning = None
        if self.operations == "amz_fbm_export_stock_from_odoo_to_amazon":
            self.check_running_schedulers('ir_cron_auto_export_inventory_seller_')

        if self.operations == "amz_fbm_update_track_number_and_ship_status":
            self.check_running_schedulers('ir_cron_auto_update_order_status_seller_')

        if self.operations == "amz_check_cancel_orders_fbm":
            self.check_running_schedulers('ir_cron_auto_check_canceled_fbm_order_in_amazon_seller_')

        if self.operations == "amz_import_fbm_unshipped_orders":
            self.check_running_schedulers('ir_cron_import_amazon_orders_seller_')

    @api.onchange('fba_operations')
    def onchange_fba_operations(self):
        """
        On change of fba_operations field it set start and end date as per configurations from
        seller
        default start date is -3 days from the date.
        @author: Keyur Kanani
        :return:
        """
        self.user_warning = None
        if self.fba_operations == "amz_shipment_report":
            self.report_start_date = datetime.now() - timedelta(self.seller_id.shipping_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_import_amazon_fba_shipment_report_seller_')

        if self.fba_operations == "amz_customer_return_report":
            self.report_start_date = datetime.now() - timedelta(
                self.seller_id.customer_return_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_auto_import_customer_return_report_seller_')

        if self.fba_operations == "amz_stock_adjustment_report":
            self.report_start_date = datetime.now() - timedelta(
                self.seller_id.inv_adjustment_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_create_fba_stock_adjustment_report_seller_')

        if self.fba_operations == "amz_removal_order_report":
            self.report_start_date = datetime.now() - timedelta(
                self.seller_id.removal_order_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_create_fba_removal_order_report_seller_')

        if self.fba_operations == "amz_fba_live_inventory_report":
            self.report_start_date = datetime.now() - timedelta(
                self.seller_id.live_inv_adjustment_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_import_stock_from_amazon_fba_live_report_')

        if self.fba_operations == "amz_import_fba_pending_orders":
            self.check_running_schedulers('ir_cron_import_amazon_fba_pending_order_seller_')

        if self.fba_operations == "amz_import_inbound_shipment":
            self.check_running_schedulers('ir_cron_inbound_shipment_check_status_')

    @api.onchange('both_operations')
    def onchange_both_operations(self):
        """
        On change of fba_fbm_operations field it will check the active scheduler or scheduler
        exist then it's next run time.
        @author: Keyur Kanani
        :return:
        """
        self.user_warning = None
        if self.both_operations == "amz_list_settlement_report":
            self.check_running_schedulers('ir_cron_auto_import_settlement_report_seller_')
        if self.both_operations == "amz_request_rating_report":
            self.report_start_date = datetime.now() - timedelta(self.seller_id.rating_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_rating_request_report_seller_')
        if self.both_operations == "amz_vcs_tax_report":
            self.report_start_date = datetime.now() - timedelta(self.seller_id.fba_vcs_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_auto_import_vcs_tax_report_seller_')

    def check_running_schedulers(self, cron_xml_id):
        """
        use: 1. If scheduler is running for ron_xml_id + seller_id, then this function will
        notify user that
                the process they are doing will be running in the scheduler.
                if they will do this process then the result cause duplicate.
            2. Also if scheduler is in progress in backend then the execution will give UserError
            Popup
                and terminates the process until scheduler job is done.
        :param cron_xml_id: string[cron xml id]
        :return:
        """
        cron_id = self.env.ref('amazon_ept.%s%d' % (cron_xml_id, self.seller_id.id),
                               raise_if_not_found=False)
        if cron_id and cron_id.sudo().active:
            res = cron_id.try_cron_lock()
            if self._context.get('raise_warning', False) and res and res.get('reason', False):
                raise UserError(_("You are not allowed to run this Action. \n"
                                  "The Scheduler is already started the Process of Importing "
                                  "Orders."))
            if res and res.get('result', {}):
                self.user_warning = "This process is executed through scheduler also, " \
                                    "Next Scheduler for this process will run in %s Minutes" \
                                    % res.get('result', {})
            elif res and res.get('reason', False):
                self.user_warning = res.get('reason', {})

    def create_and_request_amazon_vcs_report(self):
        """
        This method will check scheduler running for import VCS tax report or not and if scheduler running than raise
         warning otherwise create VCS tax report and request for that.
        """
        vcs_tax_report_obj = self.env['amazon.vcs.tax.report.ept']
        if not self.seller_id.is_vcs_activated:
            raise UserError(_("Please Select Invoice Upload Policy as per Seller Central Configurations."))
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_auto_import_vcs_tax_report_seller_')
        vcs_report_vals = self.prepare_report_values()
        vcs_report_vals.update({'report_type': 'SC_VAT_TAX_REPORT',
                                'state': 'draft'})
        vcs_report = vcs_tax_report_obj.create(vcs_report_vals)
        vcs_report.request_report()
        self.seller_id.write({'vcs_report_last_sync_on': self.report_end_date})
        return vcs_report

    def import_export_processes(self):
        """
        Import / Export Operations are managed from here.
        as per selection on wizard this function will execute
        :return: selected amazon operation function
        """
        if self.both_operations:
            return getattr(self, str(self.both_operations))()
        if self.operations:
            return getattr(self, str(self.operations))()
        if self.fba_operations:
            return getattr(self, str(self.fba_operations))()

    def prepare_report_values(self):
        """
        Prepare common values for Amazon Report request.
        :return: dict {}
        """
        return {
            'seller_id': self.seller_id.id,
            'start_date': self.report_start_date,
            'end_date': self.report_end_date
        }

    @staticmethod
    def return_report_tree_form_view(name, view_type, view_mode, res_model, res_id):
        """
         Prepare values for Ir Window action.
        :return: dict {}
        """
        return {
            'name': _(name),
            'view_type': view_type,
            'view_mode': view_mode,
            'res_model': res_model,
            'type': IT_ACTIONS_ACT_WINDOW,
            'res_id': res_id
        }

    @staticmethod
    def amz_return_tree_form_action_ept(name, res_model, records):
        """
         Prepare values of Ir Window action for tree or form view.
         :name: Return action name
         :res_model: Return model name
         :records: Filtered records from action
        :return: ir.actions.act_window action
        """
        action = {
            'name': name,
            'res_model': res_model,
            'type': IT_ACTIONS_ACT_WINDOW
        }
        if len(records) == 1:
            action.update({'res_id': records[0],
                           'view_mode': 'form',
                           'context': {'active_id': records}})
        else:
            action.update({'domain': [('id', 'in', records)],
                           'view_mode': 'tree,form'})
        return action

    def amz_list_settlement_report(self):
        """
        This method check scheduler running or not for import settlement report if scheduler running
        than raise warning otherwise download settlement report from amazon in odoo for define
        specific start and end date range.
        :return: ir.actions.act_window() action
        """
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_auto_import_settlement_report_seller_')
        vals = {'report_type': ReportType.GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2,
                'name': 'Amazon Settlement Reports',
                'model_obj': self.env[SETTLEMENT_REPORT_EPT],
                'sequence': self.env.ref('amazon_ept.seq_import_settlement_report_job', raise_if_not_found=False),
                'tree_id': self.env.ref('amazon_ept.amazon_settlement_report_tree_view_ept'),
                'form_id': self.env.ref('amazon_ept.amazon_settlement_report_form_view_ept'),
                'res_model': SETTLEMENT_REPORT_EPT,
                'start_date': self.report_start_date,
                'end_date': self.report_end_date
                }
        return self.get_reports(vals)

    def amz_request_rating_report(self):
        """
        This method check scheduler running or not for import customer rating report if scheduler running than
        raise warning otherwise import customer rating report from Amazon in odoo for specific start and end
        date range.
        :return: ir.actions.act_window() action
        """
        rating_report_obj = self.env['rating.report.history']
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_rating_request_report_seller_')
        if not self.report_start_date or not self.report_end_date:
            raise UserError(_(DATE_VALIDATION_MESSAGE))
        rating_report_vals = self.prepare_report_values()
        rating_report_record = rating_report_obj.create(rating_report_vals)
        rating_report_record.request_report()
        return self.return_report_tree_form_view('Rating Report Request History', 'form', 'form',
                                                 'rating.report.history', rating_report_record.id)

    def amz_fbm_update_track_number_and_ship_status(self):
        """
        This method check scheduler running or not for update order status in amazon or not if running
        than raise warning otherwise update order status in amazon for seller.
        """
        sale_order_obj = self.env[SALE_ORDER]
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_auto_update_order_status_seller_')
        return sale_order_obj.amz_update_tracking_number(self.seller_id)

    def amz_import_fbm_shipped_orders(self):
        """
        This method Import FBM Shipped Orders from Amazon to odoo.
        """
        sale_order_obj = self.env[SALE_ORDER]
        data_queue_list = sale_order_obj.import_fbm_shipped_or_missing_unshipped_orders(
            self.seller_id, self.instance_ids, self.fbm_order_updated_after_date, ['Shipped'],
            self.fbm_order_updated_before_date)
        if not data_queue_list:
            return True
        return self.amz_return_tree_form_action_ept(
            SHIPPED_ORDER_DATA_QUEUE, SHIPPED_ORDER_DATA_QUEUE_EPT, data_queue_list)

    def amz_import_fbm_missing_unshipped_orders(self):
        """
        This method Import FBM Missing UnShipped Orders from Amazon to odoo.
        """
        sale_order_obj = self.env[SALE_ORDER]
        data_queue_list = sale_order_obj.import_fbm_shipped_or_missing_unshipped_orders(
            self.seller_id, self.instance_ids, self.fbm_order_updated_after_date, ['Unshipped', 'PartiallyShipped'])
        if not data_queue_list:
            return True
        return self.amz_return_tree_form_action_ept(
            SHIPPED_ORDER_DATA_QUEUE, SHIPPED_ORDER_DATA_QUEUE_EPT, data_queue_list)

    def amz_import_fbm_unshipped_orders(self):
        """
        This method check scheduler running or not for Import FBM UnShipped Orders from Amazon if running
        than raise warning otherwise Import FBM UnShipped Orders from Amazon to odoo.
        :return: ir.actions.act_window() action
        """
        fbm_sale_order_report_obj = self.env['fbm.sale.order.report.ept']
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_import_amazon_orders_seller_')
        record = fbm_sale_order_report_obj.create({'seller_id': self.seller_id.id,
                                                   'report_type': ReportType.GET_FLAT_FILE_ORDER_REPORT_DATA})
        record.with_context(emipro_api='create_amazon_fbm_report_sp_api').request_report()
        return self.return_report_tree_form_view('FBM Sale Order', 'form', 'form',
                                                 'fbm.sale.order.report.ept', record.id)

    def amz_customer_return_report(self):
        """
        This method check scheduler running or not for import FBA Customer Return Report if running
        than raise warning otherwise import FBA Customer Return Report from Amazon to odoo.
        :return: ir.actions.act_window() action
        """
        customer_return_report_obj = self.env['sale.order.return.report']
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_auto_import_customer_return_report_seller_')
        customer_return_report_vals = self.prepare_report_values()
        customer_return_report_record = customer_return_report_obj.create(customer_return_report_vals)
        customer_return_report_record.request_report()
        return self.return_report_tree_form_view('Customer Return Report', False, 'form',
                                                 'sale.order.return.report', customer_return_report_record.id)

    def amz_stock_adjustment_report(self):
        """
        This method check scheduler running or not for import FBA Stock Adjustment Report if running
        than raise warning otherwise import FBA Stock Adjustment Report from Amazon to odoo.
        :return: ir.actions.act_window() action
        """
        stock_adjustment_report_obj = self.env['amazon.stock.adjustment.report.history']
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_create_fba_stock_adjustment_report_seller_')
        if not self.report_start_date or not self.report_end_date:
            raise UserError(_(DATE_VALIDATION_MESSAGE))
        stock_adjustment_report_vals = self.prepare_report_values()
        stock_adjustment_report_record = stock_adjustment_report_obj.create(stock_adjustment_report_vals)
        stock_adjustment_report_record.request_report()
        return self.return_report_tree_form_view('Stock Adjustment Report Request History',
                                                 'form', 'form', 'amazon.stock.adjustment.report.history',
                                                 stock_adjustment_report_record.id)

    def amz_fba_live_inventory_report(self):
        """
        This method import FBA Live Inventory Report from Amazon to odoo.
        """
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_import_stock_from_amazon_fba_live_report_')
        if self.seller_id.is_another_soft_create_fba_inventory:
            fba_live_stock_report = self.get_another_software_created_live_inventory_report()
            return fba_live_stock_report
        if self.amazon_program in ('pan_eu', 'cep'):
            instance_id = self.pan_eu_instance_id
            report_type = 'GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA'
            if instance_id:
                fba_live_stock_report_ids = self.with_context(
                    instance_ids=instance_id).create_and_request_amazon_live_inv_report_ids(
                    report_type, False, False, False)
            else:
                fba_live_stock_report_ids = self.create_and_request_amazon_live_inv_report_ids(report_type, False, False, False)
        elif not self.seller_id.is_european_region and not self.seller_id.amz_fba_us_program == 'narf':
            report_type = 'GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA'
            fba_live_stock_report_ids = self.with_context({
                'instance_ids': self.us_region_instance_id if self.us_region_instance_id else self.seller_id.instance_ids
            }).create_and_request_amazon_live_inv_report_ids(report_type, datetime.now(), False, False)
        elif self.amazon_program == 'efn' or self.seller_id.amz_fba_us_program == 'narf':
            start_date = (datetime.today().date() - timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
            end_date = (datetime.today().date() - timedelta(days=1)).strftime('%Y-%m-%d 23:59:59')
            report_type = 'GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA'
            # If seller is NARF then pass Amazon.com marketplace
            # If seller is efn then must be pass seller efn inventory country marketplace.
            if self.seller_id.amz_fba_us_program == 'narf':
                instance_id = self.seller_id.instance_ids.filtered(lambda instance: instance.market_place_id == 'ATVPDKIKX0DER')
            else:
                if self.efn_eu_instance_id:
                    instance_id = self.efn_eu_instance_id
                else:
                    instance_id = self.seller_id.instance_ids.filtered(
                        lambda instance: instance.country_id.id == self.seller_id.store_inv_wh_efn.id)
            fba_live_stock_report_ids = self.with_context(
                instance_ids=instance_id).create_and_request_amazon_live_inv_report_ids(
                report_type, False, start_date, end_date)
        elif self.amazon_program in ('mci', 'efn+mci'):
            start_date = (datetime.today().date() - timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
            end_date = (datetime.today().date() - timedelta(days=1)).strftime('%Y-%m-%d 23:59:59')
            report_type = 'GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA'
            fba_live_stock_report_ids = self.with_context({
                'instance_ids': self.mci_efn_instance_id if self.mci_efn_instance_id else self.seller_id.instance_ids
            }).create_and_request_amazon_live_inv_report_ids(report_type, False, start_date, end_date)
        if fba_live_stock_report_ids:
            return self.get_amz_fba_live_stock_report(fba_live_stock_report_ids)

    def get_another_software_created_live_inventory_report(self):
        """
        This method Import FBA Live Inventory report from amazon which created by using another
        software in amazon.
        :return: FBA Live Inventory Stock Report
        """
        live_inventory_request_report_record = self.env[AMZ_FBA_LIVE_STOCK_REPORT_EPT]
        start_date, date_end = live_inventory_request_report_record.get_start_end_date_ept(self.seller_id)
        vals = {'start_date': start_date,
                'end_date': date_end,
                'seller_id': self.seller_id,
                'us_region_instance_id': self.us_region_instance_id or self.mci_efn_instance_id
                                         or self.pan_eu_instance_id or False}
        fba_live_stock_report = live_inventory_request_report_record.get_inventory_report(vals)
        return fba_live_stock_report

    def get_amz_fba_live_stock_report(self, fba_live_stock_report_ids):
        """
        This method return FBA Live Stock Report.
        :param: fba_live_stock_report_ids : amazon.fba.live.stock.report.ept() objects ids
        :return: ir.actions.act_window() action
        """
        if len(fba_live_stock_report_ids) > 1:
            return {
                'name': _('FBA Live Stock Report'),
                'view_type': 'tree',
                'view_mode': 'tree',
                'res_model': AMZ_FBA_LIVE_STOCK_REPORT_EPT,
                'type': IT_ACTIONS_ACT_WINDOW,
                'domain': [('id', 'in', fba_live_stock_report_ids)]
            }
        return self.return_report_tree_form_view('FBA Live Stock Report', 'form', 'form',
                                                 AMZ_FBA_LIVE_STOCK_REPORT_EPT, fba_live_stock_report_ids[0])

    def amz_removal_order_report(self):
        """
        This method check scheduler running or not for Import Amazon Removal Order Report if running
        than raise warning otherwise Import Amazon Removal Order Report from Amazon to odoo.
        :return: ir.actions.act_window() action
        """
        removal_order_request_report_record = self.env['amazon.removal.order.report.history']
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_create_fba_removal_order_report_seller_')
        if not self.report_start_date or not self.report_end_date:
            raise UserError(_(DATE_VALIDATION_MESSAGE))
        removal_order_request_report_vals = self.prepare_report_values()
        removal_order_request_report_record = removal_order_request_report_record.create(removal_order_request_report_vals)
        removal_order_request_report_record.request_report()
        return self.return_report_tree_form_view('Removal Order Report Request History', 'form', 'form',
                                                 'amazon.removal.order.report.history',
                                                 removal_order_request_report_record.id)

    def amz_removal_order_request(self):
        """
        This method create Removal order plan in Amazon.
        :return: ir.actions.act_window() action
        """
        amazon_removal_order_obj = self.env['amazon.removal.order.ept']
        if not self.order_removal_instance_id or self.order_removal_instance_id and not\
                self.order_removal_instance_id.is_allow_to_create_removal_order:
            raise UserError(_(
                'This Seller no any instance configure removal order Please configure removal '
                'order configuration.'))
        amazon_removal_order_obj = amazon_removal_order_obj.create({
            'removal_disposition': 'Return',
            'warehouse_id': self.order_removal_instance_id and
                            self.order_removal_instance_id.removal_warehouse_id.id or False,
            'ship_address_id': self.order_removal_instance_id.company_id.partner_id.id,
            'company_id': self.seller_id.company_id.id,
            'instance_id': self.order_removal_instance_id.id,
        })
        return self.return_report_tree_form_view('Removal Order Request', 'form', 'form',
                                                 'amazon.removal.order.ept', amazon_removal_order_obj.id)

    def amz_import_inbound_shipment(self):
        """
        This method check scheduler running or not for import Inbound Shipment Report if running than raise
        warning otherwise import Inbound Shipment Report from Amazon to odoo.
        """
        import_shipment_obj = self.env['amazon.inbound.import.shipment.ept']
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_inbound_shipment_check_status_')
        inbound_shipment_list = import_shipment_obj.get_inbound_import_shipment(
            self.instance_id, self.from_warehouse_id, self.shipment_id, self.ship_to_address)
        if not inbound_shipment_list:
            return
        return self.amz_return_tree_form_action_ept(
            'Inbound Shipments', 'amazon.inbound.shipment.ept', inbound_shipment_list)

    def amz_vcs_tax_report(self):
        """
        This method import VCS Tax Report from Amazon to odoo.
        :return: ir.actions.act_window() action
        """
        vcs_report = self.create_and_request_amazon_vcs_report()
        if vcs_report:
            return self.return_report_tree_form_view('Amazon VCS Tax Reports', 'form', 'form',
                                                     'amazon.vcs.tax.report.ept', vcs_report.id)

    def amz_check_cancel_orders_fba(self):
        """
        This method import FBA Cancel orders from Amazon to odoo.
        """
        sale_order_obj = self.env[SALE_ORDER]
        instance_ids = self.get_amz_instance_ids()
        cancel_order_marketplaces = self.get_amz_cancel_and_pending_orders_details(instance_ids)
        if cancel_order_marketplaces:
            for seller, marketplaces in cancel_order_marketplaces.items():
                sale_order_obj.cancel_amazon_fba_pending_sale_orders(seller, marketplaceids=marketplaces,
                                                                     instance_ids=instance_ids.ids or [])

    def amz_check_cancel_orders_fbm(self):
        """
        This method check scheduler running or not for import FBM Cancel orders if running
        than raise warning otherwise import FBM Cancel orders from Amazon to odoo.
        """
        sale_order_obj = self.env[SALE_ORDER]
        instance_ids = self.get_amz_instance_ids()
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_auto_check_canceled_fbm_order_in_amazon_seller_')
        cancel_order_marketplaces_fbm = self.get_amz_cancel_and_pending_orders_details(instance_ids)
        if cancel_order_marketplaces_fbm:
            for seller, marketplaces in cancel_order_marketplaces_fbm.items():
                sale_order_obj.cancel_amazon_fbm_pending_sale_orders(seller, marketplaceids=marketplaces,
                                                                     instance_ids=instance_ids.ids or [])

    def amz_import_fba_pending_orders(self):
        """
        This method check scheduler running or not for import FBA Pending orders if running than raise warning
        otherwise import fba pending orders from Amazon to odoo.
        """
        sale_order_obj = self.env[SALE_ORDER]
        instance_ids = self.get_amz_instance_ids()
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_import_amazon_fba_pending_order_seller_')
        seller_pending_order_marketplaces = self.get_amz_cancel_and_pending_orders_details(instance_ids)
        if seller_pending_order_marketplaces:
            for seller, marketplaces in seller_pending_order_marketplaces.items():
                sale_order_obj.import_fba_pending_sales_order(seller, marketplaces, self.updated_after_date)

    def amz_fbm_export_stock_from_odoo_to_amazon(self):
        """
        This method will help to Export Products Stock as per seller instance wise from Odoo to Amazon.
        """
        instance_ids = self.get_amz_instance_ids()
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_auto_export_inventory_seller_')
        seller_stock_instance = self.get_amz_export_price_and_stock_details(instance_ids)
        if seller_stock_instance:
            for seller, instance_ids in seller_stock_instance.items():
                for instance in instance_ids:
                    instance.export_stock_levels()

    def amz_export_price_from_odoo_to_amazon(self):
        """
        This method will help to Export Products Price as per seller instance wise from Odoo to Amazon.
        """
        amazon_product_obj = self.env[AMZ_PRODUCT_EPT]
        instance_ids = self.get_amz_instance_ids()
        export_product_price_instance = self.get_amz_export_price_and_stock_details(instance_ids)
        if export_product_price_instance:
            for seller, instance_ids in export_product_price_instance.items():
                for instance in instance_ids:
                    amazon_products = amazon_product_obj.search([('instance_id', '=', instance.id),
                                                                 ('exported_to_amazon', '=', True)])
                    if amazon_products:
                        amazon_products.update_price(instance)

    def get_amz_instance_ids(self):
        """
        This method will get Amazon Instances from seller.
        :return: amazon.instance.ept() browse object list
        """
        if self.instance_ids:
            return self.instance_ids
        return self.seller_id.instance_ids

    @staticmethod
    def get_amz_cancel_and_pending_orders_details(instance_ids):
        """
        This method will prepare dict for process Amazon Cancel FBA and
        FBM and Pending orders.
        :param: instance_ids : amazon.instance.ept() browse object list
        :return: prepare dict
        """
        order_marketplaces_details = defaultdict(list)
        for instance in instance_ids:
            order_marketplaces_details[instance.seller_id].append(instance.market_place_id)
        return order_marketplaces_details

    @staticmethod
    def get_amz_export_price_and_stock_details(instance_ids):
        """
        This method will help to prepare dict for Export Products Stock and Prices from
        Odoo to Amazon.
        :param: instance_ids : amazon.instance.ept() browse object list
        :return: prepare dict
        """
        exported_marketplaces_details = defaultdict(list)
        for instance in instance_ids:
            exported_marketplaces_details[instance.seller_id].append(instance)
        return exported_marketplaces_details

    def create_amz_shipment_report_by_days(self):
        """
        This method will help to get shipping report as per specific days range.
        :return : shipping report record list
        """
        start_date = self.report_start_date
        end_date = False
        shipping_report_record_list = []
        while start_date <= self.report_end_date:
            if end_date:
                start_date = end_date

            if start_date >= self.report_end_date:
                break

            end_date = (start_date + timedelta(int(self.split_report_by_days))) - timedelta(1)
            if end_date > self.report_end_date:
                end_date = self.report_end_date

            shipping_report_record = self.get_amz_fba_shipping_report(start_date, end_date)
            shipping_report_record_list.append(shipping_report_record.id)
        return shipping_report_record_list

    def amz_shipment_report(self):
        """
        This method will help to Import FBA Shipment report from Amazon to odoo.
        :return: ir.actions.act_window() action
        """
        fba_shipping_report_obj = self.env[AMZ_SHIPPING_REPORT_REQUEST_HISTORY]
        self.with_context({'raise_warning': True}).check_running_schedulers(
            'ir_cron_import_amazon_fba_shipment_report_seller_')
        fba_shipment_report_name = 'FBA Shipment Report'
        if not self.report_start_date or not self.report_end_date:
            raise UserError(_(DATE_VALIDATION_MESSAGE))
        if self.seller_id.is_another_soft_create_fba_shipment:
            shipping_report_record = fba_shipping_report_obj.process_and_create_amz_shipment_report(
                self.seller_id, self.report_start_date, self.report_end_date)
            if not shipping_report_record:
                return
            return self.amz_return_tree_form_action_ept(
                fba_shipment_report_name, AMZ_SHIPPING_REPORT_REQUEST_HISTORY, shipping_report_record)

        elif self.is_split_report and not self.split_report_by_days:
            raise UserError(_('Please select the Split Report By Days.'))
        elif self.is_split_report and self.split_report_by_days:
            shipping_report_record_list = self.create_amz_shipment_report_by_days()
            if not shipping_report_record_list:
                return True
            return self.amz_return_tree_form_action_ept(
                fba_shipment_report_name, AMZ_SHIPPING_REPORT_REQUEST_HISTORY, shipping_report_record_list)
        else:
            shipping_report_record = self.get_amz_fba_shipping_report(self.report_start_date, self.report_end_date)
            return self.return_report_tree_form_view(fba_shipment_report_name, False, 'form',
                                                     AMZ_SHIPPING_REPORT_REQUEST_HISTORY, shipping_report_record.id)

    def get_amz_fba_shipping_report(self, start_date, end_date):
        """
        This method will help to get Shipment Reports as per given start and end date range.
        :param: start_date : shipping report start date
        :param: end_date : shipping report end date
        :return: shipping report record
        """
        fba_shipping_report_obj = self.env[AMZ_SHIPPING_REPORT_REQUEST_HISTORY]
        report_type = fba_shipping_report_obj.get_amz_shipment_report_type(self.seller_id.id)
        shipping_report_record = fba_shipping_report_obj.create({
            'seller_id': self.seller_id.id,
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date
        })
        shipping_report_record.with_context({'emipro_api': 'create_report_sp_api'}).request_report()
        return shipping_report_record

    def create_and_request_amazon_live_inv_report_ids(self, report_type, report_date, start_date, end_date):
        """
        Added to request for FBA line inventory report.
        :param: report_type : Report Type for FBA Live Stock
        :param: report_date : Report Date
        :param: start_date : Report Start Date
        :param: end_date : Report End Date
        :return: list of amazon.fba.live.stock.report.ept() object ids
        """
        ctx = self._context
        fba_live_stock_report_ids = []
        live_inventory_request_report_record = self.env[AMZ_FBA_LIVE_STOCK_REPORT_EPT]
        fba_live_stock_report_vals = {'seller_id': self.seller_id.id,
                                      'report_type': report_type,
                                      'report_date': report_date,
                                      'start_date': start_date,
                                      'end_date': end_date}
        if ctx.get('instance_ids', []):
            instance_ids = ctx.get('instance_ids', [])
            for instance in instance_ids:
                fba_live_stock_report_vals.update({'amz_instance_id': instance.id, })
                fba_live_stock_report = live_inventory_request_report_record.create(fba_live_stock_report_vals)
                fba_live_stock_report.request_report()
                fba_live_stock_report_ids.append(fba_live_stock_report.id)
            return fba_live_stock_report_ids
        fba_live_stock_report = live_inventory_request_report_record.create(
            fba_live_stock_report_vals)
        fba_live_stock_report.request_report()
        fba_live_stock_report_ids.append(fba_live_stock_report.id)
        return fba_live_stock_report_ids

    def prepare_merchant_report_dict(self, seller):
        """
        This method will prepare details for IAP request.
        :param: seller : amazon.seller.ept() object
        :return: This method will prepare merchant' informational dictionary which will
        passed to  amazon api calling method.
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        return {
            'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
            'app_name': 'amazon_ept_spapi',
            'account_token': account.account_token,
            'emipro_api': 'get_reports_sp_api',
            'dbuuid': dbuuid,
            'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or seller.country_id.code,
        }

    def get_reports(self, report_values):
        """
        This method will get settlement report data from amazon and create it's record in odoo.
        :param: vals: report values
        :return: This method will redirecting us to settlement report tree view.
        """
        seller = self.seller_id
        if not seller:
            raise UserError(_('Please select Seller'))

        start_date, end_date = self.get_fba_reports_date_format()
        kwargs = self.sudo().prepare_merchant_report_dict(seller)
        report_types = report_values.get('report_type', '')
        instances = seller.instance_ids
        marketplace_ids = tuple(map(lambda x: x.market_place_id, instances))
        kwargs.update({'report_type': [report_types], 'start_date': start_date, 'end_date': end_date,
                       "marketplaceids": marketplace_ids})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            raise UserError(_(response.get('error', {})))
        list_of_wrapper = response.get('result', {})
        odoo_report_ids = self.get_amazon_fba_report_ids(list_of_wrapper, report_values.get('start_date', ''),
                                                         report_values.get('end_date', ''), report_values.get('model_obj', False),
                                                         report_values.get('sequence', ''))
        if self._context.get('is_auto_process', False):
            return odoo_report_ids
        if not odoo_report_ids:
            return True
        return self.amz_return_tree_form_action_ept(
            report_values.get('name'), report_values.get('res_model'), odoo_report_ids)

    def get_fba_reports_date_format(self):
        """
        This method will convert selected time duration in specific format to send it to amazon.
        If start date and end date is empty then system will automatically select past 90 days
        time duration.
        :return: This method will return converted start and end date.
        """
        start_date = self.report_start_date
        end_date = self.report_end_date
        date_format = "%Y-%m-%dT%H:%M:%S"
        if start_date:
            db_import_time = time.strptime(str(start_date), "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime(date_format, db_import_time)
            start_date = time.strftime(date_format, time.gmtime(
                time.mktime(time.strptime(db_import_time, date_format))))
            start_date = str(start_date) + 'Z'
        else:
            today = datetime.now()
            earlier = today - timedelta(days=90)
            earlier_str = earlier.strftime(date_format)
            start_date = earlier_str + 'Z'
        if end_date:
            db_import_time = time.strptime(str(end_date), "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime(date_format, db_import_time)
            end_date = time.strftime(date_format, time.gmtime(
                time.mktime(time.strptime(db_import_time, date_format))))
            end_date = str(end_date) + 'Z'
        else:
            today = datetime.now()
            earlier_str = today.strftime(date_format)
            end_date = earlier_str + 'Z'
        return start_date, end_date

    def get_amazon_fba_report_ids(self, list_of_wrapper, start_date, end_date, model_obj, sequence):
        """
        This method will create settlement report and it's attachments from the amazon api response.
        :param list_of_wrapper: Dictionary of amazon api response.
        :param start_date: Selected start date in wizard in specific format.
        :param end_date: Selected end date in wizard in specific format.
        :param: model_obj : model object
        :param: sequence : report sequence
        :return: This method will return list of newly created settlement report id.
        """
        odoo_report_ids = []
        list_of_wrapper = list_of_wrapper.get('reports', {}) if list_of_wrapper else []
        for report in list_of_wrapper:
            report_document_id = report.get('reportDocumentId', '')
            report_id = report.get('reportId', '')
            report_type = report.get('reportType', '')
            report_exist = model_obj.search(
                ['|', ('report_document_id', '=', report_document_id), ('report_id', '=', report_id),
                 ('report_type', '=', report_type)])
            if report_exist:
                report_exist = report_exist[0]
                odoo_report_ids.append(report_exist.id)
                continue
            vals = self.prepare_fba_report_vals_for_create(report_type, report_document_id, report_id,
                                                           start_date, end_date, sequence)
            report_rec = model_obj.create(vals)
            report_rec.get_report()
            self._cr.commit()
            odoo_report_ids.append(report_rec.id)
        return odoo_report_ids

    def prepare_fba_report_vals_for_create(self, report_type, report_document_id, report_id, start_date,
                                           end_date, sequence):
        """
        Define method which help us to prepare settlement reports values.
        :param report_type: Report type.
        :param report_document_id: Amazon report document id.
        :param report_id: Amazon report id.
        :param start_date: Selected start date in wizard in specific format.
        :param end_date: Selected end date in wizard in specific format.
        :return: This method will prepare and return settlement report vals.
        """
        report_name = sequence.next_by_id() if sequence else '/'
        return {
            'name': report_name,
            'report_type': report_type,
            'report_document_id': report_document_id,
            'report_id': report_id,
            'start_date': start_date,
            'end_date': end_date,
            'state': '_DONE_',
            'seller_id': self.seller_id.id,
            'user_id': self._uid,
        }

    def amz_sync_active_products(self):
        """
        Process will create record of Active Product List of selected seller and instance
        :return: ir.actions.act_window() action
        """
        if not self.instance_id:
            raise UserError(_('Please Select Instance'))
        active_product_listing_obj = self.env['active.product.listing.report.ept']
        form_id = self.env.ref('amazon_ept.active_product_listing_form_view_ept')
        vals = {'instance_id': self.instance_id.id if self.instance_id else False,
                'seller_id': self.seller_id.id if self.seller_id else False,
                'update_price_in_pricelist': self.update_price_in_pricelist if self.update_price_in_pricelist else False,
                'auto_create_product': self.auto_create_product if self.auto_create_product else False
                }
        active_product_listing = active_product_listing_obj.create(vals)
        try:
            active_product_listing.request_report()
        except Exception as exception:
            raise UserError(_(exception))
        return {
            'type': IT_ACTIONS_ACT_WINDOW,
            'name': 'Active Product List',
            'res_model': 'active.product.listing.report.ept',
            'res_id': active_product_listing.id,
            'views': [(form_id.id, 'form')],
            'view_id': form_id.id,
            'target': 'current'
        }

    def download_sample_attachment(self):
        """
        This relocates download sample file of amazon.
        :return: This Method return downloaded file.
        """
        attachment = self.env['ir.attachment'].search([('name', '=', 'import_product_sample.xlsx'),
                                                       ('res_model', '=', 'amazon.process.import.export')])
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % (attachment.id),
            'target': 'new',
            'nodestroy': False,
        }

    def amz_manually_create_settlement_report(self):
        """
        Use: create settlement report record and attached file in the record.
        Params: Amazon Process Import Export => Self
        ---------------------------------------------
        Added on: 09-Sep-2021
        """
        settlement_report_obj = self.env[SETTLEMENT_REPORT_EPT]
        settlement_report_vals = self.prepare_settlement_report_vals()
        settlement_report_record = settlement_report_obj.create(settlement_report_vals)
        attachment_id = self.create_attachment_for_settlement_report(settlement_report_record)
        settlement_report_record.message_post(body=_("<b>Settlement Record has been created manually.</b>"),
                                              attachment_ids=attachment_id.ids)
        settlement_report_record.write({'attachment_id': attachment_id.id})
        return True

    def prepare_settlement_report_vals(self):
        """
        Define method for prepare settlement report values
        :return : dict {}
        """
        settlement_report_obj = self.env[SETTLEMENT_REPORT_EPT]
        imp_file = StringIO(base64.b64decode(self.choose_file).decode())
        content = imp_file.read()
        delimiter = ('\t', csv.Sniffer().sniff(content.splitlines()[0]).delimiter)[bool(content)]
        settlement_reader = csv.DictReader(content.splitlines(), delimiter=delimiter)
        start_date = False
        end_date = False
        for row in settlement_reader:
            start_date = row.get('settlement-start-date', False)
            end_date = row.get('settlement-end-date', False)
            if start_date and end_date:
                start_date = settlement_report_obj.format_amz_settlement_report_date(start_date)
                end_date = settlement_report_obj.format_amz_settlement_report_date(end_date)
                break
        sequence = self.env.ref('amazon_ept.seq_import_settlement_report_job', raise_if_not_found=False)
        report_name = sequence.next_by_id() if sequence else '/'
        return {
            'seller_id': self.seller_id.id if self.seller_id else False,
            'name': report_name, 'instance_id': self.instance_id.id if self.instance_id else False,
            'currency_id': self.instance_id.country_id.currency_id.id if self.instance_id.country_id.currency_id else False,
            'user_id': self.env.user.id, 'start_date': start_date and start_date.strftime('%Y-%m-%d'),
            'end_date': end_date and end_date.strftime('%Y-%m-%d'),
            'state': '_DONE_'}

    def create_attachment_for_settlement_report(self, settlement_report_record):
        """
        Use: Attach file in the settlement report record when it's create manually from the wizard.
        Params:  settlement_report_record
        Return : Attachment record.
        ----------------------------------------------
        Added on: 09-Sep-2021
        """

        vals = {
            'name': self.file_name,
            'datas': self.choose_file,
            'type': 'binary',
            'res_model': SETTLEMENT_REPORT_EPT,
            'res_id': settlement_report_record.id
        }
        return self.env['ir.attachment'].create(vals)

    def amz_import_products(self):
        """
        This Method relocates Import product csv in amazon listing and mapping of amazon product listing.
        :return: rainbow action with successfully or partially processed file message
        """
        if not self.choose_file:
            raise UserError(_('Please Upload File.'))
        if os.path.splitext(self.file_name)[1].lower() not in ['.csv', '.xls', '.xlsx']:
            raise ValidationError(_("Invalid file format. You are only allowed to upload .csv, .xls or .xlsx file."))
        if os.path.splitext(self.file_name)[1].lower() == '.csv':
            map_products_count = self.amz_map_import_csv_ept()
        else:
            map_products_count = self.amz_map_import_xls_ept()
        message = ("%s Products Imported Successfully!, Please check Logs." % map_products_count) if map_products_count else "All Products Skipped!!, Please check Logs."
        return {
            'effect': {
                'fadeout': 'none',
                'message': message,
                'img_url': '/web/static/img/smile.svg',
                'type': 'rainbow_man',
            }
        }

    def amz_map_import_csv_ept(self):
        """
        This method will help to read imported csv file.
        :return: mapped products count (int)
        """
        try:
            data = StringIO(base64.b64decode(self.choose_file).decode())
        except Exception:
            data = StringIO(base64.b64decode(self.choose_file).decode('ISO-8859-1'))
        content = data.read()
        delimiter = ('\t', csv.Sniffer().sniff(content.splitlines()[0]).delimiter)[bool(content)]
        csv_reader = csv.DictReader(content.splitlines(), delimiter=delimiter)
        headers = csv_reader.fieldnames
        # read imported file header is valid or not
        self.amz_read_import_file_header(headers)
        instance_dict = {}
        map_product_count = 0
        row_no = 1
        for line in csv_reader:
            row_no += 1
            skip_line = self.amz_read_import_file_with_product_list(line, row_no)
            if not skip_line:
                instance_dict, map_product_count = self.amz_mapped_imports_products_ept(
                    line, instance_dict, map_product_count)
            if (map_product_count % 100) == 0:
                self._cr.commit()
        return map_product_count

    def amz_map_import_xls_ept(self):
        """
        This method will help to read imported xls or xlsx file.
        :return: mapped products count (int)
        """
        sheets = xlrd.open_workbook(file_contents=base64.b64decode(self.choose_file.decode('UTF-8')))
        header = dict()
        is_header = False
        instance_dict = {}
        map_product_count = 0
        row_number = 1
        for sheet in sheets.sheets():
            for row_no in range(sheet.nrows):
                if not is_header:
                    headers = [d.value for d in sheet.row(row_no)]
                    # read imported file header is valid or not
                    self.amz_read_import_file_header(headers)
                    [header.update({d: headers.index(d)}) for d in headers]
                    is_header = True
                    continue
                row = dict()
                [row.update({k: sheet.row(row_no)[v].value}) for k, v in header.items() for c in
                 sheet.row(row_no)]
                row_number += 1
                for key in ['Seller SKU', 'Internal Reference', 'Title']:
                    if isinstance(row.get(key), float):
                        data = str(row.get(key)).split('.')
                        row[key] = data[0] if data[1] == '0' else data
                skip_line = self.amz_read_import_file_with_product_list(row, row_number)
                if not skip_line:
                    instance_dict, map_product_count = self.amz_mapped_imports_products_ept(
                        row, instance_dict, map_product_count)
                if (map_product_count % 100) == 0:
                    self._cr.commit()
        return map_product_count

    def amz_mapped_imports_products_ept(self, line, instance_dict, map_product_count):
        """
        This method will map amazon products with odoo products.
        :param : line: Iterable line of imported file
        :param : instance_dict : {} {amazon_marketplace: amazon.instance.ept() object}
        :param : map_product_count : int total mapped products count
        :return : instances dict - {}, mapped products count - int
        """
        product_obj = self.env["product.product"]
        amazon_product_ept_obj = self.env[AMZ_PRODUCT_EPT]
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        odoo_default_code = line.get('Internal Reference', '')
        seller_sku = line.get('Seller SKU', '')
        amazon_marketplace = line.get('Marketplace', '')
        fulfillment = line.get('Fulfillment', '')
        instance = False

        if amazon_marketplace:
            instance = instance_dict.get(amazon_marketplace)
            if not instance:
                instance = self.seller_id.instance_ids.filtered(
                    lambda l, amazon_marketplace=amazon_marketplace: l.marketplace_id.name == amazon_marketplace)
                instance_dict.update({amazon_marketplace: instance})

        if fulfillment not in ['FBA', 'FBM']:
            message = "Fulfillment By should be FBA or FBM"
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='product.product', default_code=seller_sku, fulfillment_by=fulfillment,
                mismatch_details=True, module='amazon_ept', operation_type='import',
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
            return instance_dict, map_product_count

        if not instance:
            message = """Amazon Marketplace Name[%s] not valid for seller sku %s and Internal Reference %s""" \
                      % (amazon_marketplace, seller_sku, odoo_default_code)
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='product.product', default_code=seller_sku, fulfillment_by=fulfillment,
                mismatch_details=True, module='amazon_ept', operation_type='import',
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
            return instance_dict, map_product_count

        if instance and fulfillment and seller_sku:
            if not odoo_default_code:
                message = """ Internal Reference Not found for seller sku %s """ % (seller_sku)
                common_log_line_obj.create_common_log_line_ept(
                    message=message, model_name='product.product', default_code=seller_sku, fulfillment_by=fulfillment,
                    mismatch_details=True, module='amazon_ept', operation_type='import',
                    amz_seller_ept=self.seller_id and self.seller_id.id or False)
                return instance_dict, map_product_count

            product_id = product_obj.search(['|', ("default_code", "=ilike", odoo_default_code),
                                             ("barcode", "=ilike", odoo_default_code),
                                             ('company_id', 'in', [instance.company_id.id, False])], limit=1)

            amazon_product_id = amazon_product_ept_obj.search_amazon_product(
                instance.id, seller_sku, fulfillment_by=fulfillment)
            mismatch = False
            if amazon_product_id and amazon_product_id.product_id.id != product_id.id:
                if product_id:
                    amazon_product_id.product_id = product_id
                    message = """ Odoo Product [%s] has been updated for Seller Sku [%s]""" \
                              % (odoo_default_code, seller_sku)
                else:
                    message = """ Odoo Product not found for the internal reference [%s]""" % (odoo_default_code)
                    mismatch = True
                common_log_line_obj.create_common_log_line_ept(
                    message=message, model_name='product.product', default_code=seller_sku, fulfillment_by=fulfillment,
                    log_line_type='fail' if mismatch else 'success', mismatch_details=mismatch,
                    product_id=amazon_product_id.product_id.id if amazon_product_id.product_id else False,
                    module='amazon_ept', operation_type='import',
                    amz_seller_ept=self.seller_id and self.seller_id.id or False)
                return instance_dict, map_product_count

            if amazon_product_id:
                message = """ Amazon product found for seller sku %s and Internal Reference %s""" \
                          % (seller_sku, odoo_default_code)
                common_log_line_obj.create_common_log_line_ept(
                    message=message, model_name='product.product', default_code=seller_sku, fulfillment_by=fulfillment,
                    log_line_type='success',
                    product_id=amazon_product_id.product_id.id if amazon_product_id.product_id else False,
                    module='amazon_ept', operation_type='import',
                    amz_seller_ept=self.seller_id and self.seller_id.id or False)
                return instance_dict, map_product_count

            if not product_id:
                product_id = self.get_odoo_product_csv_data_ept(line, fulfillment)
            if not product_id:
                return instance_dict, map_product_count
            self.create_amazon_listing(instance, product_id, line)
            map_product_count += 1
            message = """ Amazon product created for seller sku %s || Instance %s and mapped with odoo product %s """ % (
                seller_sku, instance.name, product_id.name)
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='amazon.product.ept', default_code=seller_sku, fulfillment_by=fulfillment,
                log_line_type='success', product_id=product_id.id if product_id else False, module='amazon_ept',
                operation_type='import', amz_seller_ept=self.seller_id and self.seller_id.id or False)
        return instance_dict, map_product_count

    def amz_read_import_file_with_product_list(self, line, row_number):
        """
        This method read import csv, xls or xlsx file and check file columns name are valid name
        or columns entries of Title,Seller SKU,Internal Reference,Marketplace or Fulfillment
        are fill or not.If either Column name invalid or missing then create log record also
        create log record if column field are blank.
        :param : line - Iterable line of imported file
        :param : row_number - imported file line number
        :return: This Method return boolean(True/False).
        @author: Kishan Sorani
        """
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        seller_sku = line.get(AMZ_SELLER_SKU)
        fullfillment_by = line.get('Fulfillment')
        skip_line = False
        if not line.get(AMZ_SELLER_SKU):
            message = "Line is skipped Seller SKU is required to create an product at line %s" % (row_number)
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='product.product', mismatch_details=True, fulfillment_by=fullfillment_by,
                default_code=seller_sku, module='amazon_ept', operation_type='import',
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
            skip_line = True
        elif self.auto_create_product and not line.get('Title'):
            message = 'Line is skipped Title is required to create an product at line %s' % (row_number)
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='product.product', mismatch_details=True, fulfillment_by=fullfillment_by,
                default_code=seller_sku, module='amazon_ept', operation_type='import',
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
            skip_line = True
        elif not line.get(INTERNAL_REFERENCE):
            message = 'Line is skipped Internal Reference is required to create an product at line %s' % (row_number)
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='product.product', mismatch_details=True, fulfillment_by=fullfillment_by,
                default_code=seller_sku, module='amazon_ept', operation_type='import',
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
            skip_line = True
        elif not line.get('Marketplace'):
            message = 'Line is skipped Marketplace is required to create an product at line %s' % (row_number)
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='product.product', mismatch_details=True, fulfillment_by=fullfillment_by,
                default_code=seller_sku, module='amazon_ept', operation_type='import',
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
            skip_line = True
        elif not line.get('Fulfillment'):
            message = 'Line is skipped Fulfillment is required to create an product at line %s' % (row_number)
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='product.product', mismatch_details=True, fulfillment_by=fullfillment_by,
                default_code=seller_sku, module='amazon_ept', operation_type='import',
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
            skip_line = True
        return skip_line

    def amz_read_import_file_header(self, headers):
        """
        This method read import file headers name are correct or not.
        :param : headers - list of import file headers
        :return: This Method return boolean(True/False).
        @author: Kishan Sorani
        """
        skip_header = False
        if self.auto_create_product and headers[0] != 'Title' or headers[1] != INTERNAL_REFERENCE or \
                headers[2] != AMZ_SELLER_SKU or headers[3] != 'Marketplace' or headers[4] != 'Fulfillment':
            skip_header = True
        if skip_header:
            raise UserError(_("The Header of this report must be correct,"
                              " Please contact Emipro Support for further Assistance."))
        return True

    def get_odoo_product_csv_data_ept(self, line_vals, fullfillment_by):
        """
        This method will get the product vals and  find or create the odoo product.
        :param: line_vals : csv file line data.
        :param: fullfillment_by : amazon fulfillment
        return : odoo product.
        """
        product_obj = self.env[PRODUCT_PRODUCT]
        amazon_product_ept_obj = self.env[AMZ_PRODUCT_EPT]
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        amazon_product_name = line_vals.get('Title', '')
        odoo_default_code = line_vals.get(INTERNAL_REFERENCE, '')
        seller_sku = line_vals.get(AMZ_SELLER_SKU, '')

        amazon_product = amazon_product_ept_obj.search(['|', ('active', '=', False), ('active', '=', True),
                                                        ('seller_sku', '=', seller_sku)], limit=1)
        product_id = amazon_product.product_id if amazon_product else False

        if not product_id and self.auto_create_product:
            odoo_product_dict = {
                'name': amazon_product_name,
                'default_code': odoo_default_code,
                'type': 'product'
            }
            product_id = product_obj.create(odoo_product_dict)

            message = """ Odoo Product created for seller sku %s and Internal Reference %s """ % (
                seller_sku, odoo_default_code)
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='product.product', product_id=product_id.id, log_line_type='success',
                fulfillment_by=fullfillment_by, default_code=seller_sku, module='amazon_ept', operation_type='import',
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
        if not product_id:
            message = """ Line Skipped due to product not found seller sku %s || Internal
             Reference %s """ % (seller_sku, odoo_default_code)
            common_log_line_obj.create_common_log_line_ept(
                message=message, model_name='product.product', fulfillment_by=fullfillment_by, default_code=seller_sku,
                mismatch_details=True, module='amazon_ept', operation_type='import',
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
        return product_id

    def create_amazon_listing(self, instance, product_id, line_vals):
        """
        This Method relocates if product exist in odoo and product doesn't exist in
        amazon create amazon product listing.
        :param instance: This arguments relocates instance of amazon.
        :param product_id: product record
        :param line_vals: amazon listing line vals
        :return: This method return boolean(True/False).
        """
        amazon_product_ept_obj = self.env[AMZ_PRODUCT_EPT]
        amazon_product_name = line_vals.get('Title', '')
        seller_sku = line_vals.get(AMZ_SELLER_SKU, '')
        fulfillment = line_vals.get('Fulfillment', '')

        amazon_product_ept_obj.create({
            'name': amazon_product_name or product_id.name,
            'fulfillment_by': fulfillment,
            'product_id': product_id.id,
            'seller_sku': seller_sku,
            'instance_id': instance.id})
        return True

    def amz_create_inbound_shipment_plan(self):
        """
        This method will create shipment plan record of selected seller and instance
        :return: ir.actions.act_window() action
        """
        instance = self.instance_id
        if not instance:
            raise UserError(_('Please Select Instance'))
        inbound_shipment_plan_obj = self.env['inbound.shipment.plan.ept']
        form_id = self.env.ref('amazon_ept.inbound_shipment_plan_form_view')
        warehouse_id = instance.warehouse_id
        vals = {'instance_id': instance.id,
                'warehouse_id': warehouse_id.id,
                'ship_from_address_id': warehouse_id.partner_id and \
                                        warehouse_id.partner_id.id,
                'company_id': instance.company_id and instance.company_id.id,
                'ship_to_country': instance.country_id and instance.country_id.id
                }
        shipment_plan_id = inbound_shipment_plan_obj.create(vals)
        return {
            'type': IT_ACTIONS_ACT_WINDOW,
            'name': 'Inbound Shipment Plan',
            'res_model': 'inbound.shipment.plan.ept',
            'res_id': shipment_plan_id.id,
            'views': [(form_id.id, 'form')],
            'view_id': form_id.id,
            'target': 'current'
        }
