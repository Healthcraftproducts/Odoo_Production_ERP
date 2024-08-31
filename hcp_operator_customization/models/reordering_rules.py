from odoo import api, fields, models, _

class Orderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    safety_stock = fields.Float(string="Safety Stock")

