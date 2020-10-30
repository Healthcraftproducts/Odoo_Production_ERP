# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from collections import defaultdict
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import date_utils, float_compare, float_round, float_is_zero


class MrpProduction(models.Model):
	_inherit="mrp.production"

	release_date = fields.Date(string='Release Date')

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
    batch_size = fields.Integer(string="Batch Size")
    done_by = fields.Char(string= 'Done By')
    cycle_time = fields.Float(string='Cycle Time Old')
    operator = fields.Char(string='Operator')




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
   
