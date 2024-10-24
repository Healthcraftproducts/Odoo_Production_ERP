from odoo import fields, models, api


class StockPackageType(models.Model):
    _inherit = 'stock.package.type'

    package_carrier_type = fields.Selection(selection_add=[('fedex_shipping_provider', 'Fedex')])
    weight_uom_name = fields.Char()
    active = fields.Boolean(string='Active', default=True)
