from odoo import api, models, _
from odoo.exceptions import UserError
from datetime import datetime


class DiscountDetailedReport(models.AbstractModel):
	_name = 'report.hcp_custom_reports.report_product_discount_details_given'
	_description = 'Discount Detailed Report'


	# @api.model
	def get_data(self,data):
		discount_list=[]
		return_list ={}
		prdt_list1=[]
		date_from = data['form']['date_from']
		date_to = data['form']['date_to']
		partner = data['form']['partner_id']
		if partner:
			partner = partner[0]
			# raise UserError(partner)
			sale_obj = self.env['sale.order'].search([('partner_id','=',partner)])
			if sale_obj:
				# raise UserError(sale_obj)
				for sale in sale_obj:
					dt = sale.date_order
					date = datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S").date()
					date = str(date)
					if date>=date_from and date<=date_to:
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
				date = str(date)
				if date>=date_from and date<=date_to:
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



	@api.model
	def _get_report_values(self, docids, data=None):
		discount_details = []
		if not data.get('form'):
			raise UserError(_("Content is missing, this report cannot be printed."))
			# self.model = 'sale.order'
		self.model = self.env.context.get('active_model')
		discount_details = self.get_data(data)
		# if discount_details:
		# 	raise UserError(discount_details)
		return {
			'doc_ids': self.ids,
			'doc_model': 'sale.order',
			# 'time': time,
			'discount_report': discount_details,
			}





class DiscountSummaryReport(models.AbstractModel):
	_name = 'report.hcp_custom_reports.discount_summary_product_wise_report'
	_description = 'Discount Summary Report'


	# @api.model
	def get_summary_report(self,data):

		date_from = data['form']['date_from']
		date_to = data['form']['date_to']
		# if date_from:
		# 	raise UserError(type(date_from))

		self._cr.execute("""select 
							 	
								sol.name,
								sum(sol.discount) as Disc,
								sum(sol.discount*sol.line_amount/100) as Discount_Amount

							from 
								sale_order so,
								sale_order_line sol
							where
								so.id = sol.order_id and
								date(so.date_order) >= %s and date(so.date_order) <= %s and
								sol.display_type is NULL
							group by 
 								
								sol.name;
											""", (date_from,date_to))
		sql_data = self._cr.fetchall()

		return sql_data
		





	@api.model
	def _get_report_values(self, docids, data=None):
		discount_summary = []
		if not data.get('form'):
			raise UserError(_("Content is missing, this report cannot be printed."))
			# self.model = 'sale.order'
		self.model = self.env.context.get('active_model')
		discount_summary = self.get_summary_report(data)
		# if discount_details:
		# 	raise UserError(discount_details)
		return {
			'doc_ids': self.ids,
			'doc_model': 'sale.order',
			# 'time': time,
			'discount_value': discount_summary,
			}


