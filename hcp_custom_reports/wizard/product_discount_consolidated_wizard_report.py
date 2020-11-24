from odoo import api, fields, models, _
from datetime import date,datetime, timedelta
from odoo.exceptions import UserError
import xlwt
from io import StringIO
import base64
import platform
import pdb
try:
	from odoo.tools.misc import xlsxwriter
except ImportError:
	import xlsxwriter


class DiscountReportout(models.Model):
	_name = 'discount.report.out'
	_description = 'Discount Consolidated report'

	discount_data = fields.Char('Name', size=256)
	file_name = fields.Binary('Product Discount Excel Report', readonly=True)


class ProductDiscountWizard(models.TransientModel):
	_name = "product.discount.consolidated.wizard"
	_description = "product discount xls report wizard"

	date_from = fields.Date(string="Date From",required=True)
	date_to = fields.Date(string="Date To",required=True)


	def print_xlsx_report(self):
		# pdb.set_trace()
		date_from = self.date_from
		date_to = self.date_to

		self._cr.execute("""select 
							 	
								sol.name,
								sum(sol.discount) as Disc,
								sum(sol.discount*sol.line_amount/100) as Discount_Amount

							from 
								sale_order so,
								sale_order_line sol
							where
								so.id = sol.order_id and
								date(so.date_order) >= %s and date(so.date_order) <= %s
							group by 
 								
								sol.name;
											""", (date_from,date_to))
		sql_data = self._cr.fetchall()
		print(sql_data)
		# if sql_data:
		# 	raise UserError(len(sql_data))
		workbook = xlwt.Workbook()
		sheet = workbook.add_sheet("Product Discount Consolidated XLS Report")
		format2 = xlwt.easyxf('font: bold 1') 
		# sheet.write(0,0,'product id',format2)
		sheet.write(0,0,'Product Name',format2)
		sheet.write(0,1,'Discount%',format2)
		sheet.write(0,2,'Discount Amount',format2)
		for row, line in enumerate(sql_data,start=1):
			for col, cell in enumerate(line):
				sheet.write(row, col, cell)
		
		output = StringIO()
		if platform.system() == 'Linux':
			filename = ('/tmp/Product Discount Consolidated Report' +'.xls')
		else:
			filename = ('Product Discount Consolidated Report' +'.xls')

		workbook.save(filename)
		fp = open(filename, "rb")
		file_data = fp.read()
		out = base64.encodestring(file_data)

		# Files actions
		attach_vals = {
				'discount_data': 'Product Discount Consolidated Report'+ '.xls',
				'file_name': out,
				# 'purchase_work':'Purchase'+ '.csv',
				# 'file_names':data,
				}

		act_id = self.env['discount.report.out'].create(attach_vals)
		fp.close()
		return {
			'type': 'ir.actions.act_window',
			'res_model': 'discount.report.out',
			'res_id': act_id.id,
			'view_type': 'form',
			'view_mode': 'form',
			'context': self.env.context,
			'target': 'new',
				}
				







              
                      


