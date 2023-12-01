# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from collections import defaultdict
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import date_utils, float_compare, float_round, float_is_zero
import logging

class QCImageUploadWizard(models.TransientModel):
    _name = "qc.image.upload"
    upload_image = fields.Binary('Upload Image')
	
    def upload_qc_image(self):
        work_order_ids = self.env['mrp.workorder'].sudo().search([('id','=',self.env.context.get('default_workorder_id'))])
        logging.info('%s--------------work_order_ids',work_order_ids)
        for work_order in work_order_ids.filtered(lambda self: self.state not in ['done', 'cancel']):
            work_order.write({
                    'qc_image_ids': [(0,0, {'image':self.upload_image})]
					})
        return True

class MrpWorkOrderQCImages(models.Model):

    _name = 'mrp.workorder.qc.images'
    image = fields.Binary(string='Image')
    workorder_id = fields.Many2one('mrp.workorder',string='Workorder ID')
	
class MrpWorkOrderInherit(models.Model):

    _inherit = 'mrp.workorder'
    qc_image_ids = fields.One2many('mrp.workorder.qc.images', 'workorder_id', string='QC Images')
	
class StockScrap(models.Model):
	_inherit = 'stock.scrap'


	production = fields.Char(string="Manufacturing Order",related='production_id.name')
	work_order = fields.Char(string="Work Order",related='workorder_id.name')


class MrpProduction(models.Model):
	_inherit="mrp.production"

	release_date = fields.Date(string='Release Date')
	priority = fields.Selection([('0', 'Low'), ('1', 'Medium'), ('2', 'High'), ('3', 'Very High')], 'Priority',readonly=False,states={'done': [('readonly', True)]},default='1')

	def get_attachment(self):
		import base64

		output = open(r"src/user/hcp_mrp_module/QC_Template.pdf", "rb").read()

		result = base64.b64encode(output)
		# get base url
		base_url = self.env['ir.config_parameter'].get_param('web.base.url')
		attachment_obj = self.env['ir.attachment']
		attachment_avail = self.env['ir.attachment'].search([('name','=','qc_report')])
		attachment_count = self.env['ir.attachment'].search_count([('name','=','qc_report')])
		# print(attachment_avail)
		# create attachment
		if attachment_count==0:
			attachment_id = attachment_obj.create(
			{'name': "qc_report", 'type': 'binary', 'datas': result})
			# prepare download url
			download_url = '/web/content/' + str(attachment_id.id) + '?download=true'
			# download
			return {
				"type": "ir.actions.act_url",
				"url": str(base_url) + str(download_url),
				"target": "new",
					}
		else:
			att= attachment_avail.id
			download_url = '/web/content/' + str(att) + '?download=true'
			# download
			return {
				"type": "ir.actions.act_url",
				"url": str(base_url) + str(download_url),
				"target": "new",
					}



class MrpWorkcenter(models.Model):
	_inherit = 'mrp.workcenter'

	cycle_time = fields.Float(string='Cycle Time Old')
	shiftid = fields.Selection([('production','Production'),('outside_pro','Outside Pro'),('inventory','Inventory')],string='ShiftId')
	time_stop = fields.Float('Cycle Time', help="Time in minutes for the cleaning.")
	department = fields.Selection([('assembly','Assembly'),('machining','Machining'),('welding','Welding'),('fabrication','Fabrication'),('paint','Paint')],string='Department')

	def name_get(self):
		res = []
		for category in self:
			names = []
			name=category.name
			code = category.code
			if code:
				name = '[%s] %s' % (code,name)
			temp = (category.id, name)
			res.append(temp)
		return res

	@api.model
	def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
		args = args or []
		if name:
			# Be sure name_search is symetric to name_get
			name = name.split(' / ')[-1]
			args = [('name', operator, name)] + args
		partner_category_ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
		return self.browse(partner_category_ids).name_get()    

