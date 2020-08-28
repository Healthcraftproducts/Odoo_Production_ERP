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



class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    setup_time = fields.Float(string='Setup Time')
    done_by = fields.Char(string= 'Done By')
    cycle_time = fields.Float(string='Cycle Time')
    operator = fields.Char(string='Operator')




class ProductTemplate(models.Model):
	_inherit = 'product.template'

	attachments_id = fields.Many2many(comodel_name="ir.attachment", relation="m2m_ir_attachment_relation",column1="m2m_id", column2="attachment_id", string="Attachments")


	def get_attachment(self):
		# import pdb
		# pdb.set_trace()
		# import os
		import base64
		# output is where you have the content of your file, it can be
		# any type of content

		output = open(r"src/user/hcp_mrp_module/QC_Template.pdf", "rb").read()

		# path = r'hcp_mrp_module\QC_Template.pdf'
		# output = path.encode('ascii')
		# encode
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
			# attachment_id = attachment_obj.write(
			# {'id':att,'name': "qc_report", 'type': 'binary', 'datas': result})
			download_url = '/web/content/' + str(att) + '?download=true'
			# download
			return {
				"type": "ir.actions.act_url",
				"url": str(base_url) + str(download_url),
				"target": "new",
					}





   
