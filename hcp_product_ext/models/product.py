# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
	_inherit = 'product.template'


	# xdesc = fields.Char(string="XDesc")
	# sales = fields.Char(string="Sales(Connect Sage300)")
	cust_fld2 = fields.Char(string="HTS Code")
	cust_fld3 = fields.Many2one('res.country',string="Origin Of Country")
	status = fields.Selection([('0','Active'),('1','Inactive'),('2','R&D')],string="Status",default='0')
	cycle = fields.Many2one('product.cycle',string='Cycle')
	binding_rule = fields.Char(string ="Binding Ruling #")
	duty_rate = fields.Float(string="Duty Rate in %")
	pick = fields.Char(string="Pick")
	product_categ_id = fields.Many2one('product.category.master',string="Product Category")
	name = fields.Char('Product Description', index=True, required=True, translate=True)
	default_code = fields.Char('Item Code', compute='_compute_default_code',inverse='_set_default_code', store=True)
	fda_listing = fields.Char(string="FDA Listing#")
	product_sub_categ_id = fields.Many2one('product.sub.category',string="Product Sub Category")

	@api.depends('product_variant_ids', 'product_variant_ids.default_code')
	def _compute_default_code(self):
		unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
		for template in unique_variants:
			template.default_code = template.product_variant_ids.default_code
		for template in (self - unique_variants):
			template.default_code = False


	def _set_default_code(self):
		for template in self:
			if len(template.product_variant_ids) == 1:
				template.product_variant_ids.default_code = template.default_code



	def active_stage(self):
		self.write({
		'status': '0',
		'active': True,
			})



	
	def inactive_stage(self):
		self.write({
		'status': '1',
		'active': False,
			})


	
	def rd_stage(self):
		self.write({
		'status': '2',
		'active': True,
			})



class ProductMaster(models.Model):
	_inherit = 'product.product'


	# xdesc = fields.Char(string="XDesc")
	# sales = fields.Char(string="Sales(Connect Sage300)")
	cust_fld2 = fields.Char(string="HTS Code")
	cust_fld3 = fields.Many2one('res.country',string="Origin Of Country")
	status = fields.Selection([('0','Active'),('1','Inactive'),('2','R&D')],string="Status",default='0')
	cycle = fields.Many2one('product.cycle',string='Cycle')
	binding_rule = fields.Char(string ="Binding Ruling #")
	duty_rate = fields.Float(string="Duty Rate in %")
	pick = fields.Char(string="Pick")
	product_categ_id = fields.Many2one('product.category.master',string="Product Category")
	default_code = fields.Char('Item Code', index=True)
	product_description = fields.Char(string="Product Description")
	fda_listing = fields.Char(string="FDA Listing#")
	product_sub_categ_id = fields.Many2one('product.sub.category',string="Product Sub Category")

	def active_stage(self):
		self.write({
		'status': '0',
		'active': True,
			})


	def inactive_stage(self):
		self.write({
		'status': '1',
		'active': False,
			})


	def rd_stage(self):
		self.write({
		'status': '2',
		'active': True,
			})




class StockLotMaster(models.Model):
	_inherit = 'stock.production.lot'


	lot_size = fields.Float(string="Lot Size")


class ProductCategoryMaster(models.Model):
	_name = 'product.category.master'
	_description = "Product Category"
	# _parent_name = "parent_id"
	# _parent_store = True
	_rec_name = 'complete_name'
	_order = 'complete_name'

	name = fields.Char(string="Category Name")
	complete_name = fields.Char('Complete Name', compute='_compute_complete_name',store=True)
	parent_id = fields.Many2one('product.category.master',string="Parent Category",index=True, ondelete='cascade')


	@api.depends('name', 'parent_id.complete_name')
	def _compute_complete_name(self):
		for category in self:
			if category.parent_id:
				category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
			else:
				category.complete_name = category.name

class ProductSubCategory(models.Model):
	_name = 'product.sub.category'
	_description = "Product Sub Category"

	name = fields.Char(string="Sub Category Name")
