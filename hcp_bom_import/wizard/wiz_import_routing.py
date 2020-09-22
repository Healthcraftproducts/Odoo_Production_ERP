# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
import tempfile
import binascii
import xlrd
from datetime import date, datetime
from odoo.exceptions import Warning, UserError,ValidationError
from odoo import models, fields, exceptions, api, _
import logging
_logger = logging.getLogger(__name__)
import io
try:
	import csv
except ImportError:
	_logger.debug('Cannot `import csv`.')
try:
	import xlwt
except ImportError:
	_logger.debug('Cannot `import xlwt`.')
try:
	import cStringIO
except ImportError:
	_logger.debug('Cannot `import cStringIO`.')
try:
	import base64
except ImportError:
	_logger.debug('Cannot `import base64`.')

class ImportBomData(models.TransientModel):
	_name = "import.bom.data"

	File_slect = fields.Binary(string="Select Excel File")
	import_option = fields.Selection([('xls', 'XLS File')],string='Select',default='xls')


	def imoport_file(self):

# -----------------------------
		res = {}
# ---------------------------------------
		if self.import_option == 'xls':
			try:
				fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
				fp.write(binascii.a2b_base64(self.File_slect))
				fp.seek(0)
				values = {}
				workbook = xlrd.open_workbook(fp.name)
				sheet = workbook.sheet_by_index(0)
			except:
				raise Warning(_("Invalid file!"))

			for row_no in range(sheet.nrows):
				val = {}
				if row_no <= 0:
					fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
				else:
					line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
					itemcode = line[0]
					sheet2 = workbook.sheet_by_index(3)
					for row_no in range(sheet2.nrows):
						if row_no <= 0:
						    fields = map(lambda row:row.value.encode('utf-8'), sheet2.row(row_no)) 
						else:
						    line2 = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet2.row(row_no)))  
						    sheet2_itemcode = line2[0]
						    if itemcode == line2[0]:
						        main_product = itemcode
						        prod = self.env['product.product'].search([('default_code','=',str(main_product))])
						        bom = self.env['mrp.bom'].search([('product_id','=',prod.id)])
						        if bom:
						          variant = self.env['product.product'].search([('default_code','=',str(line2[5]))])
						          if not variant:
						            raise ValidationError(_('Product (%s).') % str(line2[5]))
						         #print(bom.id,variant.id,line2[2],'TRUE #######################')
						          vals={'product_id' : variant.id,
						                'product_qty' : line2[6],
						                'sequence' : int(float(line2[3])),
						                'bom_id': bom.id,
						                }
						          self.env['mrp.bom.line'].create(vals)
						          _logger.debug(vals,'*************BOM*****************')
						    else:
						         print('AAAAAAAAAAAAAAAAAAAAAAAAAA')	
# ------------------------------------------------------------						
		else:
			raise Warning(_("Please select any one from xls or csv formate!"))

		return res

	def import_routing(self):

# -----------------------------
		res = {}
# ---------------------------------------
		if self.import_option == 'xls':
			try:
				fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
				fp.write(binascii.a2b_base64(self.File_slect))
				fp.seek(0)
				values = {}
				workbook = xlrd.open_workbook(fp.name)
				sheet = workbook.sheet_by_index(0)
			except:
				raise Warning(_("Invalid file!"))

			for row_no in range(sheet.nrows):
				val = {}
				if row_no <= 0:
					fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
				else:
					line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
					itemcode = line[0]
					sheet2 = workbook.sheet_by_index(2)
					for row_no in range(sheet2.nrows):
						if row_no <= 0:
						    fields = map(lambda row:row.value.encode('utf-8'), sheet2.row(row_no)) 
						else:
						    line2 = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet2.row(row_no)))  
						    sheet2_itemcode = line2[0]
						    if itemcode == line2[0]:
						        main_product = itemcode
						        prod = self.env['mrp.routing'].search([('name','=',str(main_product))])
						        if prod:
						          wrk_center = self.env['mrp.workcenter'].search([('code','=',str(line2[4]))])
						          if not wrk_center:
						            raise ValidationError(_('Product (%s).') % str(line2[4]))
						         #print(bom.id,variant.id,line2[2],'TRUE #######################')
						          vals={'workcenter_id' : wrk_center.id,
						                'name' : line2[2],
						                'sequence' : int(float(line2[3])),
						                'routing_id': prod.id,
						                'setup_time': float(line2[8]),
						                'cycle_time': float(line2[7]),
						                'batch_size': float(line2[6]),
						                }
						          self.env['mrp.routing.workcenter'].create(vals)
						          _logger.debug(vals,'*************BOM*****************')
						    else:
						         print('AAAAAAAAAAAAAAAAAAAAAAAAAA')	
# ------------------------------------------------------------						
		else:
			raise Warning(_("Please select any one from xls or csv formate!"))

		return res

	def operation_mapping(self):
# -----------------------------
		res = {}
# ---------------------------------------
		if self.import_option == 'xls':
			try:
				fp = tempfile.NamedTemporaryFile(delete= False,suffix=".xlsx")
				fp.write(binascii.a2b_base64(self.File_slect))
				fp.seek(0)
				values = {}
				workbook = xlrd.open_workbook(fp.name)
				sheet = workbook.sheet_by_index(0)
			except:
				raise Warning(_("Invalid file!"))

			for row_no in range(sheet.nrows):
				val = {}
				if row_no <= 0:
					fields = map(lambda row:row.value.encode('utf-8'), sheet.row(row_no))
				else:
					line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
					itemcode = line[0]
					sheet2 = workbook.sheet_by_index(2)
					for row_no in range(sheet2.nrows):
						if row_no <= 0:
						    fields = map(lambda row:row.value.encode('utf-8'), sheet2.row(row_no)) 
						else:
						    line2 = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet2.row(row_no)))  
						    sheet2_itemcode = line2[0]
						    if itemcode == line2[0]:
						        main_product = itemcode
						        if not main_product:
						            raise ValidationError(_('Product (%s).') % line2[0])
						        prod = self.env['product.product'].search([('default_code','=',str(main_product))])
						        bom = self.env['mrp.bom'].search([('product_id','=',prod.id)])
						       # print(bom,'BOM###########################')
						        if len(bom)>1:
						            raise ValidationError(_('Product (%s).') % prod.id)
						        if bom:
						            variant = self.env['product.product'].search([('default_code','=',str(line2[5]))])
						            if not variant:
						                  raise ValidationError(_('Product (%s).BOM (%s)') % (str(line2[5]),bom.id,))
						            bom_line = self.env['mrp.bom.line'].search([('product_id','=',variant.id),('bom_id','=',bom.id)])
						           # print(bom_line,'BOM LINE #######################')
						            operation_id =self.env['mrp.routing.workcenter'].search([('name','=',str(line2[9])),('routing_id','=',bom.routing_id.id)])
						           # print(operation_id,'HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH')
						            vals={'operation_id' : operation_id.id,}
						            bom_line.write(vals)
						    #else:
						         #print('AAAAAAAAAAAAAAAAAAAAAAAAAA')	
# ------------------------------------------------------------						
		else:
			raise Warning(_("Please select any one from xls or csv formate!"))

		return res
