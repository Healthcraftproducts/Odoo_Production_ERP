from odoo import models, fields, api, _
from odoo.exceptions import UserError
class SaleOrder(models.Model):
    _inherit = "sale.order"

    purolator_shipping_charge_ids = fields.One2many("purolator.shipping.charge", "sale_order_id", string="Purolator Rate ")
    purolator_shipping_charge_id = fields.Many2one("purolator.shipping.charge", string="Purolator Service")

    # def set_delivery_line(self, carrier, amount):
    #     # Remove delivery products from the sales order
    #     self._remove_delivery_line()
    #     for order in self:
    #         if order.state not in ('draft', 'sent'):
    #             raise UserError(_('You can add delivery price only on unconfirmed quotations.'))
    #         elif not carrier:
    #             raise UserError(_('No carrier set for this order.'))
    #         else:
    #             price_unit = amount
    #             # TODO check whether it is safe to use delivery_price here
    #             order._create_delivery_line(carrier, price_unit)
    #     return True