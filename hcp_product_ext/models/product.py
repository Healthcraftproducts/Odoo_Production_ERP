# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from psycopg2 import OperationalError, Error

from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
import logging

class TarrifNumber(models.Model):
	_name = 'tariff.number'
	_description = "Tariff Number"

	name = fields.Char(string="Tariff Number")

class ProductTemplate(models.Model):
	_inherit = 'product.template'

	def _get_default_category_id(self):
		if self._context.get('categ_id') or self._context.get('default_categ_id'):
			return self._context.get('categ_id') or self._context.get('default_categ_id')
		category = self.env.ref('product.product_category_all', raise_if_not_found=False)
		if not category:
			category = self.env['product.category'].search([], limit=1)
		if category:
			return category.id
		else:
			err_msg = _('You must define at least one product category in order to be able to create products.')
			redir_msg = _('Go to Internal Categories')
			raise RedirectWarning(err_msg, self.env.ref('product.product_category_action_form').id, redir_msg)

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
	deringer_uom_id = fields.Many2one('deringer.uom','Deringer UOM')
	usmca_eligible = fields.Selection([('yes','Yes'),('no','No')],'USMCA Eligible?')
	manufacturer_id = fields.Char('MID')
	product_sub_categ_id = fields.Many2one('product.sub.category',string="Product Sub Category")
	obsolute_product = fields.Boolean('Obsolute Product')
	categ_id = fields.Many2one('product.category', 'Account Category',change_default=True, default=_get_default_category_id, group_expand='_read_group_categ_id',required=True, help="Select category for the current product")
	tarrif_number = fields.Many2many('tariff.number', 'tariff_number_rel2', 'product_id', 'tariff_id',string='Tariff Number', copy=False,)

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
	obsolute_product = fields.Boolean('Obsolute Product')
	deringer_uom_id = fields.Many2one('deringer.uom','Deringer UOM')
	usmca_eligible = fields.Selection([('yes','Yes'),('no','No')],'USMCA Eligible?')
	manufacturer_id = fields.Char('MID')
	tarrif_number = fields.Many2many('tariff.number', 'tariff_number_rel', 'product_id', 'tariff_id',string='Tariff Number', copy=False,)
	batch_size = fields.Integer('Batch Size')
	
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
	ref = fields.Char('Source Reference', help="Source reference number in case it differs from the manufacturer's lot/serial number")

class Picking(models.Model):
	_inherit = "stock.picking"

	total_weight_for_shipping = fields.Float(string="Total Weight For Shipping")
	length = fields.Float(string="Length")
	width = fields.Float(string="Width")
	height = fields.Float(string="Height")
	pallet_shipment = fields.Boolean(string="Pallet Shipment")


	def action_done(self):
		"""Changes picking state to done by processing the Stock Moves of the Picking

		Normally that happens when the button "Done" is pressed on a Picking view.
		@return: True
		"""
		self._check_company()

		todo_moves = self.mapped('move_lines').filtered(lambda self: self.state in ['draft', 'waiting', 'partially_available', 'assigned', 'confirmed'])
		# Check if there are ops not linked to moves yet
		for pick in self:
			if pick.owner_id:
				pick.move_lines.write({'restrict_partner_id': pick.owner_id.id})
				pick.move_line_ids.write({'owner_id': pick.owner_id.id})

			# # Explode manually added packages
			# for ops in pick.move_line_ids.filtered(lambda x: not x.move_id and not x.product_id):
				#for quant in ops.package_id.quant_ids: #Or use get_content for multiple levels
					# self.move_line_ids.create({'product_id': quant.product_id.id,
												# 'package_id': quant.package_id.id,
												# 'result_package_id': ops.result_package_id,
												# 'lot_id': quant.lot_id.id,
												# 'owner_id': quant.owner_id.id,
												# 'product_uom_id': quant.product_id.uom_id.id,
												# 'product_qty': quant.qty,
												# 'qty_done': quant.qty,
												# 'location_id': quant.location_id.id, # Could be ops too
												# 'location_dest_id': ops.location_dest_id.id,
												# 'picking_id': pick.id
												# }) # Might change first element
												# # Link existing moves or add moves when no one is related
			for ops in pick.move_line_ids.filtered(lambda x: not x.move_id):
				# Search move with this product
				moves = pick.move_lines.filtered(lambda x: x.product_id == ops.product_id)
				moves = sorted(moves, key=lambda m: m.quantity_done < m.product_qty, reverse=True)
				if moves:
					ops.move_id = moves[0].id
				else:
					new_move = self.env['stock.move'].create({
													'name': _('New Move:') + ops.product_id.display_name,
													'product_id': ops.product_id.id,
													'product_uom_qty': ops.qty_done,
													'product_uom': ops.product_uom_id.id,
													'description_picking': ops.description_picking,
													'location_id': pick.location_id.id,
													'location_dest_id': pick.location_dest_id.id,
													'picking_id': pick.id,
													'picking_type_id': pick.picking_type_id.id,
													'restrict_partner_id': pick.owner_id.id,
													'company_id': pick.company_id.id,
													})
					ops.move_id = new_move.id
					new_move._action_confirm()
					todo_moves |= new_move
					#'qty_done': ops.qty_done})
		todo_moves._action_done(cancel_backorder=self.env.context.get('cancel_backorder'))
		so_obj = self.env['sale.order'].search([('name','=',self.origin)])
		if self.picking_type_id.sequence_code == 'OUT':
			if so_obj.commitment_date:
				self.date_done = so_obj.commitment_date
			else:
				self.write({'date_done': fields.Datetime.now()})
		else:
			self.write({'date_done': fields.Datetime.now()})
		self._send_confirmation_email()
		return True


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


