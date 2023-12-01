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
	file_name = fields.Binary('Discounts given - Summary Report', readonly=True)


class ProductDiscountWizard(models.TransientModel):
	_name = "product.discount.consolidated.wizard"
	_description = "Discounts given - Summary Report"

	date_from = fields.Date(string="Date From",required=True)
	date_to = fields.Date(string="Date To",required=True)

	def print_discount_summary_report_pdf(self):
		# data = {}
		# data['form'] = (self.read(['date_from', 'date_to', 'partner_id'])[0])
		data = {
			'model': 'product.discount.consolidated.wizard',
			'form': self.read()[0]
				}
		return self.env.ref('hcp_custom_reports.discount_summary_action_report').report_action(self, data=data)




	def print_xlsx_report(self):
		# pdb.set_trace()
		date_from = self.date_from
		date_to = self.date_to

		self._cr.execute("""select 
							 	
								sol.name,
								sum(sol.discount) as Disc,
								sum(sol.discount*sol.line_amount/100) as Discount_Amount,
								sum(sol.line_amount) as Sale_Amount

							from 
								sale_order so,
								sale_order_line sol
							where
								so.id = sol.order_id and
								date(so.date_order) >= %s and date(so.date_order) <= %s and
								sol.display_type is NULL and
								sol.discount > 0.0
							group by 
 								sol.name,
 								sol.discount;
											""", (date_from,date_to))
		sql_data = self._cr.fetchall()
		workbook = xlwt.Workbook()
		sheet = workbook.add_sheet("Discounts Given - Summary Report")
		first_col = sheet.col(0)
		two_col = sheet.col(1)
		three_col = sheet.col(2)
		fourth_col = sheet.col(3)		
		first_col.width = 500*20
		two_col.width = 200*20
		three_col.width = 250*20
		fourth_col.width = 250*20

		format2 = xlwt.easyxf('font: bold 1')
		format3 = xlwt.easyxf('font: bold 1; align: horiz right')
		style1 = xlwt.easyxf(num_format_str='#,##0.00')
		sheet.write(0,0,'Product Name',format2)
		sheet.write(0,1,'Discount(%)',format3)
		sheet.write(0,2,'Discount Amount',format3)
		sheet.write(0,3,'Sale Amount',format3)
		for row, line in enumerate(sql_data,start=1):
			for col, cell in enumerate(line):
				if isinstance(cell,float):
					sheet.write(row, col, cell,style1)
				else:
					sheet.write(row,col,cell)
		
		output = StringIO()
		if platform.system() == 'Linux':
			filename = ('/tmp/Discounts Given - Summary Report' +'.xls')
		else:
			filename = ('Discounts Given - Summary Report' +'.xls')

		workbook.save(filename)
		fp = open(filename, "rb")
		file_data = fp.read()
		out = base64.encodebytes(file_data)

		# Files actions
		attach_vals = {
				'discount_data': 'Discounts Given - Summary Report'+ '.xls',
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
				







              
                      


