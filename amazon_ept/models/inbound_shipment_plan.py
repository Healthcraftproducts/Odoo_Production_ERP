# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
This will perform the amazon inbound shipment plan operations
"""

from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError

from ..endpoint import DEFAULT_ENDPOINT

INBOUND_SHIPMENT_PLAN_EPT = 'inbound.shipment.plan.ept'
COMMON_LOG_LINES_EPT = 'common.log.lines.ept'
AMAZON_INBOUND_SHIPMENT_EPT = 'amazon.inbound.shipment.ept'


class InboundShipmentPlanEpt(models.Model):
    """
    Added class perform the amazon inbound shipment plan operations
    """
    _name = "inbound.shipment.plan.ept"
    _description = "Inbound Shipment Plan"
    _inherit = ['mail.thread']
    _order = 'id desc'

    label_preference_help = """SELLER_LABEL - Seller labels the items in the inbound shipment
    when labels are required. AMAZON_LABEL_ONLY - Amazon attempts to label the items in the 
    inbound shipment when labels are required. If Amazon determines that it does not have the 
    information required to successfully label an item, that item is not included in the inbound 
    shipment plan AMAZON_LABEL_PREFERRED - Amazon attempts to label the items in the inbound 
    shipment when labels are required. If Amazon determines that it does not have the information 
    required to successfully label an item, that item is included in the inbound shipment plan 
    and the seller must label it. """

    state = fields.Selection([('draft', 'Draft'), ('plan_approved', 'Shipment Plan Approved'), ('cancel', 'Cancelled')],
                             default='draft')
    name = fields.Char(size=120, readonly=True, required=False, index=True)
    instance_id = fields.Many2one('amazon.instance.ept', string='Marketplace', required=True,
                                  readonly=True, states={'draft': [('readonly', False)]})
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", readonly=True,
                                   states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
                                 default=lambda self: self.env.company, states={'draft': [('readonly', False)]})
    ship_from_address_id = fields.Many2one('res.partner', string='Ship From Address', readonly=True,
                                           states={'draft': [('readonly', False)]})
    ship_to_country = fields.Many2one('res.country', readonly=True,
                                      states={'draft': [('readonly', False)]},
                                      help="""The country code for the country where you want
                                      your inbound shipment to be sent. Only for sellers in North 
                                      America and Multi-Country Inventory (MCI) sellers in 
                                      Europe. """)
    label_preference = fields.Selection(
        [('SELLER_LABEL', 'SELLER_LABEL'), ('AMAZON_LABEL_ONLY', 'AMAZON_LABEL_ONLY'),
         ('AMAZON_LABEL_PREFERRED', 'AMAZON_LABEL_PREFERRED'), ], default='SELLER_LABEL',
        string='LabelPrepPreference', readonly=True, states={'draft': [('readonly', False)]},
        help=label_preference_help)

    intended_box_contents_source = fields.Selection(
        [('FEED', 'FEED')], default='FEED',
        help="If your instance is USA then you must set box content, other wise amazon will "
             "collect per piece fee",
        string="Intended BoxContents Source", readonly=1)
    is_partnered = fields.Boolean(default=False, copy=False)
    is_are_cases_required = fields.Boolean(string="Are Cases Required ?", default=False,
                                           help="Indicates whether or not an inbound shipment "
                                                "contains case-packed boxes. Note: A shipment must "
                                                "either contain all case-packed boxes or all "
                                                "individually packed boxes.")
    shipping_type = fields.Selection([('sp', 'SP (Small Parcel)'),
                                      ('ltl', 'LTL (Less Than Truckload/FullTruckload (LTL/FTL))')
                                      ], default="sp")
    shipment_line_ids = fields.One2many('inbound.shipment.plan.line', 'shipment_plan_id',
                                        string='Shipment Plan Items', readonly=True,
                                        states={'draft': [('readonly', False)]},
                                        help="SKU and quantity information for the items in an "
                                             "inbound shipment.")
    ship_to_address_ids = fields.Many2many('res.partner', 'rel_inbound_shipment_plan_res_partner',
                                           'shipment_id', 'partner_id', string='Ship To Addresses',
                                           readonly=True)
    picking_ids = fields.One2many('stock.picking', 'ship_plan_id', string="Picking", readonly=True)
    log_ids = fields.One2many(COMMON_LOG_LINES_EPT, compute='_compute_error_logs')
    odoo_shipment_ids = fields.One2many(AMAZON_INBOUND_SHIPMENT_EPT, 'shipment_plan_id',
                                        string='Amazon Shipments')
    count_odoo_shipment = fields.Integer('Count Odoo Shipment', compute='_compute_odoo_shipment')

    def _compute_odoo_shipment(self):
        """
        This method is used to compute total numbers of inbound shipments
        :return: N/A
        """
        for rec in self:
            rec.count_odoo_shipment = len(rec.odoo_shipment_ids.ids)

    def action_view_inbound_shipment(self):
        """
        This method creates and return an action for opening the view of amazon inbound shipment
        :return: action
        """
        action = {
            'name': 'Inbound Shipment',
            'res_model': 'amazon.inbound.shipment.ept',
            'type': 'ir.actions.act_window'
        }
        if self.count_odoo_shipment != 1:
            action.update({'domain': [('id', 'in', self.odoo_shipment_ids.ids)],
                           'view_mode': 'tree,form'})
        else:
            action.update({'res_id': self.odoo_shipment_ids.id,
                           'view_mode': 'form'})
        return action

    @api.model_create_multi
    def create(self, vals_list):
        """
        The below method sets name of a particular record as per the sequence.
        :param: vals_list: list of values []
        :return: inbound.shipment.plan.ept()
        """
        for vals in vals_list:
            sequence = self.env.ref('amazon_ept.seq_inbound_shipment_plan', raise_if_not_found=False)
            name = sequence.next_by_id() if sequence else '/'
            vals.update({'name': name})
        return super(InboundShipmentPlanEpt, self).create(vals_list)

    def unlink(self):
        """
        Use: Check if Shipment Plan is not in Draft state then it will not Delete.
        @param: {}
        @return: {}
        """
        for plan in self:
            if plan.state == 'plan_approved':
                raise UserError(_('You cannot delete Inbound Shipment plan which is not draft.'))
        return super(InboundShipmentPlanEpt, self).unlink()

    @api.onchange('instance_id')
    def onchange_instance_id(self):
        """
        This will set the company and country based on instance
        """
        if self.instance_id:
            self.company_id = self.instance_id.company_id and self.instance_id.company_id.id
            self.ship_to_country = self.instance_id.country_id and self.instance_id.country_id.id

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        """
        This will set the ship address based on warehouse
        """
        if self.warehouse_id:
            self.ship_from_address_id = self.warehouse_id.partner_id and \
                                        self.warehouse_id.partner_id.id

    def reset_all_lines(self):
        """
        This method will find the duplicate shipment lines and delete that
        """
        self.ensure_one()
        plan_line_obj = self.env['inbound.shipment.plan.line']
        self._cr.execute("""select amazon_product_id from inbound_shipment_plan_line where
                            shipment_plan_id=%s group by amazon_product_id having
                            count(amazon_product_id)>1;""", (self.id,))
        result = self._cr.fetchall()
        for record in result:
            duplicate_lines = self.mapped('shipment_line_ids').filtered(
                lambda r, record=record: r.amazon_product_id.id == record[0])
            qty = 0.0
            quantity_in_case = 0
            for line in duplicate_lines:
                qty += line.quantity
                quantity_in_case = line.quantity_in_case
            duplicate_lines.unlink()
            plan_line_obj.create(
                {'amazon_product_id': record[0], 'quantity': qty, 'shipment_plan_id': self.id,
                 'quantity_in_case': quantity_in_case})
        return True

    def set_to_draft_ept(self):
        """
        Purpose: Used in Reset Inbound shipment Plan into Draft State
        :return:
        """
        self.write({'state': 'draft'})
        self.odoo_shipment_ids.unlink()
        self.reset_all_lines()
        self.message_post(body=_("<b>Reset to Draft Plan</b>"))
        return True

    def _compute_error_logs(self):
        """
        This method will compute total logs crated from the current record.
        :return:
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        log_lines = log_line_obj.amz_find_mismatch_details_log_lines(self.id, INBOUND_SHIPMENT_PLAN_EPT)
        self.log_ids = log_lines.ids if log_lines else False

    def import_product_for_inbound_shipment(self):
        """
        Open wizard to import product through csv file.
        File contains only product sku and quantity.
        :return:
        """
        import_obj = self.env['import.product.inbound.shipment'].create({'shipment_id': self.id})
        ctx = self.env.context.copy()
        ctx.update({'shipment_id': self.id, 'update_existing': False, })
        return import_obj.with_context(ctx).wizard_view()

    @api.model
    def create_procurements(self, odoo_shipments):
        """
        This method will process shipments and create procurements
        param odoo_shipments : list of odoo shipments
        :param odoo_shipments: amazon.inbound.shipment.ept() object
        :return: boolean (TRUE/FALSE)
        """
        proc_group_obj = self.env['procurement.group']
        picking_obj = self.env['stock.picking']
        location_route_obj = self.env['stock.route']
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        group_wh_dict = {}
        for shipment in odoo_shipments:
            proc_group = proc_group_obj.create({'odoo_shipment_id': shipment.id, 'name': shipment.name,
                                                'partner_id': shipment.address_id.id if shipment.address_id else False})
            fulfill_center = shipment.fulfill_center_id
            ship_plan = shipment.shipment_plan_id
            fulfillment_center = self.env['amazon.fulfillment.center'].search(
                [('center_code', '=', fulfill_center),
                 ('seller_id', '=', ship_plan.instance_id.seller_id.id)])
            fulfillment_center = fulfillment_center and fulfillment_center[0]
            warehouse = fulfillment_center and fulfillment_center.warehouse_id or \
                        ship_plan.instance_id.fba_warehouse_id or ship_plan.instance_id.warehouse_id or False

            if not warehouse:
                error_value = 'No any warehouse found related to fulfillment center %s. Please set ' \
                              'fulfillment center %s in warehouse || shipment %s.' % (
                    fulfill_center, fulfill_center, shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=error_value, model_name=AMAZON_INBOUND_SHIPMENT_EPT, module='amazon_ept',
                    operation_type='export', res_id=shipment.id,
                    amz_instance_ept=ship_plan.instance_id and ship_plan.instance_id.id or False,
                    amz_seller_ept=ship_plan.instance_id.seller_id and ship_plan.instance_id.seller_id.id or False)
                continue
            location_routes = location_route_obj.search([('supplied_wh_id', '=', warehouse.id),
                                                         ('supplier_wh_id', '=', ship_plan.warehouse_id.id)])
            if not location_routes:
                error_value = 'Location routes are not found. Please configure routes in warehouse ' \
                              'properly || warehouse %s & shipment %s.' % (warehouse.name, shipment.name)
                log_line_obj.create_common_log_line_ept(
                    message=error_value, model_name=AMAZON_INBOUND_SHIPMENT_EPT, module='amazon_ept',
                    operation_type='export', res_id=shipment.id,
                    amz_instance_ept=ship_plan.instance_id and ship_plan.instance_id.id or False,
                    amz_seller_ept=ship_plan.instance_id.seller_id and ship_plan.instance_id.seller_id.id or False)
                continue
            location_routes = location_routes[0]
            group_wh_dict.update({proc_group: warehouse})
            for line in shipment.odoo_shipment_line_ids:
                qty = line.quantity
                amazon_product = line.amazon_product_id
                datas = {'route_ids': location_routes,
                         'group_id': proc_group,
                         'company_id': ship_plan.instance_id.company_id.id,
                         'warehouse_id': warehouse,
                         'priority': '1'}
                proc_group_obj.run([self.env['procurement.group'].Procurement(
                    amazon_product.product_id, qty, amazon_product.product_id.uom_id,
                    warehouse.lot_stock_id, amazon_product.product_id.name, shipment.name,
                    ship_plan.instance_id.company_id, datas)])
        if group_wh_dict:
            for group, warehouse in group_wh_dict.items():
                picking = picking_obj.search([('group_id', '=', group.id),
                                              ('picking_type_id.warehouse_id', '=', warehouse.id)])
                if picking:
                    picking.write({'is_fba_wh_picking': True})
        for shipment in odoo_shipments:
            pickings = shipment.mapped('picking_ids').filtered(
                lambda pick: not pick.is_fba_wh_picking and pick.state not in ['done', 'cancel'])
            for picking in pickings:
                picking.action_assign()
        return True

    def cancel_entire_inbound_shipment(self, shipment):
        """
        This method will help to cancel the entire inbound shipment
        :param shipment: amazon.inbound.shipment.ept() object
        :return: boolean(TRUE/False)
        """
        log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        ship_plan = shipment.shipment_plan_id
        instance = ship_plan.instance_id
        shipment_status = 'CANCELLED'
        label_prep_type = shipment.label_prep_type
        if label_prep_type == 'NO_LABEL':
            label_prep_type = 'SELLER_LABEL'
        elif label_prep_type == 'AMAZON_LABEL':
            label_prep_type = ship_plan.label_preference

        destination = shipment.fulfill_center_id
        cases_required = shipment.shipment_plan_id.is_are_cases_required

        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')

        kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                  'app_name': 'amazon_ept_spapi',
                  'account_token': account.account_token,
                  'emipro_api': 'update_shipment_in_amazon_sp_api',
                  'dbuuid': dbuuid,
                  'marketplace_id': instance.market_place_id,
                  'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                             instance.country_id.code,
                  'shipment_name': shipment.name,
                  'shipment_id': shipment.shipment_id,
                  'destination': destination,
                  'cases_required': cases_required,
                  'labelpreppreference': label_prep_type,
                  'shipment_status': shipment_status,
                  'inbound_box_content_status': shipment.intended_box_contents_source,
                  }

        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            error_value = response.get('error', {})
            log_line_obj.create_common_log_line_ept(
                message=error_value, model_name=INBOUND_SHIPMENT_PLAN_EPT, module='amazon_ept', operation_type='export',
                res_id=self.id, amz_instance_ept=ship_plan.instance_id and ship_plan.instance_id.id or False,
                amz_seller_ept=ship_plan.instance_id.seller_id and ship_plan.instance_id.seller_id.id or False)
        else:
            shipment.write({'state': 'CANCELLED'})
        return True

    def cancel_inbound_shipemnts(self, odoo_shipments):
        """
        This method used to cancel the inbound shipments
        :param odoo_shipments: amazon.inbound.shipment.ept() object
        :return: boolean (TRUE/FALSE)
        """
        shipments = odoo_shipments.filtered(
            lambda odoo_shipment: odoo_shipment.state != 'CANCELLED')

        for shipment in shipments:
            self.cancel_entire_inbound_shipment(shipment)
        return True

    def display_shipment_details(self, shipments):
        """
        This method is used to display the shipment details
        :param shipments: amazon.inbound.shipment.ept() object
        :return: ir.actions.act_window() action
        """
        view = self.env.ref('amazon_ept.view_inbound_shipment_details_wizard')
        context = dict(self._context)
        context.update({'shipments': shipments, 'plan_id': self.id})
        return {
            'name': _('Shipment Details'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'inbound.shipment.details',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context
        }

    def create_inbound_shipment_plan(self):
        """
        This method is used to request for create inbound shipment plan record
        with prepared sku_qty_dict and ship from address list
        :return:
        """
        shipment_obj = self.env[AMAZON_INBOUND_SHIPMENT_EPT]
        ship_to_country_code = self.ship_to_country.code if self.ship_to_country else False
        lines = self.shipment_line_ids.filtered(lambda r: r.quantity <= 0.0)
        if lines:
            skus = ', '.join(map(str, lines.mapped('seller_sku')))
            raise UserError(_("Qty must be greater then zero Seller Sku : %s" % skus))
        if self.is_are_cases_required:
            zero_qty_in_case_list = self.shipment_line_ids.filtered(lambda r: r.quantity_in_case <= 0)
            if zero_qty_in_case_list:
                raise UserError(_("If you ticked 'Are Cases Required' then 'Quantity In Case' must be greater then zero"
                                  " for this Seller SKU: %s" % (zero_qty_in_case_list.mapped('seller_sku'))))
        sku_qty_dict = []
        for shipment_line in self.shipment_line_ids:
            plan_req_items = {'SellerSKU': shipment_line.seller_sku,
                                  'ASIN': shipment_line.amazon_product_id.product_asin,
                                  'Condition': shipment_line.amazon_product_id.condition,
                                  'Quantity': int(shipment_line.quantity)}
            if self.is_are_cases_required:
                plan_req_items.update({'QuantityInCase': int(shipment_line.quantity_in_case)})
            sku_qty_dict.append(plan_req_items)
        address_dict = shipment_obj.prepare_inbound_shipment_address_dict(self.ship_from_address_id)
        kwargs = shipment_obj.amz_prepare_inbound_shipment_kwargs_vals(self.instance_id)
        kwargs.update({'emipro_api': 'create_inbound_shipment_plan_sp_api',
                           'ship_to_country_code': ship_to_country_code,
                           'labelpreppreference': self.label_preference,
                           'sku_qty_list': sku_qty_dict,
                           'ship_from_address': address_dict})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            log_line_obj = self.env[COMMON_LOG_LINES_EPT]
            error_value = response.get('error', {})
            log_line_obj.create_common_log_line_ept(
                    message=error_value, model_name=INBOUND_SHIPMENT_PLAN_EPT, module='amazon_ept',
                    operation_type='export', res_id=self.id,
                    amz_instance_ept=self.instance_id and self.instance_id.id or False,
                    amz_seller_ept=self.instance_id.seller_id and self.instance_id.seller_id.id or False)
            self.write({'state': 'cancel'})
            return True
        shipments = []
        result = response.get('result', {})
        if not isinstance(result.get('InboundShipmentPlans', []), list):
            shipments.append(result.get('InboundShipmentPlans', {}))
        else:
            shipments = result.get('InboundShipmentPlans', [])
        return self.display_shipment_details(shipments)
