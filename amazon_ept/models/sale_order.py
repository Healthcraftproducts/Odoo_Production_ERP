# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Inherited sale order and fields to create amazon sale orders in odoo.
"""

import json
import logging
import time
import re
from datetime import datetime, timedelta

import pytz
from dateutil import parser
from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError

from ..endpoint import DEFAULT_ENDPOINT

utc = pytz.utc
_logger = logging.getLogger(__name__)
AMZ_SELLER_EPT = 'amazon.seller.ept'
AMZ_INSTANCE_EPT = 'amazon.instance.ept'
AMZ_SHIPPING_REPORT_REQUEST_HISTORY = 'shipping.report.request.history'
AMZ_PRODUCT_EPT = 'amazon.product.ept'
IR_MODEL = 'ir.model'
SALE_ORDER = 'sale.order'
COMMON_LOG_LINES_EPT = 'common.log.lines.ept'
DATE_YMDHMS = "%Y-%m-%d %H:%M:%S"
DATE_YMDTHMS = "%Y-%m-%dT%H:%M:%S"
AMAZON_INSTANCE_NOT_CONFIGURED_WARNING = "There is no any instance is configured of seller"
amazon_messages = {'fba_warehouse_id': "The order import operation failed because the warehouse configuration" 
                                       "was not found in the instance configuration.\n"
                                       "- To resolve this issue, navigate to Amazon >> Configuration >> Settings,\n"
                                       "select Marketplace and configure FBA Warehouse",

                   'picking_policy': "The order import operation failed because the shipping policy configuration"
                                       " was not found in the auto invoice workflow configuration.\n"
                                       "- To resolve this issue, navigate to Amazon >> Configuration >> Settings.\n"
                                       "- Select Seller and Review whether Auto Workflow is configured,"
                                       "and within Auto workflow, ensure that the shipping policy is also configured.",

                   'ship_product': "When creating a new delivery method, the system encountered an issue as it could "
                                   "not find the shipping product in the instance configuration.\n"
                                   "- To resolve this issue, please follow these steps:\n"
                                   "\t1.Go to Amazon >> Configuration>> Settings >> Amazon Shipment Fee.\n"
                                   "\t2.Review whether the shipping product is set.\n"
                                   "\t3.If already set, ensure that it is active in Odoo.",

                   'fbm_warehouse_id': "The order import operation failed because the warehouse configuration"
                                       "was not found in the instance configuration.\n"
                                       "- To resolve this issue, navigate to Amazon >> Configuration >> Settings,\n"
                                       "select Marketplace and configure FBM Warehouse",

                   'pricelist_id':  "The order import operation failed because the pricelist configuration was not "
                                   " found in the instance configuration.\n"
                                   "- To resolve this issue, navigate to Amazon >> Configuration >> Settings,\n"
                                   "select Marketplace  and configure Marketplace Pricelist"
                   }


class SaleOrder(models.Model):
    """
    inherited class to create amazon sales order in odoo.
    """
    _inherit = "sale.order"

    def _search_order_ids_amazon(self, operator, value):
        # inner join amazon_sale_order_ept on sale_order_id=sale_order.id
        query = """
                select sale_order.id from stock_picking           
                inner join sale_order on sale_order.procurement_group_id=stock_picking.group_id
                inner join stock_location on stock_location.id=stock_picking.location_dest_id and 
                stock_location.usage='customer'                
                where stock_picking.updated_in_amazon=False and stock_picking.state='done'    
              """
        self._cr.execute(query)
        results = self._cr.fetchall()
        order_ids = []
        for result_tuple in results:
            order_ids.append(result_tuple[0])
        return [('id', 'in', order_ids)]

    def _compute_amazon_status(self):
        """
        This will get amazon status and update in order.
        """
        for order in self:
            if order.picking_ids:
                order.updated_in_amazon = True
            else:
                order.updated_in_amazon = False
            for picking in order.picking_ids:
                if picking.state == 'cancel':
                    continue
                if picking.location_dest_id.usage != 'customer':
                    continue
                if not picking.updated_in_amazon:
                    order.updated_in_amazon = False
                    break

    @api.onchange('warehouse_id')
    def _compute_is_fba_warehouse(self):
        """
        This method will check is order has FBA warehouse.
        """
        for record in self:
            if record.warehouse_id.is_fba_warehouse:
                record.order_has_fba_warehouse = True
            else:
                record.order_has_fba_warehouse = False

    full_fill_ment_order_help = """
            RECEIVED:The fulfillment order was received by Amazon Marketplace Web Service (Amazon 
            MWS) 
                     and validated. Validation includes determining that the destination address is 
                     valid and that Amazon's records indicate that the seller has enough sellable 
                     (undamaged) inventory to fulfill the order. The seller can cancel a 
                     fulfillment 
                     order that has a status of RECEIVED
            INVALID:The fulfillment order was received by Amazon Marketplace Web Service (Amazon 
            MWS) 
                    but could not be validated. The reasons for this include an invalid destination 
                    address or Amazon's records indicating that the seller does not have enough 
                    sellable 
                    inventory to fulfill the order. When this happens, the fulfillment order is 
                    invalid 
                    and no items in the order will ship
            PLANNING:The fulfillment order has been sent to the Amazon Fulfillment Network to begin 
                     shipment planning, but no unit in any shipment has been picked from 
                     inventory yet. 
                     The seller can cancel a fulfillment order that has a status of PLANNING
            PROCESSING:The process of picking units from inventory has begun on at least one 
            shipment 
                       in the fulfillment order. The seller cannot cancel a fulfillment order that 
                       has a status of PROCESSING
            CANCELLED:The fulfillment order has been cancelled by the seller.
            COMPLETE:All item quantities in the fulfillment order have been fulfilled.
            COMPLETE_PARTIALLED:Some item quantities in the fulfillment order were fulfilled; the 
            rest were either cancelled or unfulfillable.
            UNFULFILLABLE: item quantities in the fulfillment order could be fulfilled because t
            he Amazon fulfillment center workers found no inventory 
            for those items or found no inventory that was in sellable (undamaged) condition.
        """

    help_fulfillment_action = """
            Ship - The fulfillment order ships now

            Hold - An order hold is put on the fulfillment order.

            Default: Ship in Create Fulfillment
            Default: Hold in Update Fulfillment    
        """

    help_fulfillment_policy = """
            FillOrKill - If an item in a fulfillment order is determined to be unfulfillable 
            before any 
                        shipment in the order moves to the Pending status (the process of picking 
                        units 
                        from inventory has begun), then the entire order is considered 
                        unfulfillable. 
                        However, if an item in a fulfillment order is determined to be 
                        unfulfillable 
                        after a shipment in the order moves to the Pending status, Amazon cancels 
                        as 
                        much of the fulfillment order as possible

            FillAll - All fulfillable items in the fulfillment order are shipped. 
                    The fulfillment order remains in a processing state until all items are either 
                    shipped by Amazon or cancelled by the seller

            FillAllAvailable - All fulfillable items in the fulfillment order are shipped. 
                All unfulfillable items in the order are cancelled by Amazon.

            Default: FillOrKill
        """

    amz_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, string='Marketplace', help=" Amazon Marketplace")
    amz_seller_id = fields.Many2one(AMZ_SELLER_EPT, string='Amazon Seller', help="Unique Amazon Seller name")
    amz_fulfillment_by = fields.Selection([('FBA', 'Amazon Fulfillment Network'),
                                           ('FBM', 'Merchant Fullfillment Network')], string="Fulfillment By",
                                          help="Fulfillment Center by Amazon or Merchant")
    amz_order_reference = fields.Char('Amazon Order Reference', help="Amazon Order Reference")
    is_business_order = fields.Boolean('Business Order', default=False, help="True, if Business order")
    is_prime_order = fields.Boolean('Amazon Prime Order', default=False, help="True, if Prime order")
    amz_shipment_service_level_category = fields.Selection(
        [('Expedited', 'Expedited'), ('NextDay', 'NextDay'), ('SecondDay', 'SecondDay'),
         ('Standard', 'Standard'), ('FreeEconomy', 'FreeEconomy'), ('Priority', 'Priority'),
         ('ScheduledDelivery', 'ScheduledDelivery'), ('SameDay', 'SameDay'), ('Scheduled', 'Scheduled')],
        string="FBA Shipping Speed", default='Standard', help="ScheduledDelivery used only for japan")
    is_fba_pending_order = fields.Boolean("Is FBA Pending Order?", default=False,
                                          help="To Identify order is pending order or not")
    amz_shipment_report_id = fields.Many2one(AMZ_SHIPPING_REPORT_REQUEST_HISTORY, string="Amazon Shipping Report",
                                             help="To identify Shipment report")
    amz_sales_order_report_id = fields.Many2one('fbm.sale.order.report.ept', string="Sales Order Report Id")
    updated_in_amazon = fields.Boolean(compute="_compute_amazon_status",
                                       search='_search_order_ids_amazon', store=False)
    amz_is_outbound_order = fields.Boolean("Out Bound Order", default=False,
                                           help="If true Outbound order is created")
    order_has_fba_warehouse = fields.Boolean("Order Has FBA Warehouse",
                                             compute="_compute_is_fba_warehouse", store=False,
                                             help="True, If warehouse is set as FBA Warehouse")
    amz_fulfillment_action = fields.Selection([('Ship', 'Ship'), ('Hold', 'Hold')],
                                              string="Fulfillment Action", default="Hold",
                                              help=help_fulfillment_action)
    amz_fulfillment_policy = fields.Selection([('FillOrKill', 'FillOrKill'), ('FillAll', 'FillAll'),
                                               ('FillAllAvailable', 'FillAllAvailable')],
                                              string="Fulfillment Policy", default="FillOrKill",
                                              required=False, help=help_fulfillment_policy)
    amz_fulfullment_order_status = fields.Selection(
        [('RECEIVED', 'RECEIVED'), ('INVALID', 'INVALID'), ('PLANNING', 'PLANNING'),
         ('PROCESSING', 'PROCESSING'), ('CANCELLED', 'CANCELLED'), ('COMPLETE', 'COMPLETE'),
         ('COMPLETE_PARTIALLED', 'COMPLETE_PARTIALLED'), ('UNFULFILLABLE', 'UNFULFILLABLE')],
        string="Fulfillment Order Status", help=full_fill_ment_order_help)
    exported_in_amazon = fields.Boolean(default=False)
    amz_displayable_date_time = fields.Date("Displayable Order Date Time", required=False,
                                            help="Display Date in package")
    notify_by_email = fields.Boolean(default=False, help="If true then system will notify by email to followers")
    amz_delivery_start_time = fields.Datetime("Delivery Start Time", help="Delivery Estimated Start Time")
    amz_delivery_end_time = fields.Datetime("Delivery End Time", help="Delivery Estimated End Time")
    is_amazon_canceled = fields.Boolean("Canceled In amazon ?", default=False)
    amz_fulfillment_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, string="Fulfillment Marketplace")
    amz_instance_country_code = fields.Char(related="amz_instance_id.country_id.code", readonly=True,
                                            string="Marketplace Country",
                                            help="Used for display line_tax_amount in order line for US country")
    ship_city = fields.Char(string="Ship City")
    ship_postal_code = fields.Char(string="Ship PostCode")
    ship_state_id = fields.Many2one("res.country.state", string='Ship State')
    ship_country_id = fields.Many2one('res.country', string='Ship Country')
    bill_city = fields.Char(string="Bill City")
    bill_postal_code = fields.Char(string="Bill PostCode")
    bill_state_id = fields.Many2one("res.country.state", string='Bill State')
    bill_country_id = fields.Many2one('res.country', string='Bill Country')
    buyer_requested_cancellation = fields.Boolean(help='Is buyer requested to cancel this order', default=False)
    buyer_cancellation_reason = fields.Char(help='Cancellation reason provided by the buyer')

    _sql_constraints = [('amazon_sale_order_unique_constraint',
                         'unique(amz_instance_id, amz_order_reference, warehouse_id, '
                         'amz_fulfillment_by)',
                         "Amazon sale order must be unique.")]

    @api.constrains('amz_fulfillment_action')
    def check_fulfillment_action(self):
        """
        Added constraint for which sale order is already exported to amazon but action not updated.
        """
        for record in self:
            if record.sudo().exported_in_amazon and record.sudo().amz_fulfillment_action == 'Hold':
                raise UserError(_(
                    "You can change action Ship to Hold Which are already exported in amazon"))

    def _prepare_procurement_group_vals(self):

        """
        This Function used to add seller_id to picking for the FBM Orders.
        @author: Keyur Kanani
        :return:
        """
        res = super(SaleOrder, self)._prepare_procurement_group_vals()
        if self.amz_seller_id:
            res.update({'seller_id': self.amz_seller_id.id})
        return res

    def _create_invoices(self, grouped=False, final=False, date=None):
        """
        Create Multiple Invoices as per the shipments has been created for FBA Orders.
        :return : account.move()
        """
        res = self.env['account.move']
        amazon_orders = self.filtered(lambda order: order.amz_instance_id)
        for amz_order in amazon_orders:
            if getattr(amz_order.partner_id, 'is_amz_customer', False) and amz_order.amz_fulfillment_by == 'FBA' and\
                    not amz_order._context.get('shipment_item_ids', {}):
                shipment_ids = amz_order.prepare_amazon_shipment_dict_ept()
                for shipment, shipment_item in list(shipment_ids.items()):
                    to_invoice = amz_order.order_line.filtered(lambda l: l.qty_to_invoice != 0.0)
                    if to_invoice:
                        res += super(SaleOrder, amz_order.with_context(shipment_item_ids=shipment_item))._create_invoices(
                            grouped, final, date)
            else:
                res += super(SaleOrder, amz_order)._create_invoices(grouped, final, date)
        other_orders = self - amazon_orders
        if other_orders:
            res += super(SaleOrder, other_orders)._create_invoices(grouped, final, date)
        return res

    def prepare_amazon_shipment_dict_ept(self):
        """
        Define this method for prepare Amazon Shipments dict for create invoices as
        per shipment ids.
        :return: dict {}
        """
        # For Update Invoices in Amazon, we have to create Invoices as per Shipment id
        shipment_ids = {}
        for move in self.order_line.move_ids:
            if move.amazon_shipment_id in shipment_ids:
                shipment_ids.get(move.amazon_shipment_id).append(move.amazon_shipment_item_id)
            else:
                shipment_ids.update({move.amazon_shipment_id: [move.amazon_shipment_item_id]})
        return shipment_ids

    def _prepare_invoice(self):
        """
        Add amazon_instance_id and fulfillment_by When invoice create
        @author: Keyur Kanani
        :return:
        """
        res = super(SaleOrder, self)._prepare_invoice()
        if self.amz_instance_id:
            res.update(({'amazon_instance_id': self.amz_instance_id and
                                               self.amz_instance_id.id or False,
                         'amz_fulfillment_by': self.amz_fulfillment_by or False,
                         'amz_sale_order_id': self.id or False
                         }))
        return res

    def prepare_amazon_order_items_data(self, data):
        """
        This method wil prepare the order item data based on the order lines and
        if notify by email is True then will prepare an NotificationEmailList.
        """
        item_list = []
        for line in self.order_line:
            if line.product_id and line.product_id.type == 'service' or line.warehouse_id_ept.id not in \
                    [False, self.warehouse_id.id]:
                continue
            item_list.append({'sellerSku': str(line.amazon_product_id.seller_sku),
                              'sellerFulfillmentOrderItemId': str(line.amazon_product_id.seller_sku),
                              'quantity': str(int(line.product_uom_qty)),
                              'perUnitDeclaredValue': {'currencyCode': str(line.order_id.currency_id.name),
                                                       'value': str(line.price_unit)}
                              })
        if item_list:
            data.update({'items': item_list})
        email_list = []
        if self.notify_by_email:
            for follower in self.message_follower_ids:
                if follower.partner_id.email:
                    email_list.append(str(follower.partner_id.email))
        if email_list:
            data.update({'notificationEmails': email_list})
        return data

    def get_data(self):
        """
        This method will prepare dict for outbound orders.
        """
        data = {'marketplaceId': self.amz_instance_id.market_place_id, 'sellerFulfillmentOrderId': self.name,
                'displayableOrderId': self.amz_order_reference,
                'shippingSpeedCategory': self.amz_shipment_service_level_category}
        if self.amz_delivery_start_time and self.amz_delivery_end_time:
            start_date = self.amz_delivery_start_time.strftime(DATE_YMDTHMS)
            start_date = time.strftime(DATE_YMDTHMS, time.gmtime(
                time.mktime(time.strptime(start_date, DATE_YMDTHMS))))
            start_date = str(start_date) + 'Z'

            end_date = self.amz_delivery_end_time.strftime(DATE_YMDTHMS)
            end_date = time.strftime(DATE_YMDTHMS, time.gmtime(
                time.mktime(time.strptime(end_date, DATE_YMDTHMS))))
            end_date = str(end_date) + 'Z'
            data.update({'deliveryWindow': {'startDate': start_date,
                                            'endDate': end_date}})

        data.update({'destinationAddress': {'name': str(self.partner_shipping_id.name),
                                            'addressLine1': str(self.partner_shipping_id.street or ''),
                                            'addressLine2': str(self.partner_shipping_id.street2 or ''),
                                            'countryCode': str(self.partner_shipping_id.country_id.code or ''),
                                            'phone': str(self.partner_shipping_id.mobile or
                                                         self.partner_shipping_id.phone or ''),
                                            'city': str(self.partner_shipping_id.city or ''),
                                            'stateOrRegion': str(self.partner_shipping_id.state_id and
                                                                 self.partner_shipping_id.state_id.code or ''),
                                            'postalCode': str(self.partner_shipping_id.zip or '')}})

        displayable_date = self.amz_displayable_date_time.strftime("%Y-%m-%dT%H:%M:%S")
        displayable_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
            time.mktime(time.strptime(displayable_date, "%Y-%m-%dT%H:%M:%S"))))
        displayable_date = str(displayable_date) + 'Z'
        if self.note:
            data.update({'displayableOrderComment': str(self.note)})
        data.update({
            'displayableOrderDate': displayable_date,
            'fulfillmentAction': str(self.amz_fulfillment_action)})
        data = self.prepare_amazon_order_items_data(data)
        return data

    def import_fba_pending_sales_order(self, seller, marketplaceids, updated_after_date):
        """
        Create Object for the integrate with amazon
        Import FBA Pending Sales Order From Amazon
        :param seller: amazon.seller.ept()
        :param marketplaceids: list of Marketplaces
        :return:
        """
        # If Last FBA Sync Time is define then system will take those orders which are created
        # after last import time Otherwise System will take last 30 days orders
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        if not marketplaceids:
            marketplaceids = tuple([x.market_place_id for x in seller.instance_ids])
        if not marketplaceids:
            raise UserError(_(AMAZON_INSTANCE_NOT_CONFIGURED_WARNING + " %s" % (seller.name)))

        if updated_after_date:
            updated_after = updated_after_date.strftime(DATE_YMDHMS)
            db_import_time = time.strptime(str(updated_after), DATE_YMDHMS)
            db_import_time = time.strftime(DATE_YMDTHMS, db_import_time)
            updated_after_date = time.strftime(DATE_YMDTHMS, time.gmtime(
                time.mktime(time.strptime(db_import_time, DATE_YMDTHMS))))
            updated_after_date = str(updated_after_date) + 'Z'
            seller.fba_pending_order_last_sync_on = updated_after
        elif seller.fba_pending_order_last_sync_on:
            earlier = seller.fba_pending_order_last_sync_on - timedelta(days=3)
            earlier_str = earlier.strftime(DATE_YMDTHMS)
            updated_after_date = earlier_str + 'Z'
            seller.fba_pending_order_last_sync_on = datetime.now().strftime(DATE_YMDHMS)
        else:
            earlier = datetime.now() - timedelta(days=30)
            updated_after_date = earlier.strftime(DATE_YMDTHMS) + 'Z'
            seller.fba_pending_order_last_sync_on = datetime.now().strftime(DATE_YMDHMS)
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'import_pending_orders_sp_api')
        kwargs.update({'updated_after': updated_after_date, 'marketplaceids': marketplaceids, })
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            if self._context.get('is_auto_process', False):
                log_line_obj.create_common_log_line_ept(message=response.get('error', {}),
                                                        model_name=SALE_ORDER,
                                                        module='amazon_ept', operation_type='import', res_id=self.id,
                                                        amz_seller_ept=seller and seller.id or False)
                return True
            raise UserError(_(response.get('error', {})))
        result = response.get('result', {})
        self.process_fba_pending_sale_order_response(seller, kwargs, result)
        return True

    def process_fba_pending_sale_order_response(self, seller, kwargs, result):
        """
        This method is used to process fba pending sale order response to create pending sale
        order.
        """
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        self.create_amazon_pending_sales_order(seller, [result])
        self._cr.commit()
        next_token = result.get('NextToken', '')
        if next_token:
            # We have create list of Dictwrapper now we create orders into system
            kwargs.update({'next_token': next_token, 'emipro_api': 'order_by_next_token_sp_api', })
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                if self._context.get('is_auto_process', False):
                    common_log_line_obj.create_common_log_line_ept(message=response.get('error', {}),
                                                                   model_name=SALE_ORDER, module='amazon_ept',
                                                                   operation_type='import', res_id=self.id,
                                                                   amz_seller_ept=seller and seller.id or False)
                    return True
                raise UserError(_(response.get('error', {})))
            order_by_next_token = response.get('result', {})
            for result in order_by_next_token:
                self.create_amazon_pending_sales_order(seller, [result])
                self._cr.commit()
        return True

    def check_amazon_fba_draft_orders(self, seller, marketplaceids, instance_ids):
        """
        This method will search the amazon FBA draft sale orders.
        """
        message = ''
        domain = [('state', '=', 'draft'), ('amz_fulfillment_by', '=', 'FBA')]
        if instance_ids:
            domain.append(('amz_instance_id', 'in', instance_ids))
        min_draft_order = self.search(domain, limit=1, order='date_order')
        max_draft_order = self.search(domain, limit=1, order='date_order desc')
        if not min_draft_order or not max_draft_order:
            message = "No draft order found in odoo"
        if not marketplaceids:
            marketplaceids = tuple([x.market_place_id for x in seller.instance_ids])
            if not marketplaceids:
                message = AMAZON_INSTANCE_NOT_CONFIGURED_WARNING + " %s" % (seller.name)
        return message, min_draft_order, max_draft_order

    def cancel_amazon_fba_pending_sale_orders(self, seller, marketplaceids, instance_ids):
        """
        Check Status of draft order in Amazon and if it is cancel, then cancel that order in Odoo
        Create Object for the integrate with amazon
        :param seller: amazon.seller.ept()
        :param marketplaceids: list[]
        :param instance_ids: list[]
        :return:
        """
        auto_process = self._context.get('auto_process', False)
        message, min_draft_order, max_draft_order = self.check_amazon_fba_draft_orders(
            seller, marketplaceids, instance_ids)
        if message:
            if not auto_process:
                raise UserError(_("No draft order found in odoo"))
            return []
        min_date = datetime.strptime(str(min_draft_order.date_order), DATE_YMDHMS)
        max_date = datetime.strptime(str(max_draft_order.date_order), DATE_YMDHMS)
        date_ranges = {}
        date_from = min_date
        while date_from < max_date or date_from < datetime.now():
            date_to = date_from + timedelta(days=30)
            if date_to > max_date:
                date_to = max_date
            if date_to > datetime.now():
                date_to = datetime.now()
            date_ranges.update({date_from: date_to})
            date_from = date_from + timedelta(days=31)
        for from_date, to_date in list(date_ranges.items()):
            min_date_str = from_date.strftime(DATE_YMDTHMS)
            created_after = min_date_str + 'Z'
            result = self.check_amazon_fba_and_fbm_cancel_order(seller, marketplaceids, created_after, 'AFN')
            self.with_context({'fulfillment_by': 'FBA'}).cancel_amazon_draft_sales_order(seller, [result])
            self._cr.commit()
        return True

    def cancel_amazon_fbm_pending_sale_orders(self, seller, marketplaceids):
        """
        Check Status of draft order in Amazon and if it is cancel, then cancel that order in Odoo
        Create Object for the integrate with amazon
        :param seller: amazon.seller.ept()
        :return:
        """
        auto_process = self._context.get('is_auto_process', False)
        if seller.cancel_fbm_order_last_sync_on:
            updated_after_date = (seller.cancel_fbm_order_last_sync_on - timedelta(days=3)).replace(microsecond=0)
        else:
            today = datetime.now()
            updated_after_date = (today - timedelta(days=3)).replace(microsecond=0)
        if not marketplaceids:
            marketplaceids = tuple([x.market_place_id for x in seller.instance_ids])
            if not marketplaceids:
                if not auto_process:
                    raise UserError(_(AMAZON_INSTANCE_NOT_CONFIGURED_WARNING + " %s" % (seller.name)))
                return []
        if updated_after_date:
            db_import_time = time.strptime(str(updated_after_date), DATE_YMDHMS)
            db_import_time = time.strftime(DATE_YMDTHMS, db_import_time)
            start_date = time.strftime(DATE_YMDTHMS, time.gmtime(
                time.mktime(time.strptime(db_import_time, DATE_YMDTHMS))))
            updated_after_date = str(start_date) + 'Z'
        result = self.check_amazon_fba_and_fbm_cancel_order(seller, marketplaceids, updated_after_date, 'MFN')
        self.with_context({'fulfillment_by': 'FBM'}).cancel_amazon_draft_sales_order(seller, [result])
        self._cr.commit()
        return True

    def check_amazon_fba_and_fbm_cancel_order(self, seller, marketplaceids, updated_after,
                                              fulfillment_channels):
        """
        This method will request for check cancel order in amazon and return the response
        :param seller : seller record
        :param marketplaces id's : marketplace ids
        :param updated_after : date
        :param fulfillment_channels : amazon channel
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'check_cancel_order_in_sp_api')
        kwargs.update({'marketplaceids': marketplaceids, 'updated_after': updated_after,
                       'fulfillment_channels': fulfillment_channels})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            if self._context.get('is_auto_process', False):
                log_line_obj.create_common_log_line_ept(message=response.get('error', {}),
                                                        model_name=SALE_ORDER,
                                                        module='amazon_ept', operation_type='import',
                                                        res_id=self.id, amz_seller_ept=seller and seller.id or False)
                return {}
            raise UserError(_(response.get('error', {})))
        list_of_wrapper = response.get('result', {})
        return list_of_wrapper

    def check_and_cancel_amazon_orders(self, seller, fulfillment_by, orders):
        """
        This method will check and cancel amazon orders
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        marketplace_instance_dict = {}
        for order in orders:
            order_status = order.get('OrderStatus', '')
            if order_status != 'Canceled':
                continue
            amazon_order_ref = order.get('AmazonOrderId', '')
            if not amazon_order_ref:
                continue
            marketplace_id = order.get('MarketplaceId', '')
            instance = marketplace_instance_dict.get(marketplace_id)
            if not instance:
                instance = seller.instance_ids.filtered(
                    lambda x, marketplace_id=marketplace_id: x.market_place_id == marketplace_id)
                marketplace_instance_dict.update({marketplace_id: instance})
            existing_order = self.search([('amz_order_reference', '=', amazon_order_ref),
                                          ('amz_instance_id', '=', instance.id),
                                          ('state', '!=', 'cancel'),
                                          ('amz_fulfillment_by', '=', fulfillment_by)])
            if not existing_order:
                message = 'Amazon order[%s] not Found in Odoo.' % (amazon_order_ref)
                log_line_obj.create_common_log_line_ept(message=message, model_name=SALE_ORDER,
                                                        order_ref=amazon_order_ref, fulfillment_by=fulfillment_by,
                                                        module='amazon_ept', operation_type='import', res_id=self.id,
                                                        amz_seller_ept=seller and seller.id or False,
                                                        amz_instance_ept=instance and instance.id or False)
                continue
            if existing_order and existing_order.picking_ids.filtered(lambda pick: pick.state == 'done'):
                message = f"The sale order ({existing_order.name}) has one or more Delivery orders that have been " \
                          f"validated. Only orders whose delivery orders are not validated will be cancelled."
                log_line_obj.create_common_log_line_ept(message=message, model_name=SALE_ORDER,
                                                        order_ref=existing_order.name, fulfillment_by=fulfillment_by,
                                                        module='amazon_ept', operation_type='import', res_id=self.id,
                                                        amz_seller_ept=seller and seller.id or False,
                                                        amz_instance_ept=instance and instance.id or False)
                continue
            existing_order.picking_ids.filtered(lambda pick: pick.state != 'cancel').action_cancel()
            super(SaleOrder, existing_order.with_context(disable_cancel_warning=True)).action_cancel()
        return True

    def cancel_amazon_draft_sales_order(self, seller, list_of_wrapper):
        """
        This function Cancels Amazon Pending Orders in ERP
        :param seller: amazon.seller.ept()
        :param list_of_wrapper: {}
        :return True: Boolean
        updated to process to cancel the amazon FBA and FBM orders with the single method
        removed separate method to cancel the FBM orders and pass the dynamic fulfillment_by.
        """
        ctx = self._context.copy() or {}
        fulfillment_by = ctx.get('fulfillment_by', '')
        for wrapper_obj in list_of_wrapper:
            orders = []
            if not isinstance(wrapper_obj.get('Orders', []), list):
                orders.append(wrapper_obj.get('Orders', {}))
            else:
                orders = wrapper_obj.get('Orders', {})
            self.check_and_cancel_amazon_orders(seller, fulfillment_by, orders)
        return True

    @staticmethod
    def prepare_amazon_prod_vals(instance, order_line, sku, odoo_product, fulfillment):
        """
        Prepare Amazon Product Values
        :param instance: amazon.instance.ept()
        :param order_line: {}
        :param sku: string
        :param odoo_product: product.product()
        :return: {}
        """
        prod_vals = {}
        if not odoo_product:
            prod_vals = {'name': order_line.get('Title', ''), 'default_code': sku}

        prod_vals.update({
            'name': order_line.get('Title', ''),
            'instance_id': instance.id,
            'product_asin': order_line.get('ASIN', ''),
            'seller_sku': sku,
            'product_id': odoo_product and odoo_product.id or False,
            'exported_to_amazon': True, 'fulfillment_by': fulfillment
        })
        return prod_vals

    @staticmethod
    def fba_pending_order_partner_dict(instance):
        """
        Create Dictionary of pending order partner
        default_fba_partner_id fetched according to seller wise
        :param instance:
        :return:
        """
        return {
            'invoice_partner': instance.seller_id.def_fba_partner_id and
                               instance.seller_id.def_fba_partner_id.id,
            'shipping_partner': instance.seller_id.def_fba_partner_id and
                                instance.seller_id.def_fba_partner_id.id,
            'pricelist_id': instance.pricelist_id and instance.pricelist_id.id}

    def create_amazon_pending_sales_order(self, seller, list_of_wrapper):
        """
        This Function Create Amazon Pending Orders with Draft state into ERP System
        :param seller: amazon.seller.ept()
        :param list_of_wrapper:
        :return:
        """
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        marketplace_instance_dict = {}
        amazon_order_list = []
        product_details = {}
        for wrapper_obj in list_of_wrapper:
            orders = []
            if not isinstance(wrapper_obj.get('Orders', {}), list):
                orders.append(wrapper_obj.get('Orders', {}))
            else:
                orders = wrapper_obj.get('Orders', {})
            for order in orders:
                amazon_order_ref = order.get('AmazonOrderId', False)
                message, instance = self.check_amazon_order_vals_ept(seller, order,
                                                                     marketplace_instance_dict)
                if message:
                    common_log_line_obj.create_common_log_line_ept(message=message, model_name=SALE_ORDER,
                                                                   fulfillment_by='FBA', order_ref=amazon_order_ref,
                                                                   module='amazon_ept', operation_type='import',
                                                                   res_id=self.id,
                                                                   amz_seller_ept=seller and seller.id or False)
                    continue
                existing_order = self.search([('amz_order_reference', '=', amazon_order_ref),
                                              ('amz_instance_id', '=', instance.id),
                                              ('amz_fulfillment_by', '=', 'FBA')])
                if existing_order:
                    message = 'Order %s Already Exist in Odoo.' % (existing_order.name)
                    common_log_line_obj.create_common_log_line_ept(message=message, model_name=SALE_ORDER,
                                                                   fulfillment_by='FBA', order_ref=amazon_order_ref,
                                                                   module='amazon_ept', operation_type='import',
                                                                   res_id=self.id,
                                                                   amz_seller_ept=seller and seller.id or False,
                                                                   amz_instance_ept=instance and instance.id or False)
                    continue
                self.request_fba_pending_sale_order_and_process_ept(seller, instance, order, product_details,
                                                                    amazon_order_list)
        seller.fba_pending_order_last_sync_on = datetime.now()
        return amazon_order_list

    @staticmethod
    def check_amazon_order_vals_ept(seller, order, marketplace_instance_dict):
        """
        This method will check  required amazon vals.
        """
        message = False
        amazon_order_ref = order.get('AmazonOrderId', False)
        if not amazon_order_ref:
            message = 'Amazon Order Reference not found.'
            return message, False
        marketplace_id = order.get('MarketplaceId', False)
        instance = marketplace_instance_dict.get(marketplace_id)
        if not instance:
            instance = seller.instance_ids.filtered(lambda x: x.market_place_id == marketplace_id)
            marketplace_instance_dict.update({marketplace_id: instance})
            if not instance:
                message = 'Skipped due to Amazon Instance Not found.'
                return message, instance
        return message, instance

    def request_fba_pending_sale_order_and_process_ept(self, seller, instance, order, product_details,
                                                       amazon_order_list):
        """
        This method will request for FBA pending sale order process the response to create
        sale order and sale order line.
        :param seller: amazon.seller.ept() object
        :param instance: amazon.instance.ept() object
        :param order: fba order response from api
        :param product_details: dict {}
        :param amazon_order_list: list amazon orders
        :return: boolean (TRUE/FALSE)
        """
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        sale_order_line_obj = self.env['sale.order.line']
        # default_fba_partner_id fetched according to seller wise
        amazon_order_ref = order.get('AmazonOrderId', False)
        partner_dict = self.fba_pending_order_partner_dict(instance)
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'get_amazon_order_sp_api')
        kwargs.update({'amazon_order_ref': amazon_order_ref})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            if self._context.get('is_auto_process', False):
                common_log_line_obj.create_common_log_line_ept(message=response.get('error', {}), model_name=SALE_ORDER,
                                                               module='amazon_ept', operation_type='import',
                                                               res_id=self.id,
                                                               amz_seller_ept=seller and seller.id or False,
                                                               amz_instance_ept=instance and instance.id or False)
                return True
            raise UserError(_(response.get('error', {})))

        list_of_order_lines_wrapper = response.get('result', {})
        amazon_order = False
        skip_order = False
        order_lines = []
        for order_line_wrapper_obj in list_of_order_lines_wrapper:
            if not isinstance(order_line_wrapper_obj.get('OrderItems', []), list):
                order_lines.append(order_line_wrapper_obj.get('OrderItems', {}))
            else:
                order_lines = order_line_wrapper_obj.get('OrderItems', [])

            for order_line in order_lines:
                skip_order, product_details = self.with_context(
                    {'is_fba_order': True}).create_or_find_amazon_product(
                    order_line, product_details, instance, amazon_order_ref, self)
                if skip_order:
                    break

        if not skip_order:
            if not amazon_order:
                order_vals = self.create_amazon_sales_order_vals(partner_dict, order, instance)
                if not order_vals.get('fiscal_position_id', False):
                    order_vals.pop('fiscal_position_id')
                amazon_order = self.with_context(is_b2b_amz_order=order_vals.get(
                    'is_business_order', False)).create(order_vals)
                amazon_order_list.append(amazon_order)

            for order_line in order_lines:
                line_data = self.prepare_fba_pending_order_line_ept(order_line)
                sale_order_line_obj.create_amazon_sale_order_line(amazon_order, line_data, product_details)
            self.env.cr.commit()
        return True

    @staticmethod
    def prepare_fba_pending_order_line_ept(order_line):
        """
        Prepare Sale Order lines vals for amazon orders
        :param row:
        :param instance:
        :param product_details:
        :return:
        """

        return {
            'sku': order_line.get('SellerSKU', ''),
            'name': order_line.get('Title', ''),
            'product_uom_qty': order_line.get('QuantityOrdered', 0.0),
            'amazon_order_qty': order_line.get('QuantityOrdered', 0.0),
            'line_tax_amount': float(order_line.get('ItemTax', {}).get('Amount', 0.0)),
            'amazon_order_item_id': order_line.get('OrderItemId', ''),
            'item_price': float(order_line.get('ItemPrice', {}).get('Amount', 0.0)),
            'tax_amount': float(order_line.get('ItemTax', {}).get('Amount', 0.0)),
            'shipping_charge': float(order_line.get('ShippingPrice', {}).get('Amount', 0.0)),
            'shipping_tax': float(order_line.get('ShippingTax', {}).get('Amount', 0.0)),
            'gift_wrapper_charge': float(order_line.get('GiftWrapPrice', {}).get('Amount', 0.0)),
            'gift_wrapper_tax': float(order_line.get('GiftWrapTax', {}).get('Amount', 0.0)),
            'shipping_discount': float(order_line.get('ShippingDiscount', {}).get('Amount', 0.0)),
            'promotion_discount': float(order_line.get('PromotionDiscount', {}).get('Amount', 0.0)),
        }

    def prepare_amazon_sale_order_vals(self, instance, partner_dict, order):
        """
        Prepares Sale Order Values for import in ERP
        :param instance: amazon.instance.ept()
        :param partner_dict: {}
        :param order: {}
        :return: {}
        """
        if order.get('PurchaseDate', False):
            date_order = parser.parse(order.get('PurchaseDate', False)).astimezone(utc).strftime(DATE_YMDHMS)
        else:
            date_order = time.strftime(DATE_YMDHMS)

        shipping_partner = self.env['res.partner'].browse(partner_dict.get('shipping_partner', False))
        billing_partner = self.env['res.partner'].browse(partner_dict.get('invoice_partner', False))
        return {'company_id': instance.company_id.id,
                'partner_id': partner_dict.get('invoice_partner', False),
                'partner_invoice_id': partner_dict.get('invoice_partner', False),
                'partner_shipping_id': partner_dict.get('shipping_partner', False),
                'warehouse_id': instance.warehouse_id.id,
                'date_order': date_order or False,
                'pricelist_id': instance.pricelist_id.id or False,
                'payment_term_id': instance.seller_id.payment_term_id.id,
                'fiscal_position_id': instance.fiscal_position_id and
                                      instance.fiscal_position_id.id or False,
                'team_id': instance.team_id and instance.team_id.id or False,
                'client_order_ref': order.get('AmazonOrderId', False),
                'carrier_id': False,
                'state': 'draft',
                'ship_city': shipping_partner.city or '',
                'ship_postal_code': shipping_partner.zip or '',
                'ship_state_id': shipping_partner.state_id.id if shipping_partner.state_id else False,
                'ship_country_id': shipping_partner.country_id.id if shipping_partner.country_id else False,
                'bill_city': billing_partner.city or '',
                'bill_postal_code': billing_partner.zip or '',
                'bill_state_id': billing_partner.state_id.id if billing_partner.state_id else False,
                'bill_country_id': billing_partner.country_id.id if billing_partner.country_id else False
                }

    @api.model
    def check_already_status_updated_in_amazon(self, seller, marketplaceids, instances, next_token={}):
        """Create Object for the integrate with amazon"""
        # warehouse_ids = list(set(map(lambda x: x.warehouse_id.id, instances))) no need to check warehouse
        sales_orders = self.amz_not_updated_in_amazon_fbm_orders(instances)
        if not sales_orders:
            return [], {}
        updated_after_date = sales_orders[0].date_order - timedelta(+1)
        marketplaceids = tuple(marketplaceids)
        if updated_after_date:
            db_import_time = time.strptime(str(updated_after_date), DATE_YMDHMS)
            db_import_time = time.strftime(DATE_YMDTHMS, db_import_time)
            start_date = time.strftime(DATE_YMDTHMS, time.gmtime(
                time.mktime(time.strptime(db_import_time, DATE_YMDTHMS))))
            updated_after_date = str(start_date) + 'Z'
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'check_status_updated_in_amazon_sp_api')
        kwargs.update({'marketplaceids': marketplaceids, 'updated_after': updated_after_date, })
        if next_token:
            kwargs.update({'next_token': next_token})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            raise UserError(_(response.get('error', {})))
        list_of_wrapper = response.get('result', [])
        unshipped_sales_orders = self.prepare_amazon_fbm_unshipped_orders(list_of_wrapper, sales_orders)
        next_token_wrapper = list_of_wrapper[-1].get('NextToken', '') if \
            list_of_wrapper and isinstance(list_of_wrapper, list) else {}
        return unshipped_sales_orders, next_token_wrapper

    def amz_not_updated_in_amazon_fbm_orders(self, instances):
        """
        Define this method for get not updated in Amazon FBM unshipped orders.
        :param: instances: amazon.instance.ept()
        :return: sale.order()
        """
        query = """select sale_order.id from stock_picking inner join sale_order on 
        sale_order.procurement_group_id=stock_picking.group_id 
        inner join stock_location on stock_location.id=stock_picking.location_dest_id 
        and stock_location.usage='customer' where stock_picking.updated_in_amazon=False 
        and stock_picking.state='done' and sale_order.amz_order_reference is not NULL 
        and sale_order.amz_instance_id in %s and sale_order.amz_fulfillment_by = 'FBM'"""
        self._cr.execute(query, (tuple(instances.ids),))
        result = self._cr.dictfetchall()
        sales_orders = self.browse([order_id.get('id') for order_id in result])
        return sales_orders

    @staticmethod
    def prepare_amazon_fbm_unshipped_orders(list_of_wrapper, sales_orders):
        """
        This method will prepare the list of amazon FBM unshipped orders.
        """
        list_of_amazon_order_ref = []
        for wrapper_obj in list_of_wrapper:
            orders = []
            if not isinstance(wrapper_obj.get('Orders', []), list):
                orders.append(wrapper_obj.get('Orders', {}))
            else:
                orders = wrapper_obj.get('Orders', [])
            for order in orders:
                amazon_order_ref = order.get('AmazonOrderId', False)
                list_of_amazon_order_ref.append(amazon_order_ref)
        unshipped_sales_orders = []
        for order in sales_orders:
            if order.amz_order_reference in list_of_amazon_order_ref:
                unshipped_sales_orders.append(order)
        return unshipped_sales_orders

    def cancel_order_in_amazon(self):
        """
        This method return the cancel order in amazon wizard.
        :return: Cancel Order Wizard
        """
        view = self.env.ref('amazon_ept.view_amazon_cancel_order_wizard')
        context = dict(self._context)
        context.update({'order_id': self.id})
        return {
            'name': _('Cancel Order In Amazon'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'amazon.cancel.order.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context
        }

    @staticmethod
    def get_header(instance):
        """
        This method return the xml data header.
        :param instance: instance object
        :return:xml header
        """
        return """<?xml version="1.0"?>
            <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
            xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
            <Header>
                <DocumentVersion>1.01</DocumentVersion>
                <MerchantIdentifier>%s</MerchantIdentifier>
            </Header>
            <MessageType>OrderAcknowledgement</MessageType>
         """ % (instance.merchant_id)

    def get_message(self, lines, instance, order):
        """
        This method prepare the xml message.
        :param lines:sale order line object
        :param instance: instance object
        :param order: order object
        :return:message string
        """
        message_id = 1
        message_str = ''
        message = """
            <Message>
            <MessageID>%s</MessageID>
            <OrderAcknowledgement>
                 <AmazonOrderID>%s</AmazonOrderID>
                 <StatusCode>Failure</StatusCode>  
        """ % (message_id, order.amz_order_reference)
        for line in lines:
            message_order_line = """
                <Item> 
                <AmazonOrderItemCode>%s</AmazonOrderItemCode>
                <CancelReason>%s</CancelReason>
                <Quantity>%d</Quantity>
                </Item> 
            """ % (line.sale_line_id.amazon_order_item_id, line.message, int(line.ordered_qty))
            message = "%s %s" % (message, message_order_line)
            line.sale_line_id.write({'amz_return_reason': line.message})
        message = "%s </OrderAcknowledgement></Message>" % (message)

        message_str = "%s %s" % (message, message_str)
        header = self.get_header(instance)
        message_str = "%s %s </AmazonEnvelope>" % (header, message_str)
        return message_str

    def send_cancel_request_to_amazon(self, lines, instance, order):
        """
        This method will send cancel request to amazon.
        """
        data = self.get_message(lines, instance, order)
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                  'app_name': 'amazon_ept_spapi',
                  'account_token': account.account_token,
                  'marketplaceids': [instance.market_place_id],
                  'emipro_api': 'amazon_submit_feeds_sp_api',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                             instance.country_id.code,
                  'feed_type': 'POST_ORDER_ACKNOWLEDGEMENT_DATA',
                  'data': data, }
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            raise UserError(_(response.get('error', {})))

        results = response.get('results', {})
        if results.get('feed_result', {}).get('feedId', False):
            feed_document_id = results.get('result', {}).get('feedDocumentId', '')
            last_feed_submission_id = results.get('feed_result', {}).get('feedId', False)
            vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                    'feed_submit_date': time.strftime(DATE_YMDHMS),
                    'instance_id': instance.id, 'user_id': self._uid,
                    'feed_type': 'cancel_request', 'feed_document_id':feed_document_id,
                    'seller_id': instance.seller_id.id}
            self.env['feed.submission.history'].create(vals)
        return True

    def create_or_find_amazon_product(self, order_details, product_details, instance, amazon_order_ref, queue_order):
        """
        This method is find product in odoo based on sku. If not found than create new product.
        :param order_details : processed order line
        :param product_details : product name or description
        :param instance: instance object
        :param amazon_order_ref: amazon order reference
        :return: True/False boolean, product details
        """
        amz_product_obj = self.env[AMZ_PRODUCT_EPT]
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        fulfillment_by = 'FBM'
        skip_order = False
        ctx = self._context.copy() or {}
        seller_sku = order_details.get('SellerSKU', '')
        if not seller_sku:
            skip_order = True
            message = 'Order skipped due to seller sku is not available'
            common_log_line_obj.create_common_log_line_ept(message=message, model_name=SALE_ORDER,
                                                           default_code=seller_sku, order_ref=amazon_order_ref,
                                                           fulfillment_by=fulfillment_by, module='amazon_ept',
                                                           operation_type='import', res_id=self.id,
                                                           amz_instance_ept=instance and instance.id or False,
                                                           amz_seller_ept=instance.seller_id and
                                                                          instance.seller_id.id or False)
            return skip_order, product_details
        odoo_product = product_details.get((seller_sku, instance.id))
        if odoo_product:
            return skip_order, product_details
        if ctx.get('is_fba_order'):
            fulfillment_by = 'FBA'
        amazon_product = amz_product_obj.search_amazon_product(instance.id, seller_sku, fulfillment_by)
        if not amazon_product:
            odoo_product, skip_order = self.amz_search_or_create_odoo_product(
                instance, amazon_order_ref, fulfillment_by, order_details, skip_order, queue_order)
            if not skip_order:
                sku = seller_sku or (odoo_product and odoo_product[0].default_code) or False
                # Prepare Product Values
                prod_vals = self.prepare_amazon_prod_vals(instance, order_details, sku, odoo_product, fulfillment_by)
                # Create Amazon Product
                amz_product_obj.create(prod_vals)
            if odoo_product:
                product_details.update({(seller_sku, instance.id): odoo_product})
        else:
            product_details.update({(seller_sku, instance.id): amazon_product.product_id})
        return skip_order, product_details

    def amz_search_or_create_odoo_product(self, instance, amazon_order_ref, fulfillment_by,
                                          order_details, skip_order, queue_order):
        """
        Define method which help to search or create odoo product.
        :param : instance : amazon instance
        :param : amazon_order_ref : amazon order reference
        :param : fulfillment_by : amazon fulfillment center
        :param : order_details : order line
        :param : skip_order : True/False boolean
        :return : odoo product object, True/False Boolean
        """
        amz_product_obj = self.env[AMZ_PRODUCT_EPT]
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        product_obj = self.env['product.product']
        seller_sku = order_details.get('SellerSKU', '')
        odoo_product = amz_product_obj.search_product(seller_sku)
        if odoo_product:
            message = 'Odoo Product is already exists. System have ' \
                      'created new Amazon Product %s for %s instance' % (seller_sku, instance.name)
            common_log_line_obj.create_common_log_line_ept(message=message, model_name='product.product',
                                                           order_ref=amazon_order_ref, default_code=seller_sku,
                                                           fulfillment_by=fulfillment_by, module='amazon_ept',
                                                           operation_type='import', res_id=odoo_product.id,
                                                           amz_seller_ept=instance.seller_id and
                                                                          instance.seller_id.id or False,
                                                           amz_instance_ept=instance and instance.id or False)
        elif not instance.seller_id.create_new_product:
            skip_order = True
            model_name = 'amazon.product.ept'
            if queue_order and fulfillment_by == 'FBM':
                model_name = 'shipped.order.data.queue.ept'
            message = 'Product %s not found for %s instance' % (seller_sku, instance.name)
            common_log_line_obj.create_common_log_line_ept(message=message, model_name=model_name,
                                                           order_ref=amazon_order_ref, default_code=seller_sku,
                                                           fulfillment_by=fulfillment_by, module='amazon_ept',
                                                           operation_type='import', res_id=queue_order.id,
                                                           mismatch_details=True,
                                                           amz_seller_ept=instance.seller_id and
                                                                          instance.seller_id.id or False,
                                                           amz_instance_ept=instance and instance.id or False)
        else:
            # Create Odoo Product
            erp_prod_vals = {'name': order_details.get('Title', ''),
                             'default_code': seller_sku, 'type': 'product',
                             'purchase_ok': True, 'sale_ok': True, }
            odoo_product = product_obj.create(erp_prod_vals)
            message = 'System have created new Odoo Product %s for %s instance' % (seller_sku, instance.name)
            common_log_line_obj.create_common_log_line_ept(message=message, model_name='product.product',
                                                           order_ref=amazon_order_ref, default_code=seller_sku,
                                                           fulfillment_by=fulfillment_by, module='amazon_ept',
                                                           operation_type='import', res_id=odoo_product.id,
                                                           amz_seller_ept=instance.seller_id and
                                                                          instance.seller_id.id or False,
                                                           amz_instance_ept=instance and instance.id or False)
        return odoo_product, skip_order

    @staticmethod
    def prepare_amazon_customer_vals(row):
        """
        This method prepare the customer vals
        :param row: row of data
        :return: customer vals
        """
        return {
            'BuyerEmail': row.get('BuyerInfo', {}).get('BuyerEmail', ''),
            'BuyerName': row.get('BuyerInfo', {}).get('BuyerName', ''),
            'ShipNumber': row.get('ShippingAddress', {}).get('Phone', '') if row.get( 'ShippingAddress', {}).get(
                'Phone') else None,
            'AddressLine1': row.get('ShippingAddress', {}).get('AddressLine1', '') if row.get(
                'ShippingAddress', {}).get('AddressLine1') else None,
            'AddressLine2': row.get('ShippingAddress', {}).get('AddressLine2', '') if row.get(
                'ShippingAddress', {}).get('AddressLine2') else None,
            'AddressLine3': row.get('ShippingAddress', {}).get('AddressLine3', '') if row.get(
                'ShippingAddress', {}).get('AddressLine3') else None,
            'City': row.get('ShippingAddress', {}).get('City', '') if row.get(
                'ShippingAddress', {}).get('City') else None,
            'ShipName': row.get('ShippingAddress', {}).get('Name', '') if row.get(
                'ShippingAddress', {}).get('Name') else None,
            'CountryCode': row.get('ShippingAddress', {}).get('CountryCode', '') if row.get(
                'ShippingAddress', {}).get('CountryCode') else '',
            'StateOrRegion': row.get('ShippingAddress', {}).get('StateOrRegion', '') if row.get(
                'ShippingAddress', {}).get('StateOrRegion') else None,
            'PostalCode': row.get('ShippingAddress').get('PostalCode', '') if row.get(
                'ShippingAddress', {}).get('PostalCode') else None,
            'AddressType': row.get('ShippingAddress').get('AddressType', '') if row.get(
                'ShippingAddress', {}).get('AddressType') else None,
            'AmazonOrderId': row.get('AmazonOrderId', '') if row.get(
                'AmazonOrderId') else None,
        }

    @staticmethod
    def prepare_updated_ordervals(instance, order_ref, order):
        """
        This method prepare the order vals.
        :param expected_delivery_date: Expected Delivery Date
        :param instance: instance object
        :param seller: seller object
        :param order_ref: order reference
        :return: Order Vals
        """
        is_business_order = True if str(order.get('IsBusinessOrder', '')).lower() in ['true', 't'] else False
        is_prime_order = True if str(order.get('IsPrime', '')).lower() in ['true', 't'] else False

        ordervals = {
            'amz_instance_id': instance and instance.id or False,
            'amz_seller_id': instance.seller_id.id,
            'amz_fulfillment_by': 'FBM',
            'amz_order_reference': order_ref or order_ref[0] or False,
            'auto_workflow_process_id': instance.seller_id.fbm_auto_workflow_id.id,
            'is_business_order': is_business_order,
            'is_prime_order': is_prime_order,
            'amz_shipment_service_level_category': order.get('ShipmentServiceLevelCategory', False)
        }
        # analytic_account = instance.analytic_account_id.id if instance.analytic_account_id else False
        # if analytic_account:
        #     ordervals.update({'analytic_account_id': analytic_account})
        return ordervals

    def get_item_price(self, unit_price, tax):
        """
        This method addition the price and tax of product item cost.
        :param unit_price: item price
        :param tax: item tax
        :return: sum of price and tax.
        """
        if self.amz_seller_id.is_vcs_activated or \
                (self.amz_instance_id.amz_tax_id and not self.amz_instance_id.amz_tax_id.price_include):
            return unit_price
        return unit_price + tax

    def amz_create_order_lines(self, order, instance, order_details, dict_product_details):
        """
        This method prepare order lines.
        :param order: order Object
        :param instance: instance object
        :param order_details: sale order line from dictionary
        :param sale_order_line_obj: sale order line object
        :return: True
        """
        taxargs = {}
        product = dict_product_details.get((order_details.get('SellerSKU', ''), instance.id))
        quantity = float(order_details.get('QuantityOrdered', 1.0))
        unit_price = float(order_details.get('ItemPrice', {}).get('Amount', 0.0))
        item_tax = float(order_details.get('ItemTax', {}).get('Amount', 0.0))
        item_price = order.get_item_price(unit_price, item_tax)
        unit_price = item_price / quantity if quantity > 0.0 else item_price
        if order.amz_instance_id.is_use_percent_tax:
            unit_tax = item_tax / quantity if quantity > 0.0 else item_tax
            item_tax_percent = (unit_tax * 100) / unit_price if unit_price > 0 else 0.00
            amz_tax_id = order.amz_instance_id.amz_tax_id
            taxargs = {'line_tax_amount_percent': item_tax_percent, 'tax_id': [(6, 0, amz_tax_id.id and [
                amz_tax_id.id] or [])]}

        order_line_vals = {
            'order_id': order.id,
            'product_id': product.id,
            'company_id': instance.company_id.id or False,
            'price_unit': unit_price,
            'product_uom_qty': quantity,
            'product_uom': product and product.product_tmpl_id.uom_id.id,
            'discount': 0.0,
            'state': 'draft'
        }
        order_line_vals.update({
            'amazon_order_item_id': order_details.get('OrderItemId', ''),
            'line_tax_amount': item_tax,
            **taxargs
        })
        # Set Analytic Account in the Sale order line from Amazon Seller and Marketplace
        order_line_vals = order.order_line.set_analytic_account_ept(order, order_line_vals)
        order.order_line.create(order_line_vals)

        ## Shipping Charge Line
        self.get_fbm_shipped_order_line(instance, order, order_details)

        ## Shipping Charge Discount Line
        self.get_fbm_shipped_discount_order_line(instance, order, order_details)

        ## Promotion Discount Line
        self.get_fbm_promotion_discount_line(instance, order, order_details)
        return True

    def get_fbm_shipped_order_line(self, instance, order, order_details):
        """
        This method will prepare the values of shipped order lines and create that.
        """
        if order_details.get('ShippingPrice', False) and float(order_details.get(
                'ShippingPrice', {}).get('Amount', 0.0)) > 0 and instance.seller_id.shipment_charge_product_id:
            shipping_price = float(order_details.get('ShippingPrice', {}).get('Amount', 0.0))
            ship_tax = float(order_details.get('ShippingTax', {}).get('Amount', 0.0))
            ship_total, shipargs = self.get_amazon_fbm_shippig_vals_ept(instance, order, shipping_price, ship_tax)
            ship_line_vals = {
                'order_id': order.id,
                'product_id': instance.seller_id.shipment_charge_product_id.id,
                'company_id': instance.company_id.id or False,
                'product_uom_qty': '1.0',
                'price_unit': ship_total,
                'discount': False,
                'is_delivery': True,
                'state': 'draft'
            }
            ship_line_vals.update({
                'amazon_order_item_id': order_details.get('OrderItemId', '') + "_ship",
                'amz_shipping_charge_ept': ship_total,
                'amz_shipping_charge_tax': ship_tax,
                **shipargs
            })
            # Set Analytic Account in the Sale order line from Amazon Seller and Marketplace
            ship_line_vals = order.order_line.set_analytic_account_ept(order, ship_line_vals)
            order.order_line.create(ship_line_vals)
        return True

    @staticmethod
    def get_amazon_fbm_shippig_vals_ept(instance, order, shipping_price, ship_tax):
        """
        This method will get prepare the ship args and return that.
        """
        if order.amz_seller_id.is_vcs_activated or (instance.amz_tax_id and not instance.amz_tax_id.price_include):
            ship_total = shipping_price
        else:
            ship_total = shipping_price + ship_tax

        shipargs = {}
        if instance.is_use_percent_tax:
            item_tax_percent = (ship_tax * 100) / ship_total
            amz_tax_id = order.amz_instance_id.amz_tax_id
            shipargs = {'line_tax_amount_percent': item_tax_percent, 'tax_id': [(6, 0, [amz_tax_id.id])]}

        return ship_total, shipargs

    def get_fbm_shipped_discount_order_line(self, instance, order, order_details):
        """
        This method will prepare the FBM shipped discount order lines.
        """
        if order_details.get('ShippingDiscount', False) and float(order_details.get(
                'ShippingDiscount', {}).get('Amount', 0.0)) < 0 and instance.seller_id.ship_discount_product_id:
            shipping_price = float(order_details.get('ShippingDiscount', {}).get('Amount', 0.0))
            disc_tax = float(order_details.get('ShippingDiscountTax', {}).get('Amount', 0.0))
            discargs = {}
            discount_price = shipping_price - disc_tax
            if instance.is_use_percent_tax:
                discount_price = shipping_price
                gift_tax_percent = (disc_tax * 100) / discount_price
                amz_tax_id = order.amz_instance_id.amz_tax_id
                discargs = {'line_tax_amount_percent': abs(gift_tax_percent),
                            'tax_id': [(6, 0, [amz_tax_id.id])]}

            product_id = instance.seller_id.shipment_charge_product_id
            ship_disc_line_vals = self.create_fbm_shipped_chargable_order_line(order, instance, product_id, discount_price)
            ship_disc_line_vals.update({
                'amz_shipping_discount_ept': discount_price,
                'amazon_order_item_id': order_details.get('OrderItemId', '') + "_ship_discount",
                **discargs
            })
            order.order_line.create(ship_disc_line_vals)
        return True

    def get_fbm_promotion_discount_line(self, instance, order, order_details):
        """
        This method will create promotion discount lines.
        """
        if order_details.get('PromotionDiscount', False) and float(
                order_details.get('PromotionDiscount', {}).get('Amount', 0.0)) > 0 and instance.seller_id.promotion_discount_product_id:
            item_discount = float(order_details.get('PromotionDiscount', {}).get('Amount', 0.0)) * (-1)
            discount_tax = float(order_details.get('PromotionDiscountTax', {}).get('Amount', 0.0))
            discount = item_discount - discount_tax
            product_id = instance.seller_id.promotion_discount_product_id
            promo_disc_line_vals = self.create_fbm_shipped_chargable_order_line(order, instance, product_id, discount)
            promo_disc_line_vals.update({
                'amz_promotion_discount': discount,
                'amazon_order_item_id': order_details.get('OrderItemId', '') + '_promo_discount'
            })
            order.order_line.create(promo_disc_line_vals)
        return True

    @staticmethod
    def create_fbm_shipped_chargable_order_line(order, instance, product_id, price_unit):
        """
        This method will create shipped chargeable order lines
        """
        chargable_vals = {
            'order_id': order.id,
            'product_id': product_id.id,
            'company_id': instance.company_id.id or False,
            'product_uom_qty': '1.0',
            'price_unit': price_unit,
            'discount': 0.0,
            'state': 'draft'}
        # Set Analytic Account in the Sale order line from Amazon Seller and Marketplace
        chargable_vals = order.order_line.set_analytic_account_ept(order, chargable_vals)
        return chargable_vals

    def prepare_amazon_request_report_kwargs(self, seller_id, emipro_api):
        """
        Prepare General Amazon Order Request Dict.
        @author: Twinkal Chandarana
        :param emipro_api : Request to get response based on api
        :return: {}
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')

        return {'merchant_id': str(seller_id.merchant_id) if seller_id.merchant_id else False,
                'app_name': 'amazon_ept_spapi',
                'account_token': account.account_token,
                'emipro_api': emipro_api,
                'dbuuid': dbuuid,
                'amazon_marketplace_code': seller_id.country_id.amazon_marketplace_code or
                                           seller_id.country_id.code}

    def amz_create_sales_order(self, queue_order):
        """
        This method create the sale orders in odoo.
        :param queue_order: shipped.order.data.queue.ept()
        :param account: iap.account()
        :param dbuuid: ir.config_parameter()
        :return: True
        """
        log_line_ept = self.env[COMMON_LOG_LINES_EPT]
        marketplace_instance_dict = dict()
        request_counter = 0
        seller = queue_order.amz_seller_id
        queue_lines = queue_order.shipped_order_data_queue_lines.filtered(lambda x: x.state != 'done')

        for line in queue_lines:
            order = json.loads(line.order_data_id)
            amazon_order_ref = order.get('AmazonOrderId', False)
            message, instance = self.check_amazon_order_vals_ept(seller, order, marketplace_instance_dict)
            if message:
                log_line_ept.create_common_log_line_ept(message=message,
                                                        model_name='shipped.order.data.queue.ept',
                                                        fulfillment_by='FBM', module='amazon_ept',
                                                        operation_type='import', res_id=queue_order.id,
                                                        mismatch_details=True, amz_seller_ept=seller and seller.id
                                                                                               or False)
                line.state = 'failed'
                continue
            if not order.get('PurchaseDate', ''):
                message = 'Skipped due to Purchase Date Not found.'
                log_line_ept.create_common_log_line_ept(message=message,
                                                        model_name='shipped.order.data.queue.ept',
                                                        fulfillment_by='FBM', module='amazon_ept',
                                                        operation_type='import', res_id=queue_order.id,
                                                        mismatch_details=True,
                                                        amz_seller_ept=seller and seller.id or False,
                                                        amz_instance_ept=instance and instance.id or False)
                line.state = 'failed'
                continue
            if not order.get('BuyerInfo', {}).get('BuyerEmail', ''):
                message = "Skipped due to Buyer's Details Not found."
                log_line_ept.create_common_log_line_ept(message=message,
                                                        model_name='shipped.order.data.queue.ept',
                                                        fulfillment_by='FBM', module='amazon_ept',
                                                        operation_type='import', res_id=queue_order.id,
                                                        mismatch_details=True,
                                                        amz_seller_ept=seller and seller.id or False,
                                                        amz_instance_ept=instance and instance.id or False)
                line.state = 'failed'
                continue
            fulfillment_channel = order.get('FulfillmentChannel', '')
            if fulfillment_channel and fulfillment_channel == 'AFN' and \
                    not hasattr(instance, 'fba_warehouse_id'):
                message = 'Skipped because of Fulfillment Channel is AFN'
                log_line_ept.create_common_log_line_ept(message=message,
                                                        model_name='shipped.order.data.queue.ept',
                                                        fulfillment_by='FBM', module='amazon_ept',
                                                        operation_type='import', res_id=queue_order.id,
                                                        mismatch_details=True,
                                                        amz_seller_ept=seller and seller.id or False,
                                                        amz_instance_ept=instance and instance.id or False)
                line.state = 'failed'
                continue
            existing_order = self.search([('amz_order_reference', '=', amazon_order_ref),
                                          ('amz_instance_id', '=', instance.id),
                                          ('amz_fulfillment_by', '=', 'FBM')])

            # if boolean buyer_requested_cancellation is already True in the existing order
            if existing_order and existing_order.buyer_requested_cancellation:
                line.state = 'done'
                continue

            kwargs = self.prepare_amazon_request_report_kwargs(seller, 'get_amazon_order_sp_api')
            kwargs.update({'amazon_order_ref': amazon_order_ref})
            request_counter += 1
            if request_counter >= 25:
                request_counter = 0
                time.sleep(5)
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                log_line_ept.create_common_log_line_ept(message=response.get('error'),
                                                        model_name='shipped.order.data.queue.ept',
                                                        fulfillment_by='FBM', module='amazon_ept',
                                                        operation_type='import', res_id=queue_order.id,
                                                        mismatch_details=True,
                                                        amz_seller_ept=seller and seller.id or False,
                                                        amz_instance_ept=instance and instance.id or False)
                line.state = 'failed'
                continue

            list_of_shipped_order_lines = response.get('result', [])

            # if boolean buyer_requested_cancellation is not True in the existing order.
            # set the value of the boolean.
            if existing_order:
                self.process_existing_order_cancel_request(list_of_shipped_order_lines, existing_order, line)
                continue

            try:
                self.process_shipped_or_missing_unshipped_lines_ept(instance, order, line, list_of_shipped_order_lines,
                                                                    queue_order)
            except Exception as ex:
                log_line_ept.create_common_log_line_ept(message=str(ex),
                                                        model_name='shipped.order.data.queue.ept',
                                                        fulfillment_by='FBM', module='amazon_ept',
                                                        operation_type='import', res_id=queue_order.id,
                                                        mismatch_details=True,
                                                        amz_seller_ept=seller and seller.id or False,
                                                        amz_instance_ept=instance and instance.id or False)
                line.state = 'failed'
            self._cr.commit()
        return True

    @staticmethod
    def process_existing_order_cancel_request(list_of_shipped_order_lines, existing_order, line):
        """
        This method will set the boolean buyer_requested_cancellation if buyer request for cancellation
        :param list_of_shipped_order_lines: list of shipped order dictionary
        :param existing_order: existing order browse object
        :param line: data queue line
        :return: True
        """
        for order_line_list in list_of_shipped_order_lines:
            order_lines = []
            if not isinstance(order_line_list.get('OrderItems', []), list):
                order_lines.append(order_line_list.get('OrderItems', {}))
            else:
                order_lines = order_line_list.get('OrderItems', [])
            cancel_requests = [x.get('BuyerRequestedCancel') for x in order_lines if
                               eval(x.get('BuyerRequestedCancel', {}).
                                    get('IsBuyerRequestedCancel', 'false').capitalize())]
            if cancel_requests:
                existing_order.buyer_requested_cancellation = eval(cancel_requests[0].
                                                                   get('IsBuyerRequestedCancel', 'false').capitalize())
                existing_order.buyer_cancellation_reason = cancel_requests[0].get('BuyerCancelReason', '')
        line.state = 'done'
        return True

    def get_fbm_next_token_orders(self, seller, next_token):
        """
        This method will request for amazon order by next token and return response.
        """
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'order_by_next_token_sp_api')
        kwargs.update({'next_token': next_token, 'restricted_resources': ['buyerInfo', 'shippingAddress']})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            if self._context.get('is_auto_process', False):
                self.env['common.log.lines.ept'].create_common_log_line_ept(
                    message=response.get('error', ''), model_name='shipped.order.data.queue.ept',
                    fulfillment_by='FBM', module='amazon_ept', operation_type='import', res_id=self.id,
                    amz_seller_ept=seller and seller.id or False)
                return [], ''
            raise response.get('error', {})
        orders = response.get('result', [])
        next_token = response.get('NextToken', '')
        return orders, next_token

    def process_shipped_or_missing_unshipped_lines_ept(self, instance, order, line, list_of_shipped_order_lines,
                                                       queue_order):
        """
        This method will process amazon shipped order lines.
        """
        common_log_line_ept = self.env[COMMON_LOG_LINES_EPT]
        created_order_list = []
        line_state = line.state
        order_status = order.get('OrderStatus', '')

        order_counter = 0
        for order_line_wrapper_obj in list_of_shipped_order_lines:
            order_lines = []
            if not isinstance(order_line_wrapper_obj.get('OrderItems', []), list):
                order_lines.append(order_line_wrapper_obj.get('OrderItems', {}))
            else:
                order_lines = order_line_wrapper_obj.get('OrderItems', [])
            sales_order, line_state = self.process_shipped_or_missing_unshipped_order_ept(instance, order, order_lines,
                                                                                          line_state, queue_order)
            if sales_order:
                created_order_list.append(sales_order)
                if order_status == 'Shipped':
                    sales_order.amz_seller_id.fbm_auto_workflow_id.shipped_order_workflow_ept(sales_order)
                elif order_status in ['Unshipped', 'PartiallyShipped']:
                    sales_order.process_orders_and_invoices_ept()
                else:
                    message = 'Workflow not executed for order %s because order status is %s' % (
                        sales_order.amz_order_reference, order_status)
                    common_log_line_ept.create_common_log_line_ept(
                        message=message, model_name='shipped.order.data.queue.ept', fulfillment_by='FBM',
                        module='amazon_ept', operation_type='import', res_id=queue_order.id,
                        amz_seller_ept=instance.seller_id and instance.seller_id.id or False,
                        amz_instance_ept=instance and instance.id or False)
            line.state = line_state
            order_counter += 1
            if order_counter >= 10:
                self._cr.commit()
                order_counter = 0
        return True

    def process_shipped_or_missing_unshipped_order_ept(self, instance, order, order_lines, line_state, queue_order):
        """
        This method will process amazon shipped orders.
        updated by Kishan Sorani on date 01-Jul-2021
        @MOD : set carrier in order vals
        """
        partner = {}
        state_dict = dict()
        country_dict = dict()
        dict_product_details = dict()
        sales_order = self.browse()
        fbm_sale_order_report_obj = self.env['fbm.sale.order.report.ept']
        common_log_line_ept = self.env[COMMON_LOG_LINES_EPT]
        common_log_book_obj = self.env['common.log.book.ept']
        model_name = 'shipped.order.data.queue.ept'
        amazon_order_ref = order.get('AmazonOrderId', False)
        # checks for the cancel requests in the order lines
        cancel_requests = [x.get('BuyerRequestedCancel') for x in order_lines if eval(x.get('BuyerRequestedCancel', {}).
                                get('IsBuyerRequestedCancel', 'false').capitalize())]

        skip_order = False
        for order_line in order_lines:
            order_skip, product_details = self.create_or_find_amazon_product(order_line, dict_product_details,
                                                                             instance, amazon_order_ref, queue_order)
            if order_skip:
                skip_order = order_skip
                break
            dict_product_details.update(product_details)

        for order_line in order_lines:
            if skip_order:
                line_state = 'failed'
                # create schedule activity for the missing products
                if instance.seller_id.is_amz_create_schedule_activity:
                    missing_products = self.amz_find_missing_products_for_create_schedule_activity(
                        order_lines, 'FBM', instance.id)
                    common_log_book_obj.amz_create_schedule_activity_for_missing_products(
                        missing_products, instance.seller_id, 'shipped.order.data.queue.ept', queue_order.id, 'FBM')
                break

            # Skip order line if ordered quantity is 0.
            if float(order_line.get('QuantityOrdered', 0.0)) == 0.0:
                message = 'Skipped Order line because of 0 Quantity Ordered.'
                common_log_line_ept.create_common_log_line_ept(
                    message=message, model_name='shipped.order.data.queue.ept', fulfillment_by='FBM',
                    module='amazon_ept', operation_type='import', res_id=queue_order.id, mismatch_details=True,
                    amz_instance_ept=instance and instance.id or False, amz_seller_ept=instance.seller_id and
                                                                                       instance.seller_id.id or False)
                line_state = 'failed'
                continue

            if not sales_order or sales_order.amz_order_reference != amazon_order_ref:
                if order.get('BuyerInfo', {}).get('BuyerEmail', ''):
                    customer_vals = self.prepare_amazon_customer_vals(order)
                    partner = fbm_sale_order_report_obj.get_partner(customer_vals, state_dict, country_dict,
                                                                    instance)
                if partner:
                    ordervals = self.create_amazon_shipped_or_unshipped_order_vals(instance, partner, order)
                    if cancel_requests:
                        ordervals.update({
                            'buyer_requested_cancellation': eval(cancel_requests[0].
                                                                 get('IsBuyerRequestedCancel', 'false').capitalize()),
                            'buyer_cancellation_reason': cancel_requests[0].get('BuyerCancelReason', '')
                        })
                    if not ordervals.get('fiscal_position_id', False):
                        ordervals.pop('fiscal_position_id')
                    result = self.check_amazon_order_values(instance, ordervals, 'FBM', queue_order.id, model_name)
                    if not result:
                        line_state = 'failed'
                        return sales_order, line_state
                    sales_order = self.with_context(is_b2b_amz_order=ordervals.get(
                        'is_business_order', False)).create(ordervals)
            # Skip order line if order not found in ERP.
            if not sales_order:
                message = 'Skipped Order line because order not found in ERP.'
                common_log_line_ept.create_common_log_line_ept(
                    message=message, model_name='shipped.order.data.queue.ept', fulfillment_by='FBM',
                    module='amazon_ept', operation_type='import', res_id=queue_order.id, mismatch_details=True,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False,
                    amz_instance_ept=instance and instance.id or False)
                line_state = 'failed'
                continue
            self.amz_create_order_lines(sales_order, instance, order_line, dict_product_details)
            line_state = 'done'
        return sales_order, line_state

    def amz_find_missing_products_for_create_schedule_activity(self, order_lines, fulfillment_by, instance_id=False):
        """
        Define this method for find missing amazon products for create schedule activity.
        :param: order_lines: list of order lines
        :param: amz_fulfillment_by: amazon fulfillment by (FBA or FBM)
        :param: instance_id: amazon.instance.ept() id
        :return: blank list or list of amazon products sku
        """
        amz_product_obj = self.env['amazon.product.ept']
        missing_products = []
        for line in order_lines:
            if not instance_id:
                instance_id = line.get('instance_id', False)
            seller_sku = self.amz_get_amazon_product_sku(line)
            if seller_sku:
                amazon_product = amz_product_obj.search_amazon_product(
                    instance_id, seller_sku, fulfillment_by)
                if not amazon_product:
                    missing_products.append(seller_sku)
        return list(set(missing_products))

    @staticmethod
    def amz_get_amazon_product_sku(line):
        """
        Define this method for get amazon product seller SKU.
        :param: line: order line - dict
        :return: seller sku or ''
        """
        seller_sku = ''
        if line.get('SellerSKU', ''):
            seller_sku = line.get('SellerSKU', '')
        elif line.get('sku', ''):
            seller_sku = line.get('sku', '').strip()
        return seller_sku

    def create_amazon_shipped_or_unshipped_order_vals(self, instance, partner, order):
        """
        Define method which help to create amazon shipped or unshipped orders.
        :param : instance : amazon instance
        :param : partner : amazon partner
        :param : order : amazon order details
        : return : sale order values dict {}
        :migration done by kishan sorani on date 28-Sep-2021
        """
        delivery_carrier_obj = self.env['delivery.carrier']
        fbm_sale_order_report_obj = self.env['fbm.sale.order.report.ept']
        amazon_order_ref = order.get('AmazonOrderId', False)
        seller_id = instance.seller_id
        order_status = order.get('OrderStatus', '')
        ordervals = self.prepare_amazon_sale_order_vals(instance, partner, order)
        # set picking policy as FBM Auto workflow picking policy
        ordervals.update({'picking_policy': instance.seller_id.fbm_auto_workflow_id.picking_policy})
        if not seller_id.is_default_odoo_sequence_in_sales_order:
            name = seller_id.order_prefix + amazon_order_ref if seller_id.order_prefix else amazon_order_ref
            ordervals.update({'name': name})
        updated_ordervals = self.prepare_updated_ordervals(instance, amazon_order_ref, order)
        ordervals.update(updated_ordervals)
        # update order vals and set carrier if order status in Unshipped or Partially Shipped
        if order_status in ['Unshipped', 'PartiallyShipped']:
            shipping_category = ordervals.get('amz_shipment_service_level_category', False)
            if shipping_category:
                carrier =fbm_sale_order_report_obj.amz_find_fbm_delivery_method(
                    shipping_category,ordervals.get('partner_shipping_id',False))
                ordervals.update({'carrier_id': carrier.id if carrier else False})
        return ordervals

    def get_fbm_orders(self, seller, marketplaceids, orderstatus, updated_after_date,
                       updated_before_date=False):
        """
        This method will request for amazon orders and return response.
        """
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'import_amazon_orders_sp_api')
        kwargs.update({'marketplaceids': marketplaceids, 'updated_after_date': updated_after_date,
                       'fulfillment_channels': 'MFN', 'orderstatus': orderstatus})
        if updated_before_date:
            kwargs.update({'updated_before_date': updated_before_date})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            if self._context.get('is_auto_process', False):
                self.env['common.log.lines.ept'].create_common_log_line_ept(
                    message=response.get('error', ''), model_name='shipped.order.data.queue.ept', fulfillment_by='FBM',
                    module='amazon_ept', operation_type='import', res_id=self.id,
                    amz_seller_ept=seller and seller.id or False)
                return {}
            raise UserError(_(response.get('error', {})))
        result = response.get('result', {})
        return result

    def create_shipped_or_missing_unshipped_queue(self, datas, instance_dict, seller, data_queue):
        """
        This method will create an shipped order queue.
        """
        shipped_order_data_queue_line_obj = self.env['shipped.order.data.queue.line.ept']
        for data in datas:
            instance = instance_dict.get(data.get('SalesChannel', ''))
            if not instance:
                instance = seller.mapped('instance_ids').filtered(
                    lambda l, data=data: l.marketplace_id.name == data.get('SalesChannel', ''))
                instance_dict.update({data.get('SalesChannel', ''): instance})
            shipped_order_data_queue_line_obj.create({
                'order_id': data.get('AmazonOrderId', False),
                'order_data_id': json.dumps(data),
                'amz_instance_id': instance.id,
                'last_process_date': datetime.now(),
                'shipped_order_data_queue_id': data_queue.id
            })
        return True

    def auto_process_shipped_order_queue_line(self, data_queue):
        """
        This method will active the cron to auto process shipped order queue lines.
        """
        if data_queue.shipped_order_data_queue_lines:
            cron_id = self.env.ref('amazon_ept.ir_cron_child_to_process_shipped_order_queue_line')
            if cron_id and not cron_id.sudo().active:
                cron_id.sudo().write({'active': True, 'nextcall': datetime.now()})
            elif cron_id:
                try:
                    cron_id.sudo().write({'nextcall': datetime.now()})
                except Exception as e:
                    _logger.debug("Method %s will be called after commit", e)
        return True

    def get_marketplaceids_and_request_date(self, seller, instance, updated_after_date):
        """
        This method will return the marketplaceids and request after date to get orders
        """
        marketplaceids = tuple(map(lambda x: x.market_place_id, instance)) if instance else \
            tuple(map(lambda x: x.market_place_id, seller.instance_ids))
        if not marketplaceids:
            raise UserError(_(AMAZON_INSTANCE_NOT_CONFIGURED_WARNING + " %s") % (seller.name))

        if updated_after_date:
            updated_after_date = updated_after_date.strftime(DATE_YMDHMS)
            db_import_time = time.strptime(str(updated_after_date), DATE_YMDHMS)
            db_import_time = time.strftime(DATE_YMDTHMS, db_import_time)
            updated_after_date = time.strftime(DATE_YMDTHMS, time.gmtime(
                time.mktime(time.strptime(db_import_time, DATE_YMDTHMS))))
            updated_after_date = str(updated_after_date) + 'Z'
        else:
            today = datetime.now()
            earlier = today - timedelta(days=3)
            earlier_str = earlier.strftime(DATE_YMDTHMS)
            updated_after_date = earlier_str + 'Z'
        return marketplaceids, updated_after_date

    def import_fbm_shipped_or_missing_unshipped_orders(self, seller, instance, updated_after_date, orderstatus,
                                                       updated_before_date=False):
        """
        This method process the FBM shipped orders.
        :param seller: seller object
        :param instance: instance object
        :param updated_after_date: start date from where to get the orders
        :param orderstatus: shipped orders status.
        :param updated_before_date: end date from where to get the orders.
        :return: True
        """
        data_queue_list = []
        shipped_order_data_queue_obj = self.env['shipped.order.data.queue.ept']
        instance_dict = {}
        marketplaceids, updated_after_date = self.get_marketplaceids_and_request_date(
            seller, instance, updated_after_date)
        if updated_before_date:
            updated_before_date = updated_before_date.strftime(DATE_YMDHMS)
            db_import_time = time.strptime(str(updated_before_date), DATE_YMDHMS)
            db_import_time = time.strftime(DATE_YMDTHMS, db_import_time)
            updated_before_date = time.strftime(DATE_YMDTHMS, time.gmtime(
                time.mktime(time.strptime(db_import_time, DATE_YMDTHMS))))
            updated_before_date = str(updated_before_date) + 'Z'
        result = self.get_fbm_orders(seller, marketplaceids, orderstatus, updated_after_date,
                                     updated_before_date)
        next_token = result.get('NextToken', '')
        data_queue = shipped_order_data_queue_obj.create({'amz_seller_id': seller.id})
        data_queue_list.append(data_queue.id)
        datas = result.get('Orders', [])
        if not isinstance(datas, list) and datas:
            datas = [datas]
        if datas:
            self.create_shipped_or_missing_unshipped_queue(datas, instance_dict, seller, data_queue)
            self._cr.commit()
            self.auto_process_shipped_order_queue_line(data_queue)
            while True:
                if not next_token:
                    break
                result, next_token = self.get_fbm_next_token_orders(seller, next_token)
                if not isinstance(result, list) and datas:
                    result = [result]
                if result:
                    for data in result:
                        datas = data.get('Orders', [])
                        data_queue = shipped_order_data_queue_obj.create({'amz_seller_id': seller.id})
                        data_queue_list.append(data_queue.id)
                        self.create_shipped_or_missing_unshipped_queue(datas, instance_dict, seller, data_queue)
                        self._cr.commit()
        return data_queue_list

    @staticmethod
    def prepare_sale_order_update_values(instance, order):
        """
        Prepares Sale Order Values
        :param instance: amazon.instance.ept()
        :param order: {}
        :return: {}
        """
        is_business_order = True if str(order.get('IsBusinessOrder', '')).lower() in ['true', 't'] else False
        is_prime_order = True if str(order.get('IsPrime', '')).lower() in ['true', 't'] else False
        return {
            'auto_workflow_process_id': instance.seller_id.fba_auto_workflow_id.id or False,
            'amz_instance_id': instance and instance.id or False,
            'amz_fulfillment_by': 'FBA',
            'amz_order_reference': order.get('AmazonOrderId', ''),
            'amz_seller_id': instance.seller_id and instance.seller_id.id or False,
            'is_business_order': is_business_order,
            'is_prime_order': is_prime_order
        }

    def create_amazon_sales_order_vals(self, partner_dict, order, instance):
        """
        This function Creates Sale Orders values
        and pass the values to common connector library for import orders in odoo
        :param partner_dict: {}
        :param order: {}
        :param instance: amazon.instance.ept()
        :return: {}
        """
        # #Prepare Sale Order Values
        order_vals = self.prepare_amazon_sale_order_vals(instance, partner_dict, order)
        # set picking policy as FBA Auto workflow picking policy
        order_vals.update({'picking_policy': instance.seller_id.fba_auto_workflow_id.picking_policy})
        # Prepare Sale Order values for update
        sale_order_values = self.prepare_sale_order_update_values(instance, order)
        sale_order_values.update({'is_fba_pending_order': True})
        order_vals.update(sale_order_values)
        # #is_default_odoo_sequence_in_sale_order, order_prefix is fetched according to seller wise
        if not instance.seller_id.is_default_odoo_sequence_in_sales_order:
            order_vals.update({'name': "%s%s" % (
                instance.seller_id.fba_order_prefix or '',
                order.get('AmazonOrderId', ''))})
        # merge with FBA
        fulfillment_vals = self.fba_fulfillment_prepare_vals(instance)
        order_vals.update(fulfillment_vals)
        # analytic_account = instance.analytic_account_id.id if instance.analytic_account_id else False
        # if analytic_account:
        #     order_vals.update({'analytic_account_id': analytic_account})
        return order_vals

    @staticmethod
    def fba_fulfillment_prepare_vals(instance):
        """
        Prepare values for FBA Fulfillment workflow process
        fba_auto_workflow_id is fetched according to seller wise
        :param instance: amazon.instance.ept()
        :return: {}
        """
        workflow = instance.seller_id.fba_auto_workflow_id
        return {
            'warehouse_id': instance.fba_warehouse_id and
                            instance.fba_warehouse_id.id or instance.warehouse_id.id,
            'auto_workflow_process_id': workflow.id,
            'amz_fulfillment_by': 'FBA',
            'picking_policy': workflow.picking_policy,
            'amz_seller_id': instance.seller_id and instance.seller_id.id or False,
        }

    def amz_create_common_log(self, message, instance, order_ref, fulfillment_by, res_id, model_name):
        """
        This method is used to create the mismatch log for the orders.
        :param message: string
        :param instance: amazon.instance.ept()
        :param order_ref: string
        :param fulfillment_by: FBA/FBM
        :param res_id: res_id
        :param model_name: ir.model()
        return:
        """
        common_log_obj = self.env[COMMON_LOG_LINES_EPT]
        model_id = self.env[IR_MODEL]._get(model_name).id
        common_log_obj.create_common_log_line_ept(
            message=message, model_name=model_name, model_id=model_id, module='amazon_ept',
            fulfillment_by=fulfillment_by, order_ref=order_ref,
            operation_type='import', res_id=res_id, mismatch_details=True,
            amz_instance_ept=instance.id,
            amz_seller_ept=instance.seller_id.id if instance.seller_id else False
        )

    def check_amazon_order_values(self, instance, order_vals, fulfillment_by, res_id, model_name):
        """
        This method is used to check various fields present in order vals,
        Check the condition and according to that it invoke other method to create the common log line.
        :param : instance: amazon.instance.ept()
        :param : order_vals: dict()
        :param : fulfillment_by: FBA/FBM
        :param : res_id: relation_id
        :model_name : ir.model()
        :return : boolean
        """
        order_ref = order_vals.get('amz_order_reference', False)
        flag = True
        if not order_vals.get('pricelist_id', False):
            message = amazon_messages.get('pricelist_id', '')
            self.amz_create_common_log(message, instance, order_ref, fulfillment_by, res_id, model_name)
            flag = False
        if not order_vals.get('warehouse_id', False):
            warehouse = 'fba_warehouse_id' if fulfillment_by == 'FBA' else 'fbm_warehouse_id'
            message = amazon_messages.get(warehouse, '')
            self.amz_create_common_log(message, instance, order_ref, fulfillment_by, res_id, model_name)
            flag = False
        if not order_vals.get('picking_policy', False):
            message = amazon_messages.get('picking_policy', '')
            self.amz_create_common_log(message, instance, order_ref, fulfillment_by, res_id, model_name)
            flag = False
        return flag

    def create_amazon_shipping_report_sale_order(self, row, partner, report_id):
        """
        Process Amazon Shipping Report Sale Orders
        :param instance: amazon.instance.ept()
        :param warehouse: warehouse id
        :param row: file_data {}
        :param partner: partners {}
        :return: sale.order()
        """
        model_name = 'shipping.report.request.history'
        amz_instance_obj = self.env[AMZ_INSTANCE_EPT]
        instance = amz_instance_obj.browse(row.get('instance_id'))
        warehouse = row.get('warehouse', False) or instance.fba_warehouse_id and \
                    instance.fba_warehouse_id.id or \
                    instance.warehouse_id.id

        amazon_exist_order = self.search([
            ('amz_order_reference', '=', row.get('amazon-order-id', '')),
            ('amz_instance_id', '=', instance.id), ('warehouse_id', '=', warehouse)], order="id desc", limit=1)
        if amazon_exist_order:
            return amazon_exist_order

        order_vals = self.prepare_amazon_sale_order_vals(instance, partner, row)
        # set picking policy as FBA Auto workflow picking policy
        order_vals.update({'picking_policy': instance.seller_id.fba_auto_workflow_id.picking_policy or False})
        carrier_id = False
        order_ref = row.get('amazon-order-id', False)
        if row.get('carrier', ''):
            # #shipment_charge_product_id is fetched according to seller wise
            ship_product = instance.seller_id.shipment_charge_product_id
            carrier_id = self.with_context(shipping_report=True).get_amz_shipping_method(row.get('carrier', ''),
                                                                                         ship_product)
            if not carrier_id:
                message = amazon_messages.get('ship_product', '')
                self.amz_create_common_log(message, instance, order_ref, 'FBA', report_id, model_name)
                return False
        if row.get('purchase-date', False):
            date_order = parser.parse(row.get('purchase-date', False)) \
                .astimezone(utc).strftime(DATE_YMDHMS)
        else:
            date_order = time.strftime(DATE_YMDHMS)
        order_vals.update(
            {'warehouse_id': warehouse,
             'client_order_ref': row.get('amazon-order-id', '') or False,
             'date_order': date_order,
             'carrier_id': carrier_id
             })
        # #Prepare Sale Order values for update
        sale_order_values = self.prepare_sale_order_update_values(instance, row)
        sale_order_values.update({
            'amz_order_reference': row.get('amazon-order-id', False),
            'amz_shipment_service_level_category': row.get('ship-service-level', False),
            'amz_shipment_report_id': report_id})
        order_vals.update(sale_order_values)
        if not instance.seller_id.is_default_odoo_sequence_in_sales_order_fba:
            order_vals.update(
                {'name': "%s%s" % (
                    instance.seller_id.fba_order_prefix or '',
                    row.get('amazon-order-id', ''))})
        # analytic_account = instance.analytic_account_id.id if instance.analytic_account_id else False
        # if analytic_account:
        #     order_vals.update({'analytic_account_id': analytic_account})

        result = self.check_amazon_order_values(instance, order_vals, 'FBA', report_id, model_name)
        if not result:
            return False
        if not order_vals.get('fiscal_position_id', False):
            order_vals.pop('fiscal_position_id')
        return self.with_context(is_b2b_amz_order=order_vals.get('is_business_order', False)).create(order_vals)

    def get_amz_shipping_method(self, ship_method, ship_product):
        """
        Find or create Delivery Carrier as per carrer code in shipment report
        :param ship_method:
        :param ship_product:
        :return carrier.id: delivery carrier id
        """
        delivery_carrier_obj = self.env['delivery.carrier']
        ship_method = ship_method.replace(' ', '')
        carrier = delivery_carrier_obj.search(['|', ('amz_carrier_code', '=', ship_method),
                                               ('name', '=', ship_method)], limit=1)
        if not carrier:
            if self._context.get('shipping_report', False) and not ship_product:
                return delivery_carrier_obj
            carrier = delivery_carrier_obj.create({
                'name': ship_method,
                'product_id': ship_product.id})
        return carrier.id

    def create_outbound_shipment(self):
        """
        This method is used to create outbound shipment.
        """
        amazon_outbound_order_wizard_obj = self.env['amazon.outbound.order.wizard']
        outbound_order_vals = {"sale_order_ids": [(6, 0, [self.id])]}
        instance_id = self.warehouse_id.seller_id.instance_ids.filtered(
            lambda x: x.fba_warehouse_id == self.warehouse_id and
                      x.country_id == self.warehouse_id.partner_id.country_id)
        if not instance_id:
            instance_id = self.warehouse_id.seller_id.instance_ids.filtered(
                lambda x: x.fba_warehouse_id == self.warehouse_id)
        if instance_id:
            outbound_order_vals.update({"instance_id": instance_id[0].id})
        created_id = amazon_outbound_order_wizard_obj.with_context(
            {'active_model': self._name, 'active_ids': self.ids,
             'active_id': self.id or False}).create(outbound_order_vals)
        return amazon_outbound_order_wizard_obj.wizard_view(created_id)

    def amz_update_tracking_number(self, seller):
        """
        Check If Order already shipped in the amazon then we will skip that all orders and set update_into_amazon=True
        :param seller: amazon.seller.ept()
        :return: True
        @author: Keyur Kanani
        """
        marketplaceids = seller.instance_ids.mapped(lambda l: l.marketplace_id.market_place_id)
        if not marketplaceids:
            raise UserError(_(AMAZON_INSTANCE_NOT_CONFIGURED_WARNING + " %s" % (seller.name)))
        next_token = {}
        flag = True
        while next_token or flag:
            amazon_orders, next_token = self.check_already_status_updated_in_amazon(seller, marketplaceids,
                                                                                    seller.instance_ids, next_token)
            flag = False
            if not amazon_orders:
                continue
            message_information, shipment_pickings = self.get_amz_message_information_ept(amazon_orders)
            if not message_information:
                continue
            data = self.create_data(message_information, str(seller.merchant_id))
            kwargs = self.prepare_amazon_request_report_kwargs(seller, 'amazon_submit_feeds_sp_api')
            kwargs.update({'data': data, 'marketplaceids': marketplaceids,
                           'feed_type': 'POST_ORDER_FULFILLMENT_DATA'})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                raise UserError(_(response.get('error', {})))
            results = response.get('results', {})
            self.process_amazon_update_tracking_feed_response(results, data, seller, shipment_pickings)
            self._cr.commit()
        return True

    def process_amazon_update_tracking_feed_response(self, results, data, seller, shipment_pickings):
        """
        Process result of API after updating tracking number feed to Amazon.
        :param results: dict{}
        :param data: xml string
        :param seller:amazon.seller.ept()
        :param shipment_pickings: list[pickings]
        @author: Keyur Kanani
        """
        picking_obj = self.env['stock.picking']
        if results.get('feed_result', {}).get('feedId', False):
            feed_submission_obj = self.env['feed.submission.history']
            feed_document_id = results.get('result', {}).get('feedDocumentId', '')
            feed_submission_id = results.get('feed_result', {}).get('feedId', False)
            vals = {'message': data.encode('utf-8'), 'feed_result_id': feed_submission_id,
                    'feed_submit_date': time.strftime(DATE_YMDHMS), 'user_id': self._uid,
                    'feed_document_id': feed_document_id,
                    'seller_id': seller.id, 'feed_type': 'update_tracking_number'}
            feed_id = feed_submission_obj.create(vals)
            if feed_id:
                picking_obj.browse(shipment_pickings).write({'feed_submission_id': feed_id.id})
                cron_id = self.env.ref('amazon_ept.ir_cron_get_feed_submission_result')
                if cron_id and not cron_id.sudo().active:
                    cron_id.sudo().write(
                        {'active': True, 'nextcall': datetime.now() + timedelta(minutes=5)})
                elif cron_id:
                    try:
                        cron_id.sudo().write({'nextcall': datetime.now() + timedelta(minutes=5)})
                    except Exception as e:
                        _logger.debug("Get Feed Submission Method %s will be called after commit", e)

    @staticmethod
    def check_amazon_update_status_pickings(amazon_order, picking):
        """"
        This method will check is picking already updated in amazon
        # Here We Take only done picking and updated in amazon false
        """
        if (picking.updated_in_amazon and amazon_order.picking_ids.filtered(
                lambda l, picking=picking: l.backorder_id.id == picking.id)) or picking.state != 'done' \
                or picking.location_dest_id.usage != 'customer':
            return True
        return False

    def amz_mismatch_log_for_update_order_status(self, message, order):
        """
        Defined this method for creating the log line if any mismatch found while doing fbm update order status
        :param: message: str
        :param: order: sale.order()
        :return:
        """
        if self._context.get('auto_process', False):
            common_log_obj = self.env[COMMON_LOG_LINES_EPT]
            common_log_obj.create_common_log_line_ept(
                message=message, model_name='sale.order', module='amazon_ept',
                fulfillment_by='FBM', order_ref=order.name,
                operation_type='export', res_id=order.id,
                amz_instance_ept=order.amz_instance_id.id,
                amz_seller_ept=order.amz_instance_id.seller_id.id
                if order.amz_instance_id.seller_id else False
            )
        else:
            raise UserError(message)

    def get_amz_ship_info_and_parcel_values(self, picking, amazon_order, fulfillment_date_concat):
        """
        This method return the ship from address and prepared parcel values.
        """
        ship_info = ''
        carrier_name = self.amz_get_carrier_name_ept(picking)
        tracking_no = picking.carrier_tracking_ref
        carrier_code = self.amz_get_carrier_code_ept(picking)
        parcel = self.amz_prepare_parcel_values_ept(carrier_name, tracking_no, amazon_order,
                                                    fulfillment_date_concat, carrier_code)
        if not amazon_order.warehouse_id:
            message = ('Warehouse not found for the %s order' % amazon_order.amz_order_reference)
            self.amz_mismatch_log_for_update_order_status(message, amazon_order)
        partner = amazon_order.warehouse_id.partner_id
        if not partner:
            message = ('Partner not found in the %s Warehouse.' % amazon_order.warehouse_id.name)
            self.amz_mismatch_log_for_update_order_status(message, amazon_order)
        elif partner.name and re.search(r'[^\w\s]', partner.name):
            message = ('Special characters are found in the %s partner name for the %s warehouse.'
                       % (partner.name, amazon_order.warehouse_id.name))
            self.amz_mismatch_log_for_update_order_status(message, amazon_order)
        elif not all([partner.street, partner.city, partner.state_id, partner.zip, partner.country_id]):
            message = ('Address not found for any one of them Street, City, State, Zip, and Country for '
                       '%s partner' % partner.name)
            self.amz_mismatch_log_for_update_order_status(message, amazon_order)
        else:
            ship_info = self.amz_get_ship_from_address_details(partner)
        return ship_info, parcel

    def get_amz_message_information_ept(self, amazon_orders):
        """
        Find done pickings also find pickings location destination is customer,
        then prepare xml details to update in amazon feed
        :param amazon_orders: sale.order()
        :return: message_information, shipment_pickings
        @author: Keyur Kanani
        """
        shipment_pickings = []
        message_information = ''
        message_id = 1
        amazon_orders = list(filter(lambda order: (order.amz_shipment_service_level_category), amazon_orders))
        for amazon_order in amazon_orders:
            for picking in amazon_order.picking_ids:
                is_skip = self.check_amazon_update_status_pickings(amazon_order, picking)
                if is_skip:
                    continue
                fulfillment_date_concat = self.get_shipment_fulfillment_date(picking)
                shipment_pickings.append(picking.id)
                # will manage multiple tracking number into the delivery order if carrier tracking ref not set into
                # the picking
                # manage_multi_tracking_number_in_delivery_order = False if picking.carrier_tracking_ref else True
                # if not manage_multi_tracking_number_in_delivery_order:
                multi_tracking = True if picking.mapped('package_ids').filtered(lambda l: l.tracking_no) else False
                if picking.carrier_tracking_ref and not multi_tracking:
                    ship_info, parcel = self.get_amz_ship_info_and_parcel_values(picking, amazon_order,
                                                                                 fulfillment_date_concat)
                    message_information += self.create_parcel_for_single_tracking_number(parcel, message_id, ship_info)
                    message_id = message_id + 1
                else:
                    # Create message for bom type products
                    phantom_msg_info, message_id, update_move_ids = self.get_qty_for_phantom_type_products(
                        amazon_order, picking, message_id, fulfillment_date_concat)
                    if phantom_msg_info:
                        message_information += phantom_msg_info
                    # Create Message for each move
                    message_information, message_id = self.create_message_for_multi_tracking_number_ept(
                        picking, message_information, update_move_ids, message_id)
        return message_information, shipment_pickings

    @staticmethod
    def amz_get_ship_from_address_details(partner):
        """
        Prepare xml data for ship from address in the update tracking numbers
        :param partner:res.partner()
        :return: text
        @author: Keyur Kanani
        """
        address = ""
        if partner.street:
            address = """<AddressFieldOne>%s</AddressFieldOne>""" % partner.street
        if partner.street2:
            address += """<AddressFieldTwo>%s</AddressFieldTwo>""" % partner.street2
        ship_from = """<ShipFromAddress>
            <Name>%s</Name>
            %s
            <City>%s</City>
            <County>%s</County>
            <StateOrRegion>%s</StateOrRegion>
            <PostalCode>%s</PostalCode>
            <CountryCode>%s</CountryCode>
        </ShipFromAddress>""" % (partner.name, address, partner.city,
                                 partner.country_id.name if partner.country_id else '',
                                 partner.state_id.code if partner.state_id else '', partner.zip,
                                 partner.country_id.code if partner.country_id else '')

        return ship_from

    @staticmethod
    def prepare_tracking_no_dict_with_qty(move):
        """
        This method will prepare tracking number dictionary with quantity to update order status or tracking number
        """
        tracking_no_with_qty = {}
        for move_line in move.move_line_ids:
            if move_line.qty_done < 0.0:
                continue
            tracking_no = move_line.result_package_id.tracking_no if move_line.result_package_id else 'UNKNOWN'
            if tracking_no == 'UNKNOWN':
                continue
            quantity = tracking_no_with_qty.get(tracking_no, 0.0)
            quantity = quantity + move_line.qty_done
            tracking_no_with_qty.update({tracking_no: quantity})
        return tracking_no_with_qty

    def create_message_for_multi_tracking_number_ept(self, picking, message_information, update_move_ids, message_id):
        """
        Prepare message for multiple tracking number pickings
        :param picking: stock.move()
        :param message_information: string
        :param update_move_ids: list[]
        :param message_id: int
        :return: message_information, message_id
        @author: Keyur Kanani
        """
        fulfillment_date_concat = self.get_shipment_fulfillment_date(picking)
        carrier_name = self.amz_get_carrier_name_ept(picking)
        for move in picking.move_ids:
            if move in update_move_ids or move.sale_line_id.product_id.id != move.product_id.id:
                continue
            amazon_order_item_id = move.sale_line_id.amazon_order_item_id
            # Create Package for the each parcel
            tracking_no_with_qty = self.prepare_tracking_no_dict_with_qty(move)
            for tracking_no, product_qty in tracking_no_with_qty.items():
                tracking_no = '' if tracking_no == 'UNKNOWN' else tracking_no
                product_qty = self.amz_get_sale_line_product_qty_ept(move.sale_line_id)
                carrier_code = self.amz_get_carrier_code_ept(picking)
                parcel = self.amz_prepare_parcel_values_ept(carrier_name, tracking_no, picking.sale_id,
                                                            fulfillment_date_concat, carrier_code)
                parcel.update({'qty': product_qty, 'amazon_order_item_id': amazon_order_item_id})
                message_information += self.create_parcel_for_multi_tracking_number(parcel, message_id, picking.sale_id)
                message_id = message_id + 1
        return message_information, message_id

    @staticmethod
    def amz_prepare_parcel_values_ept(carrier_name, tracking_no, amazon_order, fulfillment_date_concat, carrier_code):
        """
        Prepare courier parcel values
        :param carrier_name: carrier name
        :param tracking_no: shipment tracking number
        :param amazon_order: sale.order()
        :return: dict{}
        @author: Keyur Kanani
        """
        picking_ids = amazon_order.picking_ids
        fba_shipping_method = picking_ids.mapped('carrier_id.fbm_shipping_method')
        shipping_service_level_category = picking_ids.mapped('carrier_id.amz_shipping_service_level_category')
        shipment_service_level_category = fba_shipping_method and fba_shipping_method[0] or \
                                          shipping_service_level_category and shipping_service_level_category[0] or \
                                          amazon_order.amz_shipment_service_level_category
        return {'tracking_no': tracking_no or '', 'order_ref': amazon_order.amz_order_reference,
                'carrier_name': carrier_name or '',
                'carrier_code': carrier_code or '',
                'shipping_level_category': shipment_service_level_category,
                'fulfillment_date_concat': fulfillment_date_concat or False}

    @staticmethod
    def get_shipment_fulfillment_date(picking):
        """
        prepare fulfillment data from shipment
        :param picking: stock.move()
        :return: date string
        @author: Keyur Kanani
        """
        if picking.date_done:
            fulfillment_date = time.strptime(str(picking.date_done), DATE_YMDHMS)
            fulfillment_date = time.strftime(DATE_YMDTHMS, fulfillment_date)
        else:
            fulfillment_date = time.strftime(DATE_YMDTHMS)
        return str(fulfillment_date) + '-00:00'

    @staticmethod
    def amz_get_carrier_name_ept(picking):
        """
        Get carrier name from picking
        :param picking: stock.move()
        :return: string
        @author: Keyur Kanani
        """
        carrier = picking.carrier_id
        if carrier and carrier.amz_carrier_code:
            carrier_name = carrier.amz_carrier_code
            if carrier.amz_carrier_code == 'Other':
                carrier_name = carrier.fbm_shipping_method if carrier.fbm_shipping_method else carrier.name
        else:
            carrier_name = carrier.name
        return carrier_name

    @staticmethod
    def amz_get_carrier_code_ept(picking):
        """
        Define method for get amazon carrier code from picking
        :param picking : stock.picking()
        : return: string
        """
        if picking.carrier_id and picking.carrier_id.amz_carrier_code:
            carrier_code = picking.carrier_id.amz_carrier_code
        else:
            carrier_code = 'Other'
        return carrier_code

    def amz_prepare_phantom_product_dict_ept(self, picking_ids):
        """
        Prepare phantom product dictionary from picking ids
        :param picking_ids: list
        :return: dict{}
        @author: Keyur Kanani
        """
        move_obj = self.env['stock.move']
        moves = move_obj.search(
            [('picking_id', 'in', picking_ids), ('picking_type_id.code', '!=', 'incoming'),
             ('state', 'not in', ['draft', 'cancel']), ('updated_in_amazon', '=', False)])
        phantom_product_dict = {}
        for move in moves:
            if move.sale_line_id.product_id.id != move.product_id.id:
                if move.sale_line_id in phantom_product_dict and move.product_id.id not in phantom_product_dict.get(
                        move.sale_line_id):
                    phantom_product_dict.get(move.sale_line_id).append(move.product_id.id)
                else:
                    phantom_product_dict.update({move.sale_line_id: [move.product_id.id]})
        return phantom_product_dict

    @staticmethod
    def get_amz_tracking_number(picking, moves):
        """
        This will return tracking number
        """
        tracking_no = picking.carrier_tracking_ref
        for move in moves:
            if not tracking_no:
                for move_line in move.move_line_ids:
                    tracking_no = move_line.result_package_id.tracking_no if \
                        move_line.result_package_id else False
        return tracking_no

    def get_qty_for_phantom_type_products(self, order, picking, message_id, fulfillment_date_concat):
        """
        Get quantity of phantom type products and prepare message information
        :param order: sale.order()
        :param picking: stock.move()
        :param message_id: int
        :param fulfillment_date_concat: date
        :return: message_information, message_id, update_move_ids
        @author: Keyur Kanani
        """
        message_information = ''
        move_obj = self.env['stock.move']
        update_move_ids = []
        picking_ids = order.picking_ids.filtered(lambda l: l.location_dest_id.usage == 'customer').ids
        phantom_product_dict = self.amz_prepare_phantom_product_dict_ept(picking_ids)
        for sale_line_id, product_ids in phantom_product_dict.items():
            moves = move_obj.search([('picking_id', 'in', picking_ids), ('state', 'in', ['draft', 'cancel']),
                                     ('product_id', 'in', product_ids)])
            if not moves:
                moves = move_obj.search([('picking_id', 'in', picking_ids), ('state', '=', 'done'),
                                         ('product_id', 'in', product_ids), ('updated_in_amazon', '=', False)])
                tracking_no = self.get_amz_tracking_number(picking, moves)
                if tracking_no:
                    update_move_ids += moves.ids
                    product_qty = self.amz_get_sale_line_product_qty_ept(sale_line_id)
                    carrier_name = self.amz_get_carrier_name_ept(picking)
                    carrier_code = self.amz_get_carrier_code_ept(picking)
                    parcel = self.amz_prepare_parcel_values_ept(carrier_name, tracking_no, order,
                                                                fulfillment_date_concat, carrier_code)
                    parcel.update({'qty': product_qty, 'amazon_order_item_id': sale_line_id.amazon_order_item_id})
                    message_information += self.create_parcel_for_multi_tracking_number(parcel, message_id, order)
                    message_id = message_id + 1

        return message_information, message_id, update_move_ids

    @staticmethod
    def amz_get_sale_line_product_qty_ept(sale_line_id):
        """
        Divide product quantity with asin quantity if asin qty is available in product
        :param sale_line_id: sale.order.line()
        :return: int
        @author: Keyur Kanani
        """
        product_qty = sale_line_id.product_qty
        if sale_line_id and sale_line_id.amazon_product_id and \
                sale_line_id.amazon_product_id.allow_package_qty:
            asin_qty = sale_line_id.amazon_product_id.asin_qty
            if asin_qty != 0:
                product_qty = product_qty / asin_qty
        return int(product_qty)

    @staticmethod
    def create_data(message_information, merchant_id):
        """
        Prepare xml header data for send in amazon feed.
        :param message_information: text
        :param merchant_id: int
        :return: text
        @author: Keyur Kanani
        """
        data = """<?xml version="1.0" encoding="utf-8"?>
                        <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
                            <Header>
                                <DocumentVersion>1.01</DocumentVersion>
                                    <MerchantIdentifier>%s</MerchantIdentifier>
                            </Header>
                        <MessageType>OrderFulfillment</MessageType>""" % (merchant_id) + message_information + """
                        </AmazonEnvelope>"""
        return data

    @staticmethod
    def create_parcel_for_single_tracking_number(parcel, message_id, ship_info):
        """
        Prepare Parcel tracking information data for single tracking number in picking
        :param parcel: dict{}
        :param message_id: int
        :return: text
        @author: Keyur Kanani
        """
        carrier_information = ''
        message_information = ''
        if parcel.get('carrier_code', ''):
            carrier_information = '''<CarrierCode>%s</CarrierCode>''' % (parcel.get('carrier_code', ''))
            if parcel.get('carrier_code', '') == 'Other':
                carrier_information += '''<CarrierName>%s</CarrierName>''' % (parcel.get('carrier_name', ''))
        message_information += """<Message>
                                        <MessageID>%s</MessageID>
                                        <OperationType>Update</OperationType>
                                        <OrderFulfillment>
                                            <AmazonOrderID>%s</AmazonOrderID>
                                            <FulfillmentDate>%s</FulfillmentDate>
                                            <FulfillmentData>
                                                %s
                                                <ShippingMethod>%s</ShippingMethod>
                                                <ShipperTrackingNumber>%s</ShipperTrackingNumber>
                                            </FulfillmentData>
                                            %s
                                        </OrderFulfillment>
                                    </Message>""" % (str(message_id), parcel.get('order_ref', ''),
                                                     parcel.get('fulfillment_date_concat', ''),
                                                     carrier_information, parcel.get('shipping_level_category', ''),
                                                     parcel.get('tracking_no', ''), ship_info)
        return message_information

    def create_parcel_for_multi_tracking_number(self, parcel, message_id, order):
        """
        Prepare Parcel tracking information for multiple tracking numbers of a picking
        :param parcel: dict{}
        :param message_id: int
        :return: text
        @author: Keyur Kanani
        """
        message_information = ''
        carrier_information = ''
        ship_info = ""
        partner = order.warehouse_id.partner_id
        if partner:
            ship_info = self.amz_get_ship_from_address_details(partner)
        if parcel.get('carrier_code', ''):
            carrier_information = '''<CarrierCode>%s</CarrierCode>''' % (parcel.get('carrier_code', ''))
            if parcel.get('carrier_code', '') == 'Other':
                carrier_information += '''<CarrierName>%s</CarrierName>''' % (parcel.get('carrier_name', ''))
        item_string = '''<Item>
                                <AmazonOrderItemCode>%s</AmazonOrderItemCode>
                                <Quantity>%s</Quantity>
                          </Item>''' % (parcel.get('amazon_order_item_id', False), parcel.get('qty', 0))
        message_information += """<Message>
                                        <MessageID>%s</MessageID>
                                        <OperationType>Update</OperationType>
                                        <OrderFulfillment>
                                            <AmazonOrderID>%s</AmazonOrderID>
                                            <FulfillmentDate>%s</FulfillmentDate>
                                            <FulfillmentData>
                                                %s
                                                <ShippingMethod>%s</ShippingMethod>
                                                <ShipperTrackingNumber>%s</ShipperTrackingNumber>
                                            </FulfillmentData>
                                            %s
                                            %s
                                        </OrderFulfillment>
                                    </Message>""" % (str(message_id), parcel.get('order_ref', ''),
                                                     parcel.get('fulfillment_date_concat', ''),
                                                     carrier_information, parcel.get('shipping_level_category', ''),
                                                     parcel.get('tracking_no', ''), item_string, ship_info)
        return message_information

    @api.onchange('warehouse_id')
    def onchange_fba_warehouse(self):
        """
        This a compute method to set the value of auto_workflow_process
        if warehouse is a FBA warehouse and auto_workflow_process is empty
        """
        if self.warehouse_id.is_fba_warehouse and not self.auto_workflow_process_id:
            self.auto_workflow_process_id = self.warehouse_id.seller_id.fba_auto_workflow_id.id

    def action_confirm(self):
        """
        Method inherited for creating outbound order in odoo and fulfillment in the Amazon.
        """
        res = super(SaleOrder, self).action_confirm()
        if res:
            orders = self.filtered(lambda x:
                                   not x.amz_instance_id and not x.exported_in_amazon and
                                   x.warehouse_id.is_fba_warehouse and
                                   x.warehouse_id.seller_id.create_outbound_on_confirmation)
            if orders:
                _logger.info("Creating Outbound Orders While order confirmation.")
                orders.create_outbound_order()

        return res

    def create_outbound_order(self):
        """
        Creates outbound orders.
        """
        for order in self:
            if not order.order_line:
                order.message_post(body=_("Outbound Order can not created without Order lines."))
                return False
            prod_types = list(set(order.order_line.mapped('product_type')))
            if 'service' in prod_types and len(prod_types) == 1:
                order.message_post(body=_("This order has been not exported to Amazon, "
                                          "because all products are service type products."))
                return False
            if not order.amz_fulfillment_instance_id:
                outbound_vals = order.prepare_outbound_order_vals_ept(order.warehouse_id.seller_id)
                order.write(outbound_vals)
                order.set_amazon_product_in_amz_order()
                order.create_fulfillment()
        return True

    def prepare_outbound_order_vals_ept(self, seller_id):
        """
        Prepare values for create outbound order from odoo to amazon.
        """
        if self.carrier_id and self.carrier_id.amz_outbound_shipping_level_category:
            shipment_level_category = self.carrier_id.amz_outbound_shipping_level_category
        elif seller_id.shipment_category:
            shipment_level_category = seller_id.shipment_category
        else:
            shipment_level_category = "Standard"

        instance = seller_id.default_outbound_instance
        if not instance:
            instance = instance.search(
                [("country_id", "=", self.company_id.partner_id.country_id.id),
                 ("seller_id", "=", seller_id.id)], limit=1)
            if not instance:
                instance = instance.search(
                    [("country_id", "=", self.warehouse_id.partner_id.country_id.id),
                     ("seller_id", "=", seller_id.id)], limit=1)
        vals = {
            "amz_instance_id": instance.id if instance else False,
            "amz_seller_id": seller_id.id,
            "amz_fulfillment_instance_id": instance.id if instance else False,
            "amz_fulfillment_action": seller_id.fulfillment_action,
            "warehouse_id": self.warehouse_id.id,
            "pricelist_id": instance.pricelist_id.id if instance else False,
            "amz_displayable_date_time": self.date_order or False,
            "amz_fulfillment_policy": seller_id.fulfillment_policy,
            "amz_shipment_service_level_category": shipment_level_category,
            "amz_is_outbound_order": True,
            # "notify_by_email": self.notify_by_email,
            "amz_order_reference": self.name,
            "note": self.note or self.name,
        }
        return vals

    def set_amazon_product_in_amz_order(self):
        """
        Search Amazon Products and set it in the amazon order for outbound orders.
        """
        _logger.info("Setting Amazon product in order lines.")
        amazon_product_obj = self.env['amazon.product.ept']
        for line in self.order_line:
            if line.product_id.type == 'service':
                self.message_post(body=_("Service type product [%s] not added in outbound order" %
                                         line.product_id.name))
                continue
            if line.product_id:
                amz_product = amazon_product_obj.search([('product_id', '=', line.product_id.id),
                                                         ('instance_id', '=', self.amz_instance_id.id),
                                                         ('fulfillment_by', '=', 'FBA')], limit=1)
                if not amz_product:
                    amz_product = amazon_product_obj.search(
                        [('product_id', '=', line.product_id.id),
                         ('instance_id', 'in', self.amz_seller_id.instance_ids.ids),
                         ('fulfillment_by', '=', 'FBA')], limit=1)
                line.write({'amazon_product_id': amz_product.id})
        return True

    def create_fulfillment(self):
        """
        Create Outbound Shipment in Amazon for selected orders.
        """
        is_auto_process = self._context.get('is_auto_process', False)
        active_ids = self._context.get('active_ids', False)

        orders = self
        if active_ids:
            orders = self.search([('id', 'in', active_ids), ('amz_is_outbound_order', '=', True),
                                  ('state', 'in', ['sale', 'done']), ('exported_in_amazon', '=', False)])
        if orders:
            filtered_orders = orders.filtered(lambda x: x.amz_instance_id.fba_warehouse_id)
            for order in filtered_orders:
                skip_order = self.validate_amz_outbound_orders_required_fields(is_auto_process)
                if skip_order:
                    continue
                _logger.info("Requesting to create fulfillment for Order %s." % order.name)
                data = order.get_data()
                kwargs = self.prepare_amz_outbound_order_kwargs()
                kwargs.update({'emipro_api': 'auto_create_outbound_order_sp_api', 'data': data})
                response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
                self.process_create_outbound_order_response(response, is_auto_process)

        return True

    @staticmethod
    def raise_warning_or_message_post(order, is_auto_process, message):
        """
        purpose: Default method of raise warning or post messages.
        :param order: sale.order()
        :param is_auto_process: Boolean
        :param message: string
        :return: Message post / raise UserError
        """
        if is_auto_process:
            order.message_post(body=_(message))
        else:
            raise UserError(_(message))

    def validate_amz_outbound_orders_required_fields(self, is_auto_process):
        """
        Validate required fields for create outbound order in amazon.
        """
        skip_order = False
        if not self.amz_shipment_service_level_category:
            skip_order = True
            message = "Field FBA Shipping Speed is required for order %s" % self.name
            self.raise_warning_or_message_post(is_auto_process, message)
        if not self.note:
            skip_order = True
            message = "Field Displayable Order Comment is required for order %s" % self.name
            self.raise_warning_or_message_post(is_auto_process, message)
        if not self.amz_fulfillment_action:
            skip_order = True
            message = "Field Order Fulfillment Action is required for order %s" % self.name
            self.raise_warning_or_message_post(is_auto_process, message)
        if not self.amz_displayable_date_time:
            skip_order = True
            message = "Field Displayable Order Date Time is required for order %s" % self.name
            self.raise_warning_or_message_post(is_auto_process, message)
        if not self.amz_fulfillment_policy:
            skip_order = True
            message = "Field Fulfillment Policy is required for order %s" % self.name
            self.raise_warning_or_message_post(is_auto_process, message)
        return skip_order

    def prepare_amz_outbound_order_kwargs(self):
        """
        Default method for preparing Amazon arguments.
        """
        iap_account_obj = self.env['iap.account']
        ir_config_obj = self.env['ir.config_parameter']
        account = iap_account_obj.search([('service_name', '=', 'amazon_ept')])
        dbuuid = ir_config_obj.sudo().get_param('database.uuid')
        return {
            'merchant_id': self.amz_instance_id.merchant_id and str(self.amz_instance_id.merchant_id) or False,
            'app_name': 'amazon_ept_spapi',
            'account_token': account.account_token,
            'dbuuid': dbuuid,
            'amazon_marketplace_code':
                self.amz_instance_id.country_id.amazon_marketplace_code or self.amz_instance_id.country_id.code,
        }

    def process_create_outbound_order_response(self, response, is_auto_process):
        """
        Processing response of auto create outbound orders.
        """
        if response.get('error', False):
            if is_auto_process:
                self.message_post(body=_(str(response.get('error', {}))))
            else:
                raise UserError(_(response.get('error', {})))
        else:
            self.write({'exported_in_amazon': True})
            self._cr.commit()
        return True

    @api.model
    def auto_create_outbound_orders(self):
        """
        Gets draft orders which has FBA warehouse and creates outbound order object.
        Prepare the sale orders for creating outbound orders in amazon.
        Creates outbound shipment in Amazon for the prepared sale orders.
        @author: Maulik Barad on Date 21-Jan-2019.
        """
        sale_orders = self.search([("state", "=", "sale"),
                                   ("amz_fulfillment_by", "!=", "FBA"),
                                   ("is_fba_pending_order", "=", False),
                                   ("exported_in_amazon", "=", False)])
        fba_orders = sale_orders.filtered(lambda x: x.order_has_fba_warehouse)
        sellers = fba_orders.warehouse_id.seller_id
        for seller in sellers:
            if seller.allow_auto_create_outbound_orders:
                _logger.info("Creating Outbound Order via Scheduler.")
                orders = fba_orders.filtered(lambda x, y=seller: x.warehouse_id.seller_id == y)
                orders.with_context(is_auto_process=True).create_outbound_order()
        return True
