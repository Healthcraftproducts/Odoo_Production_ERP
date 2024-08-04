from odoo import models, fields, api
from odoo.exceptions import ValidationError

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.constrains('qty_done', 'reserved_uom_qty','is_completed')
    def _check_qty_done(self):
        for line in self:
            if line.is_completed == False and line.qty_done > line.reserved_uom_qty:
                line.qty_done = line.reserved_uom_qty
                print(line.reserved_uom_qty,"rederedvcdrfgbjhjnkkm")
                raise ValidationError('The quantity done cannot exceed the reserved quantity.')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        for move in self:
            for move_line in move.move_line_ids:
                if move_line.is_completed == False and move_line.qty_done > move_line.reserved_uom_qty:
                    raise ValidationError('The quantity done cannot exceed the reserved quantity.')
        return super(StockPicking, self).button_validate()
