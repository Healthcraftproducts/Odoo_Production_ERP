from odoo import api, fields, models, _

class ProductProduct(models.Model):
    _inherit = 'product.product'

    value_svl = fields.Float(compute='_compute_value_svl', compute_sudo=True)
    quantity_svl = fields.Float(compute='_compute_value_svl', compute_sudo=True)
    avg_cost = fields.Monetary(string="Average Cost", compute='_compute_value_svl', compute_sudo=True, currency_field='company_currency_id')
    total_value = fields.Monetary(string="Total Value", compute='_compute_value_svl', compute_sudo=True, currency_field='company_currency_id')
    company_currency_id = fields.Many2one(
        'res.currency', 'Valuation Currency', compute='_compute_value_svl', compute_sudo=True,
        help="Technical field to correctly show the currently selected company's currency that corresponds "
             "to the totaled value of the product's valuation layers")
    stock_valuation_layer_ids = fields.One2many('stock.valuation.layer', 'product_id')
    valuation = fields.Selection(related="categ_id.property_valuation", readonly=True)
    cost_method = fields.Selection(related="categ_id.property_cost_method", readonly=True)

    def write(self, vals):
        if 'standard_price' in vals and not self.env.context.get('disable_auto_svl'):
            self.filtered(lambda p: p.cost_method != 'fifo')._change_standard_price(vals['standard_price'])
        return super(ProductProduct, self).write(vals)

    @api.depends('stock_valuation_layer_ids')
    @api.depends_context('to_date', 'company')
    def _compute_value_svl(self):
        """Compute totals of multiple svl related values"""
        company_id = self.env.company
        self.company_currency_id = company_id.currency_id
        domain = [
            ('product_id', 'in', self.ids),
            ('company_id', '=', company_id.id),
        ]
        if self.env.context.get('to_date'):
            to_date = fields.Datetime.to_datetime(self.env.context['to_date'])
            domain.append(('create_date', '<=', to_date))
        groups = self.env['stock.valuation.layer']._read_group(domain, ['value:sum', 'quantity:sum'], ['product_id'])
        products = self.browse()
        # Browse all products and compute products' quantities_dict in batch.
        self.env['product.product'].browse([group['product_id'][0] for group in groups]).sudo(False).mapped('qty_available')
        for group in groups:
            product = self.browse(group['product_id'][0])
            value_svl = company_id.currency_id.round(group['value'])
            avg_cost = value_svl / group['quantity'] if group['quantity'] else 0
            product.value_svl = value_svl
            product.quantity_svl = group['quantity']
            product.avg_cost = product.standard_price
            product.total_value = avg_cost * product.sudo(False).qty_available
            products |= product
        remaining = (self - products)
        remaining.value_svl = 0
        remaining.quantity_svl = 0
        remaining.avg_cost = 0
        remaining.total_value = 0

class StockMoveLineInherit(models.Model):
    _inherit = "stock.move.line"

    company_currency_id = fields.Many2one(
        'res.currency', 'Valuation Currency', compute='_compute_cost_total_value', compute_sudo=True,
        help="Technical field to correctly show the currently selected company's currency that corresponds "
             "to the totaled value of the product's valuation layers")
    product_id = fields.Many2one('product.product', 'Product', ondelete="cascade", check_company=True, domain="[('type', '!=', 'service'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]", index=True)
    product_cost = fields.Monetary(string="Cost Price",compute="_compute_cost_total_value", currency_field='company_currency_id')
    total_value_moved = fields.Monetary(string="Total Value", compute='_compute_cost_total_value',currency_field='company_currency_id')

    @api.depends('product_id.standard_price','qty_done')
    def _compute_cost_total_value(self):
        company_id = self.env.company
        self.company_currency_id = company_id.currency_id
        for product in self:
            if product.product_id:
                if product.product_id.standard_price:
                    product.product_cost = product.product_id.standard_price
                else:
                    product.product_cost = ""

                danger_condition = (product.location_usage in ('internal', 'transit')) and (
                            product.location_dest_usage not in ('internal', 'transit'))
                success_condition = (product.location_usage not in ('internal', 'transit')) and (
                            product.location_dest_usage in ('internal', 'transit'))
                neutral_condition = (product.location_usage in ('internal', 'transit')) and (
                        product.location_dest_usage in ('internal', 'transit'))

                if product.qty_done and danger_condition:
                    product.total_value_moved = product.qty_done * product.product_cost * -1
                elif product.qty_done and success_condition:
                    product.total_value_moved = product.qty_done * product.product_cost
                elif product.qty_done and neutral_condition:
                    product.total_value_moved = product.qty_done * product.product_cost
                else:
                    product.total_value_moved = "0"

class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    product_id = fields.Many2one(
        'product.product', 'Product', domain="[('type', 'in', ['product', 'consu']), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        required=True, states={'done': [('readonly', True)]}, check_company=True)
    product_cost_price = fields.Monetary(string="Cost Price",compute="_compute_cost_scrap_value", currency_field='company_currency_id')
    total_value_scraped = fields.Monetary(string="Total Value", compute='_compute_cost_scrap_value',currency_field='company_currency_id')
    company_currency_id = fields.Many2one(
        'res.currency', 'Valuation Currency', compute='_compute_cost_scrap_value', compute_sudo=True,
        help="Technical field to correctly show the currently selected company's currency that corresponds "
             "to the totaled value of the product's valuation layers")

    @api.depends('product_id.standard_price', 'scrap_qty')
    def _compute_cost_scrap_value(self):
        company_id = self.env.company
        self.company_currency_id = company_id.currency_id
        for product in self:
            if product.product_id:
                if product.product_id.standard_price:
                    product.product_cost_price = product.product_id.standard_price
                else:
                    product.product_cost_price = "0"

                if product.scrap_qty:
                    product.total_value_scraped = product.scrap_qty * product.product_cost_price
                else:
                    product.total_value_scraped = "0"
