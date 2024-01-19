# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
"""
Define class to process for FBM sale orders
"""

import base64
import csv
import time
from io import StringIO
import pytz
from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError
from ..reportTypes import ReportType
from ..endpoint import DEFAULT_ENDPOINT, DECODE_ENDPOINT

utc = pytz.utc

SALE_ORDER = 'sale.order'
RES_PARTNER = 'res.partner'
AMAZON_PRODUCT_EPT = 'amazon.product.ept'


class FbmSaleOrderReportEpt(models.Model):
    """
    Added class to get FBM sale order report file and process FBM sale order report file
    to import FBM sale report
    """
    _name = "fbm.sale.order.report.ept"
    _description = "FBM Sale Order Report Ept"
    _inherit = ['mail.thread', 'amazon.reports', 'mail.activity.mixin']
    _order = 'name desc'

    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', help="Select Amazon Seller Name listed in odoo")
    company_id = fields.Many2one('res.company', string="Company", related="seller_id.company_id", store=False)
    name = fields.Char(size=256, readonly=True)
    attachment_id = fields.Many2one('ir.attachment', string='Attachment')
    report_type = fields.Char(size=256)
    report_request_id = fields.Char(size=256, string='Report Request ID')
    report_document_id = fields.Char(string='Report Document ID',
                                     help="Report Document id to recognise unique request document reference")
    report_id = fields.Char(size=256, string='Report ID')
    requested_date = fields.Datetime(default=time.strftime("%Y-%m-%d %H:%M:%S"))
    state = fields.Selection([('draft', 'Draft'), ('SUBMITTED', 'SUBMITTED'),
                              ('_SUBMITTED_', 'SUBMITTED'), ('IN_QUEUE', 'IN_QUEUE'),
                              ('IN_PROGRESS', 'IN_PROGRESS'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
                              ('DONE', 'DONE'), ('_DONE_', 'DONE'), ('imported', 'Imported'),
                              ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('FATAL', 'FATAL'),
                              ('partially_processed', 'Partially Processed'), ('processed', 'PROCESSED'),
                              ('closed', 'Closed'), ('CANCELLED', 'CANCELLED'),
                              ('_CANCELLED_', 'CANCELLED')], string='Report Status', default='draft')
    user_id = fields.Many2one('res.users', string="Requested User")
    sales_order_report_ids = fields.One2many(SALE_ORDER, 'amz_sales_order_report_id', string="Sale Orders")
    sales_order_count = fields.Integer(compute='_compute_order_count', string='# of Orders')
    child_sales_order_report_id = fields.Many2one('fbm.sale.order.report.ept', string='Unshipped Sales Order Report')
    is_parent = fields.Boolean('Is Parent Report', default=True)
    mismatch_details = fields.Boolean(compute="_compute_mismatch_details", string="Mismatch Details",
                                      help='True if mismatch_details found in log lines')

    def _compute_mismatch_details(self):
        """
        Set the boolean field mismatch_details as True if found any mismatch details in log lines
        """
        log_lines_obj = self.env['common.log.lines.ept']
        model_id = self.env['ir.model']._get('fbm.sale.order.report.ept').id

        if log_lines_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id),
                                       ('mismatch_details', '=', True)]):
            self.mismatch_details = True
        else:
            self.mismatch_details = False

    @api.model
    def auto_import_unshipped_order_report(self, seller):
        """
        This method is used to auto import unshipped order report
        param seller : seller record
        """
        if seller.id:
            sale_order_report = self.create(
                {'report_type': ReportType.GET_FLAT_FILE_ORDER_REPORT_DATA,
                 'seller_id': seller.id,
                 'state': 'draft',
                 'requested_date': time.strftime("%Y-%m-%d %H:%M:%S")
                 })
            sale_order_report.with_context(
                is_auto_process=True, emipro_api='create_amazon_fbm_report_sp_api').request_report()
        return True

    @api.model
    def auto_process_unshipped_order_report(self, seller):
        """
        This method is used to auto process unshipped order report
        param seller : seller record
        """
        if seller:
            sale_order_reports = self.search([('seller_id', '=', seller.id),
                                              ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_',
                                                               'SUBMITTED', 'IN_PROGRESS', 'IN_QUEUE'])])
            for sale_order_report in sale_order_reports:
                sale_order_report.with_context(
                    is_auto_process=True, amz_report_type='fbm_report_spapi').get_report_request_list()

            sale_order_reports = self.search([('seller_id', '=', seller.id),
                                              ('state', 'in', ['_DONE_', '_SUBMITTED_', '_IN_PROGRESS_',
                                                               'DONE', 'SUBMITTED', 'IN_PROGRESS', 'IN_QUEUE']),
                                              ('report_document_id', '!=', False)])
            for sale_order_report in sale_order_reports:
                if not sale_order_report.attachment_id:
                    sale_order_report.with_context(is_auto_process=True, amz_report_type='fbm_report_spapi').get_report()
                if sale_order_report.attachment_id:
                    sale_order_report.with_context(is_auto_process=True).process_fbm_sale_order_file()
                self._cr.commit()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        will set the fbm sale order report name
        """
        for vals in vals_list:
            seq = self.env['ir.sequence'].next_by_code('fbm_shipped_sale_order_report_ept_sequence') or '/'
            vals['name'] = seq
        return super(FbmSaleOrderReportEpt, self).create(vals_list)

    @api.model
    def default_get(self, field):
        """
        inherited to update the report type
        """
        res = super(FbmSaleOrderReportEpt, self).default_get(field)
        if not field:
            return res
        res.update({'report_type': ReportType.GET_FLAT_FILE_ORDER_REPORT_DATA})
        return res

    def _compute_order_count(self):
        """
        This method Calculate the Total sales order with Sale order Report Id.
        :return: True
        """
        sale_order_obj = self.env[SALE_ORDER]
        self.sales_order_count = sale_order_obj.search_count([('amz_sales_order_report_id', '=', self.id)])

    def action_view_sales_order(self):
        """
        This method show the Sales order connected with particular report.
        :return:action
        """
        action = {
            'name': 'Sales Orders',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': SALE_ORDER,
            'type': 'ir.actions.act_window',
        }
        orders = self.env[SALE_ORDER].search([('amz_sales_order_report_id', '=', self.id)])
        if len(orders) > 1:
            action['domain'] = [('id', 'in', orders.ids)]
        elif orders:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = orders.id
        return action

    def prepare_amazon_request_report_kwargs(self, seller):
        """
        Inherited Method for prepare amazon unshipped orders data
        :param seller: amazon.seller.ept()
        :return: dict{}
        """
        kwargs = super(FbmSaleOrderReportEpt, self).prepare_amazon_request_report_kwargs(seller)
        if kwargs:
            marketplace_ids = tuple(map(lambda x: x.market_place_id, seller.instance_ids))
            kwargs.update({'report_type': ReportType.GET_FLAT_FILE_ORDER_REPORT_DATA,
                           'marketplace_ids': marketplace_ids,
                           'reportOptions': {'ShowSalesChannel': 'true'}})
        return kwargs

    def create_amazon_report_attachment(self, result):
        """
        Create Attachment for FBM Unshipped order report
        :param result: Get Report result data
        :return: boolean
        """
        file_name = "FBM_Sale_Order_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
        attachment = self.env['ir.attachment'].create({
            'name': file_name, 'datas': result.encode(),
            'res_model': 'mail.compose.message',
            'type': 'binary'
        })
        self.message_post(body=_("<b>FBM Sale Order Report Downloaded</b>"), attachment_ids=attachment.ids)
        self.write({'attachment_id': attachment.id})
        return True

    def request_report(self):
        """
        This method request in Amazon for unshipped Sales Orders.
        :return:True
        """
        common_log_line_obj = self.env['common.log.lines.ept']
        seller = self.seller_id
        report_type = self.report_type
        instances = seller.instance_ids
        marketplace_ids = tuple(map(lambda x: x.market_place_id, instances))
        if not seller:
            raise UserError(_('Please select Seller'))
        emipro_api = self._context.get('emipro_api', 'create_report_sp_api')
        kwargs = self.prepare_fbm_unshipped_data_request_ept(emipro_api)
        kwargs.update({'report_type': report_type,
                       'marketplace_ids': marketplace_ids,
                       'reportOptions': {'ShowSalesChannel': 'true'}})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            if not self._context.get('is_auto_process', False):
                raise UserError(_(response.get('error', {})))
            common_log_line_obj.create_common_log_line_ept(message=response.get('error', {}),
                                                           model_name='fbm.sale.order.report.ept',
                                                           fulfillment_by='FBM',
                                                           module='amazon_ept', operation_type='import',
                                                           res_id=self.id, amz_seller_ept=seller and seller.id or False)
        if response.get('result', {}):
            self.update_report_history(response.get('result', {}))
        return True

    @staticmethod
    def prepare_fbm_customer_vals(row):
        """
        This method prepare the customer vals
        :param row: row of data
        :return: customer vals
        """
        return {
            'BuyerEmail': row.get('buyer-email', ''),
            'BuyerName': row.get('buyer-name', ''),
            'BuyerNumber': row.get('buyer-phone-number', ''),
            'AddressLine1': row.get('ship-address-1', ''),
            'AddressLine2': row.get('ship-address-2', ''),
            'AddressLine3': row.get('ship-address-3', ''),
            'City': row.get('ship-city', ''),
            'ShipName': row.get('recipient-name', ''),
            'CountryCode': row.get('ship-country', ''),
            'StateOrRegion': row.get('ship-state', '') or False,
            'PostalCode': row.get('ship-postal-code', ''),
            'ShipNumber': row.get('ship-phone-number', '')
        }

    def prepare_fbm_unshipped_data_request_ept(self, emipro_api):
        """
        This method will prepare the FBM unshipped data request.
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        seller_id = self.seller_id
        return {'merchant_id': seller_id.merchant_id and str(seller_id.merchant_id) or False,
                'app_name': 'amazon_ept_spapi',
                'account_token': account.account_token,
                'emipro_api': emipro_api,
                'dbuuid': dbuuid,
                'amazon_marketplace_code': seller_id.country_id.amazon_marketplace_code or seller_id.country_id.code}

    def process_fbm_sale_order_file(self):
        """
        This method process the attached file with record and create Sales orders.
        :return:True
        """
        self.ensure_one()
        ir_cron_obj = self.env['ir.cron']
        common_log_line_obj = self.env['common.log.lines.ept']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_process_amazon_unshipped_orders_seller_', self.seller_id.id)
        marketplaceids = tuple(map(lambda x: x.market_place_id, self.seller_id.instance_ids))
        if not marketplaceids:
            raise UserError(_("There is no any instance is configured of seller %s" % (self.seller_id.name)))
        if not self.attachment_id:
            raise UserError(_("There is no any report are attached with this record."))
        file_order_list = self.get_unshipped_order()
        unshipped_order_list = []
        business_prime_dict = {}
        kwargs = self.prepare_fbm_unshipped_data_request_ept('get_amazon_orders_sp_api')
        kwargs.update({'marketplaceids': marketplaceids})
        for x in range(0, len(file_order_list), 50):
            sale_orders_list = file_order_list[x:x + 50]
            sale_orders_list = ",".join(sale_orders_list)
            kwargs.update({'sale_order_list': sale_orders_list})
            #Max_request_quota = 6, restore_rate = 1req/min
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                if self._context.get('is_auto_process', False):
                    common_log_line_obj.create_common_log_line_ept(
                        message=response.get('error', {}), model_name='fbm.sale.order.report.ept', fulfillment_by='FBM',
                        module='amazon_ept', operation_type='import', res_id=self.id,
                        amz_seller_ept=self.seller_id and self.seller_id.id or False)
                else:
                    raise UserError(_(response.get('error', {})))
            else:
                unshipped_order_list, business_prime_dict = self.process_fbm_shipped_order_response_ept(
                    response, unshipped_order_list, business_prime_dict)
        self.process_prepare_unshipped_order_list_ept(unshipped_order_list, business_prime_dict)
        self.write({'state': 'processed'})
        return True

    def process_prepare_unshipped_order_list_ept(self, unshipped_order_list, business_prime_dict):
        """
        Prepare Unshipped ORders List for processing File data
        :param unshipped_order_list: list[]
        :param business_prime_dict: dict {}
        :param fbm_order_dict: dict{}
        :return: boolean
        """
        marketplace_obj = self.env['amazon.marketplace.ept']
        imp_file = self.decode_amazon_encrypted_fbm_attachments_data(self.attachment_id)
        reader = csv.DictReader(imp_file, delimiter='\t')
        order_dict = dict()
        marketplace_dict, amazon_instance_dict, order_skip_list = {}, {}, []
        for row in reader:
            if not row.get('sku', ''):
                continue
            if not row.get('order-id', False) in unshipped_order_list:
                continue
            amz_ref = row.get('order-id')
            marketplace_record = marketplace_dict.get(row.get('sales-channel', ''))
            if not marketplace_record:
                marketplace_record = marketplace_obj.search([('name', '=', row.get('sales-channel', '')),
                                                             ('seller_id', '=', self.seller_id.id)])
                marketplace_dict.update({row.get('sales-channel', ''): marketplace_record})
            instance = amazon_instance_dict.get((self.seller_id, marketplace_record), '')
            if not instance:
                instance = self.seller_id.instance_ids.filtered(
                    lambda l, marketplace_record=marketplace_record: l.marketplace_id.id == marketplace_record.id)
                amazon_instance_dict.update({(self.seller_id, marketplace_record): instance})
            if (amz_ref, instance.id) in order_skip_list:
                continue
            order = self.check_order_exist_in_odoo(amz_ref, instance.id)
            if order:
                order_skip_list.append((amz_ref, instance.id))
                if not order.buyer_requested_cancellation:
                    order.buyer_requested_cancellation = eval(row.get('is-buyer-requested-cancellation',
                                                                      'false').capitalize())
                continue
            order_dict = self.prepare_order_dict(order_dict, amz_ref, instance.id, row, business_prime_dict)
        self.process_fbm_unshipped_order_dict(order_dict, business_prime_dict)
        return True

    def process_fbm_unshipped_order_dict(self, order_dict, business_prime_dict):
        """
        Process FBM Unshipped Order from prepared dictionary
        :param order_dict: dict{}
        :param business_prime_dict: dict{}
        :return:
        """
        amazon_instance_obj = self.env['amazon.instance.ept']
        common_log_book_obj = self.env['common.log.book.ept']
        sale_order_obj = self.env['sale.order']
        state_dict = {}
        country_dict = {}
        dict_product_details = {}
        count_order_number = 0
        for order_ref, order_details in order_dict.items():
            skip_order, dict_product_details = self.create_or_find_amazon_fbm_product(
                order_ref, order_details, dict_product_details)
            instance = amazon_instance_obj.browse(order_ref[1])
            if skip_order:
                # create schedule activity for the missing products
                if instance.seller_id.is_amz_create_schedule_activity:
                    missing_products = sale_order_obj.amz_find_missing_products_for_create_schedule_activity(
                        order_details, 'FBM', order_ref[1])
                    common_log_book_obj.amz_create_schedule_activity_for_missing_products(
                        missing_products, instance.seller_id, 'fbm.sale.order.report.ept', self.id, 'FBM')
                continue
            customer_vals = self.prepare_fbm_customer_vals(order_details[0])
            partner = self.get_partner(customer_vals, state_dict, country_dict, instance)
            order = self.create_amazon_fbm_unshipped_order(instance, partner, order_ref, order_details,
                                                           business_prime_dict)
            self.create_amazon_fbm_unshipped_order_lines(order, instance, order_details, dict_product_details)
            order.process_orders_and_invoices_ept()
            count_order_number += 1
            if count_order_number >= 10:
                self._cr.commit()
                count_order_number = 0
        return True

    def create_amazon_fbm_unshipped_order(self, instance, partner, order_ref, order_details, business_prime_dict):
        """
        Create FBM Unshipped Orders
        :param instance: amazon.instance.ept()
        :param partner: res.partner()
        :param order_ref: sale order reference
        :param order_details: dict of order detail
        :param business_prime_dict: dict of business and prime orders
        :return:
        """
        # set carrier in order vals
        sale_order_obj = self.env[SALE_ORDER]
        seller = self.seller_id
        order_values = {'PurchaseDate': order_details[0].get('purchase-date', '') or False,
                        'AmazonOrderId': order_ref[0] or False}
        ordervals = sale_order_obj.prepare_amazon_sale_order_vals(instance, partner, order_values)
        # set picking policy as FBM Auto workflow picking policy
        ordervals.update({'picking_policy': instance.seller_id.fbm_auto_workflow_id.picking_policy})
        if not seller.is_default_odoo_sequence_in_sales_order:
            name = seller.order_prefix + order_ref[0] if seller.order_prefix else order_ref[0]
            ordervals.update({'name': name})
        updated_ordervals = self.prepare_updated_ordervals(instance, order_ref)
        if business_prime_dict.get(order_ref[0], False):
            updated_ordervals.update(
                {'is_business_order': business_prime_dict.get(order_ref[0]).get('is_business_order', ''),
                 'is_prime_order': business_prime_dict.get(order_ref[0]).get('is_prime_order', '')})
        if order_details:
            updated_ordervals.update({'amz_shipment_service_level_category': order_details[0].get(
                'ship-service-level', False)})
            # update sale order vals set carrier which amz_shipment_service_level_category and
            # unshipped order ship-service-level is same
            shipping_category = order_details[0].get('ship-service-level', False)
            if shipping_category:
                carrier = self.amz_find_fbm_delivery_method(
                    shipping_category,ordervals.get('partner_shipping_id',False))
                updated_ordervals.update({'carrier_id': carrier.id if carrier else False})
        ordervals.update(updated_ordervals)
        if not ordervals.get('fiscal_position_id', False):
            ordervals.pop('fiscal_position_id')
        order = sale_order_obj.with_context(is_b2b_amz_order=ordervals.get('is_business_order', False)).create(ordervals)
        return order
    def amz_find_fbm_delivery_method(self,shipping_category,delivery_partner_id):
        """
        Define this method for find delivery method for FBM unshipped or partially
        shipped order based on ship partner country id.
        :return: delivery.carrier()
        :param : shipping_category: order delivery category
        """
        res_partner_obj =self.env['res.partner']
        delivery_carrier_obj = self.env['delivery.carrier']
        ship_partner = res_partner_obj.browse(delivery_partner_id)
        ship_country = ship_partner.country_id.ids if ship_partner.country_id else []
        carrier = delivery_carrier_obj.search([('amz_shipping_service_level_category', '=', shipping_category),
                                               ('country_ids','in',ship_country)],limit=1)
        if not carrier:
            carrier = delivery_carrier_obj.search([('amz_shipping_service_level_category', '=', shipping_category)],
                                                  limit=1)
        return carrier
    def process_fbm_shipped_order_response_ept(self, response, unshipped_order_list, business_prime_dict):
        """
        This method will process response and prepare unshipped order list and business prime dict
        param response : order response
        param unshipped_order_list : list of unshipped order
        param business_prime_dict : business prime dict data
        return : unshipped_order_list and business_prime_dict
        """
        result = []
        if response.get('result', {}):
            result = [response.get('result', {})]
            time.sleep(4)
        for wrapper_obj in result:
            orders = []
            if not isinstance(wrapper_obj.get('Orders', []), list):
                orders.append(wrapper_obj.get('Orders', {}))
            else:
                orders = wrapper_obj.get('Orders', [])
            unshipped_order_list, business_prime_dict = self.prepare_business_prime_orders_dict(
                orders, unshipped_order_list, business_prime_dict)
        return unshipped_order_list, business_prime_dict

    def prepare_business_prime_orders_dict(self, orders, unshipped_order_list, business_prime_dict):
        """
        Prepare list of unshipped orders and also prepare dictionary of business and prime orders data.
        :param orders: list of orders data
        :param unshipped_order_list: unshipped orders list
        :param business_prime_dict: business prime order data dict
        :param fbm_order_dict: fbm orders dict
        :return: unshipped_order_list, business_prime_dict, fbm_order_dict
        """
        for order in orders:
            amazon_order_ref = order.get('AmazonOrderId', '')
            if not amazon_order_ref:
                continue
            order_status = order.get('OrderStatus', '')
            is_business_order = True if str(order.get('IsBusinessOrder', '')).lower() in ['true',
                                                                                          't'] else False
            is_prime_order = True if str(order.get('IsPrime', '')).lower() in ['true', 't'] else False
            if order_status == 'Unshipped' and amazon_order_ref not in unshipped_order_list:
                unshipped_order_list.append(amazon_order_ref)
                order_data = dict()
                order_data.update({'buyer-name': order.get('BuyerInfo', {}).get('BuyerName'),
                                   'shipping-address': order.get('ShippingAddress', {})})
                if is_business_order or is_prime_order:
                    order_data.update({'is_business_order': is_business_order,
                                       'is_prime_order': is_prime_order})
                if order_data:
                    business_prime_dict.update({amazon_order_ref: order_data})
        return unshipped_order_list, business_prime_dict

    def get_unshipped_order(self):
        """
        Give the list of unshipped orders.
        :return: unshipped order list
        """
        file_order_list = []
        imp_file = self.decode_amazon_encrypted_fbm_attachments_data(self.attachment_id)
        reader = csv.DictReader(imp_file, delimiter='\t')
        for row in reader:
            file_order_list.append(row.get('order-id', False))
        return file_order_list

    @staticmethod
    def prepare_order_dict(order_dict, amz_ref, instance_id, row, business_prime_dict):
        """
        This method prepare the order dictionary.
        :param order_dict: order dictionary
        :param amz_ref: amazon order id
        :param instance_id : instance record
        :param row: file line
        :param business_prime_dict: business_prime_dict
        :return: order dictionary
        """
        buyer_name = row.get('buyer-name', '') if row.get('buyer-name', False) \
            else business_prime_dict.get(amz_ref, {}).get('buyer-name', '')
        recipient_name = row.get('recipient-name') if row.get('recipient-name', False) \
            else business_prime_dict.get(amz_ref, {}).get('shipping-address', {}).get('Name', '')
        address1 = row.get('ship-address-1') if row.get('ship-address-1', False) else business_prime_dict.get(
            amz_ref, {}).get('shipping-address', {}).get('AddressLine1', '')
        address2 = row.get('ship-address-2') if row.get('ship-address-2', False) else business_prime_dict.get(
            amz_ref, {}).get('shipping-address', {}).get('AddressLine2', '')
        fbm_order_dict = {
            'order-item-id': row.get('order-item-id', False),
            'purchase-date': row.get('purchase-date', ''),
            'buyer-email': row.get('buyer-email', ''),
            'buyer-name': buyer_name,
            'buyer-phone-number': row.get('buyer-phone-number', ''),
            'ship-phone-number': row.get('ship-phone-number', ''),
            'sku': row.get('sku', ''),
            'product-name': row.get('product-name', ''),
            'quantity-purchased': row.get('quantity-purchased', 0.0),
            'item-price': row.get('item-price', 0.0),
            'item-tax': row.get('item-tax', 0.0),
            'shipping-price': row.get('shipping-price', 0.0),
            'shipping-tax': row.get('shipping-tax', 0.0),
            'recipient-name': recipient_name,
            'ship-address-1': address1,
            'ship-address-2': address2,
            'ship-city': row.get('ship-city', ''),
            'ship-state': row.get('ship-state', ''),
            'ship-postal-code': row.get('ship-postal-code', ''),
            'ship-country': row.get('ship-country', ''),
            'item-promotion-discount': abs(float(row.get('item-promotion-discount', 0.0))),
            'ship-promotion-discount': abs(float(row.get('ship-promotion-discount', 0.0))),
            'sales-channel': row.get('sales-channel', ''),
            'ship-service-level': row.get('ship-service-level', ''),
            'buyer_requested_cancellation': eval(row.get('is-buyer-requested-cancellation', 'false').capitalize())
            }

        if order_dict.get((amz_ref, instance_id), False):
            fbm_order_dict.update({'promise-date': row.get('promise-date', ''), })
            order_dict.get((amz_ref, instance_id)).append(fbm_order_dict)
        else:
            order_dict.update({(amz_ref, instance_id): [fbm_order_dict]})
        return order_dict

    def check_order_exist_in_odoo(self, amz_ref, instance_id):
        """
        This method check that the order is already exist in odoo or not.
        :param amz_ref: Amazon Order Reference
        :param instance_id : amazon instance record.
        :return: True or False
        """
        sale_order_obj = self.env[SALE_ORDER]
        order = sale_order_obj.search( \
            [('amz_instance_id', '=', instance_id),
             ('amz_order_reference', '=', amz_ref),
             ('amz_fulfillment_by', '=', 'FBM')])
        return order

    def get_partner(self, vals, state_dict, country_dict, instance):
        """
        This method is find the partner and if it's not found than it create the new partner.
        :param vals: {}
        :param state_dict: {}
        :param country_dict: {}
        :param instance: amazon.instance.ept()
        :return: Partner {}
        """
        country, state = self.get_fbm_order_state_and_country_ept(vals, country_dict, state_dict)
        email = vals.get('BuyerEmail', '')
        buyer_name = vals.get('BuyerName', '')
        ship_name = vals.get('ShipName', '')
        street = vals.get('AddressLine1', '') if vals.get('AddressLine1', '') else ''
        address_line2 = vals.get('AddressLine2', '') if vals.get('AddressLine2', '') else ''
        # if street1 and street2 both are same then do not set street2 in the partner address
        if address_line2 and (street == address_line2):
            address_line2 = ''
        address_line3 = vals.get('AddressLine3', '') if vals.get('AddressLine3', '') else ''
        street2 = "%s %s" % (address_line2, address_line3) if address_line2 or address_line3 else False
        city = vals.get('City', '')
        zip_code = vals.get('PostalCode', '')
        phone = vals.get('ShipNumber', '')
        new_partner_vals = {
            'street': street,
            'street2': street2,
            'zip': zip_code,
            'city': city,
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
            'phone': phone,
            'company_id': instance.company_id.id,
            'email': email,
            'lang': instance.lang_id and instance.lang_id.code,
            'is_amz_customer': True,
        }
        partner, invoice_partner = self.search_amazon_fbm_invoice_and_partner_ept(instance, buyer_name,
                                                                                  new_partner_vals)
        delivery = self.search_or_create_fbm_delivery_partner(invoice_partner, new_partner_vals, instance, partner,
                                                              ship_name, country, state)
        return {'invoice_partner': invoice_partner.id, 'shipping_partner': delivery.id}

    def search_or_create_fbm_delivery_partner(self, invoice_partner, new_partner_vals, instance, partner, ship_name,
                                              country, state):
        """
        Search Delivery Partner if exist then return it or create new delivery partner
        :param invoice_partner: res.partner()
        :param new_partner_vals: dict {}
        :param instance: amazon.instance.ept()
        :param partner: res.partner()
        :param ship_name: string
        :param country: res.country()
        :param state: res.state()
        :return: res.partner()
        """
        partner_obj = self.env[RES_PARTNER]
        street = new_partner_vals.get('street', '')
        street2 = new_partner_vals.get('street2', '')
        zip_code = new_partner_vals.get('zip', '')
        city = new_partner_vals.get('city', '')
        delivery = invoice_partner if (
            invoice_partner.name == ship_name and invoice_partner.street == street
            and (not invoice_partner.street2 or invoice_partner.street2 == street2)
            and invoice_partner.zip == zip_code and invoice_partner.city == city
            and invoice_partner.country_id == country
            and invoice_partner.state_id == state) else False
        if not delivery:
            delivery = partner_obj.with_context(is_amazon_partner=True).search(
                [('name', '=', ship_name), ('street', '=', street),
                 '|', ('street2', '=', False), ('street2', '=', street2),
                 ('zip', '=', zip_code),
                 ('city', '=', city),
                 ('country_id', '=', country.id if country else False),
                 ('state_id', '=', state.id if state else False),
                 '|', ('company_id', '=', False),
                 ('company_id', '=', instance.company_id.id), ('vat', '=', False)], limit=1)
            if not delivery:
                delivery = partner_obj.with_context(tracking_disable=True).create({
                    'name': ship_name, 'type': 'delivery', 'parent_id': partner.id, **new_partner_vals})
        return delivery

    def get_fbm_order_state_and_country_ept(self, vals, country_dict, state_dict):
        """
        This method is used to get the FBM order state and country
        """
        partner_obj = self.env[RES_PARTNER]
        country = country_dict.get(vals.get('CountryCode', ''), False)
        if not country:
            country = partner_obj.get_country(vals.get('CountryCode', ''))
            country_dict.update({vals.get('CountryCode', ''): country})
        state = state_dict.get(vals.get('StateOrRegion', ''), False)
        if not state and country and vals.get('StateOrRegion', '') != '--':
            state = partner_obj.create_or_update_state_ept(
                country.code, vals.get('StateOrRegion', ''), vals.get('PostalCode', ''), country)
            state_dict.update({vals.get('StateOrRegion', ''): state})
        return country, state

    def search_amazon_fbm_invoice_and_partner_ept(self, instance, buyer_name, new_partner_vals):
        """
        This method is used to search the amazon FBM partner and invoice partner
        """
        partner_obj = self.env[RES_PARTNER]
        email = new_partner_vals.get('email')
        if instance.amazon_property_account_payable_id:
            new_partner_vals.update({'property_account_payable_id': instance.amazon_property_account_payable_id.id})
        if instance.amazon_property_account_receivable_id:
            new_partner_vals.update({'property_account_receivable_id':
                                         instance.amazon_property_account_receivable_id.id})
        city = new_partner_vals.get('city', '')
        state_id = new_partner_vals.get('state_id', False)
        country_id = new_partner_vals.get('country_id', False)
        if not email and buyer_name == 'Amazon':
            partner = partner_obj.with_context(is_amazon_partner=True).search(
                [('name', '=', buyer_name), ('is_company', '=', False), ('city', '=', city),
                 ('state_id', '=', state_id), ('country_id', '=', country_id),
                 '|', ('company_id', '=', False), ('company_id', '=', instance.company_id.id),
                 ('vat', '=', False)], limit=1)
        else:
            partner = partner_obj.with_context(is_amazon_partner=True).search(
                [('email', '=', email), ('is_company', '=', False), '|', ('company_id', '=', False),
                 ('company_id', '=', instance.company_id.id), ('vat', '=', False)], limit=1)
        if not partner:
            partner = partner_obj.with_context(tracking_disable=True).create({'name': buyer_name, 'type': 'invoice',
                                                                              'is_company': False, **new_partner_vals})
            invoice_partner = partner
        elif buyer_name and partner.name != buyer_name:
            invoice_partner = partner_obj.with_context(tracking_disable=True).create({
                'parent_id': partner.id, 'name': buyer_name, 'type': 'invoice', **new_partner_vals})
        else:
            invoice_partner = partner
        return partner, invoice_partner

    def create_or_find_amazon_fbm_product(self, order_ref, order_details, product_details):
        """
        This method is find product in odoo based on sku. If not found than create new product.
        :param sku:Product SKU
        :param product_name:Product name or Description
        :param seller_id:Seller Object
        :param instance: instance Object
        :return: Odoo Product Object
        """
        product_obj = self.env['product.product']
        amz_product_obj = self.env[AMAZON_PRODUCT_EPT]
        instance_obj = self.env['amazon.instance.ept']
        common_log_line_obj = self.env['common.log.lines.ept']
        instance_id = instance_obj.browse(order_ref[1])
        skip_order = False
        for order_detail in order_details:
            sku = order_detail.get('sku', '').strip()
            amz_product = amz_product_obj.search_amazon_product(order_ref[1], sku, 'FBM')
            if not amz_product:
                odoo_product = product_obj.search([('default_code', '=', sku)])
                if not odoo_product and instance_id.seller_id.create_new_product:
                    odoo_product = product_obj.create({
                        'name': order_detail.get('product-name', ''),
                        'description_sale': order_detail.get('product-name', ''),
                        'default_code': sku,
                        'type': 'product'})
                    amazon_product_id = amz_product_obj.create(
                        {'name': odoo_product.name,
                         'product_id': odoo_product.id,
                         'seller_sku': odoo_product.default_code,
                         'fulfillment_by': 'FBM',
                         'instance_id': order_ref[1]})
                    message = 'Product is not available in Amazon Odoo Connector and Odoo, So it\'ll created in both.'
                    common_log_line_obj.create_common_log_line_ept(
                        message=message, default_code=amazon_product_id.seller_sku,
                        model_name='fbm.sale.order.report.ept', fulfillment_by='FBM', module='amazon_ept',
                        operation_type='import', res_id=self.id, amz_instance_ept=instance_id and instance_id.id or
                        False, amz_seller_ept=instance_id.seller_id and instance_id.seller_id.id or False)

                elif odoo_product:
                    amz_product_obj.create({'name': odoo_product.name,
                                            'product_id': odoo_product.id,
                                            'seller_sku': odoo_product.default_code,
                                            'fulfillment_by': 'FBM',
                                            'instance_id': order_ref[1]})
                else:
                    skip_order = True
                    message = 'Order skipped due to product is not available.'
                    common_log_line_obj.create_common_log_line_ept(
                        message=message, model_name='fbm.sale.order.report.ept', fulfillment_by='FBM',
                        module='amazon_ept', operation_type='import', res_id=self.id, mismatch_details=True,
                        amz_seller_ept=instance_id.seller_id and instance_id.seller_id.id or False,
                        amz_instance_ept=instance_id and instance_id.id or False)
            else:
                odoo_product = amz_product.product_id
            product_details.update({(sku, order_ref[1]): odoo_product})
        return skip_order, product_details

    def check_order_line_exist(self, instance, amz_ref, order_line_ref, sale_order_obj):
        """
        This method find the order line is exist in Sales order or not.
        :param instance:instance object
        :param amz_ref:Order Reference
        :param order_line_ref: Order Line reference
        :param sale_order_obj:Sale order Object
        :return: Order line or False
        """
        order = sale_order_obj.search([('amz_instance_id', '=', instance.id), ('amz_order_reference', '=', amz_ref)])
        order_line = order.order_line.filtered(lambda x: x.amazon_order_item_id == order_line_ref)
        if order_line:
            return order_line
        return False

    def prepare_updated_ordervals(self, instance, order_ref):
        """
        This method prepare the order vals.
        :param expected_delivery_date: Expected Delivery Date
        :param instance: instance object
        :param seller: seller object
        :param order_ref: order reference
        :return: Order Vals
        """
        ordervals = {
            'amz_sales_order_report_id': self.id,
            'amz_instance_id': instance and instance.id or False,
            'amz_seller_id': instance.seller_id.id,
            'amz_fulfillment_by': 'FBM',
            'amz_order_reference': order_ref[0] or False,
            'auto_workflow_process_id': instance.seller_id.fbm_auto_workflow_id.id
        }
        # analytic_account = instance.analytic_account_id.id if instance.analytic_account_id else False
        # if analytic_account:
        #     ordervals.update({'analytic_account_id': analytic_account})
        return ordervals

    def create_amazon_fbm_unshipped_order_lines(self, order, instance, order_details, dict_product_details):
        """
        This method prepare order lines.
        :param order: order Object
        :param instance: instance object
        :param order_details: sale order line from dictionary
        :param sale_order_line_obj: sale order line object
        :return: True
        """
        sale_order_line_obj = self.env['sale.order.line']
        for order_detail in order_details:
            if not order_detail.get('sku', ''):
                continue
            taxargs = {}
            product = dict_product_details.get((order_detail.get('sku', ''), instance.id))
            item_price = self.get_item_price(order_detail, instance)
            quantity = float(order_detail.get('quantity-purchased', 1.0))
            unit_price = item_price / quantity
            item_tax = float(order_detail.get('item-tax'))
            if instance.is_use_percent_tax:
                unit_tax = item_tax / quantity if quantity > 0.0 else item_tax
                item_tax_percent = (unit_tax * 100) / unit_price if unit_price > 0 else 0.00
                amz_tax_id = order.amz_instance_id.amz_tax_id
                taxargs = {'line_tax_amount_percent': item_tax_percent, 'tax_id': [(6, 0, [amz_tax_id.id])]}
            order_line_vals = {
                'order_id': order.id,
                'product_id': product.id,
                'company_id': instance.company_id.id or False,
                'product_uom_qty': quantity,
                'price_unit': unit_price,
                'discount': False,
                'state': 'draft'
            }
            order_line_vals.update({'amazon_order_item_id': order_detail.get('order-item-id', False),
                                    'line_tax_amount': item_tax, **taxargs})
            # Set Analytic Account in the Sale order line from Amazon Seller and Marketplace
            order_line_vals = sale_order_line_obj.set_analytic_account_ept(order, order_line_vals)
            sale_order_line_obj.create(order_line_vals)
            self.create_fbm_unshipped_chargable_order_line_ept(instance, order, order_detail)
        return True

    def get_fbm_unshipped_order_line_vals(self, instance, order, product_id, price_unit, order_detail):
        """
        This method will prepare the FBM unshipped order line vals
        """
        sale_order_line_obj = self.env['sale.order.line']
        unshipped_order_line_vals = {
            'order_id': order.id,
            'product_id': product_id.id,
            'company_id': instance.company_id.id or False,
            'product_uom_qty': '1.0',
            'price_unit': price_unit,
            'discount': False,
            'amazon_order_item_id': order_detail.get('order-item-id', False)}
        # Set Analytic Account in the Sale order line from Amazon Seller and Marketplace
        unshipped_order_line_vals = sale_order_line_obj.set_analytic_account_ept(order, unshipped_order_line_vals)
        return unshipped_order_line_vals

    def amz_find_product(self, order_detail):
        """
        This method find the odoo product.
        :param order_detail: order line
        :return: odoo product object
        """
        amz_product_obj = self.env[AMAZON_PRODUCT_EPT]
        amz_product = amz_product_obj.search(
            [('seller_sku', '=', order_detail.get('sku', ''))])
        product = amz_product.product_id
        return product

    def create_fbm_unshipped_chargable_order_line_ept(self, instance, order, order_detail):
        """
        This method is used to create FBM unshipped chargeable order line
        """
        sale_order_line_obj = self.env['sale.order.line']
        if float(order_detail.get('shipping-price', 0.0)) > 0 and instance.seller_id.shipment_charge_product_id:
            shipping_price = self.get_shipping_price(order_detail, instance)
            shipment_charge_product_id = instance.seller_id.shipment_charge_product_id
            charges_vals = self.get_fbm_unshipped_order_line_vals(instance, order, shipment_charge_product_id,
                                                                  shipping_price, order_detail)
            if instance.is_use_percent_tax:
                shipping_tax = order_detail.get('shipping-tax', 0.0)
                ship_tax_percent = (float(shipping_tax) * 100) / float(shipping_price) if shipping_price > 0.0 else 0.0
                amz_tax_id = order.amz_instance_id.amz_tax_id
                taxargs = {'line_tax_amount': shipping_tax,
                           'line_tax_amount_percent': ship_tax_percent,
                           'tax_id': [(6, 0, [amz_tax_id.id])]}
                charges_vals.update(taxargs)
            sale_order_line_obj.create(charges_vals)
        if float(order_detail.get(
                'item-promotion-discount', 0.0) or 0) > 0 and instance.seller_id.promotion_discount_product_id:
            item_discount = float(order_detail.get('item-promotion-discount', 0.0)) * (-1)
            promotion_discount_product_id = instance.seller_id.promotion_discount_product_id
            item_promotion_vals = self.get_fbm_unshipped_order_line_vals(instance, order, promotion_discount_product_id,
                                                                         item_discount, order_detail)
            sale_order_line_obj.create(item_promotion_vals)
        if float(order_detail.get(
                'ship-promotion-discount', 0.0) or 0) > 0 and instance.seller_id.ship_discount_product_id:
            ship_discount = float(order_detail.get('ship-promotion-discount', 0.0)) * (-1)
            ship_discount_product_id = instance.seller_id.ship_discount_product_id
            ship_promotion_vals = self.get_fbm_unshipped_order_line_vals(instance, order, ship_discount_product_id,
                                                                         ship_discount, order_detail)
            sale_order_line_obj.create(ship_promotion_vals)
        return True

    def prepare_updated_orderline_vals(self, order_line_vals, order_detail):
        """
        This method prepare updated order line vals.
        :param order_line_vals: old order line vals
        :param order_detail: order line
        :return:order_line_vals
        """
        order_line_vals.update({'amazon_order_item_id': order_detail.get('order-item-id', False)})
        return order_line_vals

    def get_item_price(self, order_detail, instance):
        """
        This method addition the price and tax of product item cost.
        :param unit_price: item price
        :param tax: item tax
        :return: sum of price and tax.
        """
        unit_price = float(order_detail.get('item-price', 0.0))
        tax = float(order_detail.get('item-tax', 0.0))
        if self.seller_id.is_vcs_activated or (instance.amz_tax_id and not instance.amz_tax_id.price_include):
            return unit_price
        return unit_price + tax

    def get_shipping_price(self, order_detail, instance):
        """
        This method addition the price and tax of shipping cost.
        :param shipping_price: shipping price
        :param shipping_tax: shipping tax
        :return: sum of price and tax
        """
        shipping_price = float(order_detail.get('shipping-price', 0.0))
        shipping_tax = float(order_detail.get('shipping-tax', 0.0))
        if self.seller_id.is_vcs_activated or (instance.amz_tax_id and not instance.amz_tax_id.price_include):
            return shipping_price
        return shipping_price + shipping_tax

    def decode_amazon_encrypted_fbm_attachments_data(self, attachment_id):
        """
        This method is used to decode the amazon attachments data
        """
        common_log_line_obj = self.env['common.log.lines.ept']
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        kwargs = {'dbuuid': dbuuid, 'report_id': self.report_id, 'report_document_id': self.report_document_id,
                  'datas': attachment_id.datas.decode(), 'amz_report_type': 'fbm_report_spapi',
                  'merchant_id': self.seller_id.merchant_id}
        response = iap_tools.iap_jsonrpc(DECODE_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('result', False):
            try:
                imp_file = StringIO(base64.b64decode(response.get('result', {})).decode())
            except Exception:
                imp_file = StringIO(base64.b64decode(response.get('result', {})).decode('ISO-8859-1'))
        elif self._context.get('is_auto_process', False):
            common_log_line_obj.create_common_log_line_ept(
                message='Error found in Decryption of Data %s' % response.get('error', ''),
                model_name='fbm.sale.order.report.ept', fulfillment_by='FBM', module='amazon_ept',
                operation_type='import', res_id=self.id, amz_seller_ept=self.seller_id and self.seller_id.id or False)
            return True
        else:
            raise UserError(_(response.get('error', '')))
        return imp_file
