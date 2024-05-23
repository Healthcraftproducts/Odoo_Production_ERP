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
	_description = 'Display Healthcraft'
	_rec_name ='name'

	name = fields.Char(string='Name', required=True)


class DisplaysInvisia(models.Model):
	_name = 'displays.invisia'
	_description = 'Display invisia'
	_rec_name = 'name'

	name = fields.Char(string='Name', required=True)


class HCPFederalTax(models.Model):
	_name = 'hcp.federal.tax'
	_description = 'HCp Federal Tax'
	_rec_name = 'federal_tax_name'

	federal_tax_name = fields.Char(string='Tax Name')


class ContactTraining(models.Model):
	_name = 'contact.training'
	_description = 'Contact Training'
	_rec_name = 'contact_training_name'

	contact_training_name = fields.Char(string="Name")


class ContactsDesignation(models.Model):
	_name = 'contacts.designation'
	_description = 'Contacts Designation'
	_rec_name ='contact_designation_name'

	contact_designation_name = fields.Char(string="Name")

class ContactsRole(models.Model):
	_name = 'contact.role'
	_description = 'Contact Role'
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
	property_product_pricelist = fields.Many2one(
        'product.pricelist', 'Pricelist', compute='_compute_product_pricelist',
        inverse="_inverse_product_pricelist", company_dependent=False,
        help="This pricelist will be used, instead of the default one, for sales to the current partner", track_visibility='always')

	@api.model
	def create(self, vals):
		customer_no = False
		vendor_no = False
		if 'hcp_is_customer' in vals and 'company_type' in vals:
			if vals['hcp_is_customer'] == True:
				if vals['company_type'] == 'company':
					customer_no = self.env['ir.sequence'].next_by_code('partner.sequence')
					vals['hcp_customer_id'] = customer_no
		if 'hcp_is_vendor' in vals and 'company_type' in vals:
			if vals['hcp_is_vendor'] == True:
				if vals['company_type'] == 'company':
					vendor_no = self.env['ir.sequence'].next_by_code('vendor.sequence')
					vals['hcp_vendor_no'] = vendor_no
		if 'company_type' in vals:
			if vals['company_type'] == 'person':
				parent_id = vals.get('parent_id')
				if parent_id:
					main_company = self.env['res.partner'].search([('id', '=', parent_id)])
					vals.update({'hcp_customer_id': main_company.hcp_customer_id,'hcp_vendor_no': main_company.hcp_vendor_no,'hcp_is_customer':main_company.hcp_is_customer,'hcp_is_vendor':main_company.hcp_is_vendor,'property_delivery_carrier_id':main_company.property_delivery_carrier_id.id,'hcp_ship_via_description':main_company.hcp_ship_via_description})
		res = super(ResPartner, self).create(vals)
		return res

	def copy(self, default=None):
		self.ensure_one()
		default = dict(default or {})
		customer_no = False
		vendor_no = False
		for rec in self:
			if rec.hcp_is_customer and rec.company_type:
				if rec.hcp_is_customer == True:
					if rec.company_type == 'company':
						customer_no = self.env['ir.sequence'].next_by_code('partner.sequence')
						rec.hcp_customer_id = customer_no
					elif rec.company_type == 'person':
						if rec.parent_id:
							rec.hcp_customer_id = rec.parent_id.hcp_customer_id
							default['company_type'] = 'person'
						elif not rec.parent_id:
							customer_no = self.env['ir.sequence'].next_by_code('partner.sequence')
							rec.hcp_customer_id = customer_no
							default['company_type'] = 'person'
				else:
					rec.hcp_customer_id = False
			if rec.hcp_is_vendor and rec.company_type:
				if rec.hcp_is_vendor == True:
					if rec.company_type == 'company':
						vendor_no = self.env['ir.sequence'].next_by_code('vendor.sequence')
						rec.hcp_vendor_no = vendor_no
					elif rec.company_type == 'person':
						if rec.parent_id:
							rec.hcp_vendor_no = rec.parent_id.hcp_vendor_no
							default['company_type'] = 'person'
						elif not rec.parent_id:
							customer_no = self.env['ir.sequence'].next_by_code('partner.sequence')
							rec.hcp_vendor_no = customer_no
							default['company_type'] = 'person'
				else:
					rec.hcp_vendor_no = False
		return super(ResPartner, self).copy(default)


#def name_get(self):
		## name get function for the model executes automatically
		#res = []
		#for rec in self:
			#res.append((rec.id, '%s' % (rec.name)))
		#return res

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

class SaleOrder(models.Model):
	_inherit = "sale.order"
	# code_group_hcp = fields.Many2one('hcp.group.code', string='Group Code', store=True)
	code_group_hcp_sale = fields.Many2one('hcp.group.code',string='Group Code',compute="_compute_group_code",readonly=False,store=True)

	@api.depends('partner_id')
	def _compute_group_code(self):
		for rec in self:
			if rec.partner_id:
				if rec.partner_id.hcp_group_code:
					rec.code_group_hcp_sale = rec.partner_id.hcp_group_code
				else:
					rec.code_group_hcp_sale = ""
			else:
				rec.code_group_hcp_sale = ""


class SaleReport(models.Model):
	_inherit = "sale.report"

	code_group_hcp = fields.Many2one('hcp.group.code',string='Group Code',store=True)

	def _select_additional_fields(self):
		"""
        Inherited Select method to Add category fields filter in Reports
        :return:
        """
		res = super(SaleReport, self)._select_additional_fields()
		res['code_group_hcp'] = "s.code_group_hcp_sale"
		return res

	def _group_by_sale(self):
		"""
        Inherit group by for filter category data
        :return:
        """
		res = super(SaleReport, self)._group_by_sale()
		res += """, s.code_group_hcp_sale"""
		return res

class AccountMoveInheritModel(models.Model):
    _inherit = 'account.move'

    code_group_hcp_account_move = fields.Many2one(
        'hcp.group.code',
        string='Group Code',
        compute='_compute_group_code_account_move',
        readonly=False,
        store=True,
    )

    customer_industry_account_move = fields.Many2one(
        'res.partner.industry',
        string="Customer industry",
        compute='_compute_customer_industry_account_move',
		store=True,
    )

    @api.depends('partner_id')
    def _compute_group_code_account_move(self):
        for rec in self:
            if rec.partner_id:
                if rec.partner_id.hcp_group_code:
                    rec.code_group_hcp_account_move = rec.partner_id.hcp_group_code
                else:
                    rec.code_group_hcp_account_move = False
            else:
                rec.code_group_hcp_account_move = False

    @api.depends('partner_id')
    def _compute_customer_industry_account_move(self):
        for rec in self:
            if rec.partner_id:
                if rec.partner_id.hcp_group_code:
                    rec.customer_industry_account_move = rec.partner_id.industry_id
                else:
                    rec.customer_industry_account_move = False
            else:
                rec.customer_industry_account_move = False

class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    code_group_hcp_account_move = fields.Many2one(
        'hcp.group.code',
        string='Group Code Invoice Report'
    )

    customer_industry_account_move = fields.Many2one(
        'res.partner.industry',
        string="Customer industry",
    )

    @api.model
    def _select(self):
        res = super(AccountInvoiceReport, self)._select()
        return res + '''
            , move.code_group_hcp_account_move
            , move.customer_industry_account_move
        '''
