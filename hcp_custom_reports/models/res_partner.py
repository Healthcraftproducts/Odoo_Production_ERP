from odoo import api, fields, models

class ResPartner(models.Model):
	_inherit = 'res.partner'

	@api.model
	def _name_search(self, name='', args=None, operator='ilike', limit=100):
		args = list(args or [])
		args += ['|', ('hcp_customer_id', operator, name), ('name', operator, name)]
		return super(ResPartner,self)._search(args, limit=limit)


