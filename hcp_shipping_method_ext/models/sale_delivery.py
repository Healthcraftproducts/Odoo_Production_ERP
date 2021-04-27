from odoo import models, fields, api, _, SUPERUSER_ID, tools
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
from odoo.addons import decimal_precision as dp


class SaleOrder(models.Model):
    _inherit = "sale.order"


    partner_country_name = fields.Char('Partner Country',compute="compute_country_id",store=True)


    @api.depends('partner_shipping_id','partner_shipping_id.country_id')
    def compute_country_id(self):
        for rec in self:
            if rec.partner_shipping_id:
                rec.partner_country_name = rec.partner_shipping_id.country_id.name

class AccountMove(models.Model):
    _inherit = "account.move"


    partner_country_name = fields.Char('Delivery Country',compute="compute_country_id",store=True)

    @api.depends('partner_shipping_id', 'partner_shipping_id.country_id')
    def compute_country_id(self):
        for rec in self:
            if rec.partner_shipping_id:
                rec.partner_country_name = rec.partner_shipping_id.country_id.name

class StockPicking(models.Model):
    _inherit = "stock.picking"

    partner_country_name = fields.Char('Delivery Country', compute="compute_country_id", store=True)

    def add_delivery_cost_to_so(self):
        self._add_delivery_cost_to_so()
        return

    def _add_delivery_cost_to_so(self):
        self.ensure_one()
        res = super(StockPicking,self)._add_delivery_cost_to_so()
        sale_order = self.sale_id
        if sale_order and sale_order.shipment_pay_policy == 'post_pay' and self.carrier_id.delivery_type=='fixed' and self.carrier_price:
            delivery_lines = sale_order.order_line.filtered(lambda l: l.is_delivery  and l.product_id == self.carrier_id.product_id)
            carrier_price = self.carrier_price * (1.0 + (float(self.carrier_id.margin) / 100.0))
            if not delivery_lines:
                sale_order._create_delivery_line(self.carrier_id, carrier_price)
            else:
                delivery_line = delivery_lines[0]
                delivery_line[0].write({
                    'price_unit': carrier_price,
                    # remove the estimated price from the description
                    # 'name': sale_order.carrier_id.with_context(lang=self.partner_id.lang).name,
                })
        return res

    @api.depends('partner_id', 'partner_id.country_id')
    def compute_country_id(self):
        for rec in self:
            if rec.partner_id:
                rec.partner_country_name = rec.partner_id.country_id.name




