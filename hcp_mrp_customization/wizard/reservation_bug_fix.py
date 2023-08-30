# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models, fields, api
import pdb

class StockQuant(models.Model):
    _inherit = "stock.quant"

    def update_reserved_qty(self):
        for quant in self:
            # move_lines1 = self.env["stock.move.line"].sudo().search(
            #     [("product_id", "=", quant.product_id.id),
            #         ("location_id", "=", quant.location_id.id),
            #         ("lot_id", "=", quant.lot_id.id),
            #         ("package_id", "=", quant.package_id.id),
            #         ("owner_id", "=", quant.owner_id.id),
            #         ("product_qty", "=", 0),
            #         ("picking_id.state", "=", 'done'),
            #     ]
            # )
            # for line1 in move_lines1:
            #     line1.sudo().write({'product_uom_qty': 0})
            move_lines = self.env["stock.move.line"].sudo().search(
                [("product_id", "=", quant.product_id.id),
                    ("location_id", "=", quant.location_id.id),
                    ("lot_id", "=", quant.lot_id.id),
                    ("package_id", "=", quant.package_id.id),
                    ("owner_id", "=", quant.owner_id.id),
                    ("product_qty", "!=", 0),
                ]
            )
            reserved_quantity=0
            for line in move_lines:
                reserved_quantity += line.product_uom_qty
            quant.sudo().write({'reserved_quantity':reserved_quantity})
        return True

class StockReport(models.TransientModel):
    _name = "reservation.bug.fix.wizard"
    _description = "Reservation Bug Fix Update Wizard"

    def update_reserved_qty_stock_quant(self):
        record_ids = self._context.get('active_ids')
        if record_ids:
            for rec in record_ids:
                quants = self.env['stock.quant'].browse(rec)
                for item in quants:
                    item.update_reserved_qty()
        return True
