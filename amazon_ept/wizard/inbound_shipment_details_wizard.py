# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added method to create or update inbound shipment
"""
from odoo import models, fields, api, _


class InboundShipmentDetails(models.TransientModel):
    """
    Use: Display Inbound Shipment Details before create the Inbound Shipments When user will click
    on confirm then Shipment will be Created
    """
    _name = "inbound.shipment.details"
    _description = 'inbound.shipment.details'

    inbound_shipment_details_line_ids = fields.One2many('inbound.shipment.details.line',
                                                        'inbound_shipment_details_wizard_id',
                                                        string="Inbound Shipment Details Lines")

    @api.model
    def default_get(self, fields):
        """
        Set Shipment Details when Wizard is open
        :param fields: []
        :return: update result dict {}
        """
        shipments = self._context.get('shipments', [])
        shipment_plan_id = self._context.get('plan_id', False)
        ship_plan_rec = self.env['inbound.shipment.plan.ept'].browse(shipment_plan_id)
        instance = ship_plan_rec.instance_id
        amazon_prod_obj = self.env['amazon.product.ept']
        result = []
        res = {}

        for shipment in shipments:
            shipment_id = shipment.get('ShipmentId', '')
            fulfillment_center = shipment.get('DestinationFulfillmentCenterId', '')
            items = []
            if not isinstance(shipment.get('Items', []), list):
                items.append(shipment.get('Items', []))
            else:
                items = shipment.get('Items', [])
            for item in items:
                details_line = {}
                sku = item.get('SellerSKU', '')
                qty = float(item.get('Quantity', 0.0))
                amazon_product = amazon_prod_obj.search_amazon_product(instance and instance.id, sku, 'FBA')
                details_line.update({
                    'shipment_id': shipment_id,
                    'product_id': amazon_product.id,
                    'quantity': qty,
                    'fulfill_center_id': fulfillment_center
                })
                result.append((0, 0, details_line))
        res.update({'inbound_shipment_details_line_ids': result})
        return res

    def create_shipment(self):
        """
        Create Shipment when user confirm
        :return: ir.actions.act_window() action
        """
        address_ids = []
        odoo_shipments = []
        shipments = self._context.get('shipments', [])
        shipment_plan_id = self._context.get('plan_id', False)
        shipment_obj = self.env['amazon.inbound.shipment.ept']
        ship_plan_rec = self.env['inbound.shipment.plan.ept'].browse(shipment_plan_id)
        for shipment in shipments:
            odoo_shipment = shipment_obj.create_or_update_inbound_shipment(ship_plan_rec, shipment)
            if not odoo_shipment:
                ship_plan_rec.cancel_inbound_shipemnts(ship_plan_rec.odoo_shipment_ids)
                ship_plan_rec.write({'state': 'cancel'})
                return True
            address_ids.append(odoo_shipment.address_id.id)
            odoo_shipments.append(odoo_shipment)
        if odoo_shipments:
            ship_plan_rec.create_procurements(list(set(odoo_shipments)))
        vals = {'state': 'plan_approved'}
        if address_ids:
            address_ids = list(set(address_ids))
            vals.update({'ship_to_address_ids': [(6, 0, address_ids)]})
        ship_plan_rec.write(vals)

        return {
            'name': _('Inbound Shipments'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'amazon.inbound.shipment.ept',
            'domain': "[('id', 'in', " + str(ship_plan_rec.odoo_shipment_ids.ids) + " )]",
        }


class InboundShipmentDetailsLine(models.TransientModel):
    """
    Use: Display Inbound Shipment Details Line

    """
    _name = "inbound.shipment.details.line"
    _description = 'inbound.shipment.details.line'

    shipment_id = fields.Char(size=120, string='Shipment')
    product_id = fields.Many2one('amazon.product.ept', string="Product")
    quantity = fields.Float('Quantity')
    fulfill_center_id = fields.Char(size=120, string='Fulfillment Center',
                                    help="DestinationFulfillmentCenterId provided by Amazon "
                                         "when we send shipment Plan to Amazon")
    inbound_shipment_details_wizard_id = fields.Many2one("inbound.shipment.details",
                                                         string="Inbound Shipment Details Wizard")
