from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    def button_validate(self):
        for line in self.move_line_ids:
            if line.qty_done > line.reserved_uom_qty:
                raise ValidationError('The quantity done cannot exceed the product quantity.')
        return super(StockPicking, self).button_validate()
