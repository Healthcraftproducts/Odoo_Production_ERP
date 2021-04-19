from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang



class PurchaseOrder(models.Model):
	_inherit = "purchase.order"

	# scheduled_date = fields.Date(string="Scheduled Date")

	def action_rfq_send(self):
		'''
		This function opens a window to compose an email, with the edi purchase template message loaded by default
		'''
		self.ensure_one()
		ir_model_data = self.env['ir.model.data']
		try:
			if self.env.context.get('send_rfq', False):
				template_id = ir_model_data.get_object_reference('hcp_custom_reports', 'purchase_quotation_email_rfq_template')[1]
			else:
				template_id = ir_model_data.get_object_reference('hcp_custom_reports', 'order_purchase_send_po_email_template')[1]
		except ValueError:
			template_id = False
		try:
			compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
		except ValueError:
			compose_form_id = False
		ctx = dict(self.env.context or {})
		ctx.update({
			'default_model': 'purchase.order',
			'active_model': 'purchase.order',
			'active_id': self.ids[0],
			'default_res_id': self.ids[0],
			'default_use_template': bool(template_id),
			'default_template_id': template_id,
			'default_composition_mode': 'comment',
			'custom_layout': "mail.mail_notification_paynow",
			'force_email': True,
			'mark_rfq_as_sent': True,
		})

		# In the case of a RFQ or a PO, we want the "View..." button in line with the state of the
		# object. Therefore, we pass the model description in the context, in the language in which
		# the template is rendered.
		lang = self.env.context.get('lang')
		if {'default_template_id', 'default_model', 'default_res_id'} <= ctx.keys():
			template = self.env['mail.template'].browse(ctx['default_template_id'])
			if template and template.lang:
				lang = template._render_template(template.lang, ctx['default_model'], ctx['default_res_id'])

		self = self.with_context(lang=lang)
		if self.state in ['draft', 'sent']:
			ctx['model_description'] = _('Request for Quotation')
		else:
			ctx['model_description'] = _('Purchase Order')

		return {
			'name': _('Compose Email'),
			'type': 'ir.actions.act_window',
			'view_mode': 'form',
			'res_model': 'mail.compose.message',
			'views': [(compose_form_id, 'form')],
			'view_id': compose_form_id,
			'target': 'new',
			'context': ctx,
			}
