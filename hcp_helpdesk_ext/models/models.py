from dataclasses import field

from odoo import api, fields, models, _, exceptions
from odoo.exceptions import UserError

class HelpdeskTicketInherit(models.Model):
    _inherit = 'helpdesk.ticket'

    ticket_line_ids = fields.One2many('helpdesk.ticket.line', 'ticket_id', string='Ticket Lines')
    shipping_cost_line_ids = fields.One2many('helpdesk.shipping.cost.line','ticket_id',string='Shipping Cost Lines')
    product_ids = fields.Many2many('product.product', 'sale_order_product_ids_rel', string='Products')
    helpdesk_account_payable = fields.Many2one('account.account',string="Account Payable")
    helpdesk_journal_id = fields.Many2one('account.journal',string="Journal")
    delivery_order_count = fields.Integer(string='Delivery Orders', compute='_compute_helpdesk_delivery_order_ids')
    helpdesk_delivery_order_ids = fields.Many2many('stock.picking', string="Delivery Orders",
                                          relation='rel_helpdesk_delivery_order_ids', readonly=True, store=True,
                                          copy=False, compute='_compute_helpdesk_delivery_order_ids')
    helpdesk_journal_entry_ids = fields.Many2many('account.move', string="Journal Entries",
                                          relation='rel_helpdesk_journal_entry_ids', readonly=True, store=True,
                                          copy=False, compute='_compute_helpdesk_journal_entry_count')
    journal_entry_count = fields.Integer(string='Journal Entries', compute='_compute_helpdesk_journal_entry_count')
    warehouse_id = fields.Many2one('stock.warehouse',string="Warehouse")
    partner_shipping_id = fields.Many2one(
        comodel_name='res.partner',
        string="Delivery Address",
        compute='_compute_partner_shipping_id',
        store=True, readonly=False, required=True, precompute=True,)

    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    price_total = fields.Monetary(string='Total', compute='_compute_price_total', store=True)
    accounting_total = fields.Monetary(string='Total', compute='_compute_price_total', store=True)

    @api.depends('ticket_line_ids.line_amount', 'ticket_line_ids.product_id.detailed_type','shipping_cost_line_ids.line_amount', 'shipping_cost_line_ids.product_id.detailed_type')
    def _compute_price_total(self):
        for record in self:
            acc_total = 0
            total = 0
            for line in record.ticket_line_ids:
                total += line.line_amount
            for shp_line in record.shipping_cost_line_ids:
                if shp_line.product_id.detailed_type == 'service':
                    acc_total += shp_line.line_amount
            record.accounting_total = acc_total
            record.price_total = total

    @api.depends('partner_id')
    def _compute_partner_shipping_id(self):
        for order in self:
            order.partner_shipping_id = order.partner_id.address_get(['delivery'])['delivery'] if order.partner_id else False

    @api.model
    def _get_default_warehouse(self):
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        return warehouse.id if warehouse else False

    @api.model
    def create(self, vals):
        if 'warehouse_id' not in vals:
            vals['warehouse_id'] = self._get_default_warehouse()
        return super(HelpdeskTicketInherit, self).create(vals)

    def write(self, vals):
        if 'warehouse_id' not in vals:
            vals['warehouse_id'] = self._get_default_warehouse()
        return super(HelpdeskTicketInherit, self).write(vals)


    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            order_line_products = self.sale_order_id.order_line.mapped('product_id')
            product_domain = [('id', 'in', order_line_products.ids), ('detailed_type', '=', 'product')]
            partner_domain = [('id', '=', self.sale_order_id.partner_id.id)]
            if self.sale_order_id.partner_id:
                return {
                    'domain': {
                        'product_ids': product_domain,
                        'partner_id': partner_domain
                    }
                }
        else:
            return {
                'domain': {
                    'product_ids': [('detailed_type', '=', 'product')],
                    'partner_id': []
                }
            }

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            return {'domain': {'sale_order_id': [('partner_id', '=', self.partner_id.id)]}}
        else:
            return {'domain': {'sale_order_id': []}}

    @api.depends('helpdesk_journal_entry_ids', 'journal_entry_count')
    def _compute_helpdesk_journal_entry_count(self):
        for record in self:
            domain = [('helpdesk_id', '=', record.id)]
            helpdesk_journal_entry_ids = self.env['account.move'].sudo().search(domain)
            record.helpdesk_journal_entry_ids = helpdesk_journal_entry_ids
            record.journal_entry_count = len(helpdesk_journal_entry_ids)

    def action_view_journal_entries(self):
        journal_entries = self.env['account.move'].search([('helpdesk_id', '=', self.id)])
        action = self.env.ref('account.action_move_journal_line').read()[0]
        if len(journal_entries) > 1:
            action['domain'] = [('id', 'in', journal_entries.ids)]
        elif len(journal_entries) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = journal_entries.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.depends('helpdesk_delivery_order_ids','delivery_order_count')
    def _compute_helpdesk_delivery_order_ids(self):
        for record in self:
            domain = [('helpdesk_id', '=', record.id)]
            helpdesk_delivery_order_ids = self.env['stock.picking'].sudo().search(domain)
            record.helpdesk_delivery_order_ids = helpdesk_delivery_order_ids
            record.delivery_order_count = len(helpdesk_delivery_order_ids)

    def action_view_delivery_orders(self):
        delivery_orders = self.env['stock.picking'].search([('helpdesk_id', '=', self.id)])
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        if len(delivery_orders) > 1:
            action['domain'] = [('id', 'in', delivery_orders.ids)]
        elif len(delivery_orders) == 1:
            action['views'] = [(self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = delivery_orders.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def create_pick_ship_delivery(self):
        if not self.partner_id:
            raise UserError("Kindly Select Partner to create Delivery ")
        for line in self.ticket_line_ids:
            if not line:
                raise UserError("Please add at least one product line to create a delivery order.")
        for record in self:
            warehouse = record.warehouse_id or record.sale_order_id.warehouse_id
            picking_type_pick = warehouse.pick_type_id  # Internal picking type for 'pick'
            picking_type_ship = warehouse.out_type_id  # Outgoing picking type for 'ship'
            stock_location = warehouse.lot_stock_id
            staging_location = warehouse.wh_output_stock_loc_id  # Staging location for shipping
            delivery_steps = warehouse.delivery_steps

            if delivery_steps == "pick_ship":
                # Step 1: Create Picking (Internal Transfer)
                picking_vals = {
                    'origin': record.ticket_ref,
                    'helpdesk_id': record.id,
                    'partner_id': record.partner_id.id,
                    'picking_type_id': picking_type_pick.id,
                    'location_id': stock_location.id,
                    'location_dest_id': staging_location.id,
                    'move_ids_without_package': [],
                }

                picking = self.env['stock.picking'].create(picking_vals)

                # Create stock moves for each sale order line
                for line in record.ticket_line_ids:
                    if line.product_id.type in ['product', 'consu']:
                        move_vals = {
                            'name': line.name,
                            'product_id': line.product_id.id,
                            'product_uom_qty': line.product_uom_qty,
                            'product_uom': line.uom_id.id,
                            'location_id': stock_location.id,
                            'location_dest_id': staging_location.id,
                            'picking_id': picking.id,
                        }
                        self.env['stock.move'].create(move_vals)

                # Step 2: Validate the picking (assuming it’s automated, can also be manual)
                # picking.action_confirm()
                picking.action_assign()  # Reserve products
                # picking.button_validate()  # Validate the picking

                # Step 3: Create Picking for the Shipping Operation
                shipping_vals = {
                    'origin': record.ticket_ref,
                    'helpdesk_id': record.id,
                    'partner_id': record.partner_id.id,
                    'picking_type_id': picking_type_ship.id,
                    'location_id': staging_location.id,
                    'location_dest_id': record.partner_shipping_id.property_stock_customer.id or record.sale_order_id.partner_shipping_id.property_stock_customer.id or False,
                    'move_ids_without_package': [],
                }

                shipping_picking = self.env['stock.picking'].create(shipping_vals)

                # Create stock moves for the shipping picking
                for line in record.ticket_line_ids:
                    if line.product_id.type in ['product', 'consu']:
                        move_vals = {
                            'name': line.name,
                            'product_id': line.product_id.id,
                            'product_uom_qty': line.product_uom_qty,
                            'product_uom': line.uom_id.id,
                            'location_id': staging_location.id,
                            'location_dest_id': record.partner_shipping_id.property_stock_customer.id or record.sale_order_id.partner_shipping_id.property_stock_customer.id or False,
                            'picking_id': shipping_picking.id,
                        }
                        self.env['stock.move'].create(move_vals)

                # shipping_picking.action_confirm()
                shipping_picking.action_assign()

            elif delivery_steps == "ship_only":
                # Direct Shipping Operation
                shipping_vals = {
                    'origin': record.ticket_ref,
                    'helpdesk_id': record.id,
                    'partner_id': record.partner_id.id,
                    'picking_type_id': picking_type_ship.id,
                    'location_id': stock_location.id,  # Directly from stock location
                    'location_dest_id': record.partner_shipping_id.property_stock_customer.id or record.sale_order_id.partner_shipping_id.property_stock_customer.id or False,
                    'move_ids_without_package': [],
                }

                shipping_picking = self.env['stock.picking'].create(shipping_vals)

                # Create stock moves for the shipping picking
                for line in record.ticket_line_ids:
                    if line.product_id.type in ['product', 'consu']:
                        move_vals = {
                            'name': line.name,
                            'product_id': line.product_id.id,
                            'product_uom_qty': line.product_uom_qty,
                            'product_uom': line.uom_id.id,
                            'location_id': stock_location.id,  # Directly from stock location
                            'location_dest_id': record.partner_shipping_id.property_stock_customer.id or record.sale_order_id.partner_shipping_id.property_stock_customer.id or False,
                            'picking_id': shipping_picking.id,
                        }
                        self.env['stock.move'].create(move_vals)

                # shipping_picking.action_confirm()
                shipping_picking.action_assign()

            else:
                raise exceptions.ValidationError(
                    "Pick Pack Ship Delivery Option is Not Available for Helpdesk"
                )
        return True

    def create_accounting_entries(self):
        if self.delivery_order_count > 0:
            offset_account_id = self.env['account.account'].search([('account_type', '=', 'liability_current')], limit=1).id
            total_debit = 0.0

            journal_entry_vals = {
                'journal_id': self.env['account.journal'].search([('type', '=', 'general')], limit=1).id,
                'date': fields.Date.today(),
                'ref': f"{self.name} - {self.ticket_ref}",
                'helpdesk_id': self.id,
                'line_ids': []
            }
            print(journal_entry_vals,"jounal valssssssss")
            for line in self.shipping_cost_line_ids:
                if line.product_id.detailed_type == 'service':
                    journal_entry_vals['line_ids'].append((0, 0, {
                        'account_id': line.product_id.categ_id.property_account_expense_categ_id.id or line.product_id.property_account_expense_id.id,
                        'name': line.product_id.name,
                        'debit': line.product_uom_qty * line.unit_price,
                        'credit': 0,
                    }))
                    total_debit += line.product_uom_qty * line.unit_price

            if total_debit > 0:
                journal_entry_vals['line_ids'].append((0, 0, {
                    'account_id': self.helpdesk_account_payable.id or offset_account_id,
                    'name': 'Offsetting Payable Account',
                    'debit': 0,
                    'credit': total_debit,
                }))

                journal_entry = self.env['account.move'].create(journal_entry_vals)

                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Journal Entry',
                    'view_mode': 'form',
                    'res_model': 'account.move',
                    'res_id': journal_entry.id,
                }
            else:
                raise UserError("Please add at least one service product line with a Unit Price to create a journal entry.")
        else:
            raise UserError("Please Process delivery order to create a journal entry.")

class HelpdeskTicketLine(models.Model):
    _name = 'helpdesk.ticket.line'
    _description = 'Helpdesk Ticket Line'

    name = fields.Char(string='Description')
    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom_qty = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency',default=lambda self: self.env.company.currency_id.id)
    unit_price = fields.Float("Price Unit")
    line_amount = fields.Float("Line Amount",compute='_compute_invoice_line_level_amount',currency_field='currency_id')
    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_amount',
        store=True, precompute=True)

    @api.depends('product_uom_qty', 'unit_price')
    def _compute_invoice_line_level_amount(self):
        for line in self:
            line.line_amount = line.product_uom_qty * line.unit_price

    @api.depends('line_amount')
    def _compute_amount(self):
        for line in self:
            line.update({
                'price_subtotal': line.line_amount,
            })

    @api.onchange('product_id')
    def _onchange_ticket_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.name = self.product_id.name or False
            self.unit_price = self.product_id.list_price or False

        if self.ticket_id and self.ticket_id.sale_order_id:
            # Get all product IDs from the sale order lines
            sale_order_products = self.ticket_id.sale_order_id.order_line.mapped('product_id')
            # Add the IDs of all service products
            service_products = self.env['product.product'].search([('type', '=', 'service')])

            # Combine both lists
            allowed_products = sale_order_products | service_products

            return {'domain': {'product_id': [('id', 'in', sale_order_products.ids)]}}
        else:
            return {'domain': {'product_id': []}}

    @api.constrains('product_uom_qty')
    def _check_quantity(self):
        for line in self:
            if line.ticket_id.sale_order_id:
                # Find the corresponding sale order line for this product
                order_line = line.ticket_id.sale_order_id.order_line.filtered(
                    lambda sol: sol.product_id == line.product_id
                )
                if order_line:
                    # Calculate the total quantity of this product in all ticket lines
                    total_qty = sum(line.ticket_id.ticket_line_ids.filtered(
                        lambda l: l.product_id == line.product_id
                    ).mapped('product_uom_qty'))

                    if total_qty > order_line.product_uom_qty:
                        raise exceptions.ValidationError(
                            "The total quantity for the product '%s' in the ticket lines cannot exceed the quantity ordered in the sale order." % line.product_id.display_name
                        )

