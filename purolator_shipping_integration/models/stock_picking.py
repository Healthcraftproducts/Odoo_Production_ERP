from odoo import fields, models, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    purolator_shipment_pin = fields.Char(string="Purolator Shipment PIN",copy=False)