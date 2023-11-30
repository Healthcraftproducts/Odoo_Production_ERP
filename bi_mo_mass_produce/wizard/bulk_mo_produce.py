# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round
from odoo.tests import Form


backorders =  []

class InvoiceRecords(models.TransientModel):

	global backorders
	_name = 'mo.mass.produce.wizard'
	_description = 'Store the Selected Invoices required data for information view in wizard'

	def process_mo(self, selected_mo_records):
		for mo in selected_mo_records:
			if mo.state in ('draft','progress','confirmed','to_close'):
				if mo.state =='draft':
					mo.action_confirm()

				if mo.state in ('progress','confirmed','to_close'):
					# checking availability of the components
					mo.action_assign()

					for component in mo.move_raw_ids:
						if (not component.is_done) and (component.reserved_availability < component.product_uom_qty) and (component.product_uom_qty - component.reserved_availability > 0.0001):
							raise ValidationError(f'you can not be check availability in product not stock quant {component.product_id.name} in Manufacturing Order Reference {mo.name}')

					if len(mo.workorder_ids) > 0 and mo.is_planned == False:
						mo.button_plan()
						for wo in mo.workorder_ids :
							wo.button_start()
							wo.button_finish()

					if len(mo.workorder_ids) > 0 :
						for wo in mo.workorder_ids :
							if wo.state == 'progress':
								wo.button_finish()
							if wo.state in ['waiting','ready','pending']:
								wo.button_start()
								wo.button_finish()

					if mo.product_id.tracking == 'serial':
						#making quantity producing to 1 bcz product is trackinh by serial
						if mo.qty_producing != 1:
							mo.qty_producing = 1.0

						# if no tracking id is their we provide a new one
						if not mo.lot_producing_id.id:
							mo.lot_producing_id = self.env['stock.lot'].create({
								'name': self.env['ir.sequence'].next_by_code('stock.lot.serial'),
								'product_id': mo.product_id.id,
								'company_id': mo.company_id.id,
							}).id

						# setting move raw ids and other parameters after changing the qty producing to one
						mo._set_qty_producing()

						self.component_adjustments(mo, ids='move_raw_ids')

						if len(mo.move_byproduct_ids) > 0:
							self.component_adjustments(mo, ids='move_byproduct_ids')

					else:
						if mo.qty_producing == mo.product_qty:
							pass
						else:
							mo.qty_producing = mo.product_qty
						if mo.product_id.tracking == 'lot':
							if not mo.lot_producing_id.id:
								mo.lot_producing_id = self.env['stock.lot'].create({
									'name': self.env['ir.sequence'].next_by_code('stock.lot.serial'),
									'product_id': mo.product_id.id,
									'company_id': mo.company_id.id,
								}).id
						mo._set_qty_producing()
						self.component_adjustments(mo, ids='move_raw_ids')

						if len(mo.move_byproduct_ids) > 0:
							self.component_adjustments(mo, ids='move_byproduct_ids')

					## Code for creating any backorder for remaining quantity to produce
					if mo.product_id.tracking == 'serial' and mo.qty_producing < mo.product_qty:
						action = mo.button_mark_done()
						backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
						backorder.save().action_backorder()
						for i in mo.procurement_group_id.mrp_production_ids:
							if i.state != 'done':
								backorders.append(i)

			if mo.state == 'to_close':
				mo.button_mark_done()

	def complete_mo(self):
		active_ids = self._context.get('active_ids', [])
		selected_mo_records = self.env['mrp.production'].browse(active_ids)
		if 'done' in [i.state for i in selected_mo_records]:
			raise ValidationError('Some of the Selected MO(s) are already in Done stage. Please check')

		self.process_mo(selected_mo_records)
		while len(backorders) != 0:
			mo_ids = []
			for i in backorders:
				mo_ids.append(i.id)
			backorders.clear()
			selected_mo_records = self.env['mrp.production'].browse(mo_ids)
			self.process_mo(selected_mo_records)

	def component_adjustments(self, mo, ids):

		for move in mo[ids]:

			if ids == 'move_raw_ids':
				quantity = move.should_consume_qty
			elif ids == 'move_byproduct_ids':
				quantity = move.product_uom_qty

			if move.product_id.tracking == 'lot':
				if len(move.move_line_ids) == 1:
					for line in move.move_line_ids:
						if not line.lot_id.id:
							line.lot_id = self.env['stock.lot'].create({
								'name': self.env['ir.sequence'].next_by_code('stock.lot.serial'),
								'product_id': line.product_id.id,
								'company_id': line.company_id.id,
							}).id
						line.qty_done = float(quantity)

				elif len(move.move_line_ids) == 0:
					line = (0, 0 ,{
						'location_id': move.location_id.id,
						'location_dest_id': move.location_dest_id.id,
						'move_id': move.id,
						'lot_id': self.env['stock.lot'].create({
							'name': self.env['ir.sequence'].next_by_code('stock.lot.serial'),
							'product_id': move.product_id.id,
							'company_id': move.company_id.id,
						}).id,
						'qty_done': quantity,
						'product_uom_id': move.product_uom.id,
						'product_id': move.product_id.id,
					})
					move.move_line_ids = [(5,)] + [line]

			if move.product_id.tracking == 'serial':
				if len(move.move_line_ids) == 0:
					lines = []
					for i in range(int(quantity)):
						lines.append({
							'location_id': move.location_id.id,
							'location_dest_id': move.location_dest_id.id,
							'move_id': move.id,
							'lot_id': self.env['stock.lot'].create({
								'name': self.env['ir.sequence'].next_by_code('stock.lot.serial'),
								'product_id': move.product_id.id,
								'company_id': move.company_id.id,
							}).id,
							'qty_done': 1,
							'product_uom_id': move.product_uom.id,
							'product_id': move.product_id.id,
						})
					move.move_line_ids = [(5,)] + [(0, 0, x) for x in lines]

				elif len(move.move_line_ids) != 0:
					total_lines = len(move.move_line_ids)
					if (total_lines > 0) and (total_lines == quantity):
						for line in move.move_line_ids:
							line.update({'lot_id' :self.env['stock.lot'].create({
								'name': self.env['ir.sequence'].next_by_code('stock.lot.serial'),
								'product_id': move.product_id.id,
								'company_id': move.company_id.id,
							}).id})
							line.update({'qty_done' :1})
					if (total_lines > 0) and (total_lines != quantity):
						lines = []
						for i in range(int(quantity)):
							lines.append({
								'location_id': move.location_id.id,
								'location_dest_id': move.location_dest_id.id,
								'move_id': move.id,
								'lot_id': self.env['stock.lot'].create({
									'name': self.env['ir.sequence'].next_by_code('stock.lot.serial'),
									'product_id': move.product_id.id,
									'company_id': move.company_id.id
								}).id,
								'qty_done': 1,
								'product_uom_id': move.product_uom.id,
								'product_id': move.product_id.id,
							})
						move.move_line_ids = [(5,)] + [(0, 0, x) for x in lines]

