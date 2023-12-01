from odoo import api, fields, models, SUPERUSER_ID, _


class ProductTemplate(models.Model):
	_name = 'product.cycle'
	_description = 'Product Cycle'


	name = fields.Char(string='Name')
