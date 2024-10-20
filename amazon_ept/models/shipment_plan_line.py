# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class inbound shipment plan line and method to prepare dict to update shipment in amazon
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class InboundShipmentPlanLine(models.Model):
    """
    Added class to prepare dict and process to update shipment in amazon.
    """
    _name = "inbound.shipment.plan.line"
    _description = 'Inbound Shipment Plan Line'

    amazon_product_id = fields.Many2one('amazon.product.ept', string='Amazon Product',
                                        domain=[('fulfillment_by', '=', 'FBA')])
    odoo_product_id = fields.Many2one('product.product', related="amazon_product_id.product_id", string="Odoo Product")
    quantity = fields.Float(string="Quantity")
    seller_sku = fields.Char(size=120, string='Seller SKU', related="amazon_product_id.seller_sku", readonly=True)
    shipment_plan_id = fields.Many2one('inbound.shipment.plan.ept', string='Shipment Plan')
    odoo_shipment_id = fields.Many2one('amazon.inbound.shipment.ept', string='Shipment')
    fn_sku = fields.Char(size=120, string='Fulfillment Network SKU', readonly=True,
                         help="Provided by Amazon when we send shipment to Amazon")
    quantity_in_case = fields.Float(string="Quantity in Case", help="Amazon FBA: Quantity In Case.")
    received_qty = fields.Float(string="Received Quantity", default=0.0, copy=False, help="Received Quantity")
    difference_qty = fields.Float(string="Difference Quantity", compute="_compute_total_difference_qty",
                                  help="Difference Quantity")
    is_extra_line = fields.Boolean(string="Extra Line ?", default=False, help="Extra Line ?")

    def _compute_total_difference_qty(self):
        for shipment_line in self:
            shipment_line.difference_qty = shipment_line.quantity - shipment_line.received_qty

    @api.constrains('amazon_product_id', 'shipment_plan_id', 'odoo_shipment_id')
    def _check_unique_line(self):
        """
        Check if added amazon product is available in inbound shipment or not.
        :return:
        """
        lines = False
        for shipment_line in self:
            if shipment_line.odoo_shipment_id:
                shipment_lines = shipment_line.odoo_shipment_id.mapped('odoo_shipment_line_ids')
            else:
                shipment_lines = shipment_line.shipment_plan_id.mapped('shipment_line_ids')
            if shipment_lines:
                lines = shipment_lines.filtered(
                    lambda line, shipment_line=shipment_line: line.id != shipment_line.id and
                    line.amazon_product_id.id == shipment_line.amazon_product_id.id)
            if lines and not shipment_line._context.get('ignore_rule', False):
                raise UserError(_('Product %s line already exist in Shipping plan Line.' % (
                    shipment_line.amazon_product_id.seller_sku)))

    def process_shipment_to_prepare_sku_qty_list(self, item, line, odoo_shipment, sku_qty_list):
        """
        This method will process the shipment lines to prepare sku qty list
        """
        ship_plan = odoo_shipment.shipment_plan_id
        sku = item.get('SellerSKU', '')
        qty = float(item.get('Quantity', 0.0))
        fn_sku = item.get('FulfillmentNetworkSKU', '')
        quantity_in_case = 0
        line = line[0] if len(line) > 1 else line
        if odoo_shipment.shipment_plan_id.is_are_cases_required:
            quantity_in_case = float(item.get('QuantityInCase', 0.0)) or line.quantity_in_case
        values = {'odoo_shipment_id': odoo_shipment.id, 'fn_sku': fn_sku, 'quantity_in_case': line.quantity_in_case}
        amazon_product = line.amazon_product_id
        if line.quantity == qty:
            line.write(values)
        else:
            qty_left = line.quantity - qty
            values.update({'quantity': qty})
            line.write(values)
            self.with_context({'ignore_rule': True}).create(
                {'quantity': qty_left, 'amazon_product_id': amazon_product.id,
                 'shipment_plan_id': ship_plan.id, 'odoo_shipment_id': False,
                 'quantity_in_case': quantity_in_case, 'fn_sku': fn_sku})
        sku_qty_list.append({'SellerSKU': sku, 'QuantityShipped': int(qty), 'QuantityInCase': int(quantity_in_case)})
        return sku_qty_list

    def prepare_shipment_plan_line_dict(self, odoo_shipment, items):
        """
        This method will prepare the shipment plan line dict
        param odoo shipment : shipment record
        param items : list of dict
        return : dict
        """
        ship_plan = odoo_shipment.shipment_plan_id
        sku_qty_list = []
        for item in items:
            sku = item.get('SellerSKU', '')
            qty = float(item.get('Quantity', 0.0))
            line = ship_plan.shipment_line_ids.filtered(lambda shipment_line, sku=sku: shipment_line.seller_sku == sku)
            quantity_in_case = 0
            if odoo_shipment.shipment_plan_id.is_are_cases_required:
                plan_line = line[0] if len(line) > 1 else line
                quantity_in_case = float(item.get('QuantityInCase', 0.0)) or plan_line.quantity_in_case
            if line and len(line) > 1:
                line = line.filtered(lambda shipment_line: shipment_line.odoo_shipment_id.id == odoo_shipment.id)
                if not line:
                    line = ship_plan.shipment_line_ids.filtered(
                        lambda shipment_line, sku=sku: shipment_line.seller_sku == sku and not shipment_line.odoo_shipment_id)
            if line:
                sku_qty_list = self.process_shipment_to_prepare_sku_qty_list(item, line, odoo_shipment, sku_qty_list)
            else:
                sku_qty_list.append({'SellerSKU': sku, 'QuantityShipped': int(qty),
                                     'QuantityInCase': int(quantity_in_case)})
        return sku_qty_list