class HelpdeskShippingCostLine(models.Model):
    _name = 'helpdesk.shipping.cost.line'
    _description = 'Helpdesk Shipping Cost Line'

    name = fields.Char(string='Description')
    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom_qty = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency',default=lambda self: self.env.company.currency_id.id)
    unit_price = fields.Float("Price Unit")
    line_amount = fields.Float("Line Amount",compute='_compute_invoice_line_level_amount',currency_field='currency_id')
    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_amount',
        store=True, precompute=True)

    @api.depends('product_uom_qty', 'unit_price')
    def _compute_invoice_line_level_amount(self):
        for line in self:
            line.line_amount = line.product_uom_qty * line.unit_price

    @api.depends('line_amount')
    def _compute_amount(self):
        for line in self:
            line.update({
                'price_subtotal': line.line_amount,
            })

    @api.onchange('product_id')
    def _onchange_ticket_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.name = self.product_id.name or False
            self.unit_price = self.product_id.list_price or False

        if self.ticket_id :
            # Get all product IDs from the sale order lines
            sale_order_products = self.ticket_id.sale_order_id.order_line.mapped('product_id')
            # Add the IDs of all service products
            service_products = self.env['product.product'].search([('type', '=', 'service')])

            # Combine both lists
            allowed_products = sale_order_products | service_products

            return {'domain': {'product_id': [('id', 'in', service_products.ids)]}}
        else:
            return {'domain': {'product_id': []}}