class StockQuant(models.Model):
	_inherit = 'stock.quant'

	min_reorder_quantity = fields.Float(string="Minimum Quantity",compute='get_reordering_min_quantity')


	def get_reordering_min_quantity(self):
		for rec in self:
			if rec.product_id:
				minimum = self.env['stock.warehouse.orderpoint'].search([('product_id','=',rec.product_id.id),('location_id','=',rec.location_id.id)])
				if minimum:
					for data in minimum:
						rec.min_reorder_quantity = data.product_min_qty
				else:
					rec.min_reorder_quantity = 0.0

	@api.model
	def _get_removal_strategy_order(self, removal_strategy):
		if removal_strategy == 'fifo':
		    return 'lot_id ASC NULLS FIRST, id'
		elif removal_strategy == 'lifo':
		    return 'lot_id DESC NULLS LAST, id desc'
		raise UserError(_('Removal strategy %s not implemented.') % (removal_strategy,))
    
	#@api.model
	#def _update_reserved_quantity(self, product_id, location_id, quantity, lot_id=None, package_id=None, owner_id=None, strict=False):
		#""" Increase the reserved quantity, i.e. increase `reserved_quantity` for the set of quants
		#sharing the combination of `product_id, location_id` if `strict` is set to False or sharing
		#the *exact same characteristics* otherwise. Typically, this method is called when reserving
		#a move or updating a reserved move line. When reserving a chained move, the strict flag
		#should be enabled (to reserve exactly what was brought). When the move is MTS,it could take
		#anything from the stock, so we disable the flag. When editing a move line, we naturally
		#enable the flag, to reflect the reservation according to the edition.

		#:return: a list of tuples (quant, quantity_reserved) showing on which quant the reservation
		#was done and how much the system was able to reserve on it
		#"""
		#self = self.sudo()
		#rounding = product_id.uom_id.rounding 
		#quants = self._gather(product_id, location_id, lot_id=lot_id, package_id=package_id, owner_id=owner_id, strict=strict)
		#reserved_quants = []

		#if float_compare(quantity, 0, precision_rounding=rounding) > 0:
			## if we want to reserve
			#available_quantity = sum(quants.filtered(lambda q: float_compare(q.quantity, 0, precision_rounding=rounding) > 0).mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
			#if float_compare(quantity, available_quantity, precision_rounding=rounding) > 0:
				#raise UserError(_('It is not possible to reserve more products of %s than you have in stock.') % product_id.display_name)
		#elif float_compare(quantity, 0, precision_rounding=rounding) < 0:
			## if we want to unreserve
			#available_quantity = sum(quants.mapped('reserved_quantity'))
			#if float_compare(abs(quantity), available_quantity, precision_rounding=rounding) > 0:
				#action_fix_unreserve = self.env.ref(
					#'stock.stock_quant_stock_move_line_desynchronization', raise_if_not_found=False)
				#if action_fix_unreserve and self.user_has_groups('base.group_system'):
					#raise RedirectWarning(
						#_("""It is not possible to unreserve more products of %s than you have in stock.
						#The correction could unreserve some operations with problematics products.""") % product_id.display_name,
						#action_fix_unreserve.id,
						#_('Automated action to fix it'))
				#else:
					#raise UserError(_('It is not possible to unreserve more products of %s than you have in stock. Contact an administrator.') % product_id.display_name)
		#else:
			#return reserved_quants

		## for rec in quants:
		## 	if quants.filtered(lambda m: m.location_id != rec.location_id and m.lot_id == rec.lot_id):
		## 		quants = quants.sorted(reverse=True)
		## 	else:
		## 		quants

		##for q in quants:
			##if quants.filtered(lambda m: m.location_id != q.location_id and m.lot_id == q.lot_id):
				##vals.append(q)
				##vals.reverse()
			##else:
				##vals.append(q)
		##quants= vals
		
		#vals = []
		#for q in quants:
			#if all(r.location_id.id != q.location_id.id and r.lot_id.id == q.lot_id.id for r in quants):
				#vals.append(q)
				#vals.reverse()
				#quants= vals
			#else:
				#quants=quants

		#for quant in quants:
			#if float_compare(quantity, 0, precision_rounding=rounding) > 0:
				#max_quantity_on_quant = quant.quantity - quant.reserved_quantity
				#if float_compare(max_quantity_on_quant, 0, precision_rounding=rounding) <= 0:
					#continue
				#max_quantity_on_quant = min(max_quantity_on_quant, quantity)
				#quant.reserved_quantity += max_quantity_on_quant
				#reserved_quants.append((quant, max_quantity_on_quant))
				#quantity -= max_quantity_on_quant
				#available_quantity -= max_quantity_on_quant
			#else:
				#max_quantity_on_quant = min(quant.reserved_quantity, abs(quantity))
				#quant.reserved_quantity -= max_quantity_on_quant
				#reserved_quants.append((quant, -max_quantity_on_quant))
				#quantity += max_quantity_on_quant
				#available_quantity += max_quantity_on_quant

			#if float_is_zero(quantity, precision_rounding=rounding) or float_is_zero(available_quantity, precision_rounding=rounding):
				#break
		#return reserved_quants
    
class Pricelist(models.Model):
	_inherit = "product.pricelist"


	def unlink_pricelist_items(self):
		if self.item_ids:
			for line in self.item_ids:
				line.unlink()
