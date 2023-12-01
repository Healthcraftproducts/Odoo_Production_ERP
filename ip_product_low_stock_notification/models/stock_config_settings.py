# -*- encoding: utf-8 -*-
from odoo import api, fields, models
from ast import literal_eval

class StockSettingsInherit(models.TransientModel):
    _inherit = 'res.config.settings'

    stock_notification = fields.Selection([
        ('individual', 'Individual'),
        ('reorder', 'Reorder Rules')
        ], string='Notification Rule Type', default='individual')
    minimum_qty = fields.Integer(string="Minimum Quantity")
    notification_user_ids = fields.Many2many("res.users", string="Notification to", help="Low stock Notification goes to Selected users")
    company_ids = fields.Many2many("res.company", string="Filter by Companies", help="Check Low stock for Notification from selected company only. if its blank it checks in all company")
    location_ids = fields.Many2many("stock.location", string="Filter by Locations", help="Check Low stock for Notification from selected Locations only. if its blank it checks in all Locations")

    @api.onchange('location_ids')
    def _onchange_location_location(self):
        domain = {}
        domain['location_ids'] = []
        if self.company_ids:
            domain['location_ids'] = [('company_id', 'in', self.company_ids.ids)]
        return {'domain': domain}

    @api.model
    def get_values(self):
        res = super(StockSettingsInherit, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res.update(
            stock_notification=get_param('ip_product_low_stock_notification.stock_notification'),
            minimum_qty=int(get_param('ip_product_low_stock_notification.minimum_qty')),
            notification_user_ids=literal_eval(get_param('ip_product_low_stock_notification.notification_user_ids', default='[]')),
            company_ids=literal_eval(get_param('ip_product_low_stock_notification.company_ids', default='[]')),
            location_ids=literal_eval(get_param('ip_product_low_stock_notification.location_ids', default='[]')),
            )
        return res

    def set_values(self):
        super(StockSettingsInherit, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param
        set_param('ip_product_low_stock_notification.stock_notification', self.stock_notification)
        set_param('ip_product_low_stock_notification.minimum_qty', self.minimum_qty)
        set_param("ip_product_low_stock_notification.notification_user_ids", [user for user in self.notification_user_ids.ids])
        set_param('ip_product_low_stock_notification.company_ids', [company for company in self.company_ids.ids])
        set_param('ip_product_low_stock_notification.location_ids', [location for location in self.location_ids.ids])
