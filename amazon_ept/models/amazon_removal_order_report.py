# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class, methods and fields to import and process amazon removal order report.
"""
import base64
import csv
import time
from io import StringIO
from datetime import datetime, timedelta
from odoo.exceptions import UserError
from odoo import models, fields, api, _
from odoo.tools import float_round, float_compare
from .. reportTypes import ReportType

AMZ_SELLER_EPT = 'amazon.seller.ept'
DATE_YMDHMS = "%Y-%m-%d %H:%M:%S"
IR_MODEL = 'ir.model'
AMZ_REMOVAL_ORDER_REPORT_HISTORY = 'amazon.removal.order.report.history'
AMZ_REMOVAL_ORDER_EPT = 'amazon.removal.order.ept'


class AmazonRemovalOrderReportHistory(models.Model):
    """
    Added class to import and process removal order report.
    """
    _name = "amazon.removal.order.report.history"
    _description = "Removal Order Report"
    _inherit = ['mail.thread', 'amazon.reports']
    _order = 'id desc'

    def _compute_removal_pickings(self):
        """
        This method will count the number of removal pickings.
        """
        for record in self:
            record.removal_count = len(record.removal_picking_ids.ids)

    def list_of_removal_pickings(self):
        """
        This method will return the action of removal order pickings.
        """
        action = {
            'domain': "[('id', 'in', " + str(self.removal_picking_ids.ids) + " )]",
            'name': 'Removal Order Pickings',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
        }
        return action

    @api.depends('seller_id')
    def _compute_removal_company(self):
        """
        This will set the company in removal order report.
        """
        for record in self:
            company_id = record.seller_id.company_id.id if record.seller_id else False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    name = fields.Char(size=256, help="This Field relocates removal order report name.")
    state = fields.Selection([('draft', 'Draft'), ('SUBMITTED', 'SUBMITTED'),
                              ('_SUBMITTED_', 'SUBMITTED'), ('IN_QUEUE', 'IN_QUEUE'),
                              ('IN_PROGRESS', 'IN_PROGRESS'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
                              ('DONE', 'DONE'), ('_DONE_', 'DONE'), ('_DONE_NO_DATA_', 'DONE_NO_DATA'),
                              ('FATAL', 'FATAL'), ('partially_processed', 'Partially Processed'),
                              ('processed', 'PROCESSED'), ('CANCELLED', 'CANCELLED'),
                              ('_CANCELLED_', 'CANCELLED')], string='Report Status', default='draft',
                             help="This Field relocates state of removal order report process.")
    seller_id = fields.Many2one(AMZ_SELLER_EPT, string='Seller', copy=False,
                                help="Select Seller id from you wanted to get Shipping report")
    attachment_id = fields.Many2one('ir.attachment', string="Attachment",
                                    help="This Field relocates attachment id.")
    instance_id = fields.Many2one("amazon.instance.ept", string="Marketplace",
                                  help="This Field relocates instance")
    removal_picking_ids = fields.One2many("stock.picking", 'removal_order_report_id',
                                          string="Pickings",
                                          help="This Field relocates removal picking ids.")
    removal_count = fields.Integer(compute="_compute_removal_pickings",
                                   help="This Field relocates removal count.")
    report_id = fields.Char(size=256, string='Report ID', help="This Field relocates report id.")
    report_type = fields.Char(size=256, help='This Field relocates report type.')
    report_request_id = fields.Char(string='Report Request ID', readonly='1',
                                    help="This Field relocates report request id of amazon.")
    report_document_id = fields.Char(string='Report Document ID',
                                     help="Report Document id to recognise unique request document reference")
    start_date = fields.Datetime(help="Report Start Date")
    end_date = fields.Datetime(help="Report End Date")
    requested_date = fields.Datetime(default=time.strftime(DATE_YMDHMS),
                                     help="Report Requested Date")
    user_id = fields.Many2one('res.users', string="Requested User",
                              help="Track which odoo user has requested report")
    company_id = fields.Many2one('res.company', string="Company", copy=False,
                                 compute="_compute_removal_company",
                                 store=True, help="This Field relocates company")
    log_count = fields.Integer(compute="_compute_logs_record")
    mismatch_details = fields.Boolean(compute="_compute_logs_record")

    def unlink(self):
        """
        This Method if report is processed then raise UserError.
        """
        for report in self:
            if report.state == 'processed':
                raise UserError(_('You cannot delete processed report.'))
        return super(AmazonRemovalOrderReportHistory, self).unlink()

    def list_of_logs(self):
        """
        This method will return the removal order mismatch logs.
        """
        model_id = self.env[IR_MODEL]._get(AMZ_REMOVAL_ORDER_REPORT_HISTORY).id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + " ), ('model_id', '=', " + str(model_id) + ")]",
            'name': 'Removal Orders Logs',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'common.log.lines.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    def _compute_logs_record(self):
        """
        This method will count the number log removal order report logs.
        """
        log_line_obj = self.env['common.log.lines.ept']
        model_id = self.env[IR_MODEL]._get(AMZ_REMOVAL_ORDER_REPORT_HISTORY).id
        log_ids = log_line_obj.search([('res_id', '=', self.id), ('model_id', '=', model_id)]).ids
        self.log_count = log_ids.__len__()

        # Set the boolean field mismatch_details as True if found any mismatch details in log lines
        if log_line_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id),
                                      ('mismatch_details', '=', True)]):
            self.mismatch_details = True
        else:
            self.mismatch_details = False

    @api.constrains('start_date', 'end_date')
    def _check_duration(self):
        """
        This Method check date duration,
        :return: This Method return Boolean(True/False)
        """
        if self.start_date and self.end_date < self.start_date:
            raise UserError(_('Error!\nThe start date must be precede its end date.'))
        return True

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        """
        This Method relocates check seller and write start date and end date.
        :return: This Method return updated value.
        """
        if self.seller_id:
            self.start_date = datetime.now() - timedelta(self.seller_id.removal_order_report_days)
            self.end_date = datetime.now()

    @api.model
    def default_get(self, field):
        """
        This Method relocates default get and set type.
        """
        res = super(AmazonRemovalOrderReportHistory, self).default_get(field)
        if not field:
            return res
        res.update({'report_type': ReportType.GET_FBA_FULFILLMENT_REMOVAL_ORDER_DETAIL_DATA})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """
        The below method sets name of a particular record as per the sequence.
        :param: vals_list: list of values []
        :return: amazon.removal.order.report.history() object
        """
        for vals in vals_list:
            sequence = self.env.ref('amazon_ept.seq_removal_order_report_job', raise_if_not_found=False)
            report_name = sequence.next_by_id() if sequence else '/'
            vals.update({'name': report_name})
        return super(AmazonRemovalOrderReportHistory, self).create(vals_list)

    def create_amazon_report_attachment(self, result):
        """
        Get Removal Orders Report as an attachment in Removal Orders Reports form view.
        """
        seller = self.seller_id
        result = result.get('document', '')
        result = result.encode()
        result = base64.b64encode(result)
        file_name = "Removal_Order_Report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': result,
            'res_model': 'mail.compose.message',
            'type': 'binary'
        })
        self.message_post(body=_("<b>Removal Order Report Downloaded</b>"),
                          attachment_ids=attachment.ids)
        self.write({'attachment_id': attachment.id})
        seller.write({'removal_order_report_last_sync_on': datetime.now()})

    def check_removal_order_configuration(self):
        """
        Define method for check removal order configuration.
        :return:
        """
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_process_fba_removal_order_report_seller_', self.seller_id.id)
        if not self.attachment_id:
            raise UserError(_("There is no any report are attached with this record."))
        if not self.seller_id:
            raise UserError(_("Seller is not defined for processing report"))

    def process_removal_order_report(self):
        """
        This Method relocates process removal order report.
         - read csv file and process removal order report.
         - create order if order not found in odoo then create.
         - Check amazon removal order exist order in not in ERP.
         - If disposal line dict or return line dict found then process removal lines.
         - System processed the Pending Order from Removal Order Report file.
        :return: boolean.
        """
        log_line_obj = self.env['common.log.lines.ept']
        model_id = self.env[IR_MODEL]._get(AMZ_REMOVAL_ORDER_REPORT_HISTORY).id
        self.ensure_one()
        self.check_removal_order_configuration()
        if not self.seller_id.instance_ids.filtered(lambda l: l.is_allow_to_create_removal_order):
            if not self._context.get('is_auto_process', False):
                raise UserError(_('Please Enable Removal order configuration'))
            else:
                log_line_obj.create_common_log_line_ept(
                    message='Please Enable Removal order configuration', model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY,
                    module='amazon_ept', operation_type='import', res_id=self.id, mismatch_details=True,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False,
                    amz_instance_ept=self.instance_id and self.instance_id.id or False)
                return False
        if log_line_obj.amz_find_mismatch_details_log_lines(self.id, AMZ_REMOVAL_ORDER_REPORT_HISTORY):
            log_line_obj.amz_find_mismatch_details_log_lines(self.id, AMZ_REMOVAL_ORDER_REPORT_HISTORY).unlink()
        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        disposal_line_dict, return_line_dict, order_dict, liquidations_line_dict = {}, {}, {}, {}
        for row in reader:
            if not row.get('order-type', '') or row.get('order-type', '') == 'order-type':
                continue
            if row.get('order-status', '') not in ['Completed', 'Cancelled', 'Pending']:
                continue
            order_id = row.get('order-id', '')
            existing_order, skip_line = self.check_amazon_order_exist_order_not(row)
            if existing_order and existing_order.state == row.get('order-status', ''):
                continue
            if not existing_order and row.get('order-status', '') in ['Completed', 'Pending']:
                order_dict.get(order_id).append(
                    row) if order_id in order_dict else order_dict.update({order_id: [row]})
            if not skip_line and existing_order:
                disposal_line_dict, return_line_dict, liquidations_line_dict = self.amz_prepare_disposal_and_removal_line_dict(
                    existing_order, row, disposal_line_dict, return_line_dict, liquidations_line_dict)
        if order_dict:
            existing_order, disposal_line_dict, return_line_dict, liquidations_line_dict = self.create_order_if_not_found_in_odoo(
                order_dict, disposal_line_dict, return_line_dict, liquidations_line_dict)
        if disposal_line_dict or return_line_dict or liquidations_line_dict:
            self.process_removal_lines(disposal_line_dict, return_line_dict, liquidations_line_dict)
        is_partially_processed_report = log_line_obj.search_count([('res_id', '=', self.id),
                                                                   ('model_id', '=', model_id),
                                                                   ('mismatch_details', '=', True)])
        state = 'partially_processed' if is_partially_processed_report else 'processed'
        self.write({'state': state})
        return True

    def amz_prepare_disposal_and_removal_line_dict(self, existing_order, rows, disposal_line_dict,
                                                   return_line_dict, liquidations_line_dict):
        """
        Prepare disposal and removal lines dictionary from file data
        :param existing_order: amazon.removal.order.ept()
        :param rows: list(dict())
        :param disposal_line_dict: dict{key: [row]}
        :param return_line_dict: dict{key: [row]}
        :return: dict{key: [row]}, dict{key: [row]}
        """
        log_line_obj = self.env['common.log.lines.ept']
        rows = [rows] if not isinstance(rows, list) else rows
        for row in rows:
            amazon_removal_order_config = existing_order.instance_id.removal_order_config_ids.filtered(
                lambda l, row=row: l.removal_disposition == row.get('order-type', ''))
            if not amazon_removal_order_config:
                message = "Configuration not found for order-type {} || order-id {} ".format(
                    row.get('order-type', ''), row.get('order-id', ''))
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                    operation_type='import', res_id=self.id, mismatch_details=True,
                    amz_instance_ept=self.instance_id and self.instance_id.id or False,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False)
            else:
                key = (existing_order.id, amazon_removal_order_config.id)
                disposal_line_dict, return_line_dict, liquidations_line_dict = self.update_return_or_removal_line_dict_ept(
                    key, row, disposal_line_dict, return_line_dict, liquidations_line_dict)
        return disposal_line_dict, return_line_dict, liquidations_line_dict

    def create_order_if_not_found_in_odoo(self, order_dict, disposal_line_dict, return_line_dict,
                                          liquidations_line_dict):
        """
        Creating removal order if order not found in odoo.
        :param order_dict: dict()
        :param disposal_line_dict: dict{key: [row]}
        :param return_line_dict: dict{key: [row]}
        :return: amazon.removal.order.ept(), dict{key: [row]}, dict{key: [row]}
        :Note: Process can not create Removal Order in below condition:
              1) Return order and all lines have no shipped quantity
              2) Disposal order and all lines have no disposed quantity
        """
        log_line_obj = self.env['common.log.lines.ept']
        removal_order = []
        for order_id, rows in list(order_dict.items()):
            instance = self.seller_id.instance_ids.filtered(lambda l: l.is_allow_to_create_removal_order)
            if not instance:
                instance = self.seller_id.instance_ids[0]
            lines = []
            skip_lines = 0
            order_type = rows[0].get('order-type', '')
            for row in rows:
                amazon_product = self.get_amazon_product(row.get('sku', ''), instance)
                if not amazon_product:
                    message = "Line is skipped due to product not found in ERP || Order ref {} ||" \
                              "Seller sku {} ".format(order_id, row.get('sku', ''))
                    log_line_obj.create_common_log_line_ept(
                        message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                        operation_type='import', res_id=self.id, mismatch_details=True,
                        amz_seller_ept=self.seller_id and self.seller_id.id or False,
                        amz_instance_ept=instance and instance.id or False)
                    continue
                if float(row.get('requested-quantity', 0.0)) <= 0.0:
                    message = "Line is skipped due to request qty not found in file || " \
                              "Order ref {} || Seller sku {}".format(order_id, row.get('sku', ''))
                    log_line_obj.create_common_log_line_ept(
                        message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                        operation_type='import', res_id=self.id, mismatch_details=True,
                        amz_seller_ept=self.seller_id and self.seller_id.id or False,
                        amz_instance_ept=instance and instance.id or False)
                    continue
                lines, skip_lines = self.prepare_removal_order_lines_vals_ept(lines, skip_lines, row, amazon_product)
            # Not create Removal order if all lines of order are skip
            if len(rows) == skip_lines:
                continue
            if lines:
                removal_order = self.create_removal_order_and_process_pickings(order_id, order_type, instance, lines)
                disposal_line_dict, return_line_dict, liquidations_line_dict = self.amz_prepare_disposal_and_removal_line_dict(
                    removal_order, rows, disposal_line_dict, return_line_dict, liquidations_line_dict)
        return removal_order, disposal_line_dict, return_line_dict, liquidations_line_dict

    def update_return_or_removal_line_dict_ept(self, key, row, disposal_line_dict, return_line_dict,
                                               liquidations_line_dict):
        """
        Define method for update Removal or Return order lines dictionary.
        :param : key : removal order id
        :param : row : list(dict())
        :param : disposal_line_dict : dict{key: [row]}
        :param : return_line_dict : dict{key: [row]}
        :return : dict {}
        """
        log_line_obj = self.env['common.log.lines.ept']
        if row.get('order-type', '') == 'Disposal':
            if key in disposal_line_dict:
                disposal_line_dict.get(key).append(row)
            else:
                disposal_line_dict.update({key: [row]})
        elif row.get('order-type', '') == 'Return':
            if key in return_line_dict:
                return_line_dict.get(key).append(row)
            else:
                return_line_dict.update({key: [row]})
        elif row.get('order-type', '') == 'Liquidations':
            if key in liquidations_line_dict:
                liquidations_line_dict.get(key).append(row)
            else:
                liquidations_line_dict.update({key: [row]})
        else:
            message = "Order type {} || skipped of {} ".format(row.get('order-type', ''), row.get('order-id', ''))
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                operation_type='import', res_id=self.id, amz_seller_ept=self.seller_id and self.seller_id.id or False,
                amz_instance_ept=self.instance_id and self.instance_id.id or False)
        return disposal_line_dict, return_line_dict, liquidations_line_dict

    def create_removal_order_and_process_pickings(self, order_id, order_type, instance, lines):
        """
        Define method which help to create removal order and processed removal orders pickings.
        :param : order_id : removal order reference
        :param : order_type : amazon removal order type [Return / Disposal]
        :param : instance : amazon.instance.ept()
        :param : lines : list()
        :return : amazon.removal.order.ept() object
        """
        ctx = self._context.copy()
        ctx.update({'model_name_ept': AMZ_REMOVAL_ORDER_REPORT_HISTORY})
        amazon_removal_order_obj = self.env[AMZ_REMOVAL_ORDER_EPT]
        removal_vals = self.prepare_amz_removal_order_vals_ept(order_id, order_type, instance, lines)
        removal_order = amazon_removal_order_obj.create(removal_vals)
        removal_order.write({'state': 'plan_approved'})
        if order_type == 'Disposal':
            sell_pick, unsell_pick = removal_order.with_context(ctx).disposal_order_pickings()
            if sell_pick:
                sell_pick.write({'removal_order_report_id': self.id})
            if unsell_pick:
                unsell_pick.write({'removal_order_report_id': self.id})
        if order_type == 'Return':
            pickings = removal_order.with_context(ctx).removal_order_procurements()
            pickings.write({'removal_order_report_id': self.id})
        if order_type == 'Liquidations':
            sell_pick, unsell_pick = removal_order.with_context(ctx).disposal_order_pickings()
            if sell_pick:
                sell_pick.write({'removal_order_report_id': self.id})
            if unsell_pick:
                unsell_pick.write({'removal_order_report_id': self.id})
        return removal_order

    @staticmethod
    def prepare_removal_order_lines_vals_ept(lines, skip_lines, row, amazon_product):
        """
        Define method for prepare removal order line values.
        :param : lines : list()
        :param : skip_lines : removal order lines skip count
        :param : row : list(dict())
        :param : amazon_product : amazon.product.ept()
        :return : prepare list [], skip_lines count
        """
        if row.get('order-type', '') == 'Disposal' and float(row.get('disposed-quantity', 0.0)) <= 0.0:
            skip_lines += 1
        if row.get('order-type', '') == 'Return' and float(row.get('shipped-quantity', 0.0)) <= 0.0:
            skip_lines += 1
        if row.get('order-type', '') == 'Liquidations' and float(row.get('shipped-quantity', 0.0)) <= 0.0:
            skip_lines += 1
        vals = {'amazon_product_id': amazon_product.id, 'removal_disposition': row.get('order-type', '')}
        if row.get('disposition', '') == 'Unsellable':
            vals.update({'unsellable_quantity': float(row.get('requested-quantity', 0.0))})
        else:
            vals.update({'sellable_quantity': float(row.get('requested-quantity', 0.0))})
        lines.append((0, 0, vals))
        return lines, skip_lines

    def prepare_amz_removal_order_vals_ept(self, order_id, order_type, instance, lines):
        """
        Prepare removal order values
        :param order_id: amazon removal order id
        :param order_type: amazon removal order type [Return / Disposal]
        :param instance: amazon.instance.ept()
        :param lines: list()
        :return: dict{}
        """
        log_line_obj = self.env['common.log.lines.ept']
        try:
            ship_add_id = self.seller_id.amz_fba_liquidation_partner.id if order_type == 'Liquidations' else self.company_id.partner_id.id
        except Exception:
            message = "FBA Liquidation Partner is Missing! " \
                      "Please Configure FBA Liquidation Partner in Amazon Seller Configuration."
            if self._context.get('is_auto_process'):
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                    operation_type='import', res_id=self.id, mismatch_details=True,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False,
                    amz_instance_ept=instance and instance.id or False)
            else:
                raise UserError(_(message))
        return {
            'name': order_id or '',
            'removal_disposition': order_type or '',
            'warehouse_id': instance.removal_warehouse_id.id if instance else False,
            'ship_address_id': ship_add_id,
            'company_id': self.seller_id.company_id.id,
            'instance_id': instance.id if instance else False,
            'removal_order_lines_ids': lines or []

        }

    def check_amazon_order_exist_order_not(self, row):
        """
        This Method relocates check amazon order exist or not.If exist then find order with order ref.
        :param row: dict{}
        :return: amazon.removal.order.ept(), boolean(True / False)
        """
        log_line_obj = self.env['common.log.lines.ept']
        amz_removal_order_obj = self.env[AMZ_REMOVAL_ORDER_EPT]
        order_id = row.get('order-id', '')
        order_status = row.get('order-status', '')
        skip_line = False
        existing_order = amz_removal_order_obj.search([('name', '=', order_id)])
        if not existing_order and order_status == 'Cancelled':
            message = "Removal order not found for processing order-id {} ".format(order_id)
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                operation_type='import', res_id=self.id, mismatch_details=True,
                amz_seller_ept=self.seller_id and self.seller_id.id or False,
                amz_instance_ept=self.instance_id and self.instance_id.id or False)
            skip_line = True
        elif len(existing_order.ids) > 1:
            message = "Multiple Order found for processing order-id {} ".format(order_id)
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                operation_type='import', res_id=self.id, mismatch_details=True,
                amz_seller_ept=self.seller_id and self.seller_id.id or False,
                amz_instance_ept=self.instance_id and self.instance_id.id or False)
            skip_line = True
        elif existing_order and order_status == 'Cancelled':
            remove_order_picking_ids = existing_order.removal_order_picking_ids
            picking_ids = remove_order_picking_ids.filtered(lambda x: x.state not in ['done', 'cancel'])
            if picking_ids:
                picking_ids.action_cancel()
            if remove_order_picking_ids and not remove_order_picking_ids.filtered(lambda x: x.state not in ['cancel']):
                existing_order.write({'state': 'Cancelled'})
            skip_line = True
        return existing_order, skip_line

    def get_amazon_product(self, sku, instance):
        """
        This Method relocates get amazon product using product sku and instance of amazon.
        :param sku: This Arguments relocates sku of removal order product amazon.
        :param instance: This Arguments instance of amazon.
        :return: This Method return amazon product.
        """
        amazon_product = self.env['amazon.product.ept'].search(
            [('seller_sku', '=', sku), ('instance_id', '=', instance.id),
             ('fulfillment_by', '=', 'FBA')], limit=1)
        return amazon_product

    def process_removal_lines(self, disposal_line_dict, return_line_dict, liquidations_line_dict):
        """
        This Method relocates process removal order lines.
        :param liquidations_line_dict: dict()
        :param disposal_line_dict: dict()
        :param return_line_dict: dict()
        :return: boolean
        """
        if disposal_line_dict:
            self.process_disposal_lines(disposal_line_dict)
        if return_line_dict:
            self.process_return_lines(return_line_dict)
        if liquidations_line_dict:
            self.process_disposal_lines(liquidations_line_dict)
        return True

    def process_disposal_lines(self, disposal_line_dict):
        """
        This Method relocates process disposal line.
        If dispose quantity found grater 0 then check move processed or not.
        If dispose quantity found less or equal 0 then search stock move.
        :param disposal_line_dict: list(dict{key: [row]})
        :return: list()
        """
        amz_removal_order_config_obj = self.env['removal.order.config.ept']
        amz_removal_order_obj = self.env[AMZ_REMOVAL_ORDER_EPT]
        pickings = []
        for order_key, rows in list(disposal_line_dict.items()):
            order = amz_removal_order_obj.browse(order_key[0])
            config = amz_removal_order_config_obj.browse(order_key[1])
            picking_vals = self.amz_removal_pickings_dict(order, config)
            unsellable_source_location_id = order.disposition_location_id.id
            sellable_source_location_id = order.instance_id.fba_warehouse_id.lot_stock_id.id
            for row in rows:
                disposed_qty = float(row.get('disposed-quantity', 0.0) or 0.0)
                canceled_qty = float(row.get('cancelled-quantity', 0.0) or 0.0)
                shipped_qty = float(row.get('shipped-quantity', 0.0) or 0.0)
                product = self.find_amazon_product_for_process_removal_line(row, order.instance_id.id)
                if product:
                    source_location_id = unsellable_source_location_id if row.get(
                        'disposition', '') == 'Unsellable' else sellable_source_location_id
                    picking_vals.update({'source_location_id': source_location_id, 'product_id': product,
                                         'order': order})
                    if disposed_qty > 0.0:
                        move_pickings, skip_line = self.amz_removal_procesed_qty_ept(row, picking_vals, disposed_qty)
                        if skip_line:
                            continue
                        if move_pickings:
                            pickings += move_pickings
                    if shipped_qty > 0.0:
                        mv_pickings, skip_line = self.amz_removal_procesed_qty_ept(row, picking_vals, shipped_qty)
                        if skip_line:
                            continue
                        if mv_pickings:
                            pickings += mv_pickings
                    if canceled_qty > 0.0:
                        self.amz_removal_canceled_qty_ept(row, picking_vals, canceled_qty)
        if pickings:
            pickings = list(set(pickings))
            self.process_picking(pickings)
        return pickings

    @staticmethod
    def amz_removal_pickings_dict(order, config):
        """
        Prepare Removal order pickings filtered values.
        :param order: amazon.removal.order.ept()
        :param config: removal.order.config.ept()
        :return: dict{}
        """
        return {
            'remaining_pickings': order.removal_order_picking_ids.filtered(
                lambda l: l.state not in ['done', 'cancel']),
            'processed_pickings': order.removal_order_picking_ids.filtered(lambda l: l.state == 'done'),
            'canceled_pickings': order.removal_order_picking_ids.filtered(lambda l: l.state == 'cancel'),
            'location_dest_id': config.location_id.id or False,
        }

    def amz_removal_canceled_qty_ept(self, row, picking_vals, quantity):
        """
         Processing removal orders cancelled quantities from report.
        :param row: dict()
        :param picking_vals: dict()
        :param quantity: float
        :return: boolean
        """
        log_line_obj = self.env['common.log.lines.ept']
        remaining_pickings = picking_vals.get('remaining_pickings').ids if \
            picking_vals.get('remaining_pickings') else []
        processed_pickings = picking_vals.get('processed_pickings').ids if \
            picking_vals.get('remaining_pickings') else []
        remaining_processed_pickings = list(set(remaining_pickings + processed_pickings))
        stock_move_obj = self.env['stock.move']
        order_ref = row.get('order-id', '')
        sku = row.get('sku', '')
        qty = quantity
        if quantity:
            canceled_moves = stock_move_obj.search([('product_id', '=', picking_vals.get('product_id', False)),
                                                    ('state', '=', 'cancel'),
                                                    ('picking_id', 'in', remaining_processed_pickings),
                                                    ('location_id', '=', picking_vals.get('source_location_id', False))
                                                    ])
            if canceled_moves:
                qty = self.check_move_processed_or_not(picking_vals.get('product_id', False),
                                                       canceled_moves, sku, quantity, order_ref)
        if qty > 0.0:
            moves = self.amz_get_stock_move_from_picking_ept(picking_vals.get('product_id', False),
                                                             picking_vals.get('remaining_pickings', False),
                                                             picking_vals.get('source_location_id', False),
                                                             picking_vals.get('location_dest_id', False),
                                                             ['done', 'cancel'])
            if not moves:
                message = 'Move not found for processing sku {} order ref {}'.format(
                    sku, picking_vals.get('order', '').name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                    operation_type='import', res_id=self.id, mismatch_details=True,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False,
                    amz_instance_ept=self.instance_id and self.instance_id.id or False)
            if moves:
                self.update_cancel_qty_ept(moves, qty)
        return True

    def amz_removal_procesed_qty_ept(self, row, picking_vals, quantity):
        """
        Processed Pending Return and Disposal orders and process create back orders
        for partially done quantity
        :param row: dict()
        :param picking_vals: dict()
        :param quantity: float
        :return: list()
        """
        log_line_obj = self.env['common.log.lines.ept']
        order_ref = row.get('order-id', '')
        sku = row.get('sku', '')
        qty = quantity
        move_pickings = []
        skip_line = False
        if picking_vals.get('processed_pickings', False):
            existing_move = self.amz_get_stock_move_from_picking_ept(picking_vals.get('product_id', False),
                                                                     picking_vals.get('processed_pickings', False),
                                                                     picking_vals.get('source_location_id', False),
                                                                     picking_vals.get('location_dest_id', False), 'done'
                                                                     )
            if existing_move:
                qty = self.check_move_processed_or_not(picking_vals.get('product_id', False), existing_move,
                                                       sku, quantity, order_ref)
        if qty > 0.0:
            moves = self.amz_get_stock_move_from_picking_ept(picking_vals.get('product_id', False),
                                                             picking_vals.get('remaining_pickings', False),
                                                             picking_vals.get('source_location_id', False),
                                                             picking_vals.get('location_dest_id', False),
                                                             ['done', 'cancel'])
            if moves:
                move_pickings = self.create_pack_operations_ept(moves, qty)
            else:
                message = 'Move not found for processing sku {} order ref {}'.format(
                    sku, picking_vals.get('order', '').name)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                    operation_type='import', res_id=self.id, mismatch_details=True,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False,
                    amz_instance_ept=self.instance_id and self.instance_id.id or False)
                skip_line = True
        return move_pickings, skip_line

    @staticmethod
    def amz_get_stock_move_from_picking_ept(product_id, pickings_ids, source_location_id,
                                            location_dest_id, state):
        """
        Filter stock move based on product, source, state location and destination location from picking
        object.
        :param product_id: integer
        :param pickings_ids: stock.picking()
        :param source_location_id: integer
        :param location_dest_id: integer
        :param state : stock move state
        :return: stock.move()
        """
        if state == 'done':
            return pickings_ids.move_ids.filtered(
                lambda l: l.product_id.id == product_id and l.location_id.id == source_location_id and
                l.location_dest_id.id == location_dest_id and l.state == state)
        return pickings_ids.move_ids.filtered(
            lambda l: l.product_id.id == product_id and l.location_id.id == source_location_id and
            l.location_dest_id.id == location_dest_id and l.state not in state)

    def process_return_lines(self, return_line_dict):
        """
        This Method relocates processed return removal order lines.
        This Method find amazon product for process removal line.
        This Method check move processed or not.
        :param return_line_dict: This Arguments relocates dictionary of return line.
        :return: This Method return pickings.
        """
        procurement_rule_obj = self.env['stock.rule']
        amz_removal_order_config_obj = self.env['removal.order.config.ept']
        amz_removal_order_obj = self.env[AMZ_REMOVAL_ORDER_EPT]
        pickings = []
        for order_key, rows in list(return_line_dict.items()):
            order = amz_removal_order_obj.browse(order_key[0])
            config = amz_removal_order_config_obj.browse(order_key[1])
            picking_vals = self.amz_removal_pickings_dict(order, config)
            procurement_rule = procurement_rule_obj.search(
                [('route_id', '=', config.unsellable_route_id.id),
                 ('location_src_id', '=', order.disposition_location_id.id)])
            unsellable_source_location_id = procurement_rule.location_src_id.id
            unsellable_dest_location_id = procurement_rule.location_dest_id.id
            procurement_rule = procurement_rule_obj.search([
                ('route_id', '=', config.sellable_route_id.id),
                ('location_src_id', '=', order.instance_id.fba_warehouse_id.lot_stock_id.id)])
            sellable_source_location_id = procurement_rule.location_src_id.id
            sellable_dest_location_id = procurement_rule.location_dest_id.id
            for row in rows:
                product = self.find_amazon_product_for_process_removal_line(row, order.instance_id.id)
                if not product:
                    continue
                shipped_qty = float(row.get('shipped-quantity', 0.0))
                canceled_qty = float(row.get('cancelled-quantity', 0.0))
                source_location_id = unsellable_source_location_id if row.get(
                    'disposition', '') == 'Unsellable' else sellable_source_location_id
                location_dest_id = unsellable_dest_location_id if row.get(
                    'disposition', '') == 'Unsellable' else sellable_dest_location_id
                picking_vals.update({'location_dest_id': location_dest_id or False,
                                     'source_location_id': source_location_id or False,
                                     'product_id': product, 'order': order})
                if shipped_qty > 0.0:
                    move_pickings, skip_lines = self.amz_removal_procesed_qty_ept(row, picking_vals, shipped_qty)
                    if skip_lines:
                        continue
                    if move_pickings:
                        pickings += move_pickings
                if canceled_qty > 0.0:
                    self.amz_removal_canceled_qty_ept(row, picking_vals, canceled_qty)
        if pickings:
            pickings = list(set(pickings))
            self.process_picking(pickings)
        return pickings

    def find_amazon_product_for_process_removal_line(self, line, instance):
        """
        This Method relocates find amazon product for processed removal order line.
        :param line: This Arguments relocates Line of return line dictionary.
        :param instance: This Arguments instance of amazon.
        :return: This Method return process removal order product.
        """
        amazon_product_obj = self.env['amazon.product.ept']
        log_line_obj = self.env['common.log.lines.ept']
        sku = line.get('sku', '')
        asin = line.get('fnsku', '')
        amazon_product = amazon_product_obj.search([('seller_sku', '=', sku),
                                                    ('fulfillment_by', '=', 'FBA'),
                                                    ('instance_id', '=', instance)], limit=1)
        if not amazon_product:
            amazon_product = amazon_product_obj.search([('product_asin', '=', asin),
                                                        ('fulfillment_by', '=', 'FBA'),
                                                        ('instance_id', '=', instance)], limit=1)
        product = amazon_product.product_id.id if amazon_product else False
        if not amazon_product:
            log_line_obj.create_common_log_line_ept(
                message='Product  not found for SKU {} & ASIN {}'.format(sku, asin),
                model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept', operation_type='import',
                res_id=self.id, mismatch_details=True, amz_seller_ept=self.seller_id and self.seller_id.id or False,
                amz_instance_ept=instance or False)
        return product

    def check_move_processed_or_not(self, product_id, existing_move, sku, qty, order_ref):
        """
        check existing move is processed or not.
        :param existing_move: stock.move()
        :param product_id: product reference
        :param sku: str
        :param qty: float
        :param order_ref: str
        :return: quantity (float)
        """
        log_line_obj = self.env['common.log.lines.ept']
        for move in existing_move:
            qty -= move.product_qty
        if qty <= 0.0:
            message = """Move already processed Product {} || sku {} Qty {} ||
                Order ref {} """.format(product_id, sku, qty, order_ref)
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=AMZ_REMOVAL_ORDER_REPORT_HISTORY, module='amazon_ept',
                operation_type='import', res_id=self.id, amz_seller_ept=self.seller_id and self.seller_id.id or False,
                amz_instance_ept=self.instance_id and self.instance_id.id or False)
        return qty

    def update_cancel_qty_ept(self, moves, quantity):
        """
        This Method relocates update cancel qty.
        :param moves: This Arguments relocates stock move.
        :param quantity: This Arguments relocates cancel quantity.
        :return: This Method return boolean(True/False).
        """
        stock_move_obj = self.env['stock.move']
        for move in moves:
            if quantity > move.product_qty:
                qty = move.product_qty
            else:
                qty = quantity
            if qty == move.product_qty:
                move._action_cancel()
            else:
                new_move_vals = move._split(qty)
                new_move = stock_move_obj.create(new_move_vals)
                new_move = new_move._action_confirm(merge=False)
                new_move._action_cancel()
            quantity = quantity - qty
            if quantity <= 0.0:
                break
        return True

    def process_picking(self, pickings):
        """
        This Method relocates process picking and change state.
        :param pickings: list().
        :return: Boolean(True/False).
        """
        stock_picking_obj = self.env['stock.picking']
        for picking in pickings:
            picking = stock_picking_obj.browse(picking)
            picking.with_context({'auto_processed_orders_ept': True})._action_done()
            picking.write({'removal_order_report_id': self.id})
            removal_order_picking_ids = picking.removal_order_id.removal_order_picking_ids.filtered(
                lambda l: l.is_fba_wh_picking and l.state != 'done')
            if not removal_order_picking_ids:
                picking.removal_order_id.write({'state': 'Completed'})
        return True

    def create_pack_operations_ept(self, moves, quantity):
        """
        This Method relocates create pack operation.
        This Method create stock move line for existing move and if any quantity left then create
        stock move line.
        :param moves: stock.move()
        :param quantity: float
        :return: list()
        """
        pick_ids = []
        stock_move_line_obj = self.env['stock.move.line']
        for move in moves:
            qty_left = quantity
            if qty_left <= 0.0:
                break
            mv_done_qty = sum(line.qty_done for line in move.move_line_ids)
            move_line_remaning_qty = move.product_uom_qty - mv_done_qty   #move.move_line_ids.qty_done
            operations = move.move_line_ids.filtered(
                lambda o: o.qty_done <= 0 and not o.result_package_id)
            for operation in operations:
                op_qty = operation.reserved_uom_qty if operation.reserved_uom_qty <= qty_left else qty_left
                operation.write({'qty_done': op_qty})
                # commented this method for prevent to create back order stock move line from the connector
                # self._put_in_pack(operation)
                qty_left = float_round(qty_left - op_qty,
                                       precision_rounding=operation.product_uom_id.rounding,
                                       rounding_method='UP')
                move_line_remaning_qty = move_line_remaning_qty - op_qty
                if qty_left <= 0.0:
                    break
            picking = move.picking_id
            if qty_left > 0.0 and move_line_remaning_qty > 0.0:
                op_qty = move_line_remaning_qty if move_line_remaning_qty <= qty_left else qty_left
                sml_vals = self.amz_create_removal_stock_move_line_vals(move, picking, op_qty)
                stock_move_line_obj.create(sml_vals)
                pick_ids.append(move.picking_id.id)
                qty_left = float_round(qty_left - op_qty,
                                       precision_rounding=move.product_id.uom_id.rounding,
                                       rounding_method='UP')
                if qty_left <= 0.0:
                    break
            if qty_left > 0.0:
                sml_vals = self.amz_create_removal_stock_move_line_vals(move, picking, qty_left)
                stock_move_line_obj.create(sml_vals)
            pick_ids.append(move.picking_id.id)
        return pick_ids

    @staticmethod
    def amz_create_removal_stock_move_line_vals(move, picking, op_qty):
        """
        Prepare stock move line values for removal orders stock move.
        :param move: stock.move()
        :param picking: stock.picking()
        :param op_qty: float
        :return: dict()
        """
        return {
            'product_id': move.product_id.id,
            'product_uom_id': move.product_id.uom_id.id,
            'picking_id': move.picking_id.id,
            'qty_done': float(op_qty) or 0.0,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'move_id': move.id,
        }

    def _put_in_pack(self, operation, package=False):
        # NOTE : As of now unused this method for amazon removal order process
        # because odoo base by default create back order move and move lines for partially shipped
        # order so no need to create from the connector
        """
        This Method relocates put in pack stock move line.
        :param operation: This Arguments relocates stock move line.
        :param package: This Arguments relocates package.
        :return: This Method return Boolean(True/False).
        """
        operation_ids = self.env['stock.move.line']
        if float_compare(operation.qty_done, operation.reserved_uom_qty,
                         precision_rounding=operation.product_uom_id.rounding) >= 0:
            operation_ids |= operation
        else:
            quantity_left_todo = float_round(
                operation.reserved_uom_qty - operation.qty_done,
                precision_rounding=operation.product_uom_id.rounding, rounding_method='UP')
            new_operation = operation.copy(
                default={'reserved_uom_qty': operation.qty_done, 'qty_done': operation.qty_done})
            operation.write({'reserved_uom_qty': quantity_left_todo, 'qty_done': 0.0})
            operation_ids |= new_operation
        if package:
            operation_ids.write({'result_package_id': package.id})
        return True

    @api.model
    def auto_import_removal_order_report(self, args={}):
        """
        This method is used to import removal order report via cron.
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env[AMZ_SELLER_EPT].browse(seller_id)
            if seller.removal_order_report_last_sync_on:
                start_date = seller.removal_order_report_last_sync_on
                start_date = datetime.strftime(start_date, DATE_YMDHMS)
                start_date = datetime.strptime(str(start_date), DATE_YMDHMS)
                start_date = start_date + timedelta(days=seller.removal_order_report_days * -1 or -3)
            else:
                today = datetime.now()
                earlier = today - timedelta(days=30)
                start_date = earlier.strftime(DATE_YMDHMS)
            date_end = datetime.now()
            date_end = date_end.strftime(DATE_YMDHMS)
            rem_report = self.create({'report_type': ReportType.GET_FBA_FULFILLMENT_REMOVAL_ORDER_DETAIL_DATA,
                                      'seller_id': seller_id, 'start_date': start_date,
                                      'end_date': date_end, 'state': 'draft',
                                      'requested_date': time.strftime(DATE_YMDHMS)})
            rem_report.with_context(is_auto_process=True).request_report()
            seller.write({'removal_order_report_last_sync_on': date_end})
        return True

    @api.model
    def auto_process_removal_order_report(self, args={}):
        """
        This method is used to process removal order report via cron.
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env[AMZ_SELLER_EPT].search([('id', '=', seller_id)])
            rem_reports = self.search([('seller_id', '=', seller.id),
                                       ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_',
                                                        'SUBMITTED', 'IN_PROGRESS', 'IN_QUEUE'])])
            for report in rem_reports:
                report.with_context(is_auto_process=True).get_report_request_list()

            rem_reports = self.search([('seller_id', '=', seller.id),
                                       ('state', 'in', ['_DONE_', '_SUBMITTED_', '_IN_PROGRESS_',
                                                        'DONE', 'SUBMITTED', 'IN_PROGRESS']),
                                       ('report_document_id', '!=', False)])
            for report in rem_reports:
                if not report.attachment_id:
                    report.with_context(is_auto_process=True).get_report()
                if report.state in ['_DONE_', 'DONE'] and report.attachment_id:
                    report.with_context(is_auto_process=True).process_removal_order_report()
                self._cr.commit()
        return True
