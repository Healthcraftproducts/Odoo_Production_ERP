from odoo import fields, models, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    purolator_piece_pin = fields.Char(string="Purolator Piece PIN",copy=False)