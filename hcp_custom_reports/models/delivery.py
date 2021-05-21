from odoo import fields, models, api, _
from odoo.exceptions import UserError


#class ChooseDeliveryCarrier(models.TransientModel):
	#_inherit = 'choose.delivery.carrier'

	#def button_confirm(self):
		#self.order_id.set_delivery_line(self.carrier_id, self.delivery_price)
		#self.order_id.write({
			#'recompute_delivery_price': False,
			#'delivery_message': self.delivery_message,
		#})


class StockPicking(models.Model):
	_inherit = 'stock.picking'

	shipment_date = fields.Date(string='Shipment Date',tracking=True)

	def button_validate(self):
		res = super(StockPicking, self).button_validate()
		self.write({'shipment_date': fields.Datetime.now()})
		return res
