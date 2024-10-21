# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class, methods and fields to process to create or update inbound shipment.
"""

import base64
import os
import time
import zipfile
import requests
import logging
from datetime import datetime
import dateutil.parser
from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError
try:
    from _collections import defaultdict
except ImportError:
    pass
from ..endpoint import DEFAULT_ENDPOINT
from .utils import xml2dict

_logger = logging.getLogger(__name__)

SHIPMENT_STATUS_HELP = """
WORKING - The shipment was created by the seller, but has not yet shipped.
READY_TO_SHIP - The shipment was created by the seller, and ready for shipped.
SHIPPED - The shipment was picked up by the carrier.
IN_TRANSIT - The carrier has notified the Amazon fulfillment center that it is aware of the shipment.
DELIVERED - The shipment was delivered by the carrier to the Amazon fulfillment center.
CHECKED_IN - The shipment was checked-in at the receiving dock of the Amazon fulfillment center.
RECEIVING - The shipment has arrived at the Amazon fulfillment center, but not all items have been marked as received.
CLOSED - The shipment has arrived at the Amazon fulfillment center and all items have been marked as received.
CANCELLED - The shipment was cancelled by the seller after the shipment was sent to the Amazon fulfillment center.
DELETED - The shipment was cancelled by the seller before the shipment was sent to the Amazon fulfillment center.
ERROR - There was an error with the shipment and it was not processed by Amazon."""

TRANSPORT_STATUS = [('draft', 'Draft'), ('WORKING', 'WORKING'),
                    ('ERROR_ON_ESTIMATING', 'ERROR_ON_ESTIMATING'),
                    ('ESTIMATING', 'ESTIMATING'),
                    ('ESTIMATED', 'ESTIMATED'),
                    ('ERROR_ON_CONFIRMING', 'ERROR_ON_CONFIRMING'),
                    ('CONFIRMING', 'CONFIRMING'),
                    ('CONFIRMED', 'CONFIRMED'),
                    ('VOIDING', 'VOIDING'),
                    ('VOIDED', 'VOIDED'),
                    ('ERROR_IN_VOIDING', 'ERROR_IN_VOIDING'),
                    ('ERROR', 'ERROR')]

transport_status_list = ['WORKING', 'ERROR_ON_ESTIMATING', 'ESTIMATING', 'ESTIMATED',
                         'ERROR_ON_CONFIRMING', 'CONFIRMING', 'CONFIRMED', 'VOIDING', 'VOIDED',
                         'ERROR_IN_VOIDING', 'ERROR']

AMZ_INBOUND_SHIPMENT_EPT = "amazon.inbound.shipment.ept"
COMMON_LOG_LINES_EPT = "common.log.lines.ept"
COMMON_LOG_BOOK_EPT = 'common.log.book.ept'
INBOUND_SHIPMENT_PLAN_EPT = 'inbound.shipment.plan.ept'
RES_PARTNER = 'res.partner'
INBOUND_SHIPMENT_PLAN_LINE = 'inbound.shipment.plan.line'
STOCK_PICKING = 'stock.picking'
STOCK_QUANT_PACKAGE = 'stock.quant.package'
RES_CURRENCY = 'res.currency'
IR_ACTION_ACT_WINDOW = 'ir.actions.act_window'
AMAZON_PRODUCT_EPT = 'amazon.product.ept'


class InboundShipmentEpt(models.Model):
    """
    Added class to process to create or update inbound shipment.
    """
    _name = "amazon.inbound.shipment.ept"
    _description = "Inbound Shipment"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    @api.depends('partnered_ltl_ids.weight_unit', 'partnered_ltl_ids.weight_value')
    def _compute_shipment_weight(self):
        """
        This method will calculate the amazon shipment weight
        """
        for shipment in self:
            if shipment.is_partnered:
                if shipment.partnered_ltl_ids and shipment.transport_type == 'partnered_ltl_data':
                    weight_pound, weight_unit_pound, \
                    weight_kg, weight_unit_kg = self.calculate_partnered_ltl_parcel_weight(shipment)
                    weight_unit = max(weight_unit_kg, weight_unit_pound)
                    if weight_unit == weight_unit_kg:
                        # Convert Weight Pounds to Kilograms
                        weight_kg += (weight_pound * 0.453592)
                        shipment.amazon_shipment_weight = weight_kg
                        shipment.amazon_shipment_weight_unit = 'kilograms'
                    else:
                        # Convert Weight Kilograms to Pounds
                        weight_pound += (weight_kg * 2.20462)
                        shipment.amazon_shipment_weight = weight_pound
                        shipment.amazon_shipment_weight_unit = 'pounds'
            else:
                shipment.amazon_shipment_weight = 0.0
                shipment.amazon_shipment_weight_unit = ''

    @staticmethod
    def calculate_partnered_ltl_parcel_weight(shipment):
        """
        Calculate weights in kg or pounds as per parcel configuration.
        :param shipment: amazon.inbound.shipment.ept()
        :return: weight_pound, weight_unit_pound, weight_kg, weight_unit_kg
        """
        weight_unit_kg = weight_unit_pound = 0
        weight_kg = weight_pound = 0.0
        for parcel in shipment.partnered_ltl_ids:
            if parcel.weight_unit == 'kilograms':
                weight_unit_kg += 1
                weight_kg += parcel.weight_value
            elif parcel.weight_unit == 'pounds':
                weight_unit_pound += 1
                weight_pound += parcel.weight_value
        return weight_pound, weight_unit_pound, weight_kg, weight_unit_kg

    @api.depends('picking_ids.state', 'picking_ids.updated_in_amazon')
    def _compute_amazon_status(self):
        """
        This method is used to  set value of updated_in_amazon based on picking.
        """
        self.updated_in_amazon = bool(self.picking_ids)
        for picking in self.picking_ids:
            if picking.state == 'cancel':
                continue
            if picking.picking_type_id.code != 'outgoing':
                continue
            if not picking.updated_in_amazon:
                self.updated_in_amazon = False
                break

    state = fields.Selection([('draft', 'Draft'), ('WORKING', 'WORKING'),
                              ('READY_TO_SHIP', 'READY_TO_SHIP'), ('SHIPPED', 'SHIPPED'),
                              ('IN_TRANSIT', 'IN_TRANSIT'), ('DELIVERED', 'DELIVERED'),
                              ('CHECKED_IN', 'CHECKED_IN'), ('RECEIVING', 'RECEIVING'),
                              ('CLOSED', 'CLOSED'), ('CANCELLED', 'CANCELLED'),
                              ('DELETED', 'DELETED'), ('ERROR', 'ERROR')],
                             string='Shipment Status', default='WORKING', help=SHIPMENT_STATUS_HELP)
    name = fields.Char(size=120, readonly=True, required=False, index=True)
    shipment_id = fields.Char(size=120, string='Shipment ID', index=True)
    shipment_plan_id = fields.Many2one(INBOUND_SHIPMENT_PLAN_EPT, string='Shipment Plan')
    amazon_reference_id = fields.Char(size=50, help="A unique identifier created by Amazon that "
                                                    "identifies this Amazon-partnered, Less Than "
                                                    "Truckload/Full Truckload (LTL/FTL) shipment.")
    intended_box_contents_source = fields.Selection([('FEED', 'FEED')], default='FEED', readonly=1,
                                                    string="Intended BoxContents Source",
                                                    help="If your instance is USA then you must set box content, "
                                                         "other wise amazon will collect per piece fee")
    address_id = fields.Many2one(RES_PARTNER, string='Ship To Address')
    label_prep_type = fields.Char(size=120, string='LabelPrepType', readonly=True,
                                  help="LabelPrepType provided by Amazon when we send shipment Plan to Amazon")
    odoo_shipment_line_ids = fields.One2many(INBOUND_SHIPMENT_PLAN_LINE, 'odoo_shipment_id', string='Shipment Items')
    picking_ids = fields.One2many(STOCK_PICKING, 'odoo_shipment_id', string="Pickings", readonly=True)
    count_pickings = fields.Integer(string='Count Picking', compute='_compute_picking_count')
    shipping_type = fields.Selection([('sp', 'SP (Small Parcel)'),
                                      ('ltl', 'LTL (Less Than Truckload/FullTruckload (LTL/FTL))')], default="sp")
    transport_type = fields.Selection([('partnered_small_parcel_data', 'PartneredSmallParcelData'),
                                       ('non_partnered_small_parcel_data', 'NonPartneredSmallParcelData'),
                                       ('partnered_ltl_data', 'PartneredLtlData'),
                                       ('non_partnered_ltl_data', 'NonPartneredLtlData')],
                                      compute="_compute_transport_type", store=True)
    is_partnered = fields.Boolean(default=False, copy=False)
    transport_state = fields.Selection(TRANSPORT_STATUS, default='draft', copy=False, string='Transport States')
    log_ids = fields.One2many(COMMON_LOG_LINES_EPT, compute="_compute_error_logs")
    transport_content_exported = fields.Boolean('Transport Content Exported?', default=False, copy=False)
    fulfill_center_id = fields.Char(size=120, string='Fulfillment Center', readonly=True,
                                    help="DestinationFulfillmentCenterId provided by Amazon, "
                                         "when we send shipment Plan to Amazon")
    is_manually_created = fields.Boolean(default=False, copy=False)
    is_picking = fields.Boolean(compute="_compute_error_logs")
    partnered_small_parcel_ids = fields.One2many(STOCK_QUANT_PACKAGE, 'partnered_small_parcel_shipment_id',
                                                 string='Partnered Small Parcel')
    partnered_ltl_ids = fields.One2many(STOCK_QUANT_PACKAGE, 'partnered_ltl_shipment_id', string='Partnered LTL')
    is_update_inbound_carton_contents = fields.Boolean("Is Update Inbound Carton Contents ?", default=False, copy=False)
    is_carton_content_updated = fields.Boolean("Carton Content Updated ?", default=False, copy=False)
    void_deadline_date = fields.Datetime(help="The date after which a confirmed transportation "
                                              "request can no longer be voided. This date is 24 "
                                              "hours after you confirm a Small Parcel shipment "
                                              "transportation request or one hour after you confirm"
                                              "a Less Than Truckload/Full Truckload (LTL/FTL) "
                                              "shipment transportation request. After the void "
                                              "deadline passes your account will be charged for "
                                              "the shipping cost. In ISO 8601 format.")
    pro_number = fields.Char(size=10, help="The PRO number assigned to your shipment by the carrier. "
                                           "A string of numbers, seven to 10 characters in length.")
    updated_in_amazon = fields.Boolean(compute="_compute_amazon_status", store=True)
    instance_id_ept = fields.Many2one("amazon.instance.ept", string="Instance")
    feed_id = fields.Many2one("feed.submission.history", string="Submit Feed Id")
    are_cases_required = fields.Boolean("AreCasesRequired", default=False,
                                        help="Indicates whether or not an Inbound shipment "
                                             "contains case-packed boxes. A shipment must either "
                                             "contain all case-packed boxes or all individually "
                                             "packed boxes")
    created_date = fields.Date('Create on', default=time.strftime('%Y-%m-%d'))
    carrier_id = fields.Many2one('delivery.carrier', string='Carrier')
    is_billof_lading_available = fields.Boolean(string='IsBillOfLadingAvailable', default=False,
                                                help="Indicates whether the bill of lading for the "
                                                     "shipment is available.")
    currency_id = fields.Many2one(RES_CURRENCY, string='Currency')
    estimate_amount = fields.Float(help='The amount that the Amazon-partnered carrier will charge '
                                        'to ship the inbound shipment.')
    confirm_deadline_date = fields.Datetime(help="The date by which this estimate must be "
                                                 "confirmed. After this date the estimate is no "
                                                 "longer valid and cannot be confirmed. "
                                                 "In ISO 8601 format.")
    partnered_ltl_id = fields.Many2one(RES_PARTNER, string='Contact',
                                       help="Contact information for the person in your "
                                            "organization who is responsible for the shipment. "
                                            "Used by the carrier if they have questions "
                                            "about the shipment.")
    from_warehouse_id = fields.Many2one("stock.warehouse", string="From Warehouse")
    preview_freight_class = fields.Selection([('50', '50'), ('55', '55'), ('60', '60'), ('65', '65'), ('70', '70'),
                                              ('77.5', '77.5'), ('85', '85'), ('92.5', '92.5'), ('100', '100'),
                                              ('110', '110'), ('125', '125'), ('150', '150'), ('175', '175'),
                                              ('200', '200'), ('250', '250'), ('300', '300'), ('400', '400'),
                                              ('500', '500')], string='PreviewFreightClass',
                                             help="The freight class of the shipment as estimated by Amazon, "
                                                  "if you did not include a freight class when you called the PutTransportContent operation.")
    seller_declared_value = fields.Float(digits=(16, 2))
    seller_freight_class = fields.Selection(
        [('50', '50'), ('55', '55'), ('60', '60'), ('65', '65'), ('70', '70'), ('77.5', '77.5'),
         ('85', '85'), ('92.5', '92.5'), ('100', '100'), ('110', '110'), ('125', '125'),
         ('150', '150'), ('175', '175'), ('200', '200'), ('250', '250'), ('300', '300'),
         ('400', '400'), ('500', '500')])
    freight_ready_date = fields.Date()
    box_count = fields.Integer('Number of box')
    preview_pickup_date = fields.Datetime(string='PreviewPickupDate',
                                          help="The estimated date that the shipment will be "
                                               "picked up by the carrier. In ISO 8601 format.")
    preview_delivery_date = fields.Datetime(string='PreviewDeliveryDate',
                                            help="The estimated date that the shipment will be "
                                                 "delivered to an Amazon fulfillment center.")
    declared_value_currency_id = fields.Many2one(RES_CURRENCY, string="Declare Value Currency")
    amazon_shipment_weight = fields.Float(compute='_compute_shipment_weight',
                                          string="Shipment Weight", store=True, readonly=True)
    amazon_shipment_weight_unit = fields.Selection([('pounds', 'Pounds'), ('kilograms', 'Kilograms')],
                                                   string='Weight Unit', compute="_compute_shipment_weight",
                                                   store=True, readonly=True)
    suggest_seller_declared_value = fields.Float(digits=(16, 2))
    closed_date = fields.Date(readonly=True, copy=False)
    are_all_pickings_cancelled = fields.Boolean(compute='_compute_are_all_pickings_cancelled', store=False)
    active = fields.Boolean(string="Active", default=True)
    amz_inbound_create_date = fields.Date(string='Create Date', readonly=True)
    company_id = fields.Many2one('res.company', string="Company", copy=False, compute="_compute_company", store=True,
                                 help="This Field relocates Amazon company.")

    def _compute_picking_count(self):
        """
        This method is used to compute total numbers of pickings
        :return: N/A
        """
        for rec in self:
            rec.count_pickings = len(rec.picking_ids.ids)

    @api.depends('instance_id_ept')
    def _compute_company(self):
        """
        Define this method for assign company in the current record.
        """
        for record in self:
            company_id = record.instance_id_ept.company_id.id if record.instance_id_ept and\
                                                                 record.instance_id_ept.company_id else False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    def action_view_pickings(self):
        """
        This method creates and return an action for opening the view of stock.picking
        :return: action
        """
        action = {
            'name': 'Inbound Pickings',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window'
        }
        if self.count_pickings != 1:
            action.update({'domain': [('id', 'in', self.picking_ids.ids)],
                           'view_mode': 'tree,form'})
        else:
            action.update({'res_id': self.picking_ids.id,
                           'view_mode': 'form'})
        return action

    def _compute_are_all_pickings_cancelled(self):
        for record in self:
            record.are_all_pickings_cancelled = all([p.state == 'cancel' for p in self.picking_ids])

    @api.depends('is_partnered', 'shipping_type')
    def _compute_transport_type(self):
        for shipment in self:
            if shipment.shipping_type == 'sp' and shipment.is_partnered:
                shipment.transport_type = 'partnered_small_parcel_data'
            elif shipment.shipping_type == 'ltl' and shipment.is_partnered:
                shipment.transport_type = 'partnered_ltl_data'
            elif shipment.shipping_type == 'sp':
                shipment.transport_type = 'non_partnered_small_parcel_data'
            elif shipment.shipping_type == 'ltl':
                shipment.transport_type = 'non_partnered_ltl_data'

    def unlink(self):
        """
        Inherited unlink method to do not allow to delete shipment of which shipment plan is
        approved and which shipment is not in cancelled and deleted.
        """
        for shipment in self:
            if shipment.shipment_plan_id and shipment.shipment_plan_id.state == 'plan_approved':
                raise UserError(_('You cannot delete Inbound Shipment.'))
            if shipment.instance_id_ept and shipment.state not in ['CANCELLED', 'DELETED']:
                raise UserError(_('You cannot delete Inbound Shipment.'))
        return super(InboundShipmentEpt, self).unlink()

    def _compute_error_logs(self):
        """
        Define method to get shipment error logs.
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        log_lines = log_line_obj.amz_find_mismatch_details_log_lines(self.id, AMZ_INBOUND_SHIPMENT_EPT)
        self.log_ids = log_lines.ids if log_lines else False
        self.is_picking = bool(self.picking_ids)

    def create_or_update_address(self, address):
        """
        This method will prepare partner values based on the address details and
        return the created partner.
        """
        domain = []
        partner_obj = self.env[RES_PARTNER]
        country_obj = self.env['res.country']
        state_obj = self.env['res.country.state']
        state_id = False
        country = country_obj.search([('code', '=', address.get('CountryCode', ''))])
        state = address.get('StateOrProvinceCode', '')
        name = address.get('Name', '')
        street = address.get('AddressLine1', '')
        street2 = address.get('AddressLine2', '')
        postal_code = address.get('PostalCode', '')
        city = address.get('City', '')
        # Find state id from State or Provience Code
        if state:
            result_state = state_obj.search([('code', '=ilike', state), ('country_id', '=', country.id)])
            if not result_state:
                state = partner_obj.create_or_update_state_ept(country.code, state, postal_code, country)
                state_id = state.id
            else:
                state_id = result_state[0].id
        name and domain.append(('name', '=', name))
        street and domain.append(('street', '=', street))
        street2 and domain.append(('street2', '=', street2))
        city and domain.append(('city', '=', city))
        postal_code and domain.append(('zip', '=', postal_code))
        state_id and domain.append(('state_id', '=', state_id))
        country and domain.append(('country_id', '=', country.id))
        partner = partner_obj.with_context(is_amazon_partner=True).search(domain)
        if not partner:
            partner_vals = {
                'name': name, 'is_company': False,
                'street': street, 'street2': street2,
                'city': city, 'country_id': country.id, 'zip': postal_code, 'state_id': state_id,
                'is_amz_customer': True
            }
            partner = partner_obj.create(partner_vals)
        return partner.id

    def prepare_inbound_shipment_kwargs(self, instance, odoo_shipment):
        """
        Prepare values for request IAP service for create or Update inbound shipments
        :param instance: amazon.instance.ept()
        :param odoo_shipment: amazon.inbound.shipment.ept()
        :return: dict{}
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                  'app_name': 'amazon_ept_spapi',
                  'marketplace_id': instance.market_place_id,
                  'account_token': account.account_token,
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                             instance.country_id.code,
                  'shipment_name': odoo_shipment.name,
                  'shipment_id': odoo_shipment.shipment_id,
                  'inbound_box_content_status': odoo_shipment.intended_box_contents_source,
                  'shipment_status': 'WORKING'
                  }
        return kwargs

    @staticmethod
    def prepare_inbound_shipment_address_dict(address):
        """
        Prepare Address dictionary for inbound shipments
        :param ship_plan:
        :return: dict {}
        """
        address_dict = {
            'name': address.name, 'address_1': address.street or '',
            'address_2': address.street2 or '', 'city': address.city or '',
            'country': address.country_id.code if address.country_id else '',
            'state_or_province': address.state_id.code if address.state_id else '',
            'postal_code': address.zip or ''
        }
        return address_dict

    def prepare_inbound_shipment_vals(self, shipment, ship_plan, add_id):
        """
        Prepare Amazon inbound shipment values
        :param shipment:
        :param ship_plan:
        :param add_id:
        :return:
        """
        sequence = self.env.ref('amazon_ept.seq_inbound_shipments', raise_if_not_found=False)
        name = sequence.next_by_id() if sequence else '/'
        shipment_vals = {
            'name': name,
            'shipment_plan_id': ship_plan.id,
            'fulfill_center_id': shipment.get('DestinationFulfillmentCenterId', ''),
            'label_prep_type': shipment.get('LabelPrepType', ''),
            'address_id': add_id,
            'shipment_id': shipment.get('ShipmentId', ''),
            'state': 'WORKING',
            'intended_box_contents_source': ship_plan.intended_box_contents_source,
            'are_cases_required': ship_plan.is_are_cases_required if ship_plan else False,
            'instance_id_ept': ship_plan.instance_id.id,
            'amz_inbound_create_date': fields.datetime.now().date() if ship_plan else False
        }
        if ship_plan.shipping_type:
            shipment_vals.update({'is_partnered': ship_plan.is_partnered,
                                  'shipping_type': ship_plan.shipping_type})
        return shipment_vals


    @api.model
    def create_or_update_inbound_shipment(self, ship_plan, shipment):
        """
        Here We are not taking shipment id as domain because amazon create each time
        new shipment id & we merge with existing shipment_id in same plan.
        :param ship_plan: inbound.shipment.plan.ept() object
        :param shipment: shipment response
        :return: amazon.inbound.shipment.ept(), common.log.book.ept()
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        add_id = self.create_or_update_address(shipment.get('ShipToAddress', {}))
        fulfill_center_id = shipment.get('DestinationFulfillmentCenterId', '')
        shipment_id = shipment.get('ShipmentId', '')
        is_are_cases_required = ship_plan.is_are_cases_required if ship_plan else False
        instance = ship_plan.instance_id
        create_or_update = 'create'
        domain = [('shipment_id', '=', shipment_id), ('shipment_plan_id', '=', ship_plan.id)]
        odoo_shipment = self.search(domain)
        if odoo_shipment:
            create_or_update = 'update'
        else:
            shipment_vals = self.prepare_inbound_shipment_vals(shipment, ship_plan, add_id)
            odoo_shipment = self.create(shipment_vals)
        items = []
        if not isinstance(shipment.get('Items', []), list):
            items.append(shipment.get('Items', []))
        else:
            items = shipment.get('Items', [])
        sku_qty_list = self.env[INBOUND_SHIPMENT_PLAN_LINE].prepare_shipment_plan_line_dict(odoo_shipment, items)
        address_dict = self.prepare_inbound_shipment_address_dict(ship_plan.ship_from_address_id)

        label_prep_type = odoo_shipment.label_prep_type
        if label_prep_type == 'NO_LABEL':
            label_prep_type = 'SELLER_LABEL'
        elif label_prep_type == 'AMAZON_LABEL':
            label_prep_type = ship_plan.label_preference
        if create_or_update == 'update':
            kwargs = self.prepare_inbound_shipment_kwargs(instance, odoo_shipment)
            kwargs.update({'emipro_api': 'update_shipment_in_amazon_sp_api',
                           'destination': fulfill_center_id,
                           'labelpreppreference': label_prep_type,
                           'cases_required': is_are_cases_required,
                           'sku_qty_list': sku_qty_list,
                           'address_dict': address_dict})

            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                log_line_obj.create_common_log_line_ept(
                    message=response.get('error', {}), model_name=INBOUND_SHIPMENT_PLAN_EPT, module='amazon_ept',
                    operation_type='export', res_id=ship_plan.id,
                    amz_instance_ept=ship_plan.instance_id and ship_plan.instance_id.id or False,
                    amz_seller_ept=ship_plan.instance_id.seller_id and ship_plan.instance_id.seller_id.id or False)
                return False
        elif create_or_update == 'create':
            kwargs = self.prepare_inbound_shipment_kwargs(instance, odoo_shipment)
            kwargs.update({'emipro_api': 'create_shipment_in_amazon_sp_api',
                           'destination': fulfill_center_id,
                           'sku_qty_list': sku_qty_list,
                           'address_dict': address_dict,
                           'labelpreppreference': label_prep_type,
                           'cases_required': is_are_cases_required})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                log_line_obj.create_common_log_line_ept(
                    message=response.get('error', {}), model_name=INBOUND_SHIPMENT_PLAN_EPT, module='amazon_ept',
                    operation_type='export', res_id=ship_plan.id,
                    amz_instance_ept=ship_plan.instance_id and ship_plan.instance_id.id or False,
                    amz_seller_ept=ship_plan.instance_id.seller_id and ship_plan.instance_id.seller_id.id or False)
                return False
        shipment_id = response.get('result', {}).get('ShipmentId', '') or False
        if shipment_id:
            odoo_shipment.write({'shipment_id': shipment_id})
        return odoo_shipment

    def create_shipment_picking(self):
        """
        When Import Shipment from amazon to odoo with shipping ids this method will be used.
        Updated called create create_procurements method to pass the instance id during process
        via shipment plan
        """
        self.ensure_one()
        if not self.is_picking and self.are_all_pickings_cancelled:
            if self.is_manually_created:
                self.create_procurements()
            else:
                inbound_shipment_plan_obj = self.env[INBOUND_SHIPMENT_PLAN_EPT]
                inbound_shipment_plan_obj.create_procurements(self)
        return True

    @api.model
    def create_procurements(self):
        """
        This method will find warehouse and location according to routes,
        if found then Create and run Procurement, also it will assign pickings if found.
        :return: boolean
        """
        proc_group_obj = self.env['procurement.group']
        picking_obj = self.env[STOCK_PICKING]
        group_wh_dict = {}
        proc_group = proc_group_obj.create({'odoo_shipment_id': self.id, 'name': self.name, 'partner_id': self.address_id.id})
        instance = self.instance_id_ept
        warehouse = self.amz_inbound_get_warehouse_ept(instance, self.fulfill_center_id)
        if warehouse:
            location_routes = self.amz_find_location_routes_ept(warehouse)
            group_wh_dict.update({proc_group: warehouse})
            for line in self.odoo_shipment_line_ids:
                qty = line.quantity
                product_id = line.amazon_product_id.product_id
                datas = self.amz_inbound_prepare_procure_datas(location_routes, proc_group,
                                                               instance, warehouse)
                proc_group_obj.run([proc_group_obj.Procurement(product_id, qty, product_id.uom_id,
                                                               warehouse.lot_stock_id,
                                                               product_id.name, self.name,
                                                               instance.company_id, datas)])
        if group_wh_dict:
            for group, warehouse in group_wh_dict.items():
                picking = picking_obj.search([('group_id', '=', group.id),
                                              ('picking_type_id.warehouse_id', '=', warehouse.id)])
                if picking:
                    picking.write({'is_fba_wh_picking': True})

        pickings = self.mapped('picking_ids').filtered(lambda pick: not pick.is_fba_wh_picking and
                                                       pick.state not in ['done', 'cancel'])
        for picking in pickings:
            picking.action_assign()
        return True

    def amz_find_location_routes_ept(self, warehouse):
        """
        Find Location routes from warehouse.
        :param warehouse: stock.warehouse()
        :return: stock.location.route()
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        location_route_obj = self.env['stock.route']
        location_routes = location_route_obj.search([('supplied_wh_id', '=', warehouse.id),
                                                     ('supplier_wh_id', '=', self.from_warehouse_id.id)], limit=1)
        if not location_routes:
            error_value = 'Location routes are not found. Please configure routes in warehouse ' \
                          'properly || warehouse %s & shipment %s.' % (warehouse.name, self.name)
            log_line_obj.create_common_log_line_ept(message=error_value, model_name=AMZ_INBOUND_SHIPMENT_EPT,
                                                    module='amazon_ept', operation_type='export', res_id=self.id)
        return location_routes

    @staticmethod
    def amz_inbound_prepare_procure_datas(location_routes, proc_group, instance, warehouse):
        """
        Prepare Procurement values dictionary.
        :param location_routes: stock.location.route()
        :param proc_group: procurement.group()
        :param instance: amazon.instance.ept()
        :param warehouse: stock.warehouse()
        :return: dict{}
        """
        return {
            'route_ids': location_routes,
            'group_id': proc_group,
            'company_id': instance.company_id.id,
            'warehouse_id': warehouse,
            'priority': '1'
        }

    def amz_inbound_get_warehouse_ept(self, instance, fulfill_center):
        """
        Get warehouse from fulfillment center, if not found then from instance.
        :param instance: amazon.instance.ept()
        :param fulfill_center: Character
        :return: stock.warehouse()
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        fulfillment_center = fulfillment_center_obj.search([('center_code', '=', fulfill_center),
                                                            ('seller_id', '=', instance.seller_id.id)], limit=1)
        warehouse = fulfillment_center and fulfillment_center.warehouse_id or instance.fba_warehouse_id or instance.warehouse_id or False
        if not warehouse:
            error_value = 'No any warehouse found related to fulfillment center {fulfill_center}.' \
                          'Please set fulfillment center {fulfill_center} in warehouse || ' \
                          'shipment {name}.'.format(fulfill_center=fulfill_center, name=self.name)
            log_line_obj.create_common_log_line_ept(
                message=error_value, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                res_id=self.id, amz_instance_ept=instance and instance.id or False,
                amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
        return warehouse

    def create_pickings_ept(self):
        """
        Use: Create New Picking for Shipment
        """
        self.ensure_one()
        inbound_shipment_plan_obj = self.env[INBOUND_SHIPMENT_PLAN_EPT]
        inbound_shipment_plan_obj.create_procurements(self)

    def update_inbound_shipment_qty(self):
        """
        Usage: Update Shipment Quantity for Inbound shipment from Odoo to Amazon
        :return:
        """
        pickings = self.mapped('picking_ids').filtered(lambda picking: picking.state in ['done'])
        if pickings:
            raise UserError(_("You can not Update Shipment QTY whose Pickings are in Done State"))
        for shipment in self:
            ship_plan = shipment.shipment_plan_id
            if not ship_plan or not shipment.fulfill_center_id:
                raise UserError(_('You must have to first create Inbound Shipment Plan.'))
            instance = ship_plan.instance_id
            shipment_status = shipment.state
            destination = shipment.fulfill_center_id
            cases_required = ship_plan.is_are_cases_required
            label_prep_type = shipment.label_prep_type
            if label_prep_type == 'NO_LABEL':
                label_prep_type = 'SELLER_LABEL'
            elif label_prep_type == 'AMAZON_LABEL':
                label_prep_type = ship_plan.label_preference
            address_dict = self.prepare_inbound_shipment_address_dict(ship_plan.ship_from_address_id)
            for x in range(0, len(shipment.odoo_shipment_line_ids), 20):
                shipment_lines = shipment.odoo_shipment_line_ids[x:x + 20]
                sku_qty_list = self.prepare_amz_sku_qty_list(shipment_lines, cases_required)
                kwargs = self.prepare_inbound_shipment_kwargs(instance, shipment)
                kwargs.update({'emipro_api': 'update_shipment_in_amazon_sp_api',
                               'destination': destination,
                               'labelpreppreference': label_prep_type,
                               'cases_required': cases_required,
                               'sku_qty_list': sku_qty_list,
                               'address_dict': address_dict,
                               'shipment_status': shipment_status})
                response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
                if response.get('error', False):
                    raise UserError(_(response.get('error', {})))
            shipment.picking_ids.action_cancel()
            shipment.create_pickings_ept()
        return True

    @staticmethod
    def prepare_amz_sku_qty_list(shipment_lines, cases_required):
        """
        Prepare List for sku and it's quantity which will be updated to Amazon
        :param shipment_lines: list[]
        :param cases_required: boolean
        :return: list[]
        """
        sku_qty_list = []
        for line in shipment_lines:
            amazon_product = line.amazon_product_id
            if not amazon_product:
                raise UserError(_("Amazon Product is not available"))
            sku_qty_list.append({'SellerSKU': line.seller_sku, 'QuantityShipped': int(line.quantity),
                                 'QuantityInCase': int(line.quantity_in_case) if cases_required else 0})
        return sku_qty_list

    def cancel_shipment_in_amazon_via_shipment_lines(self):
        """
        Added methods to prepare dict of sku, quantity and request to cancel shipment.
        """
        shipment = self
        instance = self.get_instance(shipment)
        destination = shipment.fulfill_center_id
        shipment_status = 'CANCELLED'
        if not shipment.shipment_id or not shipment.fulfill_center_id:
            raise UserError(_('You must have to first create Inbound Shipment Plan.'))
        address_dict = self.prepare_inbound_shipment_address_dict(shipment.shipment_plan_id.ship_from_address_id)
        label_prep_type = shipment.label_prep_type
        if label_prep_type == 'NO_LABEL':
            label_prep_type = 'SELLER_LABEL'
        elif label_prep_type == 'AMAZON_LABEL':
            label_prep_type = shipment.shipment_plan_id.label_preference
        cases_required = shipment.shipment_plan_id.is_are_cases_required
        for x in range(0, len(shipment.odoo_shipment_line_ids), 20):
            ship_lines = shipment.odoo_shipment_line_ids[x:x + 20]
            sku_qty_list = []
            for line in ship_lines:
                sku_qty_list.append({'SellerSKU': line.seller_sku, 'QuantityShipped': int(line.quantity),
                                     'QuantityInCase': int(line.quantity_in_case) if cases_required else 0})
            kwargs = self.prepare_inbound_shipment_kwargs(instance, shipment)
            kwargs.update({'emipro_api': 'update_shipment_in_amazon_sp_api',
                           'destination': destination,
                           'labelpreppreference': label_prep_type,
                           'cases_required': cases_required,
                           'sku_qty_list': sku_qty_list,
                           'address_dict': address_dict,
                           'shipment_status': shipment_status})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                raise UserError(_(response.get('error', {})))
            break
        shipment.write({'state': 'CANCELLED'})
        shipments = shipment.shipment_plan_id.odoo_shipment_ids.filtered(lambda r: r.state != 'CANCELLED')
        if not shipments:
            shipment.shipment_plan_id.write({'state': 'cancel'})
        return True

    def open_import_inbound_shipment_report_wizard(self):
        """
        Open Wizard for Import Amazon Inbound Shipment Report
        :return: dictionary for open wizard
        """
        import_inbound_shipment_view = self.env.ref('amazon_ept.import_amazon_inbound_shipment_report_form_view',
                                                    raise_if_not_found=False)
        return {
            'name': 'Import Amazon Inbound Shipment Report',
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'amazon.inbound.shipment.report.wizard',
            'type': IR_ACTION_ACT_WINDOW,
            'view_id': import_inbound_shipment_view.id,
            'target': 'new'
        }

    def get_instance(self, shipment):
        """
        The method will return the instance of inbound shipment.
        :param shipment: amazon.inbound.shipment.ept()
        :return: amazon.instance.ept()
        """
        if shipment.instance_id_ept:
            return shipment.instance_id_ept
        return shipment.shipment_plan_id.instance_id

    @staticmethod
    def get_header(instance):
        """
        The method will return the request header.
        :param instance: amazon.instance.ept()
        :return: Header String
        """
        return """<?xml version="1.0"?>
            <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
            xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
            <Header>
                <DocumentVersion>1.01</DocumentVersion>
                <MerchantIdentifier>%s</MerchantIdentifier>
            </Header>
            <MessageType>CartonContentsRequest</MessageType>
            <Message>
         """ % instance.merchant_id

    def create_carton_contents_requests(self):
        """
        This method will prepare the data to create carton contents request and process response
        to create feed submission record.
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        message = 1
        for shipment in self:
            instance = self.get_instance(shipment)
            box_no_product_dict = self.prepare_box_no_product_dict(shipment, instance)
            total_box_list = set(box_no_product_dict.keys())
            flag = False
            for box, qty_dict in box_no_product_dict.items():
                if len(qty_dict.keys()) > 200:
                    log_message = 'System did not update carton in amazon because amazon not allow to' \
                              'update more then 200 item in one box || Box no %s || Inbound' \
                              'shipment ref %s' % (box, shipment.name)
                    log_line_obj.create_common_log_line_ept(
                        message=log_message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept',
                        operation_type='export', res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                        amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                    flag = True
                    break
            if flag:
                continue
            # Prepare Data for request cartoon content data.
            data, message = self.prepare_cartoon_content_request_data(message, shipment, box_no_product_dict, total_box_list)
            header = self.get_header(shipment.shipment_plan_id.instance_id or shipment.instance_id_ept)
            self.process_inbound_cartoon_content_request(header, data, instance, shipment)
        return True

    def process_inbound_cartoon_content_request(self, header, data, instance, shipment):
        """
        Process Inbound shipment cartoon content request data
        :param header: header data
        :param data: cartoon content data
        :param instance: amazon.instance.ept()
        :param shipment: amazon.inbound.shipment.ept()
        :return:
        """
        feed_submit_obj = self.env['feed.submission.history']
        if data:
            data = "%s %s</Message></AmazonEnvelope>" % (header, data)
            marketplaceids = [instance.market_place_id]
            kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
            kwargs.update({'emipro_api': 'amazon_submit_feeds_sp_api',
                           'feed_type': 'POST_FBA_INBOUND_CARTON_CONTENTS',
                           'marketplaceids': marketplaceids, 'data': data, })
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', {}):
                raise UserError(_(response.get('error', {})))
            results = response.get('results', {})
            if results.get('feed_result', {}).get('feedId', False):
                feed_document_id = results.get('result', {}).get('feedDocumentId', '')
                last_feed_submission_id = results.get('feed_result', {}).get('feedId', False)
                feed_vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                             'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                             'instance_id': instance.id, 'user_id': self._uid,
                             'feed_type': 'update_carton_content', 'feed_document_id': feed_document_id,
                             'seller_id': instance.seller_id.id}
                feed = feed_submit_obj.create(feed_vals)
                shipment.write({'is_update_inbound_carton_contents': True, 'feed_id': feed.id})

    @staticmethod
    def prepare_cartoon_content_request_data(message, shipment, box_no_product_dict, total_box_list):
        """
        Prepare data for update cartoon content request data from odoo to amazon.
        :param message: message id
        :param shipment: amazon.inbound.shipment.ept(0
        :param box_no_product_dict: dictionary of product with box details
        :param total_box_list: list of total boxes
        :return: data, message
        """
        data = '<MessageID>%s</MessageID><CartonContentsRequest>' % message
        message += 1
        data = "%s<ShipmentId>%s</ShipmentId><NumCartons>%s</NumCartons>" % (data, shipment.shipment_id,
                                                                             len(total_box_list))
        for box, qty_dict in box_no_product_dict.items():
            box_info = '<Carton><CartonId>%s</CartonId>' % box
            item_dict = ''
            for sku, qty, in qty_dict.items():
                if qty[2]:
                    item_dict = "%s<Item><SKU>%s</SKU><QuantityShipped>%s</QuantityShipped>" \
                                "<QuantityInCase>%s</QuantityInCase>" \
                                "<ExpirationDate>%s</ExpirationDate></Item>" % (item_dict, sku, int(qty[0]),
                                                                                int(qty[1]), qty[2])
                else:
                    item_dict = "%s<Item><SKU>%s</SKU><QuantityShipped>%s</QuantityShipped>" \
                                "<QuantityInCase>%s</QuantityInCase></Item>" % (
                                    item_dict, sku, int(qty[0]), int(qty[1]))
            box_info = "%s %s</Carton>" % (box_info, item_dict)
            data = "%s %s" % (data, box_info)
        data = "%s</CartonContentsRequest>" % data
        return data, message

    def prepare_box_no_product_dict(self, shipment, instance):
        """
        Prepare dictionary for box numbers with product quantity, quantity in box and expiry date.
        :param shipment:
        :param instance:
        :return:
        """
        box_no_product_dict = {}
        parcels = shipment.partnered_small_parcel_ids if shipment.partnered_small_parcel_ids else shipment.partnered_ltl_ids
        for content in parcels:
            box_no = content.box_no
            if box_no not in box_no_product_dict:
                box_no_product_dict.update({box_no: {}})
            for carton_line in content.carton_info_ids:
                seller_sku, quantity_in_case = self.get_amz_product_seller_sku(shipment, carton_line, instance)
                if not seller_sku:
                    continue
                qty = box_no_product_dict.get(box_no, {}).get(seller_sku, 0.0) and \
                      int(box_no_product_dict.get(box_no, {}).get(seller_sku, 0.0)[0])
                qty += carton_line.quantity
                # Convert Expiration Date to ISO Format
                expiry_date = content.box_expiration_date
                expiry_date = expiry_date.isoformat() if expiry_date else ''
                box_no_product_dict.get(box_no, {}).update(
                    {seller_sku: [str(int(qty)), str(int(quantity_in_case)), str(expiry_date)]})
        return box_no_product_dict

    def get_amz_product_seller_sku(self, shipment, carton_line, instance):
        """
        Get Amazon Product Seller SKU and Quantty in case
        :param shipment: amazon.inbound.shipment.ept()
        :param carton_line:
        :param instance:
        :return:
        """
        amazon_product_obj = self.env[AMAZON_PRODUCT_EPT]
        line = shipment.odoo_shipment_line_ids.filtered(lambda shipment_line, carton_line=carton_line:
                                                        shipment_line.amazon_product_id.id == carton_line.amazon_product_id.id)
        line = line and line[0]
        seller_sku = line and line.seller_sku
        quantity_in_case = line.quantity_in_case if line.quantity_in_case > 0.0 else 1
        if not line:
            amazon_product = amazon_product_obj.search([('id', '=', carton_line.amazon_product_id.id),
                                                        ('instance_id', '=', instance.id)], limit=1)
            seller_sku = amazon_product.seller_sku if amazon_product else False
        return seller_sku, quantity_in_case

    def setup_partnered_ltl_data(self, parcel_data):
        """
        This method will get the parcel information and update the inbound shipment values.
        """
        self.ensure_one()
        box_count = parcel_data.get('BoxCount', False)
        freight_class = parcel_data.get('SellerFreightClass', False)
        freight_ready_date = parcel_data.get('FreightReadyDate', False)
        prev_pickup_date = parcel_data.get('PreviewPickupDate', False)
        prev_delivery_date = parcel_data.get('PreviewDeliveryDate', False)
        prev_freight_class = parcel_data.get('PreviewFreightClass', False)
        amazon_ref_id = parcel_data.get('AmazonReferenceId', False)
        is_bol_available = True if str(parcel_data.get('IsBillOfLadingAvailable', '')) == 'true' else False
        currency_code = parcel_data.get('AmazonCalculatedValue', {}).get('CurrencyCode', '')
        vals = {}
        if currency_code:
            currency = self.env[RES_CURRENCY].search([('name', '=', currency_code)], limit=1)
            currency and vals.update({'declared_value_currency_id': currency.id})
        currency_value = parcel_data.get('AmazonCalculatedValue', {}).get('Value', 0.0)
        if currency_value > 0.0:
            vals.update({'seller_declared_value': currency_value})
        if freight_class:
            vals.update({'seller_freight_class': freight_class})
        if freight_ready_date:
            freight_ready_date = self.amz_convert_shipment_date_ept(freight_ready_date, '%Y-%m-%d')
            vals.update({'freight_ready_date': freight_ready_date})
        if box_count:
            vals.update({'box_count': box_count})
        if prev_pickup_date:
            prev_pickup_date = self.amz_convert_shipment_date_ept(prev_pickup_date)
            vals.update({'preview_pickup_date': prev_pickup_date})
        if prev_delivery_date:
            prev_delivery_date = self.amz_convert_shipment_date_ept(prev_delivery_date)
            vals.update({'preview_delivery_date': prev_delivery_date})
        if prev_freight_class:
            vals.update({'preview_freight_class': prev_freight_class})
        if amazon_ref_id:
            vals.update({'amazon_reference_id': amazon_ref_id})
        if is_bol_available:
            vals.update({'is_billof_lading_available': is_bol_available})
        self.write(vals)
        return True

    @staticmethod
    def amz_convert_shipment_date_ept(str_date, ymd_formate=''):
        """
        Define this method for convert string formate date from Datetime.
        :param: str_date: date in string formate
        :param: ymd_formate: date formate (YY-MM-DD)
        :return: datetime()
        """
        date_formate = '%Y-%m-%d %H:%M:%S'
        if ymd_formate:
            date_formate = ymd_formate
        date = dateutil.parser.parse(str_date)
        return datetime.strftime(date, date_formate)

    def setup_partnered_small_parcel_data(self, parcel_data):
        """
        This method will prepare package information from the parcel data and
        create or update package.
        """
        package_list = []
        packages = parcel_data.get('PackageList', [])
        if not isinstance(packages, list):
            package_list.append(packages)
        else:
            package_list = packages
        for package in package_list:
            tracking_number = package.get('TrackingId', '')
            if not tracking_number:
                continue
            package_status = package.get('PackageStatus', '')
            weight_unit = package.get('Weight', {}).get('Unit', '')
            weight_value = package.get('Weight', {}).get('Value', 0.0) and \
                           float(package.get('Weight', {}).get('Value', 0.0)) or 0.0
            package_vals = {'package_status': package_status, 'tracking_no': tracking_number}
            domain = [('partnered_small_parcel_shipment_id', '=', self.ids and self.ids[0])]
            if weight_unit:
                package_vals.update({'weight_unit': weight_unit})
                domain.append(('weight_unit', '=', weight_unit))
            if weight_value:
                package_vals.update({'weight_value': weight_value})
                domain.append(('weight_value', '=', weight_value))
            self.amz_create_stock_quant_packages(domain, package_vals, tracking_number)
        return True

    def amz_create_stock_quant_packages(self, domain, package_vals, tracking_number):
        """
        Create Stock Quant Packages for Partenered Small Parcel shipments
        :param domain: list[]
        :param package_vals: dict{}
        :param tracking_number:
        :return:
        """
        package_obj = self.env[STOCK_QUANT_PACKAGE]
        package_exist = package_obj.search([('partnered_small_parcel_shipment_id', '=', self.ids and self.ids[0]),
                                            ('tracking_no', '=', tracking_number)])
        if not package_exist:
            domain.append(('tracking_no', '=', False))
            package_exist = package_obj.search(domain, order='id')
        if package_exist:
            package_exist = package_exist[0]
            package_exist.write(package_vals)
        else:
            package_vals.update({'partnered_small_parcel_shipment_id': self.ids and self.ids[0]})
            package_obj.create(package_vals)

    def set_estimate_amount(self, parcel_data):
        """
        This method will set the currency, estimate amount, void deadline date and confirm
        deadline date.
        """
        amount = parcel_data.get('PartneredEstimate', {}).get('Amount', {})
        currency = amount.get('CurrencyCode', '')
        amount_value = amount.get('Value', 0.0)
        deadline_date = parcel_data.get('PartneredEstimate', {}).get('VoidDeadline', '')
        confirm_deadline_date = parcel_data.get('PartneredEstimate', {}).get('ConfirmDeadline', '')
        currency_id = self.env[RES_CURRENCY].search([('name', '=', currency)])
        deadline_date = deadline_date and dateutil.parser.parse(deadline_date)
        deadline_date = deadline_date and datetime.strftime(deadline_date, '%Y-%m-%d %H:%M:%S')
        vals = {'currency_id': currency_id and currency_id[0].id or False,
                'estimate_amount': amount_value, 'void_deadline_date': deadline_date}
        if confirm_deadline_date:
            confirm_deadline_date = dateutil.parser.parse(confirm_deadline_date)
            confirm_deadline_date = confirm_deadline_date and datetime.strftime(confirm_deadline_date, '%Y-%m-%d %H:%M:%S')
            vals.update({'confirm_deadline_date': confirm_deadline_date})
        self.write(vals)
        return True

    def get_transport_content(self):
        """
        This method will request for transport content based on shipment id and process response.
        """
        instance = self.get_instance(self)
        kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
        kwargs.update({'emipro_api': 'get_transport_content_sp_api', 'shipment_id': self.shipment_id,})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            raise UserError(_(response.get('error', {})))
        result = response.get('result', {})
        transport_result = result.get('TransportContent', {}).get('TransportResult', {})
        transport_detail = result.get('TransportContent', {}).get('TransportDetails', {})
        transport_header = result.get('TransportContent', {}).get('TransportHeader', {})
        transport_status = transport_result.get('TransportStatus', '')
        ship_type = transport_header.get('ShipmentType', '')
        is_partnered = True if str(transport_header.get('IsPartnered', {})) in ['true', 'True'] else False
        if is_partnered and ship_type == 'SP' and transport_status in ['ESTIMATED', 'CONFIRMING', 'CONFIRMED']:
            small_parcel_data = transport_detail.get('PartneredSmallParcelData', {})
            self.set_estimate_amount(small_parcel_data)
            self.setup_partnered_small_parcel_data(small_parcel_data)
        elif is_partnered and ship_type == 'LTL' and transport_status in ['ESTIMATED', 'CONFIRMING', 'CONFIRMED']:
            parcel_data = transport_detail.get('PartneredLtlData', {})
            self.set_estimate_amount(parcel_data)
            self.setup_partnered_ltl_data(parcel_data)
        if transport_status in transport_status_list:
            self.write({'transport_state': transport_status})
        if transport_status == 'VOIDED':
            self.reset_inbound_shipment()
        return True

    def estimate_transport_request(self):
        """
        This method is used to send estimate transport request and process transport_status_list
        to get transport content.
        """
        instance = self.get_instance(self)
        kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
        kwargs.update({'emipro_api': 'estimate_transport_request_sp_api', 'shipment_id': self.shipment_id,})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            error_value = response.get('error', {})
            raise UserError(_(error_value))
        result = response.get('result', {})
        transport_status = result and result.get('TransportResult', {}).get('TransportStatus', '')
        if transport_status in transport_status_list:
            self.write({'transport_state': transport_status})
            self.get_transport_content()
        return True

    def get_carton_content_result(self):
        """
        This method will request for get feed submission result based on feed_result_id and process
        response.
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        if self.feed_id:
            instance = self.get_instance(self)
            kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
            kwargs.update({'emipro_api': 'get_feed_submission_result_sp_api',
                           'feed_submission_id': self.feed_id.feed_result_id})
            try:
                response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
                if response.get('error', False):
                    raise UserError(_(response.get('error', {})))
                result = response.get('result', {})
                xml_to_dict_obj = xml2dict()
                result = xml_to_dict_obj.fromstring(result)
                summary = result.get('AmazonEnvelope', {}).get('Message', {}).get('ProcessingReport', {}).get(
                    'ProcessingSummary', {})
                error = summary.get('MessagesWithError').get('value', '')
                if error != '0':
                    summary = result.get('AmazonEnvelope', {}).get('Message', {}).get(
                        'ProcessingReport', {}).get('ProcessingSummary', {})
                    description = "MessagesProcessed %s" % (summary.get('MessagesProcessed').get('value',''))
                    description = "%s || MessagesSuccessful %s" % (description, summary.get(
                        'MessagesSuccessful').get('value', ''))
                    description = "%s || MessagesSuccessful %s" % (description, summary.get(
                        'MessagesSuccessful').get('value',''))
                    description = "%s || MessagesWithWarning %s" % (description, summary.get(
                        'MessagesWithWarning').get('value',''))
                    summary = result.get('AmazonEnvelope', {}).get('Message', {}).get(
                        'ProcessingReport', {}).get('Result', [])
                    if not isinstance(summary, list):
                        summary = [summary]
                    for line in summary:
                        description = "%s %s" % (description, line.get('ResultDescription', ''))
                    log_line_obj.create_common_log_line_ept(
                        message=description, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept',
                        operation_type='export', res_id=self.id or 0,
                        amz_instance_ept=instance and instance.id or False,
                        amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                    self.write({'is_update_inbound_carton_contents': False})
                else:
                    self.write({'is_carton_content_updated': True})
            except Exception as e:
                raise UserError(_(str(e)))
        return True

    def export_partnered_small_parcel(self):
        """
        This method is used to export small parcel.
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        for shipment in self:
            instance = self.get_instance(shipment)
            data = {'IsPartnered': str(bool(shipment.is_partnered)).lower(),
                    'ShipmentType': 'SP' if shipment.shipping_type == 'sp' else 'LTL'}
            if not shipment.partnered_small_parcel_ids:
                message = 'Inbound Shipment %s is not update in amazon because Parcel not found ' \
                          'for update in amazon' % shipment.name
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                continue
            data, skip_process = self.amz_prepare_partnered_small_parcel_data(shipment, data)
            if not skip_process:
                continue
            kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
            kwargs.update({'emipro_api': 'put_transport_content_sp_api',
                           'shipment_id': shipment.shipment_id, 'data': data, })
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                error_value = response.get('error', {})
                message = '%s %s' % (error_value, shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                shipment.write({'state': 'ERROR'})
            else:
                result = response.get('result', {})
                transport_status = result and result.get('TransportResult', {}).get('TransportStatus', '')
                if transport_status in transport_status_list:
                    shipment.write({'transport_state': transport_status, 'transport_content_exported': True,
                                    'updated_in_amazon': True})
                shipment.get_transport_content()
                shipment.estimate_transport_request()
        return True

    def amz_prepare_partnered_small_parcel_data(self, shipment, data):
        """
        Prepare data for Partnered Small Parcel shipment
        :param shipment: amazon.inbound.shipment.ept()
        :param data: dict{}
        :return: data, skip_process
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        skip_process = True
        package_list = []
        shipment_carrier = ''
        instance = self.get_instance(shipment)
        for package in shipment.partnered_small_parcel_ids:
            if not package.ul_id:
                message = 'Inbound Shipment %s is not update in amazon because dimension ' \
                          'package not found for update' % (shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                skip_process = False
                break
            if package.ul_id.height <= 0.0 or package.ul_id.width <= 0.0 or package.ul_id.length <= 0.0:
                message = 'Inbound Shipment %s is not update in amazon because Dimension ' \
                          'Length, Width and Height value must be greater than zero.' % (shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                skip_process = False
                break
            dimension_unit = package.ul_id.dimension_unit or 'centimeters'
            if shipment.carrier_id:
                shipment_carrier = shipment.carrier_id.amz_carrier_code or shipment.carrier_id.name
            package_list.append({'Dimensions': {'Unit': dimension_unit, 'Length': str(package.ul_id.length),
                                                'Width': package.ul_id.width, 'Height': str(package.ul_id.height)},
                                 'Weight': {'Unit': package.weight_unit, 'Value': str(package.weight_value)}})
        if package_list:
            data.update({'TransportDetails': {'PartneredSmallParcelData': {'PackageList': package_list}}})
        if shipment_carrier:
            data.get('TransportDetails', {}).get('PartneredSmallParcelData', {}).update(
                {'CarrierName': shipment_carrier})
        return data, skip_process

    def export_non_partnered_small_parcel_tracking(self):
        """
        This method used to export non partnered small parcel tracking
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        ctx = self._context.copy() or {}
        auto_called = ctx.get('auto_called', False)
        for shipment in self:
            instance = self.get_instance(shipment)
            pickings = shipment.picking_ids.filtered(lambda pick: pick.state == 'done' and not pick.is_fba_wh_picking and not pick.updated_in_amazon)
            if not pickings:
                message = 'Inbound Shipment %s is not update in amazon because of system is' \
                          'not found any transferred picking' % shipment.name
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                continue
            pickings = shipment.picking_ids.filtered(lambda pick: pick.state == 'done' and not pick.is_fba_wh_picking)
            data = {'IsPartnered':str(bool(shipment.is_partnered)).lower(),
                    'ShipmentType': 'SP' if shipment.shipping_type == 'sp' else 'LTL'}
            carrier_name = pickings[0].carrier_id.amz_carrier_code if pickings[0].carrier_id else 'OTHER'
            back_orders = shipment.picking_ids.filtered(lambda pick: pick.state not in ['done', 'cancel']
                                                        and not pick.is_fba_wh_picking and not pick.updated_in_amazon)
            if back_orders:
                back_orders.action_cancel()
            tracking_list, tacking_no_list = self.prepare_non_partnered_small_parcel_data(pickings, shipment)
            if tacking_no_list:
                data.update({'TransportDetails': {'NonPartneredSmallParcelData': {'PackageList': tracking_list}}})
            if carrier_name:
                data.get('TransportDetails', {}).get('NonPartneredSmallParcelData', {}).\
                    update({'CarrierName': carrier_name})
            kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
            kwargs.update({'emipro_api': 'put_transport_content_sp_api',
                           'shipment_id': shipment.shipment_id, 'data': data})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            self.process_small_parcel_tracking_response_result(response, pickings, shipment)
            if shipment.state != 'ERROR':
                self.update_shipment_ept(shipment, pickings, back_orders, auto_called, instance)
        return True

    def process_small_parcel_tracking_response_result(self, response, pickings, shipment):
        """
        Process response of small parcel tracking numbers
        :param response: Amazon Response dict{}
        :param pickings: stock.picking()
        :param shipment: amazon.inbound.shipment.ept()
        :return:
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        instance = self.get_instance(shipment)
        if response.get('result', False):
            result = response.get('result', {})
            pickings.write({'updated_in_amazon': True})
            transport_status = result and result.get('TransportResult', {}).get('TransportStatus', '')
            if transport_status in transport_status_list:
                shipment.write({'transport_state': transport_status, 'transport_content_exported': True,
                                'state': 'SHIPPED', 'updated_in_amazon': True})
        elif response.get('error', False):
            error_value = response.get('error', {})
            message = '%s %s' % (error_value, shipment.name)
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
            shipment.write({'state': 'ERROR'})

    def prepare_non_partnered_small_parcel_data(self, pickings, shipment):
        """
        Prepare data for update non partnered small parcel transport.
        :param pickings: stock.picking()
        :param shipment: amazon.inbound.shipment.ept()
        :return: TransportDetails dict {}
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        tracking_list = []
        tacking_no_list = []
        instance = self.get_instance(shipment)
        for picking in pickings:
            for op in picking.move_line_ids:
                tracking_no = op.result_package_id and op.result_package_id.tracking_no
                if tracking_no and tracking_no not in tacking_no_list:
                    tracking_list.append({'TrackingId': str(tracking_no)})
                    tacking_no_list.append(tracking_no)
            if not tracking_list:
                message = 'Inbound Shipment %s is not update in amazon because Tracking ' \
                          'number not found in the system' % shipment.name
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
        return tracking_list, tacking_no_list

    def update_shipment_ept(self, fba_shipment, pickings, back_orders, auto_called, instance):
        """
        This method is used to update the shipment.
        :param fba_shipment : fba shipment.
        :param pickings : stock pickings
        :param back_orders : back orders
        :param auto_called : check is execution via cron
        :param instance : instance
        """
        sku_list = []
        for picking in pickings:
            for x in range(0, len(picking.move_ids), 1):
                move_lines = picking.move_ids[x:x + 1]
                sku_qty_dict = {}
                for move in move_lines.filtered(lambda l: l.state == 'done'):
                    amazon_product = self.search_amazon_product(instance, move.product_id, "FBA")
                    line = fba_shipment.odoo_shipment_line_ids.filtered(
                        lambda line, amazon_product=amazon_product: line.amazon_product_id.id == amazon_product.id)
                    qty = sku_qty_dict.get(str(line and line.seller_sku or amazon_product[0].seller_sku), 0.0)
                    qty = move.product_qty + float(qty)
                    sku_qty_dict.update({str(line and line.seller_sku or amazon_product[0].seller_sku): str(int(qty))})
                list_of_dict = self.prepare_list_of_dict_for_update_shipment(sku_qty_dict)
                self.update_shipment_in_amazon(picking, list_of_dict, instance, fba_shipment, auto_called)
                sku_list = sku_list + list(sku_qty_dict.keys())
        for picking in back_orders:
            self.amz_update_shipment_back_orders(fba_shipment, picking, auto_called, instance, sku_list)
        pickings.write({'shipment_status': 'SHIPPED'})
        return True

    def amz_update_shipment_back_orders(self, fba_shipment, picking, auto_called, instance, sku_list):
        """
        Purpose: Process Amazon Shipment dor process backorders and update it to Amazon
        :param fba_shipment: amazon.inbound.shipment.ept()
        :param picking: stock.move()
        :param auto_called: boolean
        :param instance: amazon.instance.ept()
        :param sku_list: list[]
        :return:
        """
        for x in range(0, len(picking.move_ids), 20):
            move_lines = picking.move_ids[x:x + 20]
            sku_qty_dict = {}
            for move in move_lines:
                amazon_product = self.search_amazon_product(instance, move.product_id, "FBA")
                line = fba_shipment.odoo_shipment_line_ids.filtered(
                    lambda line, amazon_product=amazon_product: line.amazon_product_id.id == amazon_product.id)
                if str(line and line.seller_sku or amazon_product[0].seller_sku) in sku_list:
                    continue
                if str(line and line.seller_sku or amazon_product[0].seller_sku) not in sku_qty_dict:
                    sku_qty_dict.update({str(line and line.seller_sku or amazon_product[0].seller_sku): str(int(0.0))})
            list_of_dict = self.prepare_list_of_dict_for_update_shipment(sku_qty_dict)
            self.update_shipment_in_amazon(picking, list_of_dict, instance, fba_shipment, auto_called)

    def search_amazon_product(self, instance, product, fulfillment_by):
        """
        Common Method for search amazon product for inbound shipment
        :param instance: amazon.instance.ept()
        :param product: product.product()
        :param fulfillment_by: FBA / FBM / BOTH
        :return: amazon.product.ept()
        """
        amazon_product_obj = self.env[AMAZON_PRODUCT_EPT]
        amazon_product = amazon_product_obj.search([('product_id', '=', product.id), ('instance_id', '=', instance.id),
                                                    ('fulfillment_by', '=', fulfillment_by)])
        if not amazon_product:
            raise UserError(_("Amazon Product is not available for this %s product code" % (product.default_code)))
        return amazon_product

    @staticmethod
    def prepare_list_of_dict_for_update_shipment(sku_qty_dict):
        """
        Prepare List of dictionary for update in shipment
        :param sku_qty_dict: dict{}
        :return: list of dict
        """
        list_of_dict = []
        if sku_qty_dict:
            for sku, qty in sku_qty_dict.items():
                list_of_dict.append({'SellerSKU': sku, 'QuantityShipped': int(qty)})
        return list_of_dict

    def update_shipment_in_amazon(self, picking, sku_qty_list, instance, fba_shipment, auto_called):
        """
        The method will be used for update shipment from odoo to amazon
        :param picking: stock.picking
        :param sku_qty_dict: dict{}
        :param instance: amazon.instance.ept()
        :param fba_shipment: amazon.inbound.shipment.epr()
        :param auto_called: Boolean
        :return: Boolean
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        address = picking.partner_id or fba_shipment.shipment_plan_id.ship_from_address_id
        label_prep_type = fba_shipment.label_prep_type
        if label_prep_type == 'NO_LABEL':
            label_prep_type = 'SELLER_LABEL'
        elif label_prep_type == 'AMAZON_LABEL':
            label_prep_type = fba_shipment.shipment_plan_id.label_preference
        destination = fba_shipment.fulfill_center_id
        shipment_status = 'SHIPPED'
        address_dict = self.prepare_inbound_shipment_address_dict(address)
        kwargs = self.prepare_inbound_shipment_kwargs(instance, fba_shipment)
        kwargs.update({'emipro_api': 'update_shipment_in_amazon_sp_api',
                       'destination': destination,
                       'labelpreppreference': label_prep_type,
                       'sku_qty_list': sku_qty_list,
                       'address_dict': address_dict,
                       'shipment_status': shipment_status})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            error_value = response.get('error', {})
            if not auto_called:
                raise UserError(_(error_value))
            else:
                log_line_obj.create_common_log_line_ept(
                    message=error_value, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept',
                    operation_type='export', res_id=fba_shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
            fba_shipment.write({'state':'ERROR', 'updated_in_amazon':False, 'transport_content_exported':False})
            picking.write({'updated_in_amazon': False})
        return True

    def export_non_partnered_ltl_parcel_tracking(self):
        """
        Purpose: If Data updated in Amazon then update picking record and set updated_in_amazon = True
        :return:
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        ctx = self._context
        auto_called = ctx.get('auto_called', False)
        for shipment in self:
            instance = self.get_instance(shipment)
            pickings = shipment.picking_ids.filtered(lambda pick: pick.state == 'done' and not pick.is_fba_wh_picking
                                                     and not pick.updated_in_amazon)
            if not pickings:
                message = 'Inbound Shipment %s is not update in amazon because of system is ' \
                          'not found any transfered picking' % (shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                continue
            data, back_orders = self.amz_prepare_non_partnered_ltl_tracking_data(shipment)
            kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
            kwargs.update({'emipro_api': 'put_transport_content_sp_api',
                           'shipment_id': shipment.shipment_id, 'data': data})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                error_value = response.get('error', {})
                message = '%s %s' % (error_value, shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                shipment.write({'state': 'ERROR'})
            if shipment.state != 'ERROR':
                result = response.get('result', {})
                transport_status = result and result.get('TransportResult', {}).get('TransportStatus', '')
                pickings.write({'updated_in_amazon': True})
                if transport_status in transport_status_list:
                    shipment.write({'transport_state': transport_status, 'transport_content_exported': True,
                                    'state': 'SHIPPED', 'updated_in_amazon': True})
                self.update_shipment_ept(shipment, pickings, back_orders, auto_called, instance)
        return True

    @staticmethod
    def amz_prepare_non_partnered_ltl_tracking_data(shipment):
        """
        Prepare data for Amazon Non Partnered LTL Parcel tracking details
        :param shipment:amazon.inbound.shipment.ept()
        :return: data, back_orders
        """
        data = {'IsPartnered': str(bool(shipment.is_partnered)).lower(),
                'ShipmentType': 'SP' if shipment.shipping_type == 'sp' else 'LTL'}
        if not shipment.carrier_id:
            fba_pickings = shipment.picking_ids.filtered('is_fba_wh_picking')
            if fba_pickings and fba_pickings[0].carrier_id:
                carrier_name = fba_pickings[0].carrier_id.name
            else:
                carrier_name = 'OTHER'
        else:
            carrier_name = shipment.carrier_id.name
        back_orders = shipment.picking_ids.filtered(lambda pick: pick.state not in ['done', 'cancel']
                                                                 and not pick.is_fba_wh_picking and not pick.updated_in_amazon)
        if back_orders:
            back_orders.action_cancel()
        data.update({'TransportDetails': {'NonPartneredLtlData': {'CarrierName': str(carrier_name),
                                                                  'ProNumber': str(shipment.pro_number)}}})
        return data, back_orders

    def confirm_transport_request(self):
        """
        This method is used to confirm transport request.
        """
        instance = self.get_instance(self)
        kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
        kwargs.update({'emipro_api': 'confirm_transport_request_sp_api', 'shipment_id': self.shipment_id})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            error_value = response.get('error', {})
            raise UserError(_(error_value))
        result = response.get('result', {})
        transport_status = result.get('TransportResult', {}).get('TransportStatus', '')
        if transport_status in transport_status_list:
            self.write({'transport_state': transport_status})
        self.get_transport_content()
        return True

    def reset_inbound_shipment(self):
        """
        This method will set transport_content_exported to false and transport_state to draft.
        """
        self.ensure_one()
        self.transport_content_exported = False
        self.transport_state = 'draft'
        return True

    def void_transport_request(self):
        """
        Purpose: We need to only reset Inbound Shipment if we get status = Voided,
        because may be we can get status like voiding or error_in_voiding"""
        instance = self.get_instance(self)
        if not self.void_deadline_date:
            self.get_transport_content()
        kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
        kwargs.update({'emipro_api': 'void_transport_request_sp_api', 'shipment_id': self.shipment_id})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            error_value = response.get('error', {})
            raise UserError(_(error_value))
        result = response.get('result', {})
        transport_status = result and result.get('TransportResult', {}).get('TransportStatus', '')
        if transport_status in transport_status_list:
            self.write({'transport_state': transport_status})
        if transport_status == 'VOIDED':
            self.reset_inbound_shipment()
        return True

    def get_package_labels(self):
        """
        This method will return the amazon shipment label wizard to get package labels.
        :return:
        """
        ctx = self._context.copy() or {}
        if ctx.get('label_type', '') == 'delivery':
            view = self.env.ref('amazon_ept.amazon_inbound_shipment_print_delivery_label_wizard_form_view',
                                raise_if_not_found=False)
        else:
            view = self.env.ref('amazon_ept.amazon_inbound_shipment_print_shipment_label_wizard_form_view',
                                raise_if_not_found=False)
            if self.shipping_type == 'sp' and self.is_partnered and not self.partnered_small_parcel_ids:
                raise UserError(_("Box dimension information's are missing!!! "))
            if self.is_partnered and self.shipping_type == 'ltl':
                ctx.update({'default_number_of_box': self.box_count})
            elif self.is_partnered and self.partnered_small_parcel_ids:
                ctx.update({'default_number_of_box': len(self.partnered_small_parcel_ids.ids), 'box_readonly': True})
        ctx.update({'shipping_type': self.shipping_type, })
        return {
            'name': _('Labels'),
            'type': IR_ACTION_ACT_WINDOW,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'amazon.shipment.label.wizard',
            'view_id': view.id,
            'nodestroy': True,
            'target': 'new',
            'context': ctx,
        }

    def get_unique_package_labels(self):
        """
        This method will return the wizard to get unique package labels.
        """
        view = self.env.ref('amazon_ept.amazon_inbound_shipment_print_unique_label_wizard_form_view',
                            raise_if_not_found=False)
        if not self.is_partnered:
            return True
        return {
            'name': _('Labels'),
            'type': IR_ACTION_ACT_WINDOW,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'amazon.shipment.label.wizard',
            'view_id': view.id,
            'nodestroy': True,
            'target': 'new',
            'context': self._context,
        }

    def check_status(self):
        """
        Check status of Shipment from amazon and update in Odoo as per response of Amazon.
        :return:True
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        instance_shipment_ids = defaultdict(list)
        for shipment in self:
            if not shipment.shipment_id:
                continue
            instance = self.get_instance(shipment)
            instance_shipment_ids[instance].append(str(shipment.shipment_id))
        for instance, shipment_ids in instance_shipment_ids.items():
            kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
            kwargs.update({'emipro_api': 'check_status_by_shipment_ids', 'shipment_ids': shipment_ids})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', {}) and self._context.get('is_auto_process', False):
                log_line_obj.create_common_log_line_ept(
                    message=response.get('error', {}), model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept',
                    operation_type='import', res_id=self.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
            elif response.get('error', False):
                raise UserError(_(response.get('error', {})))
            amazon_shipments = response.get('amazon_shipments', [])
            self.amz_check_status_process_shipments(amazon_shipments, instance)
        return True

    def amz_check_status_process_shipments(self, amazon_shipments, instance):
        """
        :param amazon_shipments:
        :param instance:
        :return:
        """
        stock_picking_obj = self.env[STOCK_PICKING]
        for ship_member in amazon_shipments:
            flag = False
            cases_required = bool(str(ship_member.get('AreCasesRequired', 'false')) == 'true')
            shipmentid = ship_member.get('ShipmentId', '')
            shipment_status = ship_member.get('ShipmentStatus', '')
            odoo_shipment_rec = self.search([('shipment_id', '=', shipmentid)])
            already_returned = False
            if shipment_status in ['RECEIVING', 'CLOSED']:
                kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
                kwargs.update({'emipro_api': 'check_amazon_shipment_status_spapi', 'amazon_shipment_id': shipmentid})
                response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
                if response.get('error', False):
                    raise UserError(_(response.get('error', {})))
                pickings = odoo_shipment_rec.mapped('picking_ids').filtered(lambda r: r.state in ['assigned'] and r.is_fba_wh_picking)
                if pickings:
                    pickings.check_amazon_shipment_status(response)
                    backorders = odoo_shipment_rec.picking_ids.filtered(
                        lambda picking: picking.state in ('waiting', 'confirmed') and picking.is_fba_wh_picking)
                    if backorders:
                        backorders.action_assign()
                    odoo_shipment_rec.write({'state': shipment_status, 'are_cases_required': cases_required})
                    stock_picking_obj.check_qty_difference_and_create_return_picking(response, shipmentid,
                                                                                     odoo_shipment_rec.id, instance)
                    already_returned = True
                else:
                    if odoo_shipment_rec:
                        pickings = odoo_shipment_rec.mapped('picking_ids').filtered(
                            lambda r: r.state in ['draft', 'waiting', 'confirmed'] and r.is_fba_wh_picking)
                        if pickings:
                            pickings = self.amz_cancel_waiting_state_pickings(pickings, odoo_shipment_rec)
                    if not pickings:
                        flag = False
                        self.get_remaining_qty(response, instance, shipmentid, odoo_shipment_rec)
                        odoo_shipment_rec.write({'state': shipment_status, 'are_cases_required': cases_required})
                    else:
                        raise UserError(_("""Shipment Status is not update due to picking not found
                                             for processing  ||| Amazon status : %s ERP status : %s
                                             """ % (shipment_status, odoo_shipment_rec.state)))
                if shipment_status == 'CLOSED':
                    if not flag:
                        self.get_remaining_qty(response, instance, shipmentid, odoo_shipment_rec)
                    if not odoo_shipment_rec.closed_date:
                        odoo_shipment_rec.write({'closed_date': time.strftime("%Y-%m-%d")})
                    if odoo_shipment_rec:
                        pickings = odoo_shipment_rec.mapped('picking_ids').filtered(
                            lambda r: r.state not in ['done', 'cancel'] and r.is_fba_wh_picking)
                    if pickings:
                        pickings.action_cancel()
                    if not already_returned:
                        stock_picking_obj.check_qty_difference_and_create_return_picking(response, shipmentid,
                                                                                         odoo_shipment_rec.id, instance)
            else:
                odoo_shipment_rec.write({'state': shipment_status})
        return True

    @staticmethod
    def amz_cancel_waiting_state_pickings(pickings, odoo_shipment_rec):
        """
        Define this method for cancel inbound shipment waiting state pickings for non tracking products.
        :param: pickings: stock.picking()
        :param: odoo_shipment_rec: amazon.inbound.shipment.ept()
        :return: stock.picking()
        """
        for picking in pickings.filtered(lambda pick: pick.state in ('waiting', 'confirmed')):
            if not picking.move_ids.filtered(lambda move: move.product_id.tracking in ('serial', 'lot')):
                picking.action_cancel()
        return odoo_shipment_rec.mapped('picking_ids').filtered(
            lambda r: r.state in ['draft', 'waiting', 'confirmed'] and r.is_fba_wh_picking)

    def amz_prepare_inbound_shipment_kwargs_vals(self, instance):
        """
        Prepare General Arguments for call Amazon MWS API
        :param instance:
        :return: kwargs {}
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                  'app_name': 'amazon_ept_spapi',
                  'account_token': account.account_token,
                  'dbuuid': dbuuid,
                  'marketplace_id': instance.market_place_id,
                  'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                             instance.country_id.code}
        return kwargs

    def get_remaining_qty(self, response, instance, amazon_shipment_id, odoo_shipment_rec):
        """
        Get remaining Quantity from done or cancelled pickings
        :param instance: amazon.instance.ept()
        :param amazon_shipment_id:
        :param odoo_shipment_rec:
        :return: Boolean
        """
        pickings = odoo_shipment_rec.picking_ids.filtered(
            lambda picking: picking.state == 'done' and picking.is_fba_wh_picking).sorted(key=lambda x: x.id)
        if not pickings:
            pickings = odoo_shipment_rec.picking_ids.filtered(lambda picking:
                                                              picking.state == 'cancel' and picking.is_fba_wh_picking)
        picking = pickings and pickings[0]
        new_picking = self.amz_inbound_copy_new_picking(response, instance, odoo_shipment_rec,
                                                        amazon_shipment_id, picking)
        return True

    def amz_inbound_copy_new_picking(self, response, instance, odoo_shipment_rec, amazon_shipment_id, picking):
        """
        create copy of picking and stock move if quantity mismatch found from done moves and amazon received quantity.
        :param response: list(dict{})
        :param instance: amazon.instance.ept()
        :param odoo_shipment_rec:
        :param amazon_shipment_id:
        :param picking:
        :return:
        """
        picking_obj = self.env[STOCK_PICKING]
        new_picking = picking_obj
        for item in response.get('items', {}):
            received_qty = float(item.get('QuantityReceived', 0.0))
            if received_qty <= 0.0:
                continue
            amazon_product = picking_obj.amz_get_inbound_amazon_products_ept(instance, picking, item)
            if not amazon_product:
                continue
            picking_obj.amz_inbound_shipment_plan_line_ept(odoo_shipment_rec, amazon_product, item)
            odoo_product = amazon_product.product_id if amazon_product else False
            received_qty = picking_obj.amz_find_received_qty_from_done_moves(odoo_shipment_rec, odoo_product,
                                                                             received_qty, amazon_shipment_id)
            if received_qty <= 0.0:
                continue
            if not new_picking:
                picking_vals = self.amz_prepare_picking_vals_ept(picking)
                new_picking = picking.copy(picking_vals)
                picking_obj.amz_create_attachment_for_picking_datas(response.get('datas', {}), new_picking)
            move = picking.move_ids[0]
            move_vals = self.amz_prepare_inbound_move_vals_ept(new_picking, odoo_product, received_qty)
            amz_new_move = move.copy(move_vals)
            self.amz_assign_and_process_new_received_move(amz_new_move, received_qty)
        return new_picking

    @staticmethod
    def amz_prepare_inbound_move_vals_ept(new_picking, odoo_product, received_qty):
        """
        Prepare move vals for inbound shipment fba warehouse stock move.
        :param new_picking: stock.picking()
        :param odoo_product: produtc.product()
        :param received_qty: float
        :return: dict {}
        """
        return {
            'picking_id': new_picking.id,
            'product_id': odoo_product.id,
            'product_uom_qty': received_qty,
            'product_uom': odoo_product.uom_id.id,
            'procure_method': 'make_to_stock',
            'group_id': False
        }

    @staticmethod
    def amz_prepare_picking_vals_ept(picking):
        """
        Prepare vals for copy fba warehouse picking.
        :param picking: stock.picking()
        :return: dict {}
        """
        return {
            'is_fba_wh_picking': True,
            'move_ids': [],
            'group_id': False,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id
        }

    def check_status_ept(self, amazon_shipments, seller):
        """
        method is used to check amazon shipment status.
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        instance = seller.instance_ids
        if amazon_shipments:
            for key, amazon_shipment in amazon_shipments.items():
                shipmentid = key
                shipment = self.search([('shipment_id', '=', shipmentid), ('instance_id_ept', 'in', instance.ids)])
                if shipment:
                    pickings = shipment.picking_ids.filtered(
                        lambda picking: picking.state in ('partially_available', 'assigned') and picking.is_fba_wh_picking)
                    if pickings:
                        pickings.check_amazon_shipment_status_ept(amazon_shipment)
                        self.amz_create_back_orders_and_check_return_picking(shipment, shipmentid, amazon_shipment)
                    else:
                        pickings = shipment.picking_ids.filtered(lambda picking: picking.state in (
                            'draft', 'waiting', 'confirmed') and picking.is_fba_wh_picking)
                        self.amz_process_remaining_qty(pickings, shipment, shipmentid, amazon_shipment)
                else:
                    message = "Shipment %s is not found in ERP" % (shipmentid)
                    log_line_obj.create_common_log_line_ept(
                        message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept',
                        operation_type='import', amz_seller_ept=seller and seller.id or False)
        return True

    def amz_process_remaining_qty(self, pickings, shipment, shipmentid, amazon_shipment):
        """
        :param pickings:
        :param shipment:
        :param shipmentid:
        :param amazon_shipment:
        :param model_id:
        :return:
        """
        instance = self.get_instance(shipment)
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        if pickings:
            pickings = self.amz_cancel_waiting_state_pickings(pickings, shipment)
        if not pickings:
            self.get_remaining_qty_ept(shipment.instance_id_ept, shipmentid, shipment, amazon_shipment)
        else:
            message = "Shipment Status %s is not update due to picking not found for processing " \
                      "||| ERP status  : %s " % (shipmentid, shipment.state)
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='import',
                res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                amz_seller_ept=instance.seller_id and instance.seller_id.id or False)

    def amz_create_back_orders_and_check_return_picking(self, shipment, shipmentid, amazon_shipment):
        """
        :param shipment:
        :param shipmentid:
        :param amazon_shipment:
        :return:
        """
        stock_picking_obj = self.env[STOCK_PICKING]
        backorders = shipment.picking_ids.filtered(
            lambda picking: picking.state in ('waiting', 'confirmed') and picking.is_fba_wh_picking)
        if backorders:
            backorders.action_assign()
        stock_picking_obj.check_qty_difference_and_create_return_picking_ept(shipmentid, shipment,
                                                                             shipment.instance_id_ept,
                                                                             amazon_shipment)

    def get_remaining_qty_ept(self, instance, amazon_shipment_id, odoo_shipment_rec, items):
        """
        This method is used to get remaining qty
        :param instance : instance record
        :param amazon_shipment_id: amazon shipment
        :param odoo_shipment_rec : odoo shipment
        :items :
        """
        amazon_product_obj = self.env[AMAZON_PRODUCT_EPT]
        inbound_shipment_plan_line_obj = self.env[INBOUND_SHIPMENT_PLAN_LINE]
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        new_picking = False
        pickings = odoo_shipment_rec.picking_ids.filtered(
            lambda picking: picking.state == 'done' and picking.is_fba_wh_picking).sorted(key=lambda x: x.id)
        picking = pickings and pickings[0]
        if not picking:
            pickings = odoo_shipment_rec.picking_ids.filtered(
                lambda picking: picking.state == 'cancel' and picking.is_fba_wh_picking)
            picking = pickings and pickings[0]
        if picking:
            for item in items:
                sku = item.get('SellerSKU', '')
                asin = item.get('FulfillmentNetworkSKU', '')
                shipped_qty = item.get('QuantityShipped', '')
                received_qty = float(item.get('QuantityReceived', 0.0))
                if received_qty <= 0.0:
                    continue
                amazon_product = amazon_product_obj.search_amazon_product(instance.id, sku, 'FBA')
                if not amazon_product:
                    amazon_product = amazon_product_obj.search([('product_asin', '=', asin),
                                                                ('instance_id', '=', instance.id),
                                                                ('fulfillment_by', '=', 'FBA')], limit=1)
                if not amazon_product:
                    message = "Product not found in ERP ||| FulfillmentNetworkSKU : %s  SellerSKU : %s  Shipped Qty : %s" \
                              "Received Qty : %s" % (asin, sku, shipped_qty, received_qty)
                    log_line_obj.create_common_log_line_ept(
                        message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept',
                        operation_type='import', res_id=odoo_shipment_rec.id,
                        amz_instance_ept=instance and instance.id or False,
                        amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                    continue
                inbound_shipment_plan_line = odoo_shipment_rec.odoo_shipment_line_ids.filtered(
                    lambda line, amazon_product=amazon_product: line.amazon_product_id.id == amazon_product.id)
                if inbound_shipment_plan_line:
                    inbound_shipment_plan_line[0].received_qty = received_qty or 0.0
                else:
                    vals = {
                        'amazon_product_id': amazon_product.id,
                        'quantity': shipped_qty or 0.0,
                        'odoo_shipment_id': odoo_shipment_rec and odoo_shipment_rec[0].id,
                        'fn_sku': asin,
                        'received_qty': received_qty,
                        'is_extra_line': True
                    }
                    inbound_shipment_plan_line_obj.create(vals)
                odoo_product = amazon_product.product_id if amazon_product else False
                done_moves = odoo_shipment_rec.picking_ids.filtered(
                    lambda r: r.amazon_shipment_id == amazon_shipment_id and r.is_fba_wh_picking).mapped(
                        'move_ids').filtered(lambda r, odoo_product=odoo_product: r.state == 'done' and
                                                                                  r.product_id.id == odoo_product.id)
                source_location_id = picking.location_id.id
                for done_move in done_moves:
                    if done_move.location_dest_id.id != source_location_id:
                        received_qty = received_qty - done_move.product_qty
                    else:
                        received_qty = received_qty + done_move.product_qty
                if received_qty <= 0.0:
                    continue
                if not new_picking:
                    new_picking = picking.copy({'is_fba_wh_picking': True, 'move_ids': [], 'group_id': False,
                                                'location_id': picking.location_id.id,
                                                'location_dest_id': picking.location_dest_id.id})
                move = picking.move_ids[0]
                amz_new_move = move.copy({'picking_id': new_picking.id,
                                          'product_id': odoo_product.id,
                                          'product_uom_qty': received_qty,
                                          'product_uom': odoo_product.uom_id.id,
                                          'procure_method': 'make_to_stock',
                                          'group_id': False})
                self.amz_assign_and_process_new_received_move(amz_new_move, received_qty)
        return True

    def amz_assign_and_process_new_received_move(self, new_move, received_qty):
        """
        Define this method for validate received stock moves.
        :return: True
        """
        new_move._action_assign()
        new_move._set_quantity_done(abs(received_qty))
        new_move._action_done()
        return True

    def update_non_partnered_carrier(self):
        """
        This method is used to put_transport_content.
        """
        ctx = self._context.copy() or {}
        auto_called = ctx.get('auto_called', False)
        instance = self.get_instance(self)
        data = {'IsPartnered': str(bool(self.is_partnered)).lower(),
                'ShipmentType': 'SP' if self.shipping_type == 'sp' else 'LTL'}
        if self.shipping_type == 'sp':
            data.update({'TransportDetails': {'NonPartneredSmallParcelData': {'CarrierName': str('OTHER'),
                                                                              'PackageList': [
                                                                                  {'TrackingId': str(' ')}]}}})
        else:
            carrier_code = self.carrier_id.amz_carrier_code if self.carrier_id else 'OTHER'
            data.update({'TransportDetails': {'NonPartneredLtlData': {'CarrierName': str(carrier_code),
                                                                      'ProNumber': '##########'}}})
        kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
        kwargs.update({'emipro_api': 'put_transport_content_sp_api',
                       'shipment_id': self.shipment_id, 'data': data})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            error_value = response.get('error', {})
            if not auto_called:
                raise UserError(_(error_value))
        return True

    def export_partnered_ltl_parcel(self):
        """
        Purpose: Export partnered LTL Parcel data
        :return:
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        for shipment in self:
            instance = self.get_instance(shipment)
            name = shipment.partnered_ltl_id.name or ''
            phone = shipment.partnered_ltl_id.phone or ''
            email = shipment.partnered_ltl_id.email or ''
            if not name or not phone or not email:
                message = 'Invalid contact details found check name/phone/email for contact %s' % (name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                continue
            if len(shipment.partnered_ltl_ids.ids) <= 0:
                message = 'Number of box must be greater than zero for shipment %s' % (shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                continue
            data, flag = self.prepare_partnered_ltl_parcel_data(shipment)

            # Not required parameter, so if given then we will set otherwise we skip it.
            if shipment.amazon_shipment_weight_unit and shipment.amazon_shipment_weight:
                data.get('TransportDetails', {}).get('PartneredLtlData', {}).update({'TotalWeight': {
                    'Unit': str(shipment.amazon_shipment_weight_unit),
                    'Value': str(shipment.amazon_shipment_weight)
                }})
            if shipment.seller_declared_value and shipment.declared_value_currency_id:
                data.get('TransportDetails', {}).get('PartneredLtlData', {}).update({'SellerDeclaredValue': {
                    'CurrencyCode': str(shipment.declared_value_currency_id.name),
                    'Value': str(shipment.seller_declared_value)
                }})
            self.process_inbound_partnered_ltl_shipment(shipment, data, flag)
        return True

    def process_inbound_partnered_ltl_shipment(self, shipment, data, flag):
        """
        Put Transport content for Partnered LTL Shipment
        :param shipment: amazon.inbound.shipment.ept()
        :param data: data {}
        :param flag: boolean
        :return:
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        if flag:
            instance = self.get_instance(shipment)
            kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
            kwargs.update({'emipro_api': 'put_transport_content_sp_api',
                           'shipment_id': shipment.shipment_id, 'data': data})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                error_value = response.get('error', {})
                message = '%s %s' % (error_value, shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                shipment.write({'state': 'ERROR'})
            else:
                result = response.get('result', {})
                transport_status = result and result.get('TransportResult', {}).get('TransportStatus', '')
                if transport_status in transport_status_list:
                    self.write({'transport_state': transport_status,
                                'transport_content_exported': True, 'updated_in_amazon': True})
                shipment.get_transport_content()
                shipment.estimate_transport_request()

    def prepare_partnered_ltl_parcel_data(self, shipment):
        """
        Prepare data dictionary for LTL Partnered parcel data.
        :param shipment: amazon.inbound.shipment.ept()
        :return: data, flag
        """
        instance = self.get_instance(shipment)
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        name = shipment.partnered_ltl_id.name or ''
        phone = shipment.partnered_ltl_id.phone or ''
        email = shipment.partnered_ltl_id.email or ''
        data = {
            'IsPartnered': str(bool(shipment.is_partnered)).lower(),
            'ShipmentType': 'SP' if shipment.shipping_type == 'sp' else 'LTL',
            'TransportDetails': {'PartneredLtlData':{'Contact':{'Name':name,'Phone':str(phone),'Email':email},
                                                     'BoxCount':str(len(shipment.partnered_ltl_ids.ids)),
                                                     'FreightReadyDate':shipment.freight_ready_date.strftime("%Y-%m-%d")}}
        }
        if shipment.seller_freight_class:
            data.get('TransportDetails', {}).get('PartneredLtlData', {}).update({'SellerFreightClass':shipment.seller_freight_class})
        flag = True
        pallet_list = []
        for pallet in shipment.partnered_ltl_ids:
            if not pallet.ul_id:
                message = 'Inbound Shipment %s is not update in amazon because of dimension ' \
                          'for package not found' % shipment.name
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                flag = False
                break
            if pallet.ul_id.length <= 0.0 or pallet.ul_id.width <= 0.0 or pallet.ul_id.height <= 0.0:
                message = 'Inbound Shipment %s is not update in amazon because of Dimension ' \
                          'Length, Width and Height value must be greater that zero' % (shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_INBOUND_SHIPMENT_EPT, module='amazon_ept', operation_type='export',
                    res_id=shipment.id, amz_instance_ept=instance and instance.id or False,
                    amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
                flag = False
                break
            dimension_unit = pallet.ul_id.dimension_unit or 'centimeters'
            pallet_list.append({'Dimensions': {'Unit': dimension_unit, 'Length': str(pallet.ul_id.length),
                                               'Width': pallet.ul_id.width, 'Height': str(pallet.ul_id.height)},
                                'Weight': {'Unit': pallet.weight_unit,
                                           'Value': str(pallet.weight_value)},
                                'IsStacked': 'true' if pallet.is_stacked else 'false'})
        if pallet_list:
            data.get('TransportDetails', {}).get('PartneredLtlData', {}).update({'PalletList': pallet_list})
        return data, flag

    def get_bill_of_lading(self):
        """
        This method is used to get bill of lading and process to create attachment of response
        """
        self.ensure_one()
        instance = self.get_instance(self)
        kwargs = self.amz_prepare_inbound_shipment_kwargs_vals(instance)
        kwargs.update({'emipro_api': 'get_bill_of_lading_sp_api', 'shipment_id': self.shipment_id})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            raise UserError(_(response.get('error', {})))

        result = response.get('result', {})
        document_url = result.get('DownloadURL', '')
        if not document_url:
            raise UserError(_('The Bill of Lading for your Amazon Shipment is currently unavailable'
                              ' as it has not been generated yet. We suggest trying again after a few hours.'))
        document = requests.get(document_url)
        if document.status_code != 200:
            return True
        datas = base64.b64encode(document.content)
        name = document.request.path_url.split('/')[-1].split('?')[0]
        bill_of_lading = self.env['ir.attachment'].create({
            'name': name,
            'datas': datas,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary'
        })
        self.message_post(body=_("<b>Bill Of Lading Downloaded</b>"), attachment_ids=bill_of_lading.ids)
        return True
