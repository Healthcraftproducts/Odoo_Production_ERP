from odoo import api, fields, models, _, exceptions
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'


    helpdesk_id = fields.Many2one('helpdesk.ticket', string="Helpdesk ID")
