# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
inherited class and method, fields to check amazon shipment status and process to create stock move
and process to create shipment picking.
"""

import base64
import time
from odoo import models, fields, _, api
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_round
from ..endpoint import DEFAULT_ENDPOINT

AMAZON_PRODUCT_EPT = 'amazon.product.ept'

LABEL_PREFERENCE_HELP = """
        SELLER_LABEL - Seller labels the items in the inbound shipment when labels are required.
        AMAZON_LABEL_ONLY - Amazon attempts to label the items in the inbound shipment when 
                            labels are required. If Amazon determines that it does not have the 
                            information required to successfully label an item, that item is not 
                            included in the inbound shipment plan
        AMAZON_LABEL_PREFERRED - Amazon attempts to label the items in the inbound shipment when 
                                labels are required. If Amazon determines that it does not have the 
                                information required to successfully label an item, that item is 
                                included in the inbound shipment plan and the seller must label it.                    
    """

SHIPMENT_STATUS_HELP = """
        InboundShipmentHeader is used with the CreateInboundShipment operation: 
            *.WORKING - The shipment was created by the seller, but has not yet shipped.
            *.SHIPPED - The shipment was picked up by the carrier. 

        The following is an additional ShipmentStatus value when InboundShipmentHeader is used with 
        the UpdateInboundShipment operation
            *.CANCELLED - The shipment was cancelled by the seller after the shipment was 
            sent to the Amazon fulfillment center."""


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _compute_total_received_qty(self):
        """
        Added method to get total shipped and received quantity.
        """
        for picking in self:
            total_shipped_qty = 0.0
            total_received_qty = 0.0
            for move in picking.move_ids:
                if move.state == 'done':
                    total_received_qty += move.product_qty
                    total_shipped_qty += move.product_qty
                if move.state not in ['draft', 'cancel']:
                    total_shipped_qty += move.reserved_availability

            picking.total_received_qty = total_received_qty
            picking.total_shipped_qty = total_shipped_qty

    stock_adjustment_report_id = fields.Many2one('amazon.stock.adjustment.report.history',
                                                 string="Stock Adjustment Report")
    removal_order_id = fields.Many2one("amazon.removal.order.ept", string="Removal Order")
    updated_in_amazon = fields.Boolean("Updated In Amazon?", default=False, copy=False)
    is_fba_wh_picking = fields.Boolean("Is FBA Warehouse Picking", default=False)
    seller_id = fields.Many2one("amazon.seller.ept", "Seller")
    removal_order_report_id = fields.Many2one('amazon.removal.order.report.history', string="Report")
    ship_plan_id = fields.Many2one('inbound.shipment.plan.ept', readonly=True, default=False,
                                   copy=True, string="Shipment Plan")
    odoo_shipment_id = fields.Many2one('amazon.inbound.shipment.ept', string='Shipment', copy=True)
    amazon_shipment_id = fields.Char(size=120, string='Amazon Shipment ID', default=False,
                                     help="Shipment Item ID provided by Amazon when we integrate "
                                          "shipment report from Amazon")
    fulfill_center = fields.Char(size=120, string='Amazon Fulfillment Center ID', readonly=True, default=False,
                                 copy=True, help="Fulfillment Center ID provided by Amazon when we send "
                                                 "shipment Plan to Amazon")
    ship_label_preference = fields.Selection([('NO_LABEL', 'NO_LABEL'), ('SELLER_LABEL', 'SELLER_LABEL'),
                                              ('AMAZON_LABEL_ONLY', 'AMAZON_LABEL_ONLY'),
                                              ('AMAZON_LABEL_PREFERRED', 'AMAZON_LABEL_PREFERRED'),
                                              ('AMAZON_LABEL', 'AMAZON_LABEL')], default='SELLER_LABEL',
                                             string='LabelPrepType', help=LABEL_PREFERENCE_HELP)
    total_received_qty = fields.Float(compute="_compute_total_received_qty")
    total_shipped_qty = fields.Float(compute="_compute_total_received_qty")
    inbound_ship_data_created = fields.Boolean('Inbound Shipment Data Created', default=False)
    are_cases_required = fields.Boolean("AreCasesRequired", default=False,
                                        help="Indicates whether or not an inbound shipment "
                                             "contains case-packed boxes. A shipment must either "
                                             "contain all case-packed boxes or all individually "
                                             "packed boxes")
    shipment_status = fields.Selection([('WORKING', 'WORKING'), ('SHIPPED', 'SHIPPED'), ('CANCELLED', 'CANCELLED')],
                                       help=SHIPMENT_STATUS_HELP)
    estimated_arrival_date = fields.Datetime("Estimate Arrival Date")
    amazon_shipment_date = fields.Datetime("Shipment Date")
    amazon_purchase_date = fields.Datetime("Purchase Date")
    inbound_ship_updated = fields.Boolean('Inbound Shipment Updated', default=False)
    feed_submission_id = fields.Many2one('feed.submission.history', string="Feed Submission History Id", readonly=True)
    buyer_requested_cancellation = fields.Boolean(help='Is buyer request to cancel this order',
                                                  compute="_compute_buyer_cancellation_request")
    buyer_cancellation_reason = fields.Char(help='Cancellation reason provided by the buyer',
                                            compute="_compute_buyer_cancellation_request")

    @api.depends('sale_id.buyer_requested_cancellation')
    def _compute_buyer_cancellation_request(self):
        for rec in self:
            rec.buyer_requested_cancellation = rec.sale_id.buyer_requested_cancellation
            rec.buyer_cancellation_reason = rec.sale_id.buyer_cancellation_reason

    def send_to_shipper(self):
        """
        usage: If auto_processed_orders_ept = True passed in Context then we can not call send shipment from carrier
        This change is used in case of Import Shipped Orders for all connectors.
        """
        context = dict(self._context)
        if context.get('auto_processed_orders_ept', False):
            return True
        return super(StockPicking, self).send_to_shipper()

    def check_amazon_shipment_status_ept(self, items):
        """
        This method will check the shipment status and process to create stock move and move lines.
        """
        log_line_obj = self.env['common.log.lines.ept']
        stock_move_line_obj = self.env['stock.move.line']
        if self.ids:
            pickings = self

        move_obj = self.env['stock.move']
        amazon_product_obj = self.env[AMAZON_PRODUCT_EPT]

        amazon_shipment_ids = []
        for picking in pickings:
            amazon_shipment_ids.append(picking.odoo_shipment_id.id)
            instance = picking.odoo_shipment_id and picking.odoo_shipment_id.instance_id_ept or \
                       picking.ship_plan_id and picking.ship_plan_id.instance_id

            process_picking = False
            for item in items:
                sku = item.get('SellerSKU', '')
                asin = item.get('FulfillmentNetworkSKU', '')
                shipped_qty = item.get('QuantityShipped', '')
                received_qty = float(item.get('QuantityReceived', 0.0))

                if received_qty <= 0.0:
                    continue
                amazon_product = amazon_product_obj.search_amazon_product(instance.id, sku, 'FBA')
                if not amazon_product:
                    amazon_product = amazon_product_obj.search(
                        [('product_asin', '=', asin), ('instance_id', '=', instance.id),
                         ('fulfillment_by', '=', 'FBA')], limit=1)
                if not amazon_product:
                    message = """Product not found in ERP ||| FulfillmentNetworkSKU : %s 
                    SellerSKU : %s  Shipped Qty : %s Received Qty : %s""" % (asin, sku, shipped_qty, received_qty)
                    log_line_obj.create_common_log_line_ept(
                        message=message, model_name='amazon.inbound.shipment.ept', module='amazon_ept',
                        operation_type='import', res_id=picking.odoo_shipment_id.id, amz_instance_ept=instance and
                        instance.id or False, amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                    continue
                inbound_shipment_plan_line = picking.odoo_shipment_id.odoo_shipment_line_ids. \
                    filtered(lambda line, amazon_product=amazon_product: line.amazon_product_id.id == amazon_product.id)
                if inbound_shipment_plan_line:
                    inbound_shipment_plan_line[0].received_qty = received_qty or 0.0
                else:
                    vals = self.amz_prepare_inbound_shipment_plan_line_vals(amazon_product, shipped_qty,
                                                                            picking.odoo_shipment_id.id, asin,
                                                                            received_qty)
                    inbound_shipment_plan_line.create(vals)
                odoo_product_id = amazon_product.product_id.id if amazon_product else False
                done_moves = picking.odoo_shipment_id.picking_ids.filtered(
                    lambda r: r.is_fba_wh_picking and r.amazon_shipment_id == picking.amazon_shipment_id).mapped(
                    'move_ids').filtered(
                    lambda r, odoo_product_id=odoo_product_id: r.product_id.id == odoo_product_id and r.state == 'done')
                source_location_id = picking.location_id.id
                for done_move in done_moves:
                    if done_move.location_dest_id.id != source_location_id:
                        received_qty = received_qty - done_move.product_qty
                    else:
                        received_qty = received_qty + done_move.product_qty
                if received_qty <= 0.0:
                    continue
                move_lines = picking.move_ids.filtered(
                    lambda move_lines, odoo_product_id=odoo_product_id: move_lines.product_id.id == odoo_product_id and
                                                                        move_lines.state not in (
                                                                            'draft', 'done', 'cancel', 'waiting'))
                if not move_lines:
                    move_lines = picking.move_ids.filtered(
                        lambda move_line,
                               odoo_product_id=odoo_product_id: move_line.product_id.id == odoo_product_id and
                                                                move_line.state not in ('draft', 'done', 'cancel'))
                waiting_moves = move_lines and move_lines.filtered(lambda r: r.state == 'waiting')
                if waiting_moves:
                    waiting_moves.write({'state': 'assigned'})
                if not move_lines:
                    process_picking = True
                    odoo_product = amazon_product.product_id
                    move_vals = self.amz_prepare_stock_move_vals(odoo_product, received_qty, picking)
                    new_move = move_obj.create(move_vals)
                    sml_vals = self.amz_prepare_stock_move_line(odoo_product, picking, received_qty, new_move)
                    stock_move_line_obj.create(sml_vals)
                qty_left = received_qty
                for move in move_lines:
                    process_picking = True
                    if move.state == 'waiting':
                        move.write({'state': 'assigned'})
                    if qty_left <= 0.0:
                        break
                    move_line_remaning_qty = (move.product_uom_qty) - (sum(move.move_line_ids.mapped('qty_done')))
                    operations = move.move_line_ids.filtered(lambda o: o.qty_done <= 0)
                    for operation in operations:
                        if operation.reserved_uom_qty <= qty_left:
                            op_qty = operation.reserved_uom_qty
                        else:
                            op_qty = qty_left

                        move._set_quantity_done(op_qty)
                        qty_left = float_round(qty_left - op_qty,
                                               precision_rounding=operation.product_uom_id.rounding,
                                               rounding_method='UP')
                        move_line_remaning_qty = move_line_remaning_qty - op_qty
                        if qty_left <= 0.0:
                            break
                    if qty_left > 0.0 and move_line_remaning_qty > 0.0:
                        if move_line_remaning_qty <= qty_left:
                            op_qty = move_line_remaning_qty
                        else:
                            op_qty = qty_left
                        vals = self.amz_prepare_stock_move_line(move.product_id, picking, op_qty, move)
                        stock_move_line_obj.create(vals)
                        qty_left = float_round(qty_left - op_qty,
                                               precision_rounding=move.product_id.uom_id.rounding,
                                               rounding_method='UP')
                        if qty_left <= 0.0:
                            break
                move = move_lines[0] if move_lines else new_move
                if qty_left > 0.0 and move.product_id.tracking == 'none':
                    vals = self.amz_prepare_stock_move_line(amazon_product.product_id, picking, qty_left, move)
                    stock_move_line_obj.create(vals)
            if process_picking:
                picking.with_context({'auto_processed_orders_ept': True})._action_done()

        return True

    def check_qty_difference_and_create_return_picking_ept(self, amazon_shipment_id, odoo_shipment_id, instance, items):
        """
        This method will create return picking and confirm and process that.
        """
        stock_immediate_transfer_obj = self.env['stock.immediate.transfer']
        pickings = odoo_shipment_id.picking_ids.filtered(lambda picking: picking.state == 'done' and \
                                                                         picking.amazon_shipment_id == amazon_shipment_id and \
                                                                         picking.is_fba_wh_picking)
        if pickings:
            location_id = pickings[0].location_id.id
            location_dest_id = pickings[0].location_dest_id.id
            return_picking = False
            amazon_product_obj = self.env[AMAZON_PRODUCT_EPT]
            for item in items:
                sku = item.get('SellerSKU', '')
                asin = item.get('FulfillmentNetworkSKU', '')
                received_qty = float(item.get('QuantityReceived', 0.0))
                amazon_product = amazon_product_obj.search_amazon_product(instance.id, sku, 'FBA')
                if not amazon_product:
                    amazon_product = amazon_product_obj.search([('product_asin', '=', asin),
                                                                ('instance_id', '=', instance.id),
                                                                ('fulfillment_by', '=', 'FBA')],
                                                               limit=1)
                if not amazon_product:
                    continue

                done_moves = odoo_shipment_id.picking_ids.filtered(
                    lambda r: r.is_fba_wh_picking and r.amazon_shipment_id == amazon_shipment_id).mapped('move_ids'). \
                    filtered(
                    lambda r, amazon_product=amazon_product: r.product_id.id == amazon_product.product_id.id and \
                                                             r.state == 'done' and \
                                                             r.location_id.id == location_id and \
                                                             r.location_dest_id.id == location_dest_id)
                if received_qty <= 0.0 and (not done_moves):
                    continue
                for done_move in done_moves:
                    received_qty = received_qty - done_move.product_qty

                if received_qty < 0.0:
                    return_moves = odoo_shipment_id.picking_ids.filtered(
                        lambda r: r.is_fba_wh_picking and r.amazon_shipment_id == amazon_shipment_id).mapped(
                        'move_ids').filtered( \
                        lambda r, amazon_product=amazon_product: r.product_id.id == amazon_product.product_id.id and \
                                                                 r.state == 'done' and r.location_id.id == location_dest_id and \
                                                                 r.location_dest_id.id == location_id)

                    for return_move in return_moves:
                        received_qty = received_qty + return_move.product_qty
                    if received_qty >= 0.0:
                        continue
                    if not return_picking:
                        pick_type_id = pickings[0].picking_type_id.return_picking_type_id.id if pickings[
                            0].picking_type_id.return_picking_type_id else pickings[0].picking_type_id.id
                        return_picking = pickings[0].copy({
                            'move_ids': [],
                            'picking_type_id': pick_type_id,
                            'state': 'draft',
                            'origin': amazon_shipment_id,
                            'date_done': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'location_id': done_moves[0].location_dest_id.id,
                            'location_dest_id': done_moves[0].location_id.id
                        })
                    received_qty = abs(received_qty)
                    for move in done_moves:
                        if move.product_qty <= received_qty:
                            return_qty = move.product_qty
                        else:
                            return_qty = received_qty
                        amz_return_move = move.copy({
                            'product_id': move.product_id.id,
                            'product_uom_qty': abs(return_qty),
                            'picking_id': return_picking.id,
                            'state': 'draft',
                            'location_id': move.location_dest_id.id,
                            'location_dest_id': move.location_id.id,
                            'picking_type_id': pick_type_id,
                            'warehouse_id': pickings[0].picking_type_id.warehouse_id.id,
                            'origin_returned_move_id': move.id,
                            'procure_method': 'make_to_stock',
                            'move_dest_ids': [],
                        })
                        amz_return_move._action_assign()
                        amz_return_move._set_quantity_done(abs(return_qty))
                        amz_return_move._action_done()
                        received_qty = received_qty - return_qty
                        if received_qty <= 0.0:
                            break
        return True

    def amz_prepare_inbound_picking_kwargs(self, instance):
        """
        Prepare Default values for request in Amazon MWS
        :param instance: amazon.instance.ept()
        :return: dict {}
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        return {
            'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
            'app_name': 'amazon_ept_spapi',
            'account_token': account.account_token,
            'dbuuid': dbuuid,
            'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                       instance.country_id.code
        }

    def check_amazon_shipment_status(self, response):
        """
        Usage: Check Shipment Status from Amazon
        :return: True
        :rtype: boolean
        """
        amazon_shipment_ids = []
        for picking in self:
            odoo_shipment_id = picking.odoo_shipment_id and picking.odoo_shipment_id.id
            amazon_shipment_ids.append(odoo_shipment_id)
            instance = picking.odoo_shipment_id.get_instance(picking.odoo_shipment_id)
            self.amz_create_attachment_for_picking_datas(response.get('datas', {}), picking)
            process_picking = self.amz_process_inbound_picking_ept(response.get('items', {}), picking, instance)
            if process_picking:
                picking.with_context({'auto_processed_orders_ept': True})._action_done()
        return True

    def amz_process_inbound_picking_ept(self, items, picking, instance):
        """
        Process for stock move and stock move line if Quantity received values are changed to process picking.
        :param response: items dict
        :param picking: stock.picking()
        :param instance: amazon.instance.ept()
        :return: True / False
        :rtype: Boolean
        """
        move_obj = self.env['stock.move']
        stock_move_line_obj = self.env['stock.move.line']
        process_picking = False
        for item in items:
            received_qty = float(item.get('QuantityReceived', 0.0))
            if received_qty <= 0.0:
                continue
            amazon_product = self.amz_get_inbound_amazon_products_ept(instance, picking, item)
            if not amazon_product:
                continue
            self.amz_inbound_shipment_plan_line_ept(picking.odoo_shipment_id, amazon_product, item)
            odoo_product_id = amazon_product.product_id if amazon_product else False
            received_qty = self.amz_find_received_qty_from_done_moves(picking.odoo_shipment_id,
                                                                      odoo_product_id,
                                                                      received_qty,
                                                                      picking.amazon_shipment_id)
            if received_qty <= 0.0:
                continue
            stock_move = self.amz_inbound_get_stock_move_ept(picking, odoo_product_id)
            if not stock_move:
                process_picking = True
                sm_vals = self.amz_prepare_stock_move_vals(amazon_product.product_id, received_qty,
                                                           picking)
                new_move = move_obj.create(sm_vals)
                sml_vals = self.amz_prepare_stock_move_line(amazon_product.product_id, picking,
                                                            received_qty, new_move)
                stock_move_line_obj.create(sml_vals)
            qty_left = received_qty
            for move in stock_move:
                process_picking = True
                if move.state == 'waiting':
                    move.write({'state': 'assigned'})
                if qty_left <= 0.0:
                    break
                move_line_remaning_qty = (move.product_uom_qty) - (sum(move.move_line_ids.mapped('qty_done')))

                operations = move.move_line_ids.filtered(lambda o: o.qty_done <= 0)
                for operation in operations:
                    op_qty = operation.reserved_uom_qty if operation.reserved_uom_qty <= qty_left else qty_left
                    move._set_quantity_done(op_qty)
                    qty_left = float_round(qty_left - op_qty,
                                           precision_rounding=operation.product_uom_id.rounding,
                                           rounding_method='UP')
                    move_line_remaning_qty = move_line_remaning_qty - op_qty
                    if qty_left <= 0.0:
                        break
                if qty_left > 0.0 and move_line_remaning_qty > 0.0:
                    op_qty = move_line_remaning_qty if move_line_remaning_qty <= qty_left else qty_left
                    sml_vals = self.amz_prepare_stock_move_line(move.product_id, picking, op_qty,
                                                                move)
                    stock_move_line_obj.create(sml_vals)
                    qty_left = float_round(qty_left - op_qty,
                                           precision_rounding=move.product_id.uom_id.rounding,
                                           rounding_method='UP')
                    if qty_left <= 0.0:
                        break
            move = stock_move[0] if stock_move else new_move
            if qty_left > 0.0 and move.product_id.tracking == 'none':
                sml_vals = self.amz_prepare_stock_move_line(amazon_product.product_id, picking, qty_left, move)
                stock_move_line_obj.create(sml_vals)
        return process_picking

    @staticmethod
    def amz_inbound_get_stock_move_ept(picking, odoo_product_id):
        """
        Filter and get stock moves
        :param picking:
        :param odoo_product_id:
        :return: stock.move()
        """
        stock_move = picking.move_ids.filtered(lambda r: r.product_id.id == odoo_product_id.id and
                                                         r.state not in ('draft', 'done', 'cancel', 'waiting'))
        if not stock_move:
            stock_move = picking.move_ids.filtered(lambda r: r.product_id.id == odoo_product_id.id and
                                                             r.state not in ('draft', 'done', 'cancel'))
        waiting_moves = stock_move and stock_move.filtered(lambda r: r.state == 'waiting')
        if waiting_moves:
            waiting_moves.write({'state': 'assigned'})
        return stock_move

    def amz_create_attachment_for_picking_datas(self, response, picking):
        """
        Get xml response from amazon mws and store it as attachment for future reference only.
        :param response: response.get('datas')
        :param picking: stock.picking()
        :return: boolean
        """
        for data in response:
            file_name = 'inbound_shipment_report_%s.xml' % picking.id
            if data.get('origin', {}):
                attachment = self.env['ir.attachment'].create({
                    'name': file_name,
                    'datas': base64.b64encode((data.get('origin', {})).encode('utf-8')),
                    'res_model': 'mail.compose.message',
                })
                picking.message_post(body=_("<b> Inbound Shipment Report Downloaded </b>"),
                                     attachment_ids=attachment.ids)
        return True

    @staticmethod
    def amz_prepare_stock_move_vals(odoo_product, qty, picking):
        """
        Prepare Amazon Stock move Values
        :param odoo_product: product.product()
        :param qty: float
        :param picking: stock.picking()
        :return: dict {}
        """
        return {
            'name': _('New Move: {}').format(odoo_product.display_name),
            'product_id': odoo_product.id,
            'product_uom_qty': qty,
            'product_uom': odoo_product.uom_id.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'picking_id': picking.id,
        }

    @staticmethod
    def amz_prepare_stock_move_line(odoo_product, picking, qty, move):
        """
        Prepare Stock move line values
        :param odoo_product: product.product()
        :param picking: stock.picking()
        :param qty: float
        :param move: stock.move()
        :return: dict {}
        """
        return {
            'product_id': odoo_product.id,
            'product_uom_id': odoo_product.uom_id.id,
            'picking_id': picking.id,
            'qty_done': float(qty) or 0,
            'result_package_id': False,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'move_id': move.id,
        }

    @staticmethod
    def amz_find_received_qty_from_done_moves(odoo_shipment_id, odoo_product_id, received_qty,
                                              amazon_shipment_id):
        """
        Find Done Moves from all fba warehouse pickings of inbound Shipment.
        then calculate received qty if any from done moves of Inbound Shipment.
        :param picking: stock.picking()
        :param odoo_product_id: product.product()
        :param received_qty: float
        :return: received_qty(float)
        """
        ship_pickings = odoo_shipment_id.picking_ids.filtered(
            lambda r: r.amazon_shipment_id == amazon_shipment_id and r.is_fba_wh_picking)
        done_moves = ship_pickings.mapped('move_ids').filtered(
            lambda r: r.product_id.id == odoo_product_id.id and r.state == 'done').sorted(key=lambda x: x.id)
        source_location_id = done_moves and done_moves[0].location_id.id
        for done_move in done_moves:
            if done_move.location_dest_id.id != source_location_id:
                received_qty = received_qty - done_move.product_qty
            else:
                received_qty = received_qty + done_move.product_qty
        return received_qty

    def amz_inbound_shipment_plan_line_ept(self, odoo_shipment_id, amazon_product, item):
        """
        Create Inbound Shipment Plan Line values if inbound shipment with amazon product not found.
        :param odoo_shipment_id: shipment record.
        :param amazon_product: amazon.product.ept()
        :param item: dict {}
        :return: boolean
        """
        inbound_shipment_plan_line_obj = self.env['inbound.shipment.plan.line']
        asin = item.get('FulfillmentNetworkSKU', '')
        shipped_qty = item.get('QuantityShipped', 0.0)
        received_qty = float(item.get('QuantityReceived', 0.0))
        inbound_shipment_plan_line_id = odoo_shipment_id.odoo_shipment_line_ids. \
            filtered(lambda line: line.amazon_product_id.id == amazon_product.id)
        if inbound_shipment_plan_line_id:
            inbound_shipment_plan_line_id[0].received_qty = received_qty or 0.0
        else:
            vals = self.amz_prepare_inbound_shipment_plan_line_vals(amazon_product, shipped_qty, odoo_shipment_id.id,
                                                                    asin, received_qty)
            inbound_shipment_plan_line_obj.create(vals)
        return True

    def amz_get_inbound_amazon_products_ept(self, instance, picking, item):
        """
        Search Product from amazon products
        :param instance: amazon.instance.ept()
        :param picking: stock.picking()
        :param item: dict{}
        :return: amazon_product
        """
        amazon_product_obj = self.env[AMAZON_PRODUCT_EPT]
        sku = item.get('SellerSKU', '')
        asin = item.get('FulfillmentNetworkSKU', '')
        shipped_qty = item.get('QuantityShipped', 0.0)
        received_qty = float(item.get('QuantityReceived', 0.0))
        amazon_product = amazon_product_obj.search_amazon_product(instance.id, sku, 'FBA')
        if not amazon_product:
            amazon_product = amazon_product_obj.search([('product_asin', '=', asin), ('instance_id', '=', instance.id),
                                                        ('fulfillment_by', '=', 'FBA')], limit=1)
        if not amazon_product:
            picking.message_post(body=_("""Product not found in ERP |||
                                                        FulfillmentNetworkSKU : {}
                                                        SellerSKU : {}  
                                                        Shipped Qty : {}
                                                        Received Qty : {}                          
                                                     """.format(asin, sku, shipped_qty, received_qty)))
        return amazon_product

    @staticmethod
    def amz_prepare_inbound_shipment_plan_line_vals(amazon_product, shipped_qty, odoo_shipment_id, asin, received_qty):
        """
        Prepare Amazon Inbound Shipment Plan Line values.
        :param amazon_product: amazon.product.ept()
        :param shipped_qty: float
        :param odoo_shipment_id: int
        :param asin: char
        :param received_qty: float
        :return: dict {}
        """
        return {
            'amazon_product_id': amazon_product.id,
            'quantity': shipped_qty or 0.0,
            'odoo_shipment_id': odoo_shipment_id,
            'fn_sku': asin,
            'received_qty': received_qty,
            'is_extra_line': True
        }

    @staticmethod
    def get_amazon_label_prep_type(odoo_shipment, ship_plan):
        """
        This method will return label prep type
        """
        if not odoo_shipment.shipment_id or not odoo_shipment.fulfill_center_id:
            raise UserError(_('You must have to first create Inbound Shipment Plan.'))
        label_prep_type = odoo_shipment.label_prep_type
        if label_prep_type == 'NO_LABEL':
            label_prep_type = 'SELLER_LABEL'
        elif label_prep_type == 'AMAZON_LABEL':
            label_prep_type = ship_plan.label_preference
        return label_prep_type

    def get_inbound_shipment_line_product(self, move, instance):
        """
        This method will search the amazon product
        return : amazon product record if found other wise raise User Error
        """
        amazon_product_obj = self.env[AMAZON_PRODUCT_EPT]
        amazon_product = amazon_product_obj.search([('product_id', '=', move.product_id.id),
                                                    ('instance_id', '=', instance.id),
                                                    ('fulfillment_by', '=', 'FBA')], limit=1)
        if not amazon_product:
            raise UserError(_("Amazon Product is not available for this %s product code" % (
                move.product_id.default_code)))
        return amazon_product

    def check_qty_difference_and_create_return_picking(self, response, amazon_shipment_id, odoo_shipment_id,
                                                       instance):
        """
        Check quantity difference and create return picking if required.
        :param response: amazon inbound shipment response
        :param amazon_shipment_id: amazon shipment id - str
        :param odoo_shipment_id: odoo shipment id - str
        :param instance: amazon.instance.ept()
        :return: stock.picking() object or FALSE
        """
        amazon_product_obj = self.env[AMAZON_PRODUCT_EPT]
        return_picking = False
        pick_type_id = False
        pickings = self.search([('state', '=', 'done'), ('odoo_shipment_id', '=', odoo_shipment_id),
                                ('amazon_shipment_id', '=', amazon_shipment_id), ('is_fba_wh_picking', '=', True)],
                               order="id", limit=1)
        location_id = pickings.location_id.id
        location_dest_id = pickings.location_dest_id.id
        for item in response.get('items', {}):
            sku = item.get('SellerSKU', '')
            asin = item.get('FulfillmentNetworkSKU', '')
            received_qty = float(item.get('QuantityReceived', 0.0))
            amazon_product = amazon_product_obj.search_amazon_product(instance.id, sku, 'FBA')
            if not amazon_product:
                amazon_product = amazon_product_obj.search(
                    [('product_asin', '=', asin), ('instance_id', '=', instance.id),
                     ('fulfillment_by', '=', 'FBA')], limit=1)
            if not amazon_product:
                continue
            shipment_pickings = self.search(
                [('odoo_shipment_id', '=', odoo_shipment_id), ('is_fba_wh_picking', '=', True),
                 ('amazon_shipment_id', '=', amazon_shipment_id)])
            done_moves = shipment_pickings.mapped('move_ids').filtered(
                lambda r, amazon_product=amazon_product: r.state == 'done' and
                                                         r.product_id.id == amazon_product.product_id.id and
                                                         r.location_dest_id.id == location_dest_id and
                                                         r.location_id.id == location_id)
            if received_qty <= 0.0 and (not done_moves):
                continue
            for done_move in done_moves:
                received_qty = received_qty - done_move.product_qty
            if received_qty < 0.0:
                return_moves = shipment_pickings.move_ids.filtered(
                    lambda r, amazon_product=amazon_product: r.product_id.id == amazon_product.product_id.id and
                                                             r.state == 'done' and
                                                             r.location_id.id == location_dest_id and
                                                             r.location_dest_id.id == location_id)
                for return_move in return_moves:
                    received_qty = received_qty + return_move.product_qty
                if received_qty >= 0.0:
                    continue
                if not return_picking:
                    pick_type_id = pickings.picking_type_id.return_picking_type_id.id if pickings.picking_type_id.return_picking_type_id else pickings.picking_type_id.id
                    return_picking = self.copy_amazon_picking_data(pickings, pick_type_id, amazon_shipment_id, done_moves)
                    self.amz_create_attachment_for_picking_datas(response.get('datas', {}), return_picking)
                received_qty = abs(received_qty)
                for move in done_moves:
                    if move.product_qty <= received_qty:
                        return_qty = move.product_qty
                    else:
                        return_qty = received_qty
                    # create stock move and stock move line for process return picking
                    amz_return_move = self.amz_copy_stock_move_data_ept(move, return_picking, return_qty,
                                                                        pickings, pick_type_id)
                    amz_return_move._action_assign()
                    amz_return_move._set_quantity_done(abs(return_qty))
                    amz_return_move._action_done()

                    received_qty = received_qty - return_qty
                    if received_qty <= 0.0:
                        break
        return return_picking

    @staticmethod
    def amz_copy_stock_move_data_ept(move, return_picking, received_qty, pickings, pick_type_id):
        """
        Copy of stock move for count received quantity.
        :param move: stock.move()
        :param return_picking: stock.picking()
        :param received_qty: float
        :param pickings:
        :param pick_type_id:
        :return: stock.move()
        """
        return move.copy({
            'product_id': move.product_id.id,
            'product_uom_qty': abs(received_qty),
            'picking_id': return_picking.id if return_picking else False,
            'state': 'draft',
            'location_id': move.location_dest_id.id,
            'location_dest_id': move.location_id.id,
            'picking_type_id': pick_type_id,
            'warehouse_id': pickings.picking_type_id.warehouse_id.id,
            'origin_returned_move_id': move.id,
            'procure_method': 'make_to_stock',
            'move_dest_ids': [],
        })

    @staticmethod
    def copy_amazon_picking_data(pickings, pick_type_id, amazon_shipment_id, done_moves):
        """
        Copy picking for create return Pickings
        :param pickings:
        :param pick_type_id:
        :param amazon_shipment_id:
        :param done_moves:
        :return:
        """
        return pickings.copy({
            'move_ids': [],
            'picking_type_id': pick_type_id,
            'state': 'draft',
            'origin': amazon_shipment_id,
            'location_id': done_moves[0].location_dest_id.id,
            'location_dest_id': done_moves[0].location_id.id,
        })
