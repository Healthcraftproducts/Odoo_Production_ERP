# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class and fields to configure the FBA cron and added fields to active the
FBA operation's cron configurations
"""

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

RES_USERS = "res.users"
IR_MODEL_DATA = 'ir.model.data'
IR_CRON = 'ir.cron'
IMPORT_PENDING_ORDER = 'amazon_ept.ir_cron_import_amazon_fba_pending_order_seller_%d'
IMPORT_INBOUND_SHIPMENT = 'amazon_ept.ir_cron_inbound_shipment_check_status_%d'
IMPORT_SHIPMENT_REPORT = 'amazon_ept.ir_cron_import_amazon_fba_shipment_report_seller_%d'
REMOVAL_ORDER_REPORT = 'amazon_ept.ir_cron_create_fba_removal_order_report_seller_%d'
CUSTOMER_RETURN_REPORT = 'amazon_ept.ir_cron_auto_import_customer_return_report_seller_%d'
STOCK_ADJUSTMENT_REPORT = 'amazon_ept.ir_cron_create_fba_stock_adjustment_report_seller_%d'


class FbaCronConfiguration(models.TransientModel):
    """
    Added class to configure the FBA operation's cron.
    """
    _name = "fba.cron.configuration"
    _description = "Amazon FBA Cron Configuration"

    def _get_amazon_seller(self):
        """
        will return the amazon seller record
        """
        return self.env.context.get('amz_seller_id', False)

    def _get_amazon_selling(self):
        """
        will return the amazon selling
        """
        return self.env.context.get('amazon_selling', False)

    amz_seller_id = fields.Many2one( \
        'amazon.seller.ept', string='Amazon Seller', default=_get_amazon_seller, readonly=True)
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')],
                                      default=_get_amazon_selling, readonly=True)
    # FBA Import Pending order
    amz_auto_import_fba_pending_order = fields.Boolean(
        string='Auto Request FBA Pending Order ?')
    amz_pending_order_next_execution = fields.Datetime('Import FBA Pending Order Next Execution',
                                                       help='Import Pending Order next execution time')
    amz_pending_order_import_interval_number = fields.Integer(
        'Import FBA Pending Order Interval Number', help="FBA Pending Order Repeat Interval Number.")
    amz_pending_order_import_interval_type = fields.Selection([('hours', 'Hours'),
                                                               ('days', 'Days')],
                                                              'Import FBA Pending Order Interval Unit')
    amz_pending_order_import_user_id = fields.Many2one(RES_USERS,
                                                       string="Import FBA Pending Order User")
    # FBA Shipment Report
    amz_auto_import_shipment_report = fields.Boolean(
        string='Auto Request FBA Shipment Report?')
    amz_ship_report_import_next_execution = fields.Datetime(
        'Import FBA Shipment Report Next Execution', help=' FBA Shipment Report Next Execution')
    amz_ship_report_import_interval_number = fields.Integer(
        'Import FBA Shipment Report Interval Number', help="FBA Shipment Report Interval Number.")
    amz_ship_report_import_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                            'Import FBA Shipment Report Interval Unit')
    amz_ship_report_import_user_id = fields.Many2one(RES_USERS,
                                                     string="Import FBA Shipment Report User")

    # Auto Create Removal Order Report
    auto_create_removal_order_report = fields.Boolean(
        string="Auto Request Removal Order Report ?")
    fba_removal_order_next_execution = fields.Datetime(
        'Auto Create Removal Order Report Next Execution', help='Removal Order Report Next Execution')
    fba_removal_order_interval_number = fields.Integer(
        'Auto Create Removal Order Report Interval Number', help="Removal Order Report Repeat Interval Number.")
    fba_removal_order_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                       'Auto Create Removal Order Report Interval Unit')
    fba_removal_order_user = fields.Many2one(
        RES_USERS, string="Auto Create Removal Order Report User", help="Select the user.")

    # FBA Customer Return Report
    amz_auto_import_return_report = fields.Boolean(
        string='Auto Request FBA Customer Return Report ?')
    amz_return_report_import_next_execution = fields.Datetime(
        'Import FBA Customer Return Report Next Execution', help='Customer Return Report Next Execution Time')
    amz_return_report_import_interval_number = fields.Integer(
        'Import FBA Customer Return Report Interval Number', help="Customer Return Report Repeat Interval Number")
    amz_return_report_import_interval_type = fields.Selection(
        [('hours', 'Hours'), ('days', 'Days')],
        'Import FBA Customer Return Report Interval Unit')
    amz_return_report_import_user_id = fields.Many2one(RES_USERS,
                                                       string="Import FBA Customer Return Report User")
    # Live Stock Report
    amz_stock_auto_import_by_report = fields.Boolean(string='Auto Request FBA Live Stock Report?')
    amz_inventory_import_next_execution = fields.Datetime(
        'Import FBA Live Stock Report Next Execution', help='FBA Live Stock Report Next Execution Time')
    amz_inventory_import_interval_number = fields.Integer(
        'Import FBA Live Stock Report Interval Number', help="FBA Live Stock Report Repeat Interval Number")
    amz_inventory_import_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                          'Import FBA Live Stock Report Interval Unit')
    amz_inventory_import_user_id = fields.Many2one(RES_USERS,
                                                   string="Import FBA Live Stock Report User")

    # Request FBA Stock Adjustment Report
    auto_create_fba_stock_adj_report = fields.Boolean(
        string="Auto Request FBA Stock Adjustment Report ?")
    fba_stock_adj_report_next_execution = fields.Datetime(
        'Auto Create Stock Adjustment Report Next Execution', help='Stock Adjustment Report Next Execution Time')
    fba_stock_adj_report_interval_number = fields.Integer(
        'Auto Create Stock Adjustment Report Interval Number', help="Repeat every x.")
    fba_stock_adj_report_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                          'Auto Create Stock Adjustment Report Interval Unit')
    fba_stock_adj_report_user_id = fields.Many2one(RES_USERS,
                                                   string="Import FBA Live Stock Adjustment User")

    # inbound cron
    amz_auto_import_inbound_shipment_status = fields.Boolean(string='Auto Import FBA Inbound Shipment Item Status?')
    amz_shipment_status_import_next_execution = fields.Datetime( \
        'Auto Import FBA Inbound Shipment Next Execution', help='Next execution time')
    amz_shipment_status_import_interval_number = fields.Integer( \
        'Auto Import FBA Inbound Shipment Interval Number', help="Repeat every x.")
    amz_shipment_status_import_interval_type = fields.Selection([('minutes', 'Minutes'),
                                                                 ('hours', 'Hours'),
                                                                 ('days', 'Days'),
                                                                 ('weeks', 'Weeks'),
                                                                 ('months', 'Months')],
                                                                'Auto Import FBA Inbound Shipment Status Unit')
    amz_shipment_status_import_user_id = fields.Many2one(RES_USERS,
                                                         string="Auto Import FBA Inbound Shipment User")

    @api.onchange("amz_seller_id")
    def onchange_amazon_seller_id(self):
        """
        Based on seller it will update the existing cron values
        """
        amz_seller = self.amz_seller_id
        self.update_amz_pending_order_cron_field(amz_seller)
        self.update_amz_shipment_report_cron_field(amz_seller)
        self.update_amz_removal_order_report_cron_field(amz_seller)
        self.update_amz_return_report_cron_field(amz_seller)
        self.update_amz_fba_live_report_cron_field(amz_seller)
        self.update_amz_fba_stock_auto_import_cron_field(amz_seller)
        self.update_amz_inbound_shipment_status(amz_seller)

    def update_amz_inbound_shipment_status(self, amz_seller):
        """
        This method is used to update the inbound shipment status cron values based on
        configurations.
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_inbound_status_cron = self.env.ref(IMPORT_INBOUND_SHIPMENT % amz_seller.id, raise_if_not_found=False)
            if amz_inbound_status_cron:
                self.amz_auto_import_inbound_shipment_status = amz_inbound_status_cron.active or False
                self.amz_shipment_status_import_next_execution = \
                    amz_inbound_status_cron.nextcall or False
                self.amz_shipment_status_import_interval_number = \
                    amz_inbound_status_cron.interval_number or False
                self.amz_shipment_status_import_interval_type = \
                    amz_inbound_status_cron.interval_type or False
                self.amz_shipment_status_import_user_id = amz_inbound_status_cron.user_id.id or False

    def update_amz_pending_order_cron_field(self, amz_seller):
        """
        This method is used to update amazon pending order cron values based on configurations.
        :param amz_seller : seller record.
        """

        if amz_seller:
            amz_pending_order_cron_exist = self.env.ref(IMPORT_PENDING_ORDER % amz_seller.id, raise_if_not_found=False)
            if amz_pending_order_cron_exist:
                self.amz_auto_import_fba_pending_order = amz_pending_order_cron_exist.active or False
                self.amz_pending_order_import_interval_number = \
                    amz_pending_order_cron_exist.interval_number or False
                self.amz_pending_order_import_interval_type = \
                    amz_pending_order_cron_exist.interval_type or False
                self.amz_pending_order_next_execution = amz_pending_order_cron_exist.nextcall or False
                self.amz_pending_order_import_user_id = amz_pending_order_cron_exist.user_id.id or False

    def update_amz_shipment_report_cron_field(self, amz_seller):
        """
        This method is used to update shipment report cron values based on configurations.
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_check_shipment_report_cron_exist = self.env.ref(IMPORT_SHIPMENT_REPORT % (\
                amz_seller.id), raise_if_not_found=False)
            if amz_check_shipment_report_cron_exist:
                self.amz_auto_import_shipment_report = amz_check_shipment_report_cron_exist.active or False
                self.amz_ship_report_import_interval_number = \
                    amz_check_shipment_report_cron_exist.interval_number or False
                self.amz_ship_report_import_interval_type = \
                    amz_check_shipment_report_cron_exist.interval_type or False
                self.amz_ship_report_import_next_execution = \
                    amz_check_shipment_report_cron_exist.nextcall or False
                self.amz_ship_report_import_user_id = \
                    amz_check_shipment_report_cron_exist.user_id.id or False

    def update_amz_removal_order_report_cron_field(self, amz_seller):
        """
        This method is used to update removal order cron values based on configurations.
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_check_removal_order_cron_exist = self.env.ref(REMOVAL_ORDER_REPORT % (\
                amz_seller.id), raise_if_not_found=False)
            if amz_check_removal_order_cron_exist:
                self.auto_create_removal_order_report = \
                    amz_check_removal_order_cron_exist.active or False
                self.fba_removal_order_interval_number = \
                    amz_check_removal_order_cron_exist.interval_number or False
                self.fba_removal_order_interval_type = \
                    amz_check_removal_order_cron_exist.interval_type or False
                self.fba_removal_order_next_execution = \
                    amz_check_removal_order_cron_exist.nextcall or False
                self.fba_removal_order_user = amz_check_removal_order_cron_exist.user_id.id or False

    def update_amz_return_report_cron_field(self, amz_seller):
        """
        This method is used to update return report cron values based on configurations.
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_check_return_customer_report_cron_exist = self.env.ref(CUSTOMER_RETURN_REPORT % (
                amz_seller.id), raise_if_not_found=False)
            if amz_check_return_customer_report_cron_exist:
                self.amz_auto_import_return_report = amz_check_return_customer_report_cron_exist.active or False
                self.amz_return_report_import_interval_number = \
                    amz_check_return_customer_report_cron_exist.interval_number or False
                self.amz_return_report_import_interval_type = \
                    amz_check_return_customer_report_cron_exist.interval_type or False
                self.amz_return_report_import_next_execution = \
                    amz_check_return_customer_report_cron_exist.nextcall or False
                self.amz_return_report_import_user_id = \
                    amz_check_return_customer_report_cron_exist.user_id.id or False

    def update_amz_fba_live_report_cron_field(self, amz_seller):
        """
        This method is used to update amazon fba live report cron values based on configurations.
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_check_live_stock_report_process_cron_exist = self.env.ref( \
                'amazon_ept.ir_cron_process_fba_live_stock_report_seller_%d' % (amz_seller.id),
                raise_if_not_found=False)
            if amz_check_live_stock_report_process_cron_exist:
                self.amz_stock_auto_import_by_report = \
                    amz_check_live_stock_report_process_cron_exist.active or False
                self.amz_inventory_import_interval_number = \
                    amz_check_live_stock_report_process_cron_exist.interval_number or False
                self.amz_inventory_import_interval_type = \
                    amz_check_live_stock_report_process_cron_exist.interval_type or False
                self.amz_inventory_import_next_execution = \
                    amz_check_live_stock_report_process_cron_exist.nextcall or False
                self.amz_inventory_import_user_id = \
                    amz_check_live_stock_report_process_cron_exist.user_id.id or False

    def update_amz_fba_stock_auto_import_cron_field(self, amz_seller):
        """
        This method is used to update amazon import FBA stock cron values based on configurations.
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_check_stock_report_cron_exist = self.env.ref(STOCK_ADJUSTMENT_REPORT % (
                amz_seller.id), raise_if_not_found=False)
            if amz_check_stock_report_cron_exist:
                self.auto_create_fba_stock_adj_report = \
                    amz_check_stock_report_cron_exist.active or False
                self.fba_stock_adj_report_interval_number = \
                    amz_check_stock_report_cron_exist.interval_number or False
                self.fba_stock_adj_report_interval_type = \
                    amz_check_stock_report_cron_exist.interval_type or False
                self.fba_stock_adj_report_next_execution = \
                    amz_check_stock_report_cron_exist.nextcall or False
                self.fba_stock_adj_report_user_id = \
                    amz_check_stock_report_cron_exist.user_id.id or False

    def save_cron_configuration(self):
        """
        This method will configure the amazon FBA operations cron
        """
        amazon_seller = self.amz_seller_id
        vals = {}
        self.auto_import_fba_pending_order(amazon_seller)
        self.auto_fba_import_shipment_report(amazon_seller)
        self.setup_removal_order_report_create_cron(amazon_seller)
        self.setup_auto_import_customer_return_report(amazon_seller)
        self.setup_amz_seller_live_stock_cron(amazon_seller, self.amz_stock_auto_import_by_report,
                                              self.amz_inventory_import_interval_type,
                                              self.amz_inventory_import_interval_number,
                                              self.amz_inventory_import_next_execution,
                                              self.amz_inventory_import_user_id, 'FBA',
                                              ['ir_cron_import_stock_from_amazon_fba_live_report',
                                               'ir_cron_process_fba_live_stock_report'])
        self.setup_stock_adjustment_report_create_cron(amazon_seller)
        self.setup_inbound_shipment_status_cron(amazon_seller)

        vals['auto_import_fba_pending_order'] = self.amz_auto_import_fba_pending_order or False
        vals['auto_import_shipment_report'] = self.amz_auto_import_shipment_report or False
        vals['auto_create_removal_order_report'] = self.auto_create_removal_order_report or False
        vals['auto_import_return_report'] = self.amz_auto_import_return_report or False
        vals['auto_import_product_stock'] = self.amz_stock_auto_import_by_report or False
        vals['auto_create_fba_stock_adj_report'] = self.auto_create_fba_stock_adj_report or False
        vals['amz_auto_import_inbound_shipment_status'] = self.amz_auto_import_inbound_shipment_status or False
        amazon_seller.write(vals)

    def create_amazon_fba_scheduler(self, cron_id, model_name):
        """
        Will create seller wise amazon fba operations scheduler.
        """
        self.env[IR_MODEL_DATA].create({'module': 'amazon_ept', 'name': model_name, 'model': IR_CRON,
                                        'res_id': cron_id, 'noupdate': True})
        return True

    def auto_import_fba_pending_order(self, amazon_seller):
        """
        This method will active the import FBA pending order cron.
        param amazon_seller : seller record.
        """
        if self.amz_auto_import_fba_pending_order and self.amazon_selling not in ['FBM']:
            cron_exist = self.env.ref(IMPORT_PENDING_ORDER % (amazon_seller.id), raise_if_not_found=False)
            vals = {
                'active': True,
                'interval_number': self.amz_pending_order_import_interval_number,
                'interval_type': self.amz_pending_order_import_interval_type,
                'nextcall': self.amz_pending_order_next_execution,
                'user_id': self.amz_pending_order_import_user_id.id,
                'code': "model.auto_import_fba_pending_sale_order_ept({'seller_id':%d, "
                        "'is_auto_process': True})" % ( \
                            amazon_seller.id), 'amazon_seller_cron_id': amazon_seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref( \
                    'amazon_ept.ir_cron_import_amazon_fba_pending_order',
                    raise_if_not_found=False)
                if not import_order_cron:
                    raise UserError(
                        _('Core settings of Amazon Pending Order are deleted, please upgrade Amazon module to '
                          'back this settings.'))

                name = 'FBA-' + amazon_seller.name + ' : Import Amazon Pending Orders'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                model_name = 'ir_cron_import_amazon_fba_pending_order_seller_%d' % (amazon_seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(IMPORT_PENDING_ORDER % (amazon_seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def auto_fba_import_shipment_report(self, amazon_seller):
        """
        This method will active the import FBA import shipment report cron.
        param amazon_seller : seller record.
        """
        if self.amz_auto_import_shipment_report and self.amazon_selling not in ['FBM']:
            cron_exist = self.env.ref(IMPORT_SHIPMENT_REPORT % (amazon_seller.id), raise_if_not_found=False)
            vals = {
                'active': True,
                'interval_number': self.amz_ship_report_import_interval_number,
                'interval_type': self.amz_ship_report_import_interval_type,
                'nextcall': self.amz_ship_report_import_next_execution,
                'user_id': self.amz_ship_report_import_user_id.id,
                'code': "model.auto_import_shipment_report({'seller_id':%d, "
                        "'is_auto_process': True})" % (amazon_seller.id), 'amazon_seller_cron_id': amazon_seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref(\
                    'amazon_ept.ir_cron_import_amazon_fba_shipment_report', raise_if_not_found=False)
                if not import_order_cron:
                    raise UserError(_( \
                        'Core settings of Amazon import shipment report are deleted, please upgrade Amazon module to '
                        'back this settings.'))
                name = 'FBA-' + amazon_seller.name + ' : Import Amazon FBA Shipment Report'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                model_name = 'ir_cron_import_amazon_fba_shipment_report_seller_%d' % (amazon_seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(IMPORT_SHIPMENT_REPORT % (amazon_seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        self.auto_fba_process_shipment_report(amazon_seller)
        return True

    def auto_fba_process_shipment_report(self, amazon_seller):
        """
        This method will active the cron to process FBA shipment report.
        param amazon_seller : seller record.
        """
        if self.amz_auto_import_shipment_report and self.amazon_selling not in ['FBM']:
            cron_exist = self.env.ref( \
                'amazon_ept.ir_cron_process_amazon_fba_shipment_report_seller_%d' % ( \
                    amazon_seller.id),
                raise_if_not_found=False)
            process_next_execution = self.amz_ship_report_import_next_execution + relativedelta(
                minutes=10)
            vals = {
                'active': True,
                'interval_number': self.amz_ship_report_import_interval_number,
                'interval_type': self.amz_ship_report_import_interval_type,
                'nextcall': process_next_execution,
                'user_id': self.amz_ship_report_import_user_id.id,
                'code': "model.auto_process_shipment_report({'seller_id':%d, "
                        "'is_auto_process': True})" % ( \
                            amazon_seller.id),
                'amazon_seller_cron_id': amazon_seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref( \
                    'amazon_ept.ir_cron_process_amazon_fba_shipment_report',
                    raise_if_not_found=False)
                if not import_order_cron:
                    raise UserError(_( \
                        'Core settings of Amazon process shipment report are deleted, please upgrade Amazon module to '
                        'back this settings.'))

                name = 'FBA-' + amazon_seller.name + ' : Process Amazon FBA Shipment Report'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                model_name = 'ir_cron_process_amazon_fba_shipment_report_seller_%d' % (amazon_seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_process_amazon_fba_shipment_report_seller_%d' % (
                    amazon_seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_removal_order_report_create_cron(self, seller):
        """
        This method will active the cron to import removal order report.
        param amazon_seller : seller record.
        """
        if self.auto_create_removal_order_report and self.amazon_selling not in ['FBM']:
            cron_exist = self.env.ref(REMOVAL_ORDER_REPORT % (seller.id), raise_if_not_found=False)
            vals = {
                'active': True,
                'interval_number': self.fba_removal_order_interval_number,
                'interval_type': self.fba_removal_order_interval_type,
                'nextcall': self.fba_removal_order_next_execution,
                'code': "model.auto_import_removal_order_report({'seller_id':%d})" % (seller.id),
                'user_id': self.fba_removal_order_user and self.fba_removal_order_user.id,
                'amazon_seller_cron_id': seller.id
            }

            if cron_exist:
                cron_exist.write(vals)
            else:
                inv_report_cron = self.env.ref( \
                    'amazon_ept.ir_cron_create_fba_removal_order_report', raise_if_not_found=False)
                if not inv_report_cron:
                    raise UserError(
                        _('Core settings of Amazon import removal order are deleted, please upgrade Amazon module to '
                          'back this settings.'))

                name = 'FBA-' + seller.name + ' : Create Amazon Removal Order Report'
                vals.update({'name': name})
                new_cron = inv_report_cron.copy(default=vals)
                model_name = 'ir_cron_create_fba_removal_order_report_seller_%d' % (seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(REMOVAL_ORDER_REPORT % (seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        self.setup_removal_order_report_process_cron(seller)
        return True

    def setup_removal_order_report_process_cron(self, seller):
        """
        This method will active the cron to process removal order report.
        param amazon_seller : seller record.
        """
        if self.auto_create_removal_order_report and self.amazon_selling not in ['FBM']:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_process_fba_removal_order_report_seller_%d' % (seller.id), raise_if_not_found=False)
            process_next_execution = self.fba_removal_order_next_execution + relativedelta(minutes=10)
            vals = {
                'active': True,
                'interval_number': self.fba_removal_order_interval_number,
                'interval_type': self.fba_removal_order_interval_type,
                'nextcall': process_next_execution,
                'code': "model.auto_process_removal_order_report({'seller_id':%d})" % seller.id,
                'user_id': self.fba_removal_order_user and self.fba_removal_order_user.id,
                'amazon_seller_cron_id': seller.id
            }
            if cron_exist:
                cron_exist.write(vals)
            else:
                inv_report_cron = self.env.ref( \
                    'amazon_ept.ir_cron_process_fba_removal_order_report', raise_if_not_found=False)
                if not inv_report_cron:
                    raise UserError(
                        _('Core settings of Amazon process removal order are deleted, please upgrade Amazon module to '
                          'back this settings.'))
                name = 'FBA-' + seller.name + ' : Process Removal Order Report'
                vals.update({'name': name})
                new_cron = inv_report_cron.copy(default=vals)
                model_name = 'ir_cron_process_fba_removal_order_report_seller_%d' % (seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref('amazon_ept.ir_cron_process_fba_removal_order_report_seller_%d' % (seller.id),
                                      raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_auto_import_customer_return_report(self, amazon_seller):
        """
        This method will active the cron to import removal order report.
        param amazon_seller : seller record.
        """
        if self.amz_auto_import_return_report and self.amazon_selling not in ['FBM']:
            cron_exist = self.env.ref(CUSTOMER_RETURN_REPORT % (amazon_seller.id), raise_if_not_found=False)
            vals = {
                'active': True,
                'interval_number': self.amz_return_report_import_interval_number,
                'interval_type': self.amz_return_report_import_interval_type,
                'nextcall': self.amz_return_report_import_next_execution,
                'user_id': self.amz_return_report_import_user_id.id,
                'code': "model.auto_import_return_report({'seller_id':%d, 'is_auto_process': True})" % (
                    amazon_seller.id),
                'amazon_seller_cron_id': amazon_seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref( \
                    'amazon_ept.ir_cron_auto_import_customer_return_report', raise_if_not_found=False)
                if not import_order_cron:
                    raise UserError(_( \
                        'Core settings of Amazon import customer return report are deleted, please upgrade Amazon '
                        'module to back this settings.'))

                name = 'FBA-' + amazon_seller.name + ' : Import Amazon FBA Customer Return Report'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                model_name = 'ir_cron_auto_import_customer_return_report_seller_%d' % (amazon_seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(CUSTOMER_RETURN_REPORT % (amazon_seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        self.setup_auto_process_customer_return_report(amazon_seller)
        return True

    def setup_auto_process_customer_return_report(self, amazon_seller):
        """
        This method will active the cron to process customer return report.
        param amazon_seller : seller record.
        """
        if self.amz_auto_import_return_report and self.amazon_selling not in ['FBM']:
            cron_exist = self.env.ref( \
                'amazon_ept.ir_cron_auto_process_customer_return_report_seller_%d' % ( \
                    amazon_seller.id),
                raise_if_not_found=False)
            process_next_execution = self.amz_return_report_import_next_execution + relativedelta(
                minutes=10)
            vals = {
                'active': True,
                'interval_number': self.amz_return_report_import_interval_number,
                'interval_type': self.amz_return_report_import_interval_type,
                'nextcall': process_next_execution,
                'user_id': self.amz_return_report_import_user_id.id,
                'code': "model.auto_process_return_order_report({'seller_id':%d, "
                        "'is_auto_process': True})" % ( \
                            amazon_seller.id),
                'amazon_seller_cron_id': amazon_seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref(
                    'amazon_ept.ir_cron_auto_process_customer_return_report',
                    raise_if_not_found=False)
                if not import_order_cron:
                    raise UserError(_( \
                        'Core settings of Amazon processs return report are deleted, please upgrade Amazon module to '
                        'back this settings.'))

                name = 'FBA-' + amazon_seller.name + ' : Process Amazon FBA Customer Return Report'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                model_name = 'ir_cron_auto_process_customer_return_report_seller_%d' % (amazon_seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_process_customer_return_report_seller_%d' % (amazon_seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_amz_seller_live_stock_cron(self, amazon_seller, auto_import, interval_type, interval_number,
                                         next_call, cron_user, prefix, cron_xml_ids, module='amazon_ept'):
        """
        This method will active cron to process FBA live stock report.
        param amazon_seller : seller record.
        Updated by twinkalc on 7th jan 2021
        Changes done to set cron for UK.
        """
        for cron_xml_id in cron_xml_ids:
            if auto_import and self.amazon_selling not in ['FBM']:
                non_european_country = ['CA', 'BR', 'MX', 'US', 'SG', 'AU', 'JP', 'AE', 'EG', 'IN', 'SA', 'TR', 'ZA']
                cron_import_xml_id = 'ir_cron_import_stock_from_amazon_fba_live_report'
                if cron_xml_id == cron_import_xml_id and (
                        (amazon_seller.country_id.code in non_european_country and not amazon_seller.amz_fba_us_program) or
                        (amazon_seller.amazon_program and amazon_seller.amazon_program in ['mci', 'mci+efn'])):
                    delay_cron_time = 0
                    for instnace in amazon_seller.instance_ids:
                        cron_exist = self.env.ref(
                            module + '.' + cron_xml_id + '_seller_%d_instance_%d' % (amazon_seller.id, instnace.id),
                            raise_if_not_found=False)

                        vals = {
                            'active': True,
                            'interval_number': interval_number,
                            'interval_type': interval_type,
                            'nextcall': next_call + relativedelta(minutes=delay_cron_time),
                            'code': "model.auto_import_amazon_fba_live_stock_report({'seller_id':%d, 'instance_id': %d})"
                                    % (amazon_seller.id, instnace.id),
                            'user_id': cron_user and cron_user.id,
                            'amazon_seller_cron_id': amazon_seller.id}

                        if cron_exist:
                            cron_exist.write(vals)
                        else:
                            import_return_cron = self.env.ref(module + '.' + cron_xml_id,
                                                              raise_if_not_found=False)
                            if not import_return_cron:
                                raise UserError(_( \
                                    'Core settings of Amazon import FBA live stock are deleted, please upgrade Amazon '
                                    'module to back this settings.'))
                            cron_name = import_return_cron.name.replace( \
                                '(Do Not Delete)', '')
                            name = prefix + '-' + amazon_seller.name + ' : ' + cron_name + ' : ' + str(
                                instnace.name) if prefix else amazon_seller.name + ' : ' + cron_name + ' : ' + str(instnace.name)
                            vals.update({'name': name})
                            new_cron = import_return_cron.copy(default=vals)
                            model_name = cron_xml_id + '_seller_%d_instance_%d' % (amazon_seller.id, instnace.id)
                            self.create_amazon_fba_scheduler(new_cron.id, model_name)
                        delay_cron_time += 20
                else:
                    cron_exist = self.env.ref(
                        module + '.' + cron_xml_id + '_seller_%d' % amazon_seller.id,
                        raise_if_not_found=False)
                    if cron_xml_id == 'ir_cron_process_fba_live_stock_report':
                        next_call = next_call + relativedelta(minutes=20)
                    vals = {
                        'active': True,
                        'interval_number': interval_number,
                        'interval_type': interval_type,
                        'nextcall': next_call,
                        'code': "model.({'seller_id':%d})" % amazon_seller.id,
                        'user_id': cron_user and cron_user.id,
                        'amazon_seller_cron_id': amazon_seller.id
                    }
                    if cron_xml_id == 'ir_cron_import_stock_from_amazon_fba_live_report':
                        vals.update({
                            'code': "model.auto_import_amazon_fba_live_stock_report({'seller_id':%d})" % (
                                amazon_seller.id)})
                    if cron_xml_id == 'ir_cron_process_fba_live_stock_report':
                        vals.update({
                            'code': "model.auto_process_amazon_fba_live_stock_report({'seller_id':%d})" % (
                                amazon_seller.id)})
                    if cron_exist:
                        cron_exist.write(vals)
                    else:
                        import_return_cron = self.env.ref(module + '.' + cron_xml_id, raise_if_not_found=False)
                        if not import_return_cron:
                            raise UserError(_( \
                                'Core settings of Amazon are deleted, please upgrade Amazon module to '
                                'back this settings.'))
                        cron_name = import_return_cron.name.replace('(Do Not Delete)', '')
                        name = prefix + '-' + amazon_seller.name + ' : ' + cron_name if prefix else amazon_seller.name + ' : ' + cron_name
                        vals.update({'name': name})
                        new_cron = import_return_cron.copy(default=vals)
                        model_name = cron_xml_id + '_seller_%d' % (amazon_seller.id)
                        self.create_amazon_fba_scheduler(new_cron.id, model_name)
                    if cron_xml_id != 'ir_cron_process_fba_live_stock_report' and amazon_seller.amazon_program and \
                            amazon_seller.amazon_program in ('pan_eu'):
                        self.setup_amz_uk_instance_live_stock_cron(amazon_seller, interval_type, interval_number,
                                                                   next_call, cron_user, prefix)
                    if cron_xml_id != 'ir_cron_process_fba_live_stock_report' and \
                            amazon_seller.amazon_program in ['MCI', 'MCI+EFN']:
                        self.setup_amz_uk_instance_live_stock_cron(amazon_seller, interval_type, interval_number,
                                                                   next_call, cron_user, prefix)
            else:
                cron_exist = self.env.ref(module + '.' + cron_xml_id + '_seller_%d' % (
                    amazon_seller.id), raise_if_not_found=False)
                if cron_exist:
                    cron_exist.write({'active': False})
                else:
                    for instnace in amazon_seller.instance_ids:
                        cron_exist = self.env.ref(
                            module + '.' + cron_xml_id + '_seller_%d_instance_%d' % (
                                amazon_seller.id, instnace.id), raise_if_not_found=False)
                        if cron_exist:
                            cron_exist.write({'active': False})

                uk_cron_exist = self.env.ref(
                    module + '.' + 'ir_cron_import_stock_from_amazon_uk_fba_live_report_uk_seller_%d' % (
                        amazon_seller.id), raise_if_not_found=False)
                if uk_cron_exist:
                    uk_cron_exist.write({'active': False})
        return True

    def setup_amz_uk_instance_live_stock_cron(self, amazon_seller, interval_type, interval_number,
                                              next_call, cron_user, prefix, module='amazon_ept'):
        """
        Author : Twinkalc
        Updated on : 7 jan 2021
        Added method to auto process live inventory report for UK.
        """
        ir_cron_obj = self.env[IR_CRON]
        model_id = self.env['ir.model']._get('amazon.fba.live.stock.report.ept').id
        uk_insatance_id = self.env['amazon.instance.ept'].search([('seller_id', '=', amazon_seller.id),
                                                                  ('market_place_id', '=', 'A1F83G8C2ARO7P')])
        if uk_insatance_id:
            cron_xml_id = 'ir_cron_import_stock_from_amazon_uk_fba_live_report'
            cron_exist = self.env.ref(module + '.' + cron_xml_id + '_uk_seller_%d' % (amazon_seller.id),
                                      raise_if_not_found=False)
            next_call = next_call + relativedelta(minutes=10)
            vals = {
                'active': True,
                'interval_number': interval_number,
                'interval_type': interval_type,
                'nextcall': next_call,
                'code': "model.({'seller_id':%d})" % (amazon_seller.id),
                'user_id': cron_user and cron_user.id,
                'model_id': model_id,
                'amazon_seller_cron_id': amazon_seller.id
            }
            vals.update({
                'code': "model.auto_import_amazon_fba_live_stock_report({'seller_id':%d, 'uk_instance_id': %d})" % (
                    amazon_seller.id, uk_insatance_id)})

            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_name = 'Import Amazon FBA Live Stock Report'
                name = prefix + '-' + amazon_seller.name + ' UK ' + ' : ' + cron_name if prefix else amazon_seller.name + ' : ' + cron_name
                vals.update({'name': name})
                new_cron = ir_cron_obj.create(vals)
                model_name = cron_xml_id + '_uk_seller_%d' % (amazon_seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        return True

    def setup_inbound_shipment_status_cron(self, seller):
        """
        This method will active the cron to import FBA shipment status.
        param amazon_seller : seller record.
        """
        if self.amz_auto_import_inbound_shipment_status:
            cron_exist = self.env.ref(IMPORT_INBOUND_SHIPMENT % (seller.id), raise_if_not_found=False)
            vals = {
                'active': True,
                'interval_number': self.amz_shipment_status_import_interval_number,
                'interval_type': self.amz_shipment_status_import_interval_type,
                'nextcall': self.amz_shipment_status_import_next_execution,
                'code': "model.auto_import_fba_shipment_status_ept({'seller_id':%d})" % (seller.id),
                'amazon_seller_cron_id': seller.id, }

            if cron_exist:
                cron_exist.write(vals)
                self.amz_setup_all_inbound_shipment_check_status_cron(seller, vals)
            else:
                inbound_cron = self.env.ref(
                    'amazon_ept.ir_cron_inbound_shipment_check_status', raise_if_not_found=False)
                if not inbound_cron:
                    raise UserError(_(
                        'Core settings of Amazon import shipment status are deleted, please upgrade '
                        'Amazon module to back this settings.'))
                name = 'FBA-' + seller.name + ' : Amazon inbound shipment check status'
                vals.update({'name': name})
                new_cron = inbound_cron.copy(default=vals)
                model_name = 'ir_cron_inbound_shipment_check_status_%d' % (seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
                self.amz_setup_all_inbound_shipment_check_status_cron(seller, vals)
        else:
            cron_exist = self.env.ref(IMPORT_INBOUND_SHIPMENT % (seller.id), raise_if_not_found=False)
            all_check_status_cron_exist = self.env.ref(
                'amazon_ept.ir_cron_auto_check_status_all_inbound_shipment_%d' % (seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
            if all_check_status_cron_exist:
                all_check_status_cron_exist.write({'active': False})
        return True

    def amz_setup_all_inbound_shipment_check_status_cron(self, seller, cron_values):
        """
        Define this method for active a scheduler for check all inbound shipment status.
        :param: seller: amazon.seller.ept()
        :param: cron_values: dict {}
        :return: True
        """
        cron_values.update({
            'code': "model.auto_all_inbound_shipment_check_status_ept({'seller_id':%d})" % (seller.id)})
        cron_exist = self.env.ref(
            'amazon_ept.ir_cron_auto_check_status_all_inbound_shipment_%d' % (seller.id), raise_if_not_found=False)
        if cron_exist:
            cron_exist.write(cron_values)
        else:
            auto_inbound_cron = self.env.ref(
                'amazon_ept.ir_cron_auto_all_inbound_shipment_check_status', raise_if_not_found=False)
            if not auto_inbound_cron:
                raise UserError(_(
                    'Core settings of Amazon import all shipment status are deleted, please upgrade '
                    'Amazon module to back this settings.'))
            name = 'FBA-' + seller.name + ' : Amazon all inbound shipment check status'
            cron_values.update({'name': name})
            new_cron = auto_inbound_cron.copy(default=cron_values)
            model_name = 'ir_cron_auto_check_status_all_inbound_shipment_%d' % (seller.id)
            self.create_amazon_fba_scheduler(new_cron.id, model_name)
        return True

    def setup_stock_adjustment_report_create_cron(self, seller):
        """
        This method will active the cron to import stock adjustment report.
        param amazon_seller : seller record.
        """
        if self.auto_create_fba_stock_adj_report:
            cron_exist = self.env.ref(STOCK_ADJUSTMENT_REPORT % (seller.id), raise_if_not_found=False)
            vals = {
                'active': True,
                'interval_number': self.fba_stock_adj_report_interval_number,
                'interval_type': self.fba_stock_adj_report_interval_type,
                'nextcall': self.fba_stock_adj_report_next_execution,
                'code': "model.auto_import_stock_adjustment_report({'seller_id':%d})" % (seller.id),
                'amazon_seller_cron_id': seller.id,
                'user_id': self.fba_stock_adj_report_user_id and self.fba_stock_adj_report_user_id.id,
            }
            if cron_exist:
                cron_exist.write(vals)
            else:
                inv_report_cron = self.env.ref('amazon_ept.ir_cron_create_fba_stock_adjustment_report', raise_if_not_found=False)
                if not inv_report_cron:
                    raise UserError(_(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.'))
                name = 'FBA-' + seller.name + ' : Create Amazon Stock Adjustment Report'
                vals.update({'name': name})
                new_cron = inv_report_cron.copy(default=vals)
                model_name = 'ir_cron_create_fba_stock_adjustment_report_seller_%d' % (seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(STOCK_ADJUSTMENT_REPORT % (seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        self.setup_stock_adjustment_report_process_cron(seller)
        return True

    def setup_stock_adjustment_report_process_cron(self, seller):
        """
        This method will active the cron to process stock adjustment report.
        param amazon_seller : seller record.
        """
        if self.auto_create_fba_stock_adj_report:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_process_fba_stock_adjustment_report_seller_%d' % (
                    seller.id), raise_if_not_found=False)
            process_next_execution = self.fba_stock_adj_report_next_execution + relativedelta(minutes=10)
            vals = {
                'active': True,
                'interval_number': self.fba_stock_adj_report_interval_number,
                'interval_type': self.fba_stock_adj_report_interval_type,
                'nextcall': process_next_execution,
                'code': "model.auto_process_stock_adjustment_report({'seller_id':%d})" % (seller.id),
                'amazon_seller_cron_id': seller.id,
                'user_id': self.fba_stock_adj_report_user_id and self.fba_stock_adj_report_user_id.id,
            }
            if cron_exist:
                cron_exist.write(vals)
            else:
                inv_report_cron = self.env.ref('amazon_ept.ir_cron_process_fba_stock_adjustment_report',
                                               raise_if_not_found=False)
                if not inv_report_cron:
                    raise UserError(_(
                        'Core settings of Amazon are deleted, please upgrade Amazon module to back this settings.'))

                name = 'FBA-' + seller.name + ' : Process Stock Adjustment Report'
                vals.update({'name': name})
                new_cron = inv_report_cron.copy(default=vals)
                model_name = 'ir_cron_process_fba_stock_adjustment_report_seller_%d' % (seller.id)
                self.create_amazon_fba_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref('amazon_ept.ir_cron_process_fba_stock_adjustment_report_seller_%d' % (\
                seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True
