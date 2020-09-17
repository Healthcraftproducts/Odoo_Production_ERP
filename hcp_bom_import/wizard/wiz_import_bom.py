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
						        prod = self.env['product.template'].search([('default_code','=',str(main_product))])
						        bom = self.env['mrp.bom'].search([('product_tmpl_id','=',prod.id)])
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
						    else:
						         print('AAAAAAAAAAAAAAAAAAAAAAAAAA')	
# ------------------------------------------------------------						
		else:
			raise Warning(_("Please select any one from xls or csv formate!"))

		return res
