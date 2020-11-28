# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from ast import literal_eval


class ProductLowStock(models.TransientModel):
    _name = "product.low.stock"
    _description = "product low stock wizard"

    stock_notification = fields.Selection([
        ('individual', 'Individual'),
        ('reorder', 'Reorder Rules')
        ], string='Notification Rule Type')
    minimum_qty = fields.Integer(string="Minimum Quantity")
    company_ids = fields.Many2many("res.company", string="Filter by Companies", help="Check Low stock for Notification from selected company only. if its blank it checks in all company")
    # location_ids = fields.Many2many("stock.location", string="Filter by Locations", help="Check Low stock for Notification from selected Locations only. if its blank it checks in all Locations")
    stock_lctn_id = fields.Many2one("stock.location",string="Filter by Locations")

    @api.onchange('company_ids')
    def _onchange_location_company(self):
        self.stock_lctn_id = [(6, 0, [])]

    @api.onchange('stock_lctn_id')
    def _onchange_location_location(self):
        domain = {}
        domain['stock_lctn_id'] = []
        if self.company_ids:
            domain['stock_lctn_id'] = [('company_id', 'in', self.company_ids.ids)]
        return {'domain': domain}

    @api.onchange('stock_notification')
    def on_change_location_id(self):
        if self.stock_notification in ('reorder','individual'):
            
            get_param = self.env['ir.config_parameter'].sudo().get_param
            lctn = literal_eval(get_param('ip_product_low_stock_notification.location_ids'))
            
            return {'domain': {
                    'stock_lctn_id': [('id' ,'in', lctn )],
                        }
                    }

    def print_low_stock_notification_report(self):
        data = {}
        data['form'] = (self.read(['stock_notification', 'minimum_qty', 'company_ids', 'stock_lctn_id'])[0])
        return self.env.ref('ip_product_low_stock_notification.action_report_product_stock').report_action(self, data=data, config=False)

    @api.model
    def default_get(self, fields):
        rec = super(ProductLowStock, self).default_get(fields)
        get_param = self.env['ir.config_parameter'].sudo().get_param
        rec['stock_notification'] = get_param('res.config.settings.stock_notification')
        rec['minimum_qty'] = get_param('res.config.settings.minimum_qty')
        company_ids = get_param('res.config.settings.company_ids')
        if company_ids:
            rec['company_ids'] = company_ids
        location_ids = get_param('res.config.settings.location_ids')
        if location_ids:
            rec['stock_lctn_id'] = location_ids
        return rec
