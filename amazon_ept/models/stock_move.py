# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
"""
Inherited stock move to relate with the amazon
"""

from odoo import models, fields


class StockMove(models.Model):
    """
    inherited class to set Amazon Instance in Stock Picking
    """
    _inherit = "stock.move"

    amazon_instance_id = fields.Many2one('amazon.instance.ept', string='Marketplace')
    updated_in_amazon = fields.Boolean("Update Status in Amazon", default=False,
                                       help="Use only for phantom products")
    amazon_order_reference = fields.Char("Amazon Order Ref", default=False,
                                         help="Order Reference provided by Amazon")
    amazon_order_item_id = fields.Char("Amazon Order Item", default=False,
                                       help="Order Reference Item id provided by"
                                            " Amazon in Order Reference")
    amazon_shipment_id = fields.Char(size=120, string='Amazon Shipment ID', default=False,
                                     copy=False,
                                     help="Shipment Item ID provided by Amazon when we integrate "
                                          "shipment report from Amazon")

    amazon_shipment_item_id = fields.Char(size=120, string='Amazon Shipment Item ID', default=False,
                                          copy=False,
                                          help="Shipment Item ID provided by Amazon "
                                               "when we integrate shipment report from Amazon")
    tracking_number = fields.Char(string="Amazon Shipment Tracking No", size=120, default=False,
                                  copy=False)
    amz_shipment_report_id = fields.Many2one('shipping.report.request.history',
                                             string="Amazon Shipping Report Id")
    adjusted_date = fields.Datetime("Adjustment Time", copy=False)
    code_description = fields.Char("FBA Stock Adjustment Description")
    fulfillment_center_id = fields.Many2one('amazon.fulfillment.center',
                                            string='Fulfillment Center', copy=False,
                                            default=False)
    transaction_item_id = fields.Char("Transaction Item", copy=False)
    seller_id = fields.Many2one("amazon.seller.ept", "Seller")
    code_id = fields.Many2one('amazon.adjustment.reason.code', string='FBA Stock Adjustment Code',
                              copy=False)
    amz_stock_adjustment_report_id = fields.Many2one("amazon.stock.adjustment.report.history",
                                                     "Amazon Stock Adjustment Report History")
    return_created = fields.Boolean(string='FBA Return Created', default=False, copy=False,
                                    help="True, If customer return created")
    fba_returned_date = fields.Datetime("Return Date",
                                        help="When return processed in the FBA warehouse.")
    return_reason_id = fields.Many2one("amazon.return.reason.ept", string="Return Reason",
                                       help="Product Return Reason by Customer.")
    amz_return_report_id = fields.Many2one('sale.order.return.report',
                                           string="Amazon Return Report Id")
    detailed_disposition = fields.Selection(
        [('SELLABLE', 'SELLABLE'), ('DAMAGED', 'DAMAGED'),
         ('CUSTOMER_DAMAGED', 'CUSTOMER DAMAGED'),
         ('DEFECTIVE', 'DEFECTIVE'),
         ('CARRIER_DAMAGED', 'CARRIER DAMAGED'),
         ('EXPIRED', 'EXPIRED')],
        help="Product's Status while Return")
    status_ept = fields.Char(string='FBA return status', help="Status Of Returned Product")

    def _get_new_picking_values(self):
        """We need this method to set Amazon Instance in Stock Picking"""
        res = super(StockMove, self)._get_new_picking_values()
        proc_group = self.group_id
        if proc_group and proc_group.odoo_shipment_id:
            res.update({
                'partner_id': proc_group.odoo_shipment_id.address_id and
                              proc_group.odoo_shipment_id.address_id.id,
                'ship_plan_id': proc_group.odoo_shipment_id.shipment_plan_id and
                                proc_group.odoo_shipment_id.shipment_plan_id.id,
                'amazon_shipment_id': proc_group.odoo_shipment_id.shipment_id,
                'ship_label_preference': proc_group.odoo_shipment_id.label_prep_type,
                'fulfill_center': proc_group.odoo_shipment_id.fulfill_center_id,
                'odoo_shipment_id': proc_group.odoo_shipment_id.id,
                'seller_id': proc_group.odoo_shipment_id and
                             proc_group.odoo_shipment_id.shipment_plan_id and
                             proc_group.odoo_shipment_id.shipment_plan_id.instance_id.seller_id and
                             proc_group.odoo_shipment_id.shipment_plan_id.instance_id.seller_id.id or
                             False, })
        return res

    def _prepare_procurement_origin(self):
        """
        Inherited this method for set origin as removal order reference in the removal orders pickings.
        :return: picking origin
        """
        self.ensure_one()
        if self.group_id and self.group_id.removal_order_id:
            return self.origin
        return super(StockMove, self)._prepare_procurement_origin()
