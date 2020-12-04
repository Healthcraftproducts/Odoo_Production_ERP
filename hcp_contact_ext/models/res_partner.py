from odoo import models, fields, api
import logging
import threading
from psycopg2 import sql
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, tools, SUPERUSER_ID
from odoo.tools.translate import _
from odoo.tools import email_re, email_split
from odoo.exceptions import UserError, AccessError
from odoo.addons.phone_validation.tools import phone_validation
from collections import OrderedDict, defaultdict

class DisplaysHealthcraft(models.Model):
	_name = 'displays.healthcraft'
	_rec_name ='name'

	name = fields.Char(string='Name', required=True)


class DisplaysInvisia(models.Model):
	_name = 'displays.invisia'
	_rec_name = 'name'

	name = fields.Char(string='Name', required=True)


class HCPFederalTax(models.Model):
	_name = 'hcp.federal.tax'
	_rec_name = 'federal_tax_name'

	federal_tax_name = fields.Char(string='Tax Name')


class ContactTraining(models.Model):
	_name = 'contact.training'
	_rec_name = 'contact_training_name'

	contact_training_name = fields.Char(string="Name")


class ContactsDesignation(models.Model):
	_name = 'contacts.designation'
	_rec_name ='contact_designation_name'

	contact_designation_name = fields.Char(string="Name")

class ContactsRole(models.Model):
	_name = 'contact.role'
	_rec_name = 'contact_role_name'

	contact_role_name = fields.Char(string="Name")



class HcpGroupCode(models.Model):
	_name = 'hcp.group.code'
	_description = "Group Code"
	_rec_name = 'name'

	name = fields.Char(string='Name', required=True)

class DeliveryCarrier(models.Model):
	_inherit = 'delivery.carrier'

	website_description = fields.Char(string="Website Description")

