from odoo import api, fields, models, _


class HelpdeskTicketInherit(models.Model):
    _inherit = 'helpdesk.ticket'

    product_ids = fields.Many2many('product.product', 'sale_order_product_ids_rel', string='Products')
    pickup_cost_currency_id = fields.Many2one('res.currency', string='Currency')
    pickup_cost = fields.Monetary(string='Pickup Cost', currency_field='pickup_cost_currency_id')
    re_shipment_cost = fields.Monetary(string='Re-Shipment Cost', currency_field='pickup_cost_currency_id')
    additional_shipment_cost = fields.Monetary(string='Additional Shipment Cost', currency_field='pickup_cost_currency_id')

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            order_line_products = self.sale_order_id.order_line.mapped('product_id')
            domain = [('id', 'in', order_line_products.ids), ('detailed_type', '=', 'product')]
            if self.sale_order_id.partner_id:
                self.write({'partner_id': self.sale_order_id.partner_id.id})
            return {'domain': {'product_ids': domain}}
        else:
            return {'domain': {'product_ids': [('detailed_type', '=', 'product')]}}

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            return {'domain': {'sale_order_id': [('partner_id', '=', self.partner_id.id)]}}
        else:
            return {'domain': {'sale_order_id': []}}
