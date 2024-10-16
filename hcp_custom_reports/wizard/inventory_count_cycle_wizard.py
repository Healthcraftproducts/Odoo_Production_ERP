from odoo import api, fields, models, _
from datetime import date,datetime, timedelta
from odoo.exceptions import UserError
import xlwt
from io import StringIO
import base64
import platform
import pdb
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz
try:
	from odoo.tools.misc import xlsxwriter
except ImportError:
	import xlsxwriter

class InventoryReportOut(models.Model):
	_name = 'inventory.count.report.out'
	_description = 'Inventory Cycle Report Out'

	inv_rep_data = fields.Char('Name', size=256)
	file_name = fields.Binary('Inventory Cycle Count Report', readonly=True)


class InventoryCountCycleReportWizard(models.TransientModel):
	_name = "inventory.count.report.wizard"
	_description = "Inventory Count Report Wizard"

	date_from = fields.Date(string="Date From",required=True)
	date_to = fields.Date(string="Date To",required=True)
	# location_id = fields.Many2one('stock.location',string="Location",required=True)
	loc_ids = fields.Many2many('stock.location',string="Location",required=True,domain="[('usage','=','internal')]")

	#def get_data(self):
		#inv_list = []
		#stock_list1 =[]
		#return_list = {}
		#date_from = self.date_from
		#date_to = self.date_to
		## location_id = self.location_id.id
		#loc_ids = self.loc_ids.ids

		## loc_name = self.loc_ids.complete_name
		## if loc_ids:
		## 	raise UserError(loc_ids)
		## loc_name=self.location_id.complete_name
		#stock_inventory = self.env['stock.inventory'].search([('location_ids','in',loc_ids)])
		#for stock in stock_inventory:
			#dt = stock.date
			#st_date = datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S").date()
			#if st_date>=date_from and st_date<=date_to:
				#for line in stock.line_ids:
					#if line.location_id.id in loc_ids:
						## product = self.env['product.product'].search([('id','=',line.product_id.id)])
						## loc_name = [loc_id.complete_name for loc_id in self.loc_ids if loc_id.id == line.location_id.id]
						## onhand_qty = sum(line.theoretical_qty for line in stock.line_ids if line.product_id.id in product.ids)
						## adj_qty = sum(line.product_qty for line in stock.line_ids if line.product_id.id in product.ids)
						#a=line.product_id.id
						#b=[stock.name,line.location_id.complete_name,line.inventory_date,line.product_id.default_code,line.product_id.name,line.prod_lot_id.name,line.theoretical_qty,line.product_qty,line.difference_qty,line.product_uom_id.name,line.product_id.standard_price,line.difference_qty*line.product_id.standard_price]
						#invent_details={'id':a,'values':b}
						#inv_list.append(invent_details)
		#list_inventory = inv_list
		## new_v =[]
		## for y in list_inventory:
		## 	if y not in new_v:
		## 		new_v.append(y)
		#for data in list_inventory:
			#stock_list=[]
			#stock_list.append(data['values'][0])
			#stock_list.append(data['values'][1])
			#stock_list.append(data['values'][2])
			#stock_list.append(data['values'][3])
			#stock_list.append(data['values'][4])
			#stock_list.append(data['values'][5])
			#stock_list.append(data['values'][6])
			#stock_list.append(data['values'][7])
			#stock_list.append(data['values'][8])
			#stock_list.append(data['values'][9])
			#stock_list.append(data['values'][10])
			#stock_list.append(data['values'][11])
			#stock_list1.append(stock_list)
		
		#return_list['stock_ids'] = stock_list1
		## if stock_list1:
		## 	raise UserError(stock_list1)

		#return return_list
	
	def print_inv_count_xls_report(self):
		workbook = xlwt.Workbook()
		sheet = workbook.add_sheet("Inventory Cycle Count Report")
		format2 = xlwt.easyxf('font: bold 1,height 180;align: horiz center;')
		format3 = xlwt.easyxf('font: bold 1; align: horiz right',)
		style1 = xlwt.easyxf(num_format_str='#,##0.00')
		style2 = xlwt.easyxf('align: horiz left',num_format_str='mm-dd-yyyy hh:mm:ss')
		style3 = xlwt.easyxf(num_format_str ='"$"#,##0.00')
		sheet.row(0).height_mismatch = True
		sheet.row(0).height = 300
		sheet.col(0).width = 2000
		sheet.col(1).width = 10000
		sheet.col(2).width = 10000
		sheet.col(3).width = 7000
		sheet.col(4).width = 5000
		sheet.col(5).width = 5000
		sheet.col(6).width = 10000
		sheet.col(7).width = 5000
		sheet.col(8).width = 4000
		sheet.col(9).width = 4000
		sheet.col(10).width = 4000
		sheet.col(11).width = 4000
		sheet.col(12).width = 4000
		sheet.col(13).width = 4000

		field_heading1 = ["S.NO","Inventory","Location Name","Inventory Date",
                        "Item Code", "Product Name", "Lot/Serial No", "OnHand Qty",
                        "Counted Qty", "Difference Qty", "Unit Of Measure",
                        "Product Cost", "$Difference(Price)"]

		for index, col_data in enumerate(field_heading1):
			sheet.write(0, index, col_data, format2)

		sheet.set_panes_frozen(True)
		sheet.set_horz_split_pos(1)
		sheet.set_remove_splits(True)

		# data = self.get_data()
		# dt = data.get('stock_ids')
		date_from = self.date_from
		date_to = self.date_to
		loc_ids = self.loc_ids.ids
		
		domain=[('location_id','in',loc_ids),('date','>=',date_from),('date','<=',date_to),('is_inventory','=',True)]
		stock_inventory = self.env['stock.move'].search(domain)
		row_number = 1
		s_no = 1
		#for value in dt:
		for stock in stock_inventory:
			#import pdb
			#pdb.set_trace()
			for line in stock.move_line_ids:
				for quant in stock.move_line_ids.product_stock_quant_ids:
					differnce_inventory_quantity = line.qty_done - quant.quantity
					sheet.write(row_number,0,s_no)
					sheet.write(row_number,1,stock.name)
					sheet.write(row_number,2,line.location_id.complete_name)
					custm_date = line.date
					#- timedelta(hours=5, minutes=30)
					user_tz = self.env.user.tz or pytz.utc
					local_time = pytz.timezone(user_tz)
					display_date_result = datetime.strftime(pytz.utc.localize(datetime.strptime(str(line.date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local_time),"%d-%m-%Y %H:%M:%S")
					sheet.write(row_number,3,display_date_result,style2)
					sheet.write(row_number,4,line.product_id.default_code)
					sheet.write(row_number,5,line.product_id.name)
					sheet.write(row_number,6,line.lot_id.name)
					sheet.write(row_number,7,quant.quantity,style1)
					sheet.write(row_number,8,line.qty_done,style1)
					sheet.write(row_number,9,differnce_inventory_quantity,style1)
					sheet.write(row_number,10,line.product_uom_id.name)
					sheet.write(row_number,11,line.product_id.standard_price,style3)

					different_price = differnce_inventory_quantity*line.product_id.standard_price
					#line.difference_qty*line.product_id.standard_price
					sheet.write(row_number,12,different_price,style3)
					row_number +=1
					s_no+=1


		output = StringIO()
		if platform.system() == 'Linux':
			filename = ('/tmp/Inventory Cycle Count Report' +'.xls')
		else:
			filename = ('Inventory Cycle Count Report' +'.xls')

		workbook.save(filename)
		fp = open(filename, "rb")
		file_data = fp.read()
		out = base64.encodebytes(file_data)
		# Files actions
		attach_vals = {
				'inv_rep_data': 'Inventory Cycle Count Report'+ '.xls',
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













