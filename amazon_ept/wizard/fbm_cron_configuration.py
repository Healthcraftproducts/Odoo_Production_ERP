# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class and fields to configure the FBM cron and added fields to active the
FBM operation's cron configurations
"""

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
RES_USERS = "res.users"
IR_MODEL_DATA = 'ir.model.data'
IR_CRON = 'ir.cron'

IMPORT_FBM_ORDER = 'amazon_ept.ir_cron_import_amazon_orders_seller_%d'
UPDATE_ORDER_STATUS = 'amazon_ept.ir_cron_auto_update_order_status_seller_%d'
EXPORT_INVENTORY = 'amazon_ept.ir_cron_auto_export_inventory_seller_%d'
CHECK_CANCEL_ORDER = 'amazon_ept.ir_cron_auto_check_canceled_fbm_order_in_amazon_seller_%d'
IMPORT_FBM_SHIPPED_ORDER = 'amazon_ept.ir_cron_auto_import_amazon_fbm_shipped_orders_to_amazon_seller_%d'

class FbmCronConfiguration(models.TransientModel):
    """
    Added class to configure the FBM operation's cron.
    """
    _name = "fbm.cron.configuration"
    _description = "Amazon FBM Cron Configuration"

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

    amz_seller_id = fields.Many2one(
        'amazon.seller.ept', string='Amazon Seller', default=_get_amazon_seller, readonly=True)
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')], default=_get_amazon_selling, readonly=True)
    # Auto FBM Import order
    amz_order_auto_import = fields.Boolean(string='Auto Import FBM Order Report ?')
    amz_order_import_next_execution = fields.Datetime('Auto Import FBM Order Next Execution',
                                                      help='Import FBM order next execution time')
    amz_order_import_interval_number = fields.Integer('Auto Import FBM Order Interval Number',
                                                      help="FBM Order Repeat Interval Number.")
    amz_order_import_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                      'Auto Import FBM Order Interval Unit')
    amz_order_import_user_id = fields.Many2one(RES_USERS, string="Auto Import FBM Order User")

    # Update FBM order status
    amz_order_auto_update = fields.Boolean("Auto Update FBM Order Status ?")
    amz_order_update_interval_number = fields.Integer('FBM Order Update Interval Number',
                                                      help="Update order repeat interval number")
    amz_order_update_next_execution = fields.Datetime('FBM Order Update Next Execution',
                                                      help='FBM order next execution time')
    amz_order_update_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                      'FBM Order Update Interval Unit')
    amz_order_update_user_id = fields.Many2one(RES_USERS, string="FBM Order Update User")

    # Auto Check cancel order
    amz_auto_check_cancel_order = fields.Boolean(
        string='Auto Check Canceled FBM Order in Amazon ?')
    amz_cancel_order_next_execution = fields.Datetime(
        'Check Canceled FBA Order in Amazon Next Execution', help='Next execution time')
    amz_cancel_order_interval_number = fields.Integer(
        'Check Canceled FBA Order in Amazon Interval Number', help="Cancel order repeat interval number")
    amz_cancel_order_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                      'Check Canceled FBA Order in Amazon Interval Unit')
    amz_cancel_order_report_user_id = fields.Many2one(RES_USERS,
                                                      string="Check Canceled FBA Order in Amazon User")
    # FBM auto export stock
    amz_stock_auto_export = fields.Boolean(string="Auto Export Stock ?")
    amz_inventory_export_next_execution = fields.Datetime('Inventory Export Next Execution',
                                                          help='Export Inventory Next execution time')
    amz_inventory_export_interval_number = fields.Integer('Export stock Interval Number',
                                                          help="Repeat every x.")
    amz_inventory_export_interval_type = fields.Selection([('minutes', 'Minutes'),
                                                           ('hours', 'Hours')],
                                                          'Export Stock Interval Unit')
    amz_inventory_export_user_id = fields.Many2one(RES_USERS, string="Inventory Export User")

    # Auto Import FBM Shipped Orders
    amz_auto_import_shipped_orders = fields.Boolean(string='Auto Import FBM shipped Orders ?')
    auto_import_fbm_shipped_next_execution = fields.Datetime('Auto Import FBM shipped Order Next Execution',
                                                             help='Next execution time')
    auto_import_fbm_shipped_interval_number = fields.Integer('Auto Import FBM Shipped Order Interval Number',
                                                             help="Repeat every x.")
    auto_import_fbm_shipped_interval_type = fields.Selection([('hours', 'Hours'), ('days', 'Days')],
                                                             'Auto Import FBM Shipped Order Interval Unit')
    auto_import_fbm_shipped_user_id = fields.Many2one(RES_USERS, string="Auto Import FBM Shipped Order User")

    @api.onchange("amz_seller_id")
    def onchange_amazon_seller_id(self):
        """
        Based on seller it will update the existing cron values
        """
        amz_seller = self.amz_seller_id
        self.update_amz_order_import_cron_field(amz_seller)
        self.update_amz_update_order_status_cron_field(amz_seller)
        self.update_amz_inventory_export_cron_field(amz_seller)
        self.update_amz_check_cancel_cron_field(amz_seller)
        self.update_amz_import_shipped_order_cron_field(self.amz_seller_id)

    def update_amz_order_import_cron_field(self, amz_seller):
        """
        This method is used to import amazon FBM orders.
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_order_import_cron_exist = self.env.ref(IMPORT_FBM_ORDER % amz_seller.id, raise_if_not_found=False)
            if amz_order_import_cron_exist:
                self.amz_order_auto_import = amz_order_import_cron_exist.active or False
                self.amz_order_import_interval_number = \
                    amz_order_import_cron_exist.interval_number or False
                self.amz_order_import_interval_type = \
                    amz_order_import_cron_exist.interval_type or False
                self.amz_order_import_next_execution = \
                    amz_order_import_cron_exist.nextcall or False
                self.amz_order_import_user_id = amz_order_import_cron_exist.user_id.id or False

    def update_amz_update_order_status_cron_field(self, amz_seller):
        """
        This method is used to auto update order status
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_update_order_status_cron_exist = self.env.ref(UPDATE_ORDER_STATUS % (\
                amz_seller.id), raise_if_not_found=False)
            if amz_update_order_status_cron_exist:
                self.amz_order_auto_update = amz_update_order_status_cron_exist.active or False
                self.amz_order_update_interval_number = \
                    amz_update_order_status_cron_exist.interval_number or False
                self.amz_order_update_interval_type = \
                    amz_update_order_status_cron_exist.interval_type or False
                self.amz_order_update_next_execution = \
                    amz_update_order_status_cron_exist.nextcall or False
                self.amz_order_update_user_id = amz_update_order_status_cron_exist.user_id.id or False

    def update_amz_inventory_export_cron_field(self, amz_seller):
        """
        This method is used to export inventory.
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_update_inventory_export_cron_exist = self.env.ref(EXPORT_INVENTORY % (
                amz_seller.id), raise_if_not_found=False)
            if amz_update_inventory_export_cron_exist:
                self.amz_stock_auto_export = amz_update_inventory_export_cron_exist.active or False
                self.amz_inventory_export_interval_number = \
                    amz_update_inventory_export_cron_exist.interval_number or False
                self.amz_inventory_export_interval_type = \
                    amz_update_inventory_export_cron_exist.interval_type or False
                self.amz_inventory_export_next_execution = \
                    amz_update_inventory_export_cron_exist.nextcall or False
                self.amz_inventory_export_user_id = amz_update_inventory_export_cron_exist.user_id.id or False

    def update_amz_check_cancel_cron_field(self, amz_seller):
        """
        This method is used to check cancel FBM order in amazon.
        :param amz_seller : seller record.
        """
        if amz_seller:
            amz_check_cancel_order_cron_exist = self.env.ref(CHECK_CANCEL_ORDER % (
                amz_seller.id), raise_if_not_found=False)
            if amz_check_cancel_order_cron_exist:
                self.amz_auto_check_cancel_order = amz_check_cancel_order_cron_exist.active or False
                self.amz_cancel_order_interval_number = \
                    amz_check_cancel_order_cron_exist.interval_number or False
                self.amz_cancel_order_interval_type = \
                    amz_check_cancel_order_cron_exist.interval_type or False
                self.amz_cancel_order_next_execution = \
                    amz_check_cancel_order_cron_exist.nextcall or False
                self.amz_cancel_order_report_user_id = \
                    amz_check_cancel_order_cron_exist.user_id.id or False

    def save_cron_configuration(self):
        """
        This method will configure the amazon FBM operations cron
        """
        amazon_seller = self.amz_seller_id
        vals = {}
        self.setup_amz_order_import_cron(amazon_seller)
        self.setup_amz_unshipped_order_update_cron(amazon_seller)
        self.setup_amz_missing_unshipped_order_cron(amazon_seller)
        self.setup_amz_order_update_order_status_cron(amazon_seller)
        self.setup_amz_inventory_export_cron(amazon_seller)
        self.setup_amz_fbm_check_cancel_order_cron(amazon_seller)
        self.import_amz_shipped_orders_seller_wise(amazon_seller)
        vals['order_auto_import'] = self.amz_order_auto_import or False
        vals['amz_order_auto_update'] = self.amz_order_auto_update or False
        vals['auto_check_cancel_order'] = self.amz_auto_check_cancel_order or False
        vals['amz_stock_auto_export'] = self.amz_stock_auto_export or False
        vals['amz_auto_import_shipped_orders'] = self.amz_auto_import_shipped_orders or False
        amazon_seller.write(vals)

    def create_amazon_fbm_scheduler(self, cron_id, model_name):
        """
        Will create seller wise amazon fbm operations scheduler.
        """
        self.env[IR_MODEL_DATA].create({'module': 'amazon_ept', 'name': model_name, 'model': IR_CRON,
                                        'res_id': cron_id, 'noupdate': True})
        return True

    def setup_amz_order_import_cron(self, amazon_seller):
        """
        This method will active the import amazon FBM order cron.
        param amazon_seller : seller record.
        """
        if self.amz_order_auto_import and self.amazon_selling not in ['FBA']:
            cron_exist = self.env.ref(IMPORT_FBM_ORDER % (amazon_seller.id), raise_if_not_found=False)
            vals = {
                'active': True,
                'interval_number': self.amz_order_import_interval_number,
                'interval_type': self.amz_order_import_interval_type,
                'nextcall': self.amz_order_import_next_execution,
                'user_id': self.amz_order_import_user_id.id,
                'code': "model.auto_import_sale_order_ept({'seller_id':%d, 'is_auto_process': True})" % (
                    amazon_seller.id),
                'amazon_seller_cron_id': amazon_seller.id}

            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref('amazon_ept.ir_cron_import_amazon_orders',
                                                 raise_if_not_found=False)
                if not import_order_cron:
                    raise UserError(_(\
                        'Core settings of Amazon import fbm orders are deleted, please upgrade Amazon module to '
                        'back this settings.'))
                name = 'FBM-' + amazon_seller.name + ' : Import Amazon Orders'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                model_name = 'ir_cron_import_amazon_orders_seller_%d' % (amazon_seller.id)
                self.create_amazon_fbm_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(IMPORT_FBM_ORDER % (amazon_seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        self.setup_amz_unshipped_order_update_cron(amazon_seller)
        return True

    def setup_amz_missing_unshipped_order_cron(self, amazon_seller):
        """
        This method will setup the auto import missing unshipped order scheduler
        """
        if self.amz_order_auto_import and self.amazon_selling not in ['FBA']:
            cron_exist = self.env.ref('amazon_ept.ir_cron_import_missing_unshipped_orders_seller_%d' % (\
                amazon_seller.id), raise_if_not_found=False)
            process_next_execution = self.amz_order_import_next_execution + relativedelta(minutes=30)
            vals = {
                'active': True,
                'interval_number': 8,
                'interval_type': 'hours',
                'nextcall': process_next_execution,
                'user_id': self.amz_order_import_user_id.id,
                'code': "model.auto_process_missing_unshipped_sale_order_ept({'seller_id':%d, 'is_auto_process': True})" % (
                    amazon_seller.id),
                'amazon_seller_cron_id': amazon_seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref('amazon_ept.ir_cron_import_missing_unshipped_orders',
                                                 raise_if_not_found=False)
                if not import_order_cron:
                    raise UserError(_('Core settings of Amazon import missing unshipped orders '
                                      'are deleted, please upgrade Amazon module to back this settings.'))
                name = 'FBM-' + amazon_seller.name + ' : Amazon Import Missing Unshipped Orders'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                model_name = 'ir_cron_import_missing_unshipped_orders_seller_%d' % (amazon_seller.id)
                self.create_amazon_fbm_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref('amazon_ept.ir_cron_import_missing_unshipped_orders_seller_%d' %
                                      (amazon_seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_amz_unshipped_order_update_cron(self, amazon_seller):
        """
        This method will active cron to process amazon unshipped orders.
        param amazon_seller : seller record.
        """
        if self.amz_order_auto_import and self.amazon_selling not in ['FBA']:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_process_amazon_unshipped_orders_seller_%d' % (
                    amazon_seller.id),
                raise_if_not_found=False)
            process_next_execution = self.amz_order_import_next_execution + relativedelta(
                minutes=10)
            vals = {
                'active': True,
                'interval_number': self.amz_order_import_interval_number,
                'interval_type': self.amz_order_import_interval_type,
                'nextcall': process_next_execution,
                'user_id': self.amz_order_import_user_id.id,
                'code': "model.auto_process_unshipped_sale_order_ept({'seller_id':%d, "
                        "'is_auto_process': True})" % (\
                    amazon_seller.id),
                'amazon_seller_cron_id': amazon_seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                import_order_cron = self.env.ref(
                    'amazon_ept.ir_cron_process_amazon_unshipped_orders',
                    raise_if_not_found=False)
                if not import_order_cron:
                    raise UserError(_(\
                        'Core settings of Amazon import unshipped orders are deleted, please upgrade Amazon module to '
                        'back this settings.'))

                name = 'FBM-' + amazon_seller.name + ' : Process Amazon Orders'
                vals.update({'name': name})
                new_cron = import_order_cron.copy(default=vals)
                model_name = 'ir_cron_process_amazon_unshipped_orders_seller_%d' % (amazon_seller.id)
                self.create_amazon_fbm_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(
                'amazon_ept.ir_cron_process_amazon_unshipped_orders_seller_%d' % (\
                    amazon_seller.id),
                raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_amz_order_update_order_status_cron(self, seller):
        """
        This method will active cron to auto update order status.
        param amazon_seller : seller record.
        """
        if self.amz_order_auto_update and self.amazon_selling not in ['FBA']:
            cron_exist = self.env.ref(UPDATE_ORDER_STATUS % (seller.id), raise_if_not_found=False)
            vals = {'active': True,
                    'interval_number': self.amz_order_update_interval_number,
                    'interval_type': self.amz_order_update_interval_type,
                    'nextcall': self.amz_order_update_next_execution,
                    'user_id': self.amz_order_update_user_id.id,
                    'code': "model.auto_update_order_status_ept({'seller_id':%d})" % (seller.id),
                    'amazon_seller_cron_id': seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                update_order_cron = self.env.ref('amazon_ept.ir_cron_auto_update_order_status', raise_if_not_found=False)
                if not update_order_cron:
                    raise UserError(_(\
                        'Core settings of Amazon update order status are deleted, please upgrade Amazon module to '
                        'back this settings.'))

                name = 'FBM-' + seller.name + ' : Update Order Status'
                vals.update({'name': name})
                new_cron = update_order_cron.copy(default=vals)
                model_name = 'ir_cron_auto_update_order_status_seller_%d' % (seller.id)
                self.create_amazon_fbm_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(UPDATE_ORDER_STATUS % (seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_amz_inventory_export_cron(self, seller):
        """
        This method will active cron to auto export inventory.
        param amazon_seller : seller record.
        """
        if self.amz_stock_auto_export and self.amazon_selling not in ['FBA']:
            cron_exist = self.env.ref(EXPORT_INVENTORY % (seller.id), raise_if_not_found=False)
            vals = {'active': True,
                    'interval_number': self.amz_inventory_export_interval_number,
                    'interval_type': self.amz_inventory_export_interval_type,
                    'nextcall': self.amz_inventory_export_next_execution,
                    'user_id': self.amz_inventory_export_user_id.id,
                    'code': "model.auto_export_inventory_ept({'seller_id':%d})" % seller.id,
                    'amazon_seller_cron_id': seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                export_stock_cron = self.env.ref('amazon_ept.ir_cron_auto_export_inventory',
                                                 raise_if_not_found=False)
                if not export_stock_cron:
                    raise UserError(_(\
                        'Core settings of Amazon export inventory are deleted, please upgrade Amazon module to '
                        'back this settings.'))

                name = 'FBM-' + seller.name + ' : Auto Export Inventory'
                vals.update({'name': name})
                new_cron = export_stock_cron.copy(default=vals)
                model_name = 'ir_cron_auto_export_inventory_seller_%d' % (seller.id)
                self.create_amazon_fbm_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(EXPORT_INVENTORY % (seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def setup_amz_fbm_check_cancel_order_cron(self, seller):
        """
        This method will active cron to check the FBM canceled FBM orders.
        param amazon_seller : seller record.
        """
        if self.amz_auto_check_cancel_order and self.amazon_selling not in ['FBA']:
            cron_exist = self.env.ref(CHECK_CANCEL_ORDER % (seller.id), raise_if_not_found=False)
            vals = {'active': True,
                    'interval_number': self.amz_cancel_order_interval_number,
                    'interval_type': self.amz_cancel_order_interval_type,
                    'nextcall': self.amz_cancel_order_next_execution,
                    'user_id': self.amz_cancel_order_report_user_id.id,
                    'code': "model.fbm_auto_check_cancel_order_in_amazon({'seller_id':%d})" % (seller.id),
                    'amazon_seller_cron_id': seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                export_stock_cron = self.env.ref('amazon_ept.ir_cron_auto_check_canceled_fbm_order_in_amazon',
                                                 raise_if_not_found=False)
                if not export_stock_cron:
                    raise UserError(_(\
                        'Core settings of Amazon check cancelled orders are deleted, please upgrade '
                        'Amazon module to back this settings.'))

                name = 'FBM-' + seller.name + ' : Check cancel order'
                vals.update({'name': name})
                new_cron = export_stock_cron.copy(default=vals)
                model_name = 'ir_cron_auto_check_canceled_fbm_order_in_amazon_seller_%d' % (seller.id)
                self.create_amazon_fbm_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(CHECK_CANCEL_ORDER % (seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True

    def update_amz_import_shipped_order_cron_field(self, amz_seller):
        """
        This method is used to import amazon FBM Shipped orders.
        :param amz_seller: seller record
        :return:
        """
        if amz_seller:
            amz_import_fbm_shipped_order_cron_exist = self.env.ref(IMPORT_FBM_SHIPPED_ORDER % (
                amz_seller.id), raise_if_not_found=False)
            if amz_import_fbm_shipped_order_cron_exist:
                self.amz_auto_import_shipped_orders = amz_import_fbm_shipped_order_cron_exist.active or False
                self.auto_import_fbm_shipped_interval_number = amz_import_fbm_shipped_order_cron_exist.interval_number or False
                self.auto_import_fbm_shipped_interval_type = amz_import_fbm_shipped_order_cron_exist.interval_type or False
                self.auto_import_fbm_shipped_next_execution = amz_import_fbm_shipped_order_cron_exist.nextcall or False
                self.auto_import_fbm_shipped_user_id = amz_import_fbm_shipped_order_cron_exist.user_id.id or False

    def import_amz_shipped_orders_seller_wise(self, seller):
        """
        Will Seller wise create or update import FBM Shipped Order Cron.
        :param seller: seller record
        :return: True
        """
        if self.amz_auto_import_shipped_orders:
            cron_exist = self.env.ref(IMPORT_FBM_SHIPPED_ORDER % (seller.id), raise_if_not_found=False)
            vals = {'active': True,
                    'interval_number': self.auto_import_fbm_shipped_interval_number,
                    'interval_type': self.auto_import_fbm_shipped_interval_type,
                    'nextcall': self.auto_import_fbm_shipped_next_execution,
                    'user_id': self.auto_import_fbm_shipped_user_id.id,
                    'code': "model.auto_process_shipped_sale_order_ept({'seller_id':%d})" % (seller.id),
                    'amazon_seller_cron_id': seller.id}
            if cron_exist:
                cron_exist.write(vals)
            else:
                cron_exist = self.env.ref('amazon_ept.ir_cron_auto_import_amazon_fbm_shipped_orders',
                                          raise_if_not_found=False)
                if not cron_exist:
                    raise UserError(_('Core settings of Amazon import  fbm shipped orders '
                                      'are deleted, please upgrade Amazon module to back this settings.'))
                name = 'FBM-' + seller.name + ' : Import FBM Shipped Orders'
                vals.update({'name':name})
                new_cron = cron_exist.copy(default=vals)
                model_name = 'ir_cron_auto_import_amazon_fbm_shipped_orders_to_amazon_seller_%d' % (seller.id)
                self.create_amazon_fbm_scheduler(new_cron.id, model_name)
        else:
            cron_exist = self.env.ref(IMPORT_FBM_SHIPPED_ORDER % (seller.id), raise_if_not_found=False)
            if cron_exist:
                cron_exist.write({'active': False})
        return True
