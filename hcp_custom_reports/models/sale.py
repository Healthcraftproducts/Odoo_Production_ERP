from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare



from werkzeug.urls import url_encode


class SaleOrder(models.Model):
	_inherit ="sale.order"

	# def set_delivery_line(self, carrier, amount):
	# 	# Remove delivery products from the sales order
	# 	self._remove_delivery_line()

	# 	for order in self:
	# 		order.carrier_id = carrier.id
	# 		order._create_delivery_line(carrier, amount)
	# 	return True

	# def _create_delivery_line(self, carrier, price_unit):
	# 	SaleOrderLine = self.env['sale.order.line']
	# 	if self.partner_id:
	# 		# set delivery detail in the customer language
	# 		carrier = carrier.with_context(lang=self.partner_id.lang)

	# 	# Apply fiscal position
	# 	taxes = carrier.product_id.taxes_id.filtered(lambda t: t.company_id.id == self.company_id.id)
	# 	taxes_ids = taxes.ids
	# 	if self.partner_id and self.fiscal_position_id:
	# 		taxes_ids = self.fiscal_position_id.map_tax(taxes, carrier.product_id, self.partner_id).ids

	# 	# Create the sales order line
	# 	carrier_with_partner_lang = carrier.with_context(lang=self.partner_id.lang)
	# 	if carrier_with_partner_lang.product_id.description_sale:
	# 		so_description = '%s: %s' % (carrier_with_partner_lang.name,
	# 										carrier_with_partner_lang.product_id.description_sale)
	# 	else:
	# 		so_description = carrier_with_partner_lang.name
	# 	values = {
	# 		'order_id': self.id,
	# 		'name': so_description,
	# 		'product_uom_qty': 1,
	# 		'product_uom': carrier.product_id.uom_id.id,
	# 		'product_ship_method':True,
	# 		'product_id': carrier.product_id.id,
	# 		'tax_id': [(6, 0, taxes_ids)],
	# 		'is_delivery': True,
	# 		}
	# 	if carrier.invoice_policy == 'real':
	# 		values['price_unit'] = 0
	# 		values['name'] += _(' (Estimated Cost: %s )') % self._format_currency_amount(price_unit)
	# 	else:
	# 		values['price_unit'] = price_unit
	# 	if carrier.free_over and self.currency_id.is_zero(price_unit) :
	# 		values['name'] += '\n' + 'Free Shipping'
	# 	if self.order_line:
	# 		values['sequence'] = self.order_line[-1].sequence + 1
	# 	sol = SaleOrderLine.sudo().create(values)
	# 	return sol







	@api.depends('order_line.price_total')
	def compute_amount_all(self):
		"""
		Compute the total amounts of the SO.
		"""
		for order in self:
			amount_untaxed = amount_tax = 0.0
			for line in order.order_line:
				amount_untaxed += line.price_subtotal
				amount_tax += line.price_tax
			order.update({
				# 'amount_untaxed': amount_untaxed,
				# 'amount_tax': amount_tax,
				'total_amount': amount_untaxed + amount_tax,
			})




	quotation_id = fields.Char(string="Quotation No", readonly=True, required=True, copy=False, default='New')
	contact_name = fields.Many2one('res.partner',string='Contact Person')
	person_name = fields.Char(string='Person Name')
	email = fields.Char(string="Email")
	phone = fields.Char(string="Phone")
	total_amount = fields.Float(string='Total Amount',compute='compute_amount_all',store=True)
	expected_date = fields.Datetime( help="Delivery date you can promise to the customer, computed from the minimum lead time of "
											"the order lines in case of Service products. In case of shipping, the shipping policy of "
											"the order will be taken into account to either use the minimum or maximum lead time of "
											"the order lines.",inverse='_inverse_expected_date')

	@api.depends('picking_policy')
	def _compute_expected_date(self):
		super(SaleOrder, self)._compute_expected_date()
		for order in self:
			dates_list = []
			for line in order.order_line.filtered(lambda x: x.state != 'cancel' and not x._is_delivery()):
				dt = line._expected_date()
				dates_list.append(dt)
			if dates_list:
				expected_date = min(dates_list) if order.picking_policy == 'direct' else max(dates_list)
				order.expected_date = fields.Datetime.to_string(expected_date)

	# @api.depends('picking_policy')
	def _inverse_expected_date(self):
		super(SaleOrder, self)._compute_expected_date()
		for order in self:
			dates_list = []
			for line in order.order_line.filtered(lambda x: x.state != 'cancel' and not x._is_delivery()):
				dt = line._expected_date()
				dates_list.append(dt)
			if dates_list:
				expected_date = min(dates_list) if order.picking_policy == 'direct' else max(dates_list)
				order.expected_date = fields.Datetime.to_string(expected_date)





	@api.onchange('partner_id')
	def on_change_partner_id(self):
		for rec in self:
			if rec.partner_id:
				for child in rec.partner_id.child_ids:
					rec.contact_name = child
			else:
				rec.contact_name=False

			return {'domain': {
						'contact_name': [('parent_id', '=', rec.partner_id.id)],
						'partner_invoice_id': [('parent_id', '=', rec.partner_id.id)],
						'partner_shipping_id':[('parent_id','=',rec.partner_id.id)]	
															}
					}
														


	@api.onchange('contact_name')
	def compute_contact_name(self):
		if self.contact_name:
			self.person_name = self.contact_name.name
			self.email = self.contact_name.email
			self.phone = self.contact_name.phone
		else:
			self.person_name= False
			self.email=False
			self.phone=False
			




	# @api.model
	# def create(self, vals):
	# 	if vals.get('quotation_id', 'New') == 'New':
	# 		vals['quotation_id'] = self.env['ir.sequence'].next_by_code('quotation.id') or 'New'
	# 	result = super(SaleOrder, self).create(vals)
	# 	return result


	@api.model
	def create(self, vals):
		if vals.get('quotation_id', 'New') == 'New':
			vals['quotation_id'] = self.env['ir.sequence'].next_by_code('quotation.id') or 'New'

		if vals.get('name', _('New')) == _('New'):
			seq_date = None
			if 'date_order' in vals:
				seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
			if 'company_id' in vals:
				vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(
					'order.id', sequence_date=seq_date) or _('New')
			else:
				vals['name'] = self.env['ir.sequence'].next_by_code('order.id', sequence_date=seq_date) or _('New')

		# Makes sure partner_invoice_id', 'partner_shipping_id' and 'pricelist_id' are defined
		if any(f not in vals for f in ['partner_invoice_id', 'partner_shipping_id', 'pricelist_id']):
			partner = self.env['res.partner'].browse(vals.get('partner_id'))
			addr = partner.address_get(['delivery', 'invoice'])
			vals['partner_invoice_id'] = vals.setdefault('partner_invoice_id', addr['invoice'])
			vals['partner_shipping_id'] = vals.setdefault('partner_shipping_id', addr['delivery'])
			vals['pricelist_id'] = vals.setdefault('pricelist_id', partner.property_product_pricelist and partner.property_product_pricelist.id)
		result = super(SaleOrder, self).create(vals)
		return result




	def _find_mail_template(self, force_confirmation_template=False):
		template_id = False

		if force_confirmation_template or (self.state == 'sale' and not self.env.context.get('proforma', False)):
			template_id = int(self.env['ir.config_parameter'].sudo().get_param('hcp_custom_reports.default_email_confirmation_template'))
			template_id = self.env['mail.template'].search([('id', '=', template_id)]).id
			if not template_id:
				template_id = self.env['ir.model.data'].xmlid_to_res_id('hcp_custom_reports.order_confirmation_email_template', raise_if_not_found=False)
		if not template_id:
			template_id = self.env['ir.model.data'].xmlid_to_res_id('hcp_custom_reports.quotation_email_template_send', raise_if_not_found=False)

		return template_id

	def action_quotation_send(self):
		''' Opens a wizard to compose an email, with relevant mail template loaded by default '''
		self.ensure_one()
		template_id = self._find_mail_template()
		lang = self.env.context.get('lang')
		template = self.env['mail.template'].browse(template_id)
		if template.lang:
			lang = template._render_template(template.lang, 'sale.order', self.ids[0])
		ctx = {
			'default_model': 'sale.order',
			'default_res_id': self.ids[0],
			'default_use_template': bool(template_id),
			'default_template_id': template_id,
			'default_composition_mode': 'comment',
			'mark_so_as_sent': True,
			'custom_layout': "mail.mail_notification_paynow",
			'proforma': self.env.context.get('proforma', False),
			'force_email': True,
			'model_description': self.with_context(lang=lang).type_name,
		}
		if ctx['mark_so_as_sent'] == True and self.state in ['sale', 'done']:
			self.write({'so_email_status': 'so_email_sent'})

		return {
			'type': 'ir.actions.act_window',
			'view_mode': 'form',
			'res_model': 'mail.compose.message',
			'views': [(False, 'form')],
			'view_id': False,
			'target': 'new',
			'context': ctx,
		}






class SaleOrderLine(models.Model):
	_inherit = 'sale.order.line'


	product_ship_method = fields.Boolean(string='Product Ship',default=False)
