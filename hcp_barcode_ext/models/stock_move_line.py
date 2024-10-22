from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # def button_validate(self):
    #     for line in self.move_line_ids:
    #         if line.qty_done > line.reserved_uom_qty:
    #             raise ValidationError('The quantity done cannot exceed the product quantity.')
    #     return super(StockPicking, self).button_validate()


    def button_validate(self):
        if self.picking_type_id.code == 'internal':
            total_qty_done = sum(line.qty_done for line in self.move_line_ids)
            total_reserved_uom_qty = sum(line.reserved_uom_qty for line in self.move_line_ids)
            if total_qty_done > total_reserved_uom_qty:
                raise ValidationError('The total quantity done cannot exceed the total reserved quantity.')

        if self.picking_type_id.code == 'outgoing':
            for line in self.move_line_ids:
                if self.origin:
                    related_pickings = self.env['stock.picking'].search([
                        ('origin', '=', self.origin),
                        ('id', '!=', self.id),
                        ('picking_type_id.code', '=', 'internal')
                    ])
                    if related_pickings:
                        related_lots = related_pickings.mapped('move_line_ids.lot_id')
                        if related_lots and line.lot_id:
                            if line.lot_id not in related_lots:
                                raise ValidationError(
                                    'The lot number used in this order must match the lot number used in the related pickings.')
                if line.qty_done > line.reserved_uom_qty:
                    raise ValidationError('The quantity done cannot exceed the reserved quantity.')
        return super(StockPicking, self).button_validate()