class ResPartner(models.Model):
	_inherit = 'res.partner'


	#def name_get(self):
		## name get function for the model executes automatically
		#res = []
		#for rec in self:
			#res.append((rec.id, '%s' % (rec.name)))
		#return res

	@api.depends('is_company')
	def _compute_company_type(self):
		for partner in self:
			partner.company_type = 'company' if partner.is_company else 'person'

	def _write_company_type(self):
		for partner in self:
			partner.is_company = partner.company_type == 'company'


	hcp_type = fields.Selection([('customer','Customer'),
		('suspect','Suspect'),
		('prospect','Prospect'),
		('lead','Lead'),
		('opportunity','Opportunity'),
		('lapsed','Lapsed'),
		('dormant','Dormant'),
		('influencer','Influencer'),
		('facility','Facility'),
		('competitor','Competitor'),
		('not_intrested','Not Intrested'),
		('vendor','Vendor')],string="Type")
	hcp_customer_id = fields.Char("Customer ID")
	hcp_vendor_no = fields.Char(string="Vendor No.")
	hcp_first_name = fields.Char(string= 'First Name')
	hcp_last_name = fields.Char(string='Last Name')
	hcp_training_completed = fields.Many2many('contact.training',string="Training Completed")
	hcp_website_mapping = fields.Selection([('onmap_platinum','ON Map-Platinum'),
		('onmap_regular_pin_noton_map','ON Map-Regular Pin'),
		('not_on_map','Not on Map')],string="HCP - Website Mapping")
	hcp_inv_website_mapping = fields.Selection([('onmap_platinum','ON Map-Platinum'),
		('onmap_regular_pin_noton_map','ON Map-Regular Pin'),
		('not_on_map','Not on Map')],string="INV - Website Mapping")
	hcp_location_type = fields.Selection([('ho','HO'),
		('residential','Residential'),
		('retail','Retail'),
		('dropship','DropShip'),
		('warehouse','Warehouse')],string="Location Type")
	hcp_designation = fields.Many2many('contacts.designation',string="Designation")
	hcp_role_in_decision_making = fields.Many2many('contact.role',string="Role in Decision Making")
	hcp_fax_no = fields.Char(string="Fax")
	hcp_status = fields.Selection([('active','Active'),
		('inactive','InActive'),
		('out_of_business','Out Of Business'),
		('not_relevant','Not Relevant'),
		('dormant','Dormant'),
		('closed','Closed')],string="Contact Status")
	hcp_price_level = fields.Selection([('platinum','HCP Platinum - 50%'),
		('premium','HCP Premium - 40%'),
		('professional','HCP Professional - 30%'),
		('hcp_special','HCP Special'),
		('other','Other'),
		('see_sales_manager','See Sales Manager'),
		('all_inclusive_us_professional','All Inclusive - US Professional')],string="HCP - Price Level")
	hcp_inv_price_level = fields.Selection([('platinum','Platinum - 50%'),
		('premium','Premium - 40%'),
		('professional-30%','Professional - 30%'),
		('professional','Professional'),		
		('inv_special','Invisia Special'),
		('other','Other'),
		('check_sales_manager','Check With Sales Manager'),
		('all_inclusive_us_professional','All Inclusive - US Professional')],string="INV - Price Level")
	hcp_account_program = fields.Selection([('platinum_nurturing_program','Platinum Nurturing Program'),
		('no_program','No Program')],string="Account Program")
	hcp_sdr_start_date = fields.Date(string="SDR Start Date")
	hcp_type_subcategory = fields.Selection([('state_work_only','State Work Only')],string="Type - SubCategory")
	hcp_source = fields.Selection([('phone','Phone'),
								('email','Email'),
								('inbound_phone','Inbound - Phone'),
								('outbound_sdr','Outbound - SDR'),
								('employee','Employee'),
								('import','Import'),
								('web','Web'),
								('mql_cold_list','MQL Cold List'),
								('inbound_website','Inbound Website'),
								('email_marketing_campaign','Email Marketing Campaign'),
								('customer_referal','Customer Referral'),
								('invacare_transition','Invacare Transition'),
								('google','Google'),
								('alfa','ALFA - Assisted Living Federation of America'),
								('tradeshow','Tradeshow'),
								('live_chat','Live Chat')],string="Source")
	hcp_display_healthcraft = fields.Many2many('displays.healthcraft',string="Display HealthCraft")
	hcp_display_invisia = fields.Many2many('displays.invisia',string="Display Invisia")
	hcp_ship_via_description = fields.Char(string="Ship Via Description")
	hcp_credit_limit = fields.Integer(string="Credit Limit")
	hcp_federal_tax = fields.Many2one('hcp.federal.tax',string="Federal Tax")
	hcp_secondary_email = fields.Char(string="Secondary Email")
	hcp_old_customer_id = fields.Char(string="Old Customer ID")
	hcp_taxes_id = fields.Many2many('account.tax', 'tax_id', string='Tax Groups',domain=[('type_tax_use', '=', 'sale')])
	hcp_group_code = fields.Many2one('hcp.group.code', string='Group Code - New')
	federal_tax_id = fields.Char('Federal Tax ID')
	hcp_fea_registration = fields.Char(string="FEA Registration #")
	company_type = fields.Selection(string='Company Type',
		selection=[('person', 'Individual'), ('company', 'Company')],
		compute='_compute_company_type', inverse='_write_company_type',
		default='company')	
	hcp_is_customer = fields.Boolean(string="Is Customer?",default=True)
	hcp_customer_currency = fields.Many2one("res.currency",string="Customer Currency")
	hcp_is_vendor = fields.Boolean(string="Is Vendor?")	

	@api.model
	def create(self, vals):

		if vals['hcp_is_customer'] == True and vals['company_type'] == 'company':
			customer_no = self.env['ir.sequence'].next_by_code('partner.sequence')
			vals['hcp_customer_id'] = customer_no

		if vals['hcp_is_vendor'] == True and vals['company_type'] == 'company':
			vendor_no = self.env['ir.sequence'].next_by_code('vendor.sequence')
			vals['hcp_vendor_no'] = vendor_no
		if vals['company_type'] == 'person':
			parent_id = vals.get('parent_id')
			if parent_id:
				main_company = self.env['res.partner'].search([('id', '=', parent_id)])
				vals.update({'hcp_customer_id': main_company.hcp_customer_id})
		res = super(ResPartner, self).create(vals)
		return res

	# @api.onchange('company_id', 'parent_id')
	# def _onchange_company_id(self):
	# 	super(ResPartner, self)._onchange_company_id()
	# 	if self.parent_id:
	# 		self.hcp_customer_id = self.parent_id.hcp_customer_id


	# @api.onchange('property_delivery_carrier_id')
	# def onchange_property_delivery_carrier_id(self):
	# 	if self.property_delivery_carrier_id:
	# 		desc = self.property_delivery_carrier_id.website_description
	# 		self.hcp_ship_via_description = desc

class Lead(models.Model):
	_inherit = "crm.lead"

	def _create_lead_partner_data(self, name, is_company, parent_id=False):
		""" extract data from lead to create a partner
			:param name : furtur name of the partner
			:param is_company : True if the partner is a company
			:param parent_id : id of the parent partner (False if no parent)
			:returns res.partner record
		"""
		email_split = tools.email_split(self.email_from)
		res = {
			'name': name,
			'user_id': self.env.context.get('default_user_id') or self.user_id.id,
			'comment': self.description,
			'team_id': self.team_id.id,
			'parent_id': parent_id,
			'phone': self.phone,
			'mobile': self.mobile,
			'hcp_is_customer':True,
			'hcp_is_vendor':False,
			'company_type':'company',
			'email': email_split[0] if email_split else False,
			'title': self.title.id,
			'function': self.function,
			'street': self.street,
			'street2': self.street2,
			'zip': self.zip,
			'city': self.city,
			'country_id': self.country_id.id,
			'state_id': self.state_id.id,
			'website': self.website,
			'is_company': is_company,
			'type': 'contact'
		}
		if self.lang_id:
			res['lang'] = self.lang_id.code
		return res