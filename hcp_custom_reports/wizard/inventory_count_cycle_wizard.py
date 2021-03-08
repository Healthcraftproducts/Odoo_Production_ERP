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

class InventoryReportOut(models.Model):
	_name = 'inventory.count.report.out'
	_description = 'Inventory Cycle Report Out'

	inv_rep_data = fields.Char('Name', size=256)
	file_name = fields.Binary('Inventory Count Cycle Report', readonly=True)


class InventoryCountCycleReportWizard(models.TransientModel):
	_name = "inventory.count.report.wizard"
	_description = "Inventory Count Report Wizard"

	date_from = fields.Date(string="Date From",required=True)
	date_to = fields.Date(string="Date To",required=True)
	location_id = fields.Many2one('stock.location',string="Location",required=True)

	def get_data(self):
		inv_list = []
		stock_list1 =[]
		return_list = {}
		date_from = self.date_from
		date_to = self.date_to
		location_id = self.location_id.id
		loc_name=self.location_id.complete_name
		stock_inventory = self.env['stock.inventory'].search([])
		for stock in stock_inventory:
			for loc in stock.location_ids:
				if loc.id == location_id:
					dt = stock.date
					st_date = datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S").date()
					if st_date>=date_from and st_date<=date_to:
						for line in stock.line_ids:
							product = self.env['product.product'].search([('id','=',line.product_id.id)])
							onhand_qty = sum(line.theoretical_qty for line in stock.line_ids if line.product_id.id in product.ids)
							adj_qty = sum(line.product_qty for line in stock.line_ids if line.product_id.id in product.ids)
							a=line.product_id.id
							b=[stock.name,loc_name,line.product_id.default_code,line.product_id.name,onhand_qty,adj_qty,line.product_uom_id.name]
							invent_details={'id':a,'values':b}
							inv_list.append(invent_details)
		list_inventory = inv_list
		new_v =[]
		for y in list_inventory:
			if y not in new_v:
				new_v.append(y)
		for data in new_v:
			stock_list=[]
			stock_list.append(data['values'][0])
			stock_list.append(data['values'][1])
			stock_list.append(data['values'][2])
			stock_list.append(data['values'][3])
			stock_list.append(data['values'][4])
			stock_list.append(data['values'][5])
			stock_list.append(data['values'][6])
			stock_list1.append(stock_list)
		
		return_list['stock_ids'] = stock_list1
		# if stock_list1:
		# 	raise UserError(stock_list1)

		return return_list
	
	def print_inv_count_xls_report(self):
		workbook = xlwt.Workbook()
		sheet = workbook.add_sheet("Inventory Count Cycle Report")
		format2 = xlwt.easyxf('font: bold 1')
		format3 = xlwt.easyxf('font: bold 1; align: horiz right',)
		style1 = xlwt.easyxf(num_format_str='#,##0.00')
		first_col = sheet.col(0)
		two_col = sheet.col(1)
		three_col = sheet.col(2)
		fourth_col = sheet.col(3)
		fifth_col = sheet.col(4)
		sixth_col = sheet.col(5)
		seventh_col = sheet.col(6)
		first_col.width = 250*20
		two_col.width = 250*20
		three_col.width = 150*20
		fourth_col.width = 400*20
		fifth_col.width = 200*20
		sixth_col.width = 200*20
		seventh_col.width = 200*20
		sheet.write(0,0,'Inventory',format2)
		sheet.write(0,1,'Location Name',format2)
		sheet.write(0,2,'Item Code',format2)
		sheet.write(0,3,'Product Name',format2)
		sheet.write(0,4,'OnHand Qty',format3)
		sheet.write(0,5,'Adjusted Qty',format3)
		sheet.write(0,6,'Unit Of Measure',format2)
		data = self.get_data()
		dt = data.get('stock_ids')
		row_number = 1
		for value in dt:
			sheet.write(row_number,0,value[0])
			sheet.write(row_number,1,value[1])
			sheet.write(row_number,2,value[2])
			sheet.write(row_number,3,value[3])
			sheet.write(row_number,4,value[4],style1)
			sheet.write(row_number,5,value[5],style1)
			sheet.write(row_number,6,value[6])
			row_number +=1


		output = StringIO()
		if platform.system() == 'Linux':
			filename = ('/tmp/Inventory Count Cycle Report' +'.xls')
		else:
			filename = ('Inventory Count Cycle Report' +'.xls')

		workbook.save(filename)
		fp = open(filename, "rb")
		file_data = fp.read()
		out = base64.encodestring(file_data)
		# Files actions
		attach_vals = {
				'inv_rep_data': 'Inventory Count Cycle Report'+ '.xls',
				'file_name': out,
				# 'purchase_work':'Purchase'+ '.csv',
				# 'file_names':data,
				}

		act_id = self.env['inventory.count.report.out'].create(attach_vals)
		fp.close()
		return {
			'type': 'ir.actions.act_window',
			'res_model': 'inventory.count.report.out',
			'res_id': act_id.id,
			'view_type': 'form',
			'view_mode': 'form',
			'context': self.env.context,
			'target': 'new',
				}

































	# def print_inv_count_xls_report(self):
		
	# 	date_from = self.date_from
	# 	date_to = self.date_to
	# 	location_id = self.location_id.id
	# 	self._cr.execute("""select 
	# 							sil.location_id,
	#  							sil.product_id,
	#  							sum(sil.theoretical_qty) as OnHandQuantity,
	#  							sum(sil.product_qty) as AdjustedQty
	# 						from 
	# 							stock_inventory_line sil
	# 						where
	# 							date(sil.inventory_date)>= %s and date(sil.inventory_date)<= %s and 
	# 							sil.location_id= %s
	# 						group by 
 # 								sil.product_id,
	# 							sil.location_id;
	# 										""", (date_from,date_to,location_id))
	# 	sql_data = self._cr.fetchall()
	# 	workbook = xlwt.Workbook()
	# 	sheet = workbook.add_sheet("Inventory Count Cycle Report")
	# 	first_col = sheet.col(0)
	# 	two_col = sheet.col(1)
	# 	three_col = sheet.col(2)
	# 	fourth_col = sheet.col(3)		
	# 	first_col.width = 250*20
	# 	two_col.width = 500*20
	# 	three_col.width = 250*20
	# 	fourth_col.width = 250*20
	# 	format2 = xlwt.easyxf('font: bold 1')
	# 	format3 = xlwt.easyxf('font: bold 1; align: horiz right')
	# 	style1 = xlwt.easyxf(num_format_str='#,##0.00')
	# 	sheet.write(0,0,'Location Name',format2)
	# 	sheet.write(0,1,'Product Name',format2)
	# 	sheet.write(0,2,'OnHand Qty',format3)
	# 	sheet.write(0,3,'Adjusted Qty',format3)
	# 	for row, line in enumerate(sql_data,start=1):
	# 		for col, cell in enumerate(line):
	# 			if isinstance(cell,float):
	# 				sheet.write(row, col, cell,style1)
	# 			else:
	# 				sheet.write(row,col,cell)

	# 	output = StringIO()
	# 	if platform.system() == 'Linux':
	# 		filename = ('/tmp/Inventory Count Cycle Report' +'.xls')
	# 	else:
	# 		filename = ('Inventory Count Cycle Report' +'.xls')

	# 	workbook.save(filename)
	# 	fp = open(filename, "rb")
	# 	file_data = fp.read()
	# 	out = base64.encodestring(file_data)
	# 	# Files actions
	# 	attach_vals = {
	# 			'inv_rep_data': 'Inventory Count Cycle Report'+ '.xls',
	# 			'file_name': out,
	# 			# 'purchase_work':'Purchase'+ '.csv',
	# 			# 'file_names':data,
	# 			}

	# 	act_id = self.env['inventory.count.report.out'].create(attach_vals)
	# 	fp.close()
	# 	return {
	# 		'type': 'ir.actions.act_window',
	# 		'res_model': 'inventory.count.report.out',
	# 		'res_id': act_id.id,
	# 		'view_type': 'form',
	# 		'view_mode': 'form',
	# 		'context': self.env.context,
	# 		'target': 'new',
	# 			}













