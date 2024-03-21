from odoo import api, fields, models, tools, SUPERUSER_ID
from odoo.tools.translate import _
from odoo.tools import email_re, email_split
from datetime import datetime, timedelta, date
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, is_html_empty, clean_context


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'
class IrActionsActWindowView(models.Model):
    _inherit = 'ir.actions.act_window.view'
class IrActionsActWindowclose(models.Model):
    _inherit = 'ir.actions.act_window_close'

class RepairOrder(models.Model):
    _inherit = 'repair.order'

    is_return_id_repair = fields.Boolean(string="Is Return")
    destination_location_id = fields.Many2one('stock.location', 'Destination Location',
                                              domain=[('usage', '=', 'internal')], required=1)
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
        ('done', 'Repaired'), ('transfered', 'Transfer')], string='Status',
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
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        picking_id = pickings.filtered(lambda l: l.picking_type_id.code == 'INT')
        if picking_id:
            picking_id = picking_id[0]
        else:
            picking_id = pickings[0]
        action['context'] = dict(self._context, default_partner_id=self.partner_id.id,
                                 default_picking_type_id=picking_id.picking_type_id.id, default_origin=self.name,
                                 default_group_id=picking_id.group_id.id)
        return action

    
    def action_stock_move(self):
        type_id = self.env['stock.picking.type'].sudo().search(
            [('name', '=', 'Returns'), ('warehouse_id', '=', 'CANADA')])
        if not self.destination_location_id:
            raise UserError(_(
                " Please select a Destination Location"))
        for order in self:
            if not self.repair_picking_id:
                pick = {
                    'picking_type_id': type_id.id,
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
        self.write({'state': 'transfered'})

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

    def action_validate(self):
        self.ensure_one()
        if self.filtered(lambda repair: any(op.product_uom_qty < 0 for op in repair.operations)):
            raise UserError(_("You can not enter negative quantities."))
        if self.product_id.type == 'consu':
            return self.action_repair_confirm()
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        available_qty_owner = self.env['stock.quant']._get_available_quantity(self.product_id, self.location_id,
                                                                              self.lot_id, owner_id=self.partner_id,
                                                                              strict=True)
        available_qty_noown = self.env['stock.quant']._get_available_quantity(self.product_id, self.location_id,
                                                                              self.lot_id, strict=True)
        repair_qty = self.product_uom._compute_quantity(self.product_qty, self.product_id.uom_id)
        for available_qty in [available_qty_owner, available_qty_noown]:
            if float_compare(available_qty, repair_qty, precision_digits=precision) >= 0:
                self.is_return_id_repair = True
                return self.action_repair_confirm()
        else:
            self.is_return_id_repair = True
            return {
                'name': self.product_id.display_name + _(': Insufficient Quantity To Repair'),
                'view_mode': 'form',
                'res_model': 'stock.warn.insufficient.qty.repair',
                'view_id': self.env.ref('repair.stock_warn_insufficient_qty_repair_form_view').id,
                'type': 'ir.actions.act_window',
                'context': {
                    'default_product_id': self.product_id.id,
                    'default_location_id': self.location_id.id,
                    'default_repair_id': self.id,
                    'default_quantity': repair_qty,
                    'default_product_uom_name': self.product_id.uom_name
                },
                'target': 'new'
            }

    def action_repair_end(self):
        """ Writes repair order state to 'To be invoiced' if invoice method is
        After repair else state is set to 'Ready'.
        @return: True
        """
        if self.filtered(lambda repair: repair.state != 'under_repair'):
            raise UserError(_("Repair must be under repair in order to end reparation."))
        self._check_product_tracking()
        for repair in self:
            self.is_return_id_repair = False
            repair.write({'repaired': True})
            vals = {'state': 'done'}
            vals['move_id'] = repair.action_repair_done().get(repair.id)
            if not repair.invoice_id and repair.invoice_method == 'after_repair':
                vals['state'] = '2binvoiced'
            repair.write(vals)
        return True

    # repair = self.env['repair.order'].browse()
    # repair.update_return_order()


class StockMove(models.Model):
    _inherit = 'stock.move'

    # is_repair_confirm = fields.Boolean("confirmed repair", compute='_compute_is_confirmed_repair_order')
    #
    # def _compute_is_confirmed_repair_order(self):
    #   for rec in self:
    #      rec.is_repair_confirm = rec.repair_id.is_return_id_repair or self.picking_id.is_return_transfer

    def _generate_valuation_lines_data(self, partner_id, qty, debit_value, credit_value, debit_account_id,
                                       credit_account_id, svl_id, description):
        self.ensure_one()
        if self.repair_id.is_return_id_repair or self.picking_id.is_return_transfer == True:
            repair_credit_account_id = self.env['account.account'].search([('code', '=', '110300')], limit=1)
            credit_line_vals = {
                'name': description,
                'product_id': self.product_id.id,
                'quantity': qty,
                'product_uom_id': self.product_id.uom_id.id,
                'ref': description,
                'partner_id': partner_id,
                'balance': -credit_value,
                'account_id': repair_credit_account_id.id,
            }
        else:
            credit_line_vals = {
                'name': description,
                'product_id': self.product_id.id,
                'quantity': qty,
                'product_uom_id': self.product_id.uom_id.id,
                'ref': description,
                'partner_id': partner_id,
                'balance': -credit_value,
                'account_id': credit_account_id,
            }

        debit_line_vals = {
            'name': description,
            'product_id': self.product_id.id,
            'quantity': qty,
            'product_uom_id': self.product_id.uom_id.id,
            'ref': description,
            'partner_id': partner_id,
            'balance': debit_value,
            'account_id': debit_account_id,
        }

        rslt = {'credit_line_vals': credit_line_vals, 'debit_line_vals': debit_line_vals}
        if credit_value != debit_value:
            # for supplier returns of product in average costing method, in anglo saxon mode
            diff_amount = debit_value - credit_value
            price_diff_account = self.env.context.get('price_diff_account')
            if not price_diff_account:
                raise UserError(
                    _('Configuration error. Please configure the price difference account on the product or its category to process this operation.'))

            rslt['price_diff_line_vals'] = {
                'name': self.name,
                'product_id': self.product_id.id,
                'quantity': qty,
                'product_uom_id': self.product_id.uom_id.id,
                'balance': -diff_amount,
                'ref': description,
                'partner_id': partner_id,
                'account_id': price_diff_account.id,
            }
        return rslt


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    is_return_transfer = fields.Boolean(string="Is Return")

    def action_confirm(self):
        self._check_company()
        if self.sale_id.carrier_id:
            self.carrier_id = self.sale_id.carrier_id
        self.mapped('package_level_ids').filtered(lambda pl: pl.state == 'draft' and not pl.move_ids)._generate_moves()
        # call `_action_confirm` on every draft move
        self.move_ids.filtered(lambda move: move.state == 'draft')._action_confirm()

        # run scheduler for moves forecasted to not have enough in stock
        self.move_ids.filtered(lambda move: move.state not in ('draft', 'cancel', 'done'))._trigger_scheduler()
        return True

    def button_validate(self):
        res = super(StockPickingInherit, self).button_validate()
        for rec in self:
            type_id = rec.env['stock.picking.type'].sudo().search(
                [('name', '=', 'Returns'), ('warehouse_id', '=', 'Amazon Canada')])
            if rec.picking_type_id.id == type_id.id:
                rec.is_return_transfer = True
            else:
                rec.is_return_transfer = False
        return res


class RepairLineExt(models.Model):
    _inherit = 'repair.line'

# To update cost price in repair line instead of sale price as per client requirement
    @api.onchange('product_id')
    def _onchange_product_uom(self):
        if self.product_id:
            self.price_unit = self.product_id.standard_price
        else:
            self.price_unit == 0.0