class MrpRoutingWorkcenter(models.Model):
	_inherit = 'mrp.routing.workcenter'

	setup_time = fields.Float(string='Setup Time')
	custom_batch_size = fields.Integer(string="Batch Size")
	batch_size = fields.Integer(string="Partial Batch Size")
	done_by = fields.Char(string= 'Done By')
	cycle_time = fields.Float(string='Cycle Time Old')
	operator = fields.Char(string='Operator')
	setuptime_per_unit = fields.Float(string='Setuptime Per Unit(Mins)',compute='_compute_setuptime_per_unit')
	runtime_per_unit = fields.Float(string='Runtime Per Unit(Mins)')
	total_time = fields.Float(string='Total Time(Mins)',compute='_compute_total_time')

	@api.depends('setup_time', 'custom_batch_size')
	def _compute_setuptime_per_unit(self):
		for line in self:
			if line.setup_time and line.custom_batch_size:
 				line.setuptime_per_unit = (line.setup_time / line.custom_batch_size)
			else:
 				line.setuptime_per_unit = 0            

	@api.depends('setup_time', 'custom_batch_size', 'runtime_per_unit')
	def _compute_total_time(self):
		setuptime_per_unit = 0 
		runtime_per_unit = 0
		for line in self:
			if line.setup_time and line.custom_batch_size:
 				setuptime_per_unit = (line.setup_time / line.custom_batch_size)
			if line.runtime_per_unit:
 				runtime_per_unit = line.runtime_per_unit
			line.total_time = setuptime_per_unit + runtime_per_unit


class ProductTemplate(models.Model):
	_inherit = 'product.template'

	attachments_id = fields.Many2many(comodel_name="ir.attachment", relation="m2m_ir_attachment_relation",column1="m2m_id", column2="attachment_id", string="Attachments")


	# def get_attachment(self):
	# 	# import pdb
	# 	# pdb.set_trace()
	# 	# import os
	# 	import base64
	# 	# output is where you have the content of your file, it can be
	# 	# any type of content

	# 	output = open(r"src/user/hcp_mrp_module/QC_Template.pdf", "rb").read()

	# 	# path = r'hcp_mrp_module\QC_Template.pdf'
	# 	# output = path.encode('ascii')
	# 	# encode
	# 	result = base64.b64encode(output)
	# 	# get base url
	# 	base_url = self.env['ir.config_parameter'].get_param('web.base.url')
	# 	attachment_obj = self.env['ir.attachment']
	# 	attachment_avail = self.env['ir.attachment'].search([('name','=','qc_report')])
	# 	attachment_count = self.env['ir.attachment'].search_count([('name','=','qc_report')])
	# 	# print(attachment_avail)
	# 	# create attachment
	# 	if attachment_count==0:
	# 		attachment_id = attachment_obj.create(
	# 		{'name': "qc_report", 'type': 'binary', 'datas': result})
	# 		# prepare download url
	# 		download_url = '/web/content/' + str(attachment_id.id) + '?download=true'
	# 		# download
	# 		return {
	# 			"type": "ir.actions.act_url",
	# 			"url": str(base_url) + str(download_url),
	# 			"target": "new",
	# 				}
	# 	else:
	# 		att= attachment_avail.id
	# 		# attachment_id = attachment_obj.write(
	# 		# {'id':att,'name': "qc_report", 'type': 'binary', 'datas': result})
	# 		download_url = '/web/content/' + str(att) + '?download=true'
	# 		# download
	# 		return {
	# 			"type": "ir.actions.act_url",
	# 			"url": str(base_url) + str(download_url),
	# 			"target": "new",
	# 				}


class MrpBom(models.Model):
	_inherit = 'mrp.bom'

	def update_main_bom(self):
		if self.product_uom_id:
			for line in self:
				line.product_uom_id=line.product_tmpl_id.uom_id
				
	def update_bom(self):
		if self.bom_line_ids:
			for line in self.bom_line_ids:
				line.product_uom_id=line.product_id.uom_id
   
# class ReportBomStructure(models.AbstractModel):
# 	_inherit = 'report.mrp.report_bom_structure'

# 	def _get_operation_line(self, routing, qty, level):
# 		operations = []
# 		total = 0.0
# 		for operation in routing.operation_ids:
# 			operation_cycle = float_round(qty / operation.workcenter_id.capacity, precision_rounding=1, rounding_method='UP')
# 			duration_expected = operation_cycle * operation.time_cycle + operation.workcenter_id.time_stop + operation.workcenter_id.time_start + operation.setup_time
# 			total = ((duration_expected / 60.0) * operation.workcenter_id.costs_hour)
# 			operations.append({
# 				'level': level or 0,
# 				'operation': operation,
# 				'name': operation.name + ' - ' + operation.workcenter_id.name,
# 				'duration_expected': duration_expected,
# 				'total': self.env.company.currency_id.round(total),
# 			})
# 		return operations


class MrpWorkorder(models.Model):
	_inherit = 'mrp.workorder'

	hcp_priority = fields.Selection('Production Priority', readonly=True,related='production_id.priority',help='Technical: used in views only.')
	workcenter_department = fields.Selection('Department', readonly=True,related='workcenter_id.department')
	
	def name_get(self):
		return [(wo.id, "%s - %s - %s" % (wo.production_id.name, wo.product_id.display_name, wo.name)) for wo in self]

