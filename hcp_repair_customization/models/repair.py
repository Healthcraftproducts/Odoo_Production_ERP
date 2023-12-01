from odoo import api, fields, models, tools, SUPERUSER_ID
from odoo.tools.translate import _
from odoo.tools import email_re, email_split
from datetime import datetime, timedelta, date
from odoo.exceptions import UserError, ValidationError

class RepairOrder(models.Model):
    _inherit = 'repair.order'
    
    destination_location_id = fields.Many2one('stock.location','Destination Location',domain=[('usage', '=', 'internal')],required=1)
    picking_count = fields.Integer(string="Count")
    repair_picking_id = fields.Many2one('stock.picking', string="Picking Id")
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('cancel', 'Cancelled'),
        ('confirmed', 'Confirmed'),
        ('under_repair', 'Under Repair'),
        ('ready', 'Ready to Repair'),
        ('2binvoiced', 'To be Invoiced'),
        ('invoice_except', 'Invoice Exception'),
        ('done', 'Repaired'),('transfered', 'Transfer')], string='Status',
        copy=False, default='draft', readonly=True, tracking=True,
        help="* The \'Draft\' status is used when a user is encoding a new and unconfirmed repair order.\n"
             "* The \'Confirmed\' status is used when a user confirms the repair order.\n"
             "* The \'Ready to Repair\' status is used to start to repairing, user can start repairing only after repair order is confirmed.\n"
             "* The \'To be Invoiced\' status is used to generate the invoice before or after repairing done.\n"
             "* The \'Done\' status is set when repairing is completed.\n"
             "* The \'Cancelled\' status is used when user cancel repair order.")

    def view_transfer(self):
        onboard_ids = []
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        pickings = self.mapped('repair_picking_id')
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        picking_id = pickings.filtered(lambda l: l.picking_type_id.code == 'INT')
        if picking_id:
            picking_id = picking_id[0]
        else:
            picking_id = pickings[0]
        action['context'] = dict(self._context, default_partner_id=self.partner_id.id, default_picking_type_id=picking_id.picking_type_id.id, default_origin=self.name, default_group_id=picking_id.group_id.id)
        return action

    
    def action_stock_move(self):
            if not self.destination_location_id:
                raise UserError(_(
                    " Please select a Destination Location"))
            for order in self:
                if not self.repair_picking_id:
                    pick = {
                        'picking_type_id': 5,
                        'partner_id': self.partner_id.id,
                        'origin': self.name,
                        'location_dest_id': self.destination_location_id.id,
                        'location_id': self.location_id.id
                    }
                    picking = self.env['stock.picking'].create(pick)
                    self.repair_picking_id = picking.id
                    self.picking_count = len(picking)
                    moves = order.filtered(
                        lambda r: r.product_id.type in ['product', 'consu'])._create_stock_moves(picking)
                    move_ids = moves._action_confirm()
                    move_ids._action_assign()
            self.write({'state':'transfered'})

    def _create_stock_moves(self, picking):
            moves = self.env['stock.move']
            done = self.env['stock.move'].browse()
            price_unit = self.product_id.lst_price
            template = {
                'name': self.name or '',
                'product_id': self.product_id.id,
                'product_uom': self.product_id.uom_id.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'picking_id': picking.id,
                'state': 'draft',
                'company_id': 1,
                'price_unit': price_unit,
                'picking_type_id': picking.picking_type_id.id,
                'route_ids': 1 and [
                    (6, 0, [x.id for x in self.env['stock.route'].search([('id', 'in', (2, 3))])])] or [],
                'warehouse_id': picking.picking_type_id.warehouse_id.id,
            }
            diff_quantity = self.product_qty
            tmp = template.copy()
            tmp.update({
                'product_uom_qty': diff_quantity,
            })
            template['product_uom_qty'] = diff_quantity
            done += moves.create(template)
            return done
