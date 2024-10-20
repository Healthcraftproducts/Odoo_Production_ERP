# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Added class and method to process for outbound order operations and added method to
create and update fulfillment.
"""

import logging
from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError
from ..endpoint import DEFAULT_ENDPOINT

_logger = logging.getLogger(__name__)
AMZ_INSTANCE_EPT = 'amazon.instance.ept'
SALE_ORDER = 'sale.order'


class AmazonOutboundOrderWizard(models.TransientModel):
    """
    Added class to create outbound orders.
    """
    _name = "amazon.outbound.order.wizard"
    _description = 'Amazon Outbound Order Wizard'

    help_fulfillment_action = """
        Ship - The fulfillment order ships now
        Hold - An order hold is put on the fulfillment order.3
        Default: Ship in Create Fulfillment
        Default: Hold in Update Fulfillment    
    """

    help_fulfillment_policy = """
        FillOrKill - If an item in a fulfillment order is determined to be unfulfillable before any 
                    shipment in the order moves to the Pending status (the process of picking units 
                    from inventory has begun), then the entire order is considered unfulfillable. 
                    However, if an item in a fulfillment order is determined to be unfulfillable 
                    after a shipment in the order moves to the Pending status, Amazon cancels as 
                    much of the fulfillment order as possible
        FillAll - All fulfillable items in the fulfillment order are shipped. 
                The fulfillment order remains in a processing state until all items are either 
                shipped by Amazon or cancelled by the seller
        FillAllAvailable - All fulfillable items in the fulfillment order are shipped. 
            All unfulfillable items in the order are cancelled by Amazon.
        Default: FillOrKill
    """

    instance_id = fields.Many2one("amazon.instance.ept", "Marketplace", help="Unique Amazon Instance")
    fba_warehouse_id = fields.Many2one("stock.warehouse", "Warehouse", help="Amazon FBA Warehouse")
    sale_order_ids = fields.Many2many(SALE_ORDER, "convert_sale_order_bound_rel", "wizard_id",
                                      "sale_id", "Sales Orders",
                                      help="Sale Orders for create outbound shipments")
    fulfillment_action = fields.Selection([('Ship', 'Ship'), ('Hold', 'Hold')],
                                          default="Hold", help=help_fulfillment_action)
    displayable_date_time = fields.Date("Displayable Order Date", required=False,
                                        help="Display Date in package")
    fulfillment_policy = fields.Selection([('FillOrKill', 'FillOrKill'), ('FillAll', 'FillAll'),
                                           ('FillAllAvailable', 'FillAllAvailable')],
                                          default="FillOrKill", required=True, help=help_fulfillment_policy)
    shipment_service_level_category = fields.Selection([('Expedited', 'Expedited'), ('Standard', 'Standard'),
                                                        ('Priority', 'Priority'),
                                                        ('ScheduledDelivery', 'ScheduledDelivery')],
                                                       string="FBA Shipping Speed", default='Standard')
    delivery_start_time = fields.Datetime(help="Delivery Estimated Start Time")
    delivery_end_time = fields.Datetime(help="Delivery Estimated End Time")
    notify_by_email = fields.Boolean(default=False, help="If true then system will notify by email to followers")
    note = fields.Text(help="To set note in outbound order")

    def create_outbound_order(self):
        """
        Create Outbound orders for amazon in ERP
        @author: Keyur Kanani
        :return: True
        """
        for amazon_order in self.sale_order_ids:
            if not amazon_order.order_line:
                amazon_order.message_post(body=_("Outbound Order can not created without Order lines."))
                continue
            prod_types = list(set(amazon_order.order_line.mapped('product_type')))
            if 'service' in prod_types and len(prod_types) == 1:
                amazon_order.message_post(body=_("This order has been not exported to Amazon, "
                                                 "because all products are service type products."))
                continue
            if not amazon_order.amz_fulfillment_instance_id:
                outbound_dict = self.prepare_outbound_order_vals_ept(amazon_order)
                if self.delivery_start_time or self.delivery_end_time:
                    outbound_dict.update({'amz_delivery_start_time': self.delivery_start_time or False,
                                          'amz_delivery_end_time': self.delivery_end_time or False})
                amazon_order.write(outbound_dict)
                amazon_order.set_amazon_product_in_amz_order()
                amazon_order.create_fulfillment()
        return True

    def prepare_outbound_order_vals_ept(self, amazon_order):
        """
        Prepare values for create outbound order from odoo to amazon
        :param amazon_order: sale.order()
        :return: vals dict{}
        """
        instance = self.env[AMZ_INSTANCE_EPT]
        if self.shipment_service_level_category:
            shipment_level_category = self.shipment_service_level_category
        elif amazon_order.carrier_id and amazon_order.carrier_id.amz_outbound_shipping_level_category:
            shipment_level_category = amazon_order.carrier_id.amz_outbound_shipping_level_category
        elif self.instance_id.seller_id.shipment_category:
            shipment_level_category = self.instance_id.seller_id.shipment_category
        else:
            shipment_level_category = 'Standard'
        if self._context.get('is_auto_process', False):
            instance = instance.search(
                [('country_id', '=', amazon_order.warehouse_id.partner_id.country_id.id),
                 ('seller_id', '=', amazon_order.warehouse_id.seller_id.id)], limit=1)
        if not instance:
            instance = self.instance_id
        vals = {
            'amz_instance_id': instance.id if instance else False,
            "amz_seller_id": instance.seller_id.id if instance else False,
            'amz_fulfillment_instance_id': instance.id if instance else False,
            'amz_fulfillment_action': self.fulfillment_action,
            'warehouse_id': instance.fba_warehouse_id.id if instance else False,
            'pricelist_id': instance.pricelist_id.id if instance else False,
            'amz_displayable_date_time': self.displayable_date_time or
                                         amazon_order.date_order or False,
            'amz_fulfillment_policy': self.fulfillment_policy,
            'amz_shipment_service_level_category': shipment_level_category,
            'amz_is_outbound_order': True,
            'notify_by_email': self.notify_by_email,
            'amz_order_reference': amazon_order.name,
            'note': self.note or amazon_order.name,
        }
        return vals

    def wizard_view(self, created_id):
        """
        Added method to return the outbound order wizard.
        """
        view = self.env.ref('amazon_ept.amazon_outbound_order_wizard')
        return {
            'name': _('Amazon Outbound Orders'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'amazon.outbound.order.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': created_id and created_id.id or False,
            'context': self._context,
        }

    def create_fulfillment(self):
        """
        Create Outbound Shipment in Amazon for selected orders
        @author: Keyur Kanani
        :return: boolean
        """
        active_ids = self._context.get('active_ids', False)
        if active_ids:
            orders = self.env[SALE_ORDER].browse(active_ids)
            orders.create_fulfillment()

        return True

    def update_fulfillment(self):
        """
        Update fulfillment for Outbound Orders
        @author: Keyur Kanani
        :return: boolean
        """
        amazon_instance_obj = self.env[AMZ_INSTANCE_EPT]
        sale_order_obj = self.env[SALE_ORDER]
        active_ids = self._context.get('active_ids', False)
        progress_orders = sale_order_obj.search([('id', 'in', active_ids), ('amz_is_outbound_order', '=', True),
                                                 ('state', '=', 'sale'), ('exported_in_amazon', '=', True)])
        if progress_orders:
            instances = amazon_instance_obj.search([('fba_warehouse_id', '!=', False)])
            filtered_orders = progress_orders.filtered(lambda x: x.amz_instance_id in instances)
            for order in filtered_orders:
                data = order.get_data()
                kwargs = order.prepare_amz_outbound_order_kwargs()
                kwargs.update({'emipro_api': 'update_fulfillment_sp_api', 'data': data})
                response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
                if response.get('error', False):
                    raise UserError(_(response.get('error', {})))
                self._cr.commit()
        return True

    def cancel_fulfillment(self):
        """
        Cancel fulfillment for outbound order
        @author: Keyur Kanani
        :return: boolean
        """
        amazon_instance_obj = self.env[AMZ_INSTANCE_EPT]
        sale_order_obj = self.env[SALE_ORDER]

        active_ids = self._context.get('active_ids', False)
        progress_orders = sale_order_obj.search([('id', 'in', active_ids), ('amz_is_outbound_order', '=', True),
                                                 ('state', 'in', ['sale', 'cancel']),
                                                 ('exported_in_amazon', '=', True)])
        if progress_orders:
            instances = amazon_instance_obj.search([('fba_warehouse_id', '!=', False)])
            filtered_orders = progress_orders.filtered(lambda x: x.amz_instance_id in instances)
            for order in filtered_orders:
                # action_cancel_v13 is incomplete in MWS
                kwargs = order.prepare_amz_outbound_order_kwargs()
                kwargs.update({'emipro_api': 'cancel_fulfillment_sp_api', 'order_name': order.name})
                response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
                if response.get('error', False):
                    raise UserError(_(response.get('error', {})))
                order.is_amazon_canceled = True
                order.message_post(body=_("Order Fulfillment Successfully Cancelled in Amazon."))
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
        self.env[SALE_ORDER].auto_create_outbound_orders()
