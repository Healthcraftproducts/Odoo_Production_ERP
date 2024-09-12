from odoo import api, fields, models, _


class StockPicking(models.Model):
	_inherit = "stock.picking"


	helpdesk_id = fields.Many2one('helpdesk.ticket', string="Helpdesk ID")
