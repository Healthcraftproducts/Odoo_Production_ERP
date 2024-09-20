from odoo import models, fields

class PurolatorShippingCharge(models.Model):
    _name = "purolator.shipping.charge"
    _rec_name = "purolator_service_id"
    _description = "Purolator Shipping Charge"


    purolator_service_id = fields.Char(string="Service Id",help="Purolator Carrier Id")
    expected_delivery_date = fields.Char(string="Expected Delivery Date")
    estimated_transit_days = fields.Char(string="Estimated Transit Days",help="EstimatedTransitDays")
    purolator_total_charge = fields.Float(string="Total Charge", help="Rate given by Purolator")
    sale_order_id = fields.Many2one("sale.order", string="Sales Order")

    def set_service(self):
        self.ensure_one()
        carrier = self.sale_order_id.carrier_id
        self.sale_order_id.purolator_shipping_charge_id = self.id
        self.sale_order_id.carrier_id = carrier.id
        self.sale_order_id.set_delivery_line(carrier, self.purolator_total_charge)#This Line Used For set updated rate in sale order line
