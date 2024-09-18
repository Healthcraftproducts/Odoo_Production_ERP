from odoo import models, fields, api


class PurolatorResCompany(models.Model):
    _inherit = 'res.company'

    purolator_username = fields.Char(string="Username", help="Your purolator Account Username")
    purolator_password = fields.Char(string="Password", help="Your purolator Account Password")
    purolator_account_number = fields.Char(string="Account Number",help="Your Purolator Account Number")
    purolator_api_url = fields.Char(string="API URl")
    use_purolator_shipping_provider = fields.Boolean(copy=False, string="Are You Using purolator?",
                                                 help="If use purolator shipping Integration then set value to TRUE.",
                                                 default=False)
