from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_is_zero, float_compare, safe_eval, date_utils, email_split, email_escape_char, email_re
from odoo.tools.misc import formatLang, format_date, get_lang

from datetime import date, timedelta
from itertools import groupby
from itertools import zip_longest
from hashlib import sha256
from json import dumps

import json
import re
import time



class AccountMove(models.Model):
	_inherit = "account.move"
	

	@api.depends('invoice_line_ids.price_total')
	def compute_amount_all(self):
		"""
		Compute the total amounts of the invoice.
		"""
		for invoice in self:
			amount_untaxed = amount_tot = 0.0
			for line in invoice.invoice_line_ids:
				amount_untaxed += line.price_subtotal
				amount_tot += line.price_total
			invoice.update({
				# 'amount_untaxed': amount_untaxed,
				# 'amount_tax': amount_tax,
				'total_amount': amount_tot,
			})




	total_amount= fields.Float(string="Total Amount",compute='compute_amount_all',store=True)





	# def action_invoice_sent(self):
	# 	""" Open a window to compose an email, with the edi invoice template
	# 		message loaded by default
	# 	"""
	# 	self.ensure_one()
	# 	template = self.env.ref('hcp_custom_reports.invoice_send_email_template_id', raise_if_not_found=False)
	# 	lang = get_lang(self.env)
	# 	if template and template.lang:
	# 		lang = template._render_template(template.lang, 'account.move', self.id)
	# 	else:
	# 		lang = lang.code
	# 	compose_form = self.env.ref('account.account_invoice_send_wizard_form', raise_if_not_found=False)
	# 	ctx = dict(
	# 		default_model='account.move',
	# 		default_res_id=self.id,
	# 		default_use_template=bool(template),
	# 		default_template_id=template and template.id or False,
	# 		default_composition_mode='comment',
	# 		mark_invoice_as_sent=True,
	# 		custom_layout="mail.mail_notification_paynow",
	# 		model_description=self.with_context(lang=lang).type_name,
	# 		force_email=True
	# 	)
	# 	return {
	# 		'name': _('Send Invoice'),
	# 		'type': 'ir.actions.act_window',
	# 		'view_type': 'form',
	# 		'view_mode': 'form',
	# 		'res_model': 'account.invoice.send',
	# 		'views': [(compose_form.id, 'form')],
	# 		'view_id': compose_form.id,
	# 		'target': 'new',
	# 		'context': ctx,
	# 	}





class AccountMoveLine(models.Model):
	_inherit = "account.move.line"






	price_tax = fields.Float(string="Total Tax")
	invoice_ship_method = fields.Boolean(string='Invoice ship',default=False,compute='ship_line_method')
	inv_line_amount = fields.Float(string="Line Amount",compute='_compute_invoice_line_level_amount',store=True)


	@api.depends('quantity','price_unit')
	def _compute_invoice_line_level_amount(self):
		for line in self:
			line.inv_line_amount = line.quantity * line.price_unit



	def ship_line_method(self):
		for line in self:
			ship_line = self.env['delivery.carrier'].search([('name','=',line.name)])
			if ship_line:
				line.invoice_ship_method = True
			else:
				line.invoice_ship_method = False




