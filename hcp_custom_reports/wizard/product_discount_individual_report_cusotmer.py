from odoo import api, fields, models, _
from datetime import date,datetime, timedelta
from odoo.exceptions import UserError
import xlwt
from io import StringIO
import base64
import platform
try:
	from odoo.tools.misc import xlsxwriter
except ImportError:
	import xlsxwriter

class ProductReportOut(models.Model):
	_name = 'product.report.out'
	_description = 'Discount order report'

	product_data = fields.Char('Name', size=256)
	file_name = fields.Binary('Discounts given - Detailed Report', readonly=True)


class ProductDiscountWizard(models.TransientModel):
	_name = "product.discount.individual.customer.wizard"
	_description = "Discounts given - Detailed Report"

	date_from = fields.Date(string="Date From",required=True)
	date_to = fields.Date(string="Date To",required=True)
	partner_id = fields.Many2one('res.partner', string="Customer")

	def print_discount_details_report_pdf(self):
		# data = {}
		# data['form'] = (self.read(['date_from', 'date_to', 'partner_id'])[0])
		data = {
			'model': 'product.discount.individual.customer.wizard',
			'form': self.read()[0]
				}
		return self.env.ref('hcp_custom_reports.action_report_discount_details').report_action(self, data=data)


	def get_data(self):
		discount_list=[]
		return_list ={}
		prdt_list1=[]
		if self.partner_id:
			sale_obj = self.env['sale.order'].search([('partner_id','=',self.partner_id.id)])
			if sale_obj:
				for sale in sale_obj:
					dt = sale.date_order
					date = datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S").date()
					if date>=self.date_from and date<=self.date_to:
						for line in sale.order_line:
							if not line.display_type:
								a = sale.id
								b = [sale.name,sale.partner_id.hcp_customer_id,sale.partner_id.name,line.product_id.default_code,line.product_id.name,line.discount,line.line_amount*line.discount/100]
								discount_details ={'id':a,'values':b}
								discount_list.append(discount_details)
				list_product=discount_list
				for data in list_product:
					prdt_details =[]
					prdt_details.append(data['values'][0])
					prdt_details.append(data['values'][1])
					prdt_details.append(data['values'][2])
					prdt_details.append(data['values'][3])
					prdt_details.append(data['values'][4])
					prdt_details.append(data['values'][5])
					prdt_details.append(data['values'][6])
					prdt_list1.append(prdt_details)
				return_list['sale_ids'] = prdt_list1

			else:
				raise UserError("No Sale order has been generated for this customer")
		else:
			sale_obj= self.env['sale.order'].search([])
			for sale in sale_obj:
				dt = sale.date_order
				date = datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S").date()
				if date>=self.date_from and date<=self.date_to:
					for line in sale.order_line:
						if not line.display_type:
							a = sale.id
							b = [sale.name,sale.partner_id.hcp_customer_id,sale.partner_id.name,line.product_id.default_code,line.product_id.name,line.discount,line.line_amount*line.discount/100]
							discount_details ={'id':a,'values':b}
							discount_list.append(discount_details)
			list_product=discount_list
			for data in list_product:
				prdt_details =[]
				prdt_details.append(data['values'][0])
				prdt_details.append(data['values'][1])
				prdt_details.append(data['values'][2])
				prdt_details.append(data['values'][3])
				prdt_details.append(data['values'][4])
				prdt_details.append(data['values'][5])
				prdt_details.append(data['values'][6])
				prdt_list1.append(prdt_details)
			return_list['sale_ids'] = prdt_list1


		return return_list


	def print_xlsx_report(self):
		workbook = xlwt.Workbook()
		sheet = workbook.add_sheet("Discounts Given - Detailed Report")
		format2 = xlwt.easyxf('font: bold 1')
		format3 = xlwt.easyxf('font: bold 1; align: horiz right',)
		first_col = sheet.col(0)
		two_col = sheet.col(1)
		three_col = sheet.col(2)
		fourth_col = sheet.col(3)
		fifth_col = sheet.col(4)
		sixth_col = sheet.col(5)
		seventh_col = sheet.col(6)
		first_col.width = 150*20
		two_col.width = 150*20
		three_col.width = 500*20
		fourth_col.width = 150*20
		fifth_col.width = 500 * 20
		sixth_col.width = 200 * 20
		seventh_col.width = 250 * 20

		style1 = xlwt.easyxf(num_format_str='#,##0.00')
		sheet.write(0,0,'SO#',format2)
		sheet.write(0,1,'CUST#',format2)
		sheet.write(0,2,'Customer Name',format2)
		sheet.write(0,3,'Product#',format2)
		sheet.write(0,4,'Product Name',format2)
		sheet.write(0,5,'Discount(%)',format3)
		sheet.write(0,6,'Discount Amount',format3)
		data = self.get_data()
		dt = data.get('sale_ids')
		row_number = 1
		# col_number =0
		for value in dt:
			# raise UserError(round(value[5],2))
			sheet.write(row_number,0,value[0])
			sheet.write(row_number,1,value[1])
			sheet.write(row_number,2,value[2])
			sheet.write(row_number,3,value[3])
			sheet.write(row_number,4,value[4])
			sheet.write(row_number,5,value[5],style1)
			sheet.write(row_number,6,value[6],style1)
			row_number+=1	

		output = StringIO()
		if platform.system() == 'Linux':
			filename = ('/tmp/Discounts Given - Detailed Report' +'.xls')
		else:
			filename = ('Discounts Given - Detailed Report' +'.xls')

		workbook.save(filename)
		fp = open(filename, "rb")
		file_data = fp.read()
		out = base64.encodestring(file_data)

		# Files actions
		attach_vals = {
				'product_data': 'Discounts Given - Detailed Report'+ '.xls',
				'file_name': out,
				# 'purchase_work':'Purchase'+ '.csv',
				# 'file_names':data,
				}

		act_id = self.env['product.report.out'].create(attach_vals)
		fp.close()
		return {
			'type': 'ir.actions.act_window',
			'res_model': 'product.report.out',
			'res_id': act_id.id,
			'view_type': 'form',
			'view_mode': 'form',
			'context': self.env.context,
			'target': 'new',
				}


		
	

					







              
                      


