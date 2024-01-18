# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class, methods and fields to import and process Sale Orders Return Report.
"""
from datetime import datetime, timedelta
import time
import base64
import csv
from io import StringIO
from dateutil import parser
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .. reportTypes import ReportType

STOCK_MOVE = 'stock.move'
IR_MODEL = 'ir.model'
AMZ_SELLER_EPT = 'amazon.seller.ept'
SALE_ORDER_RETURN_REPORT = 'sale.order.return.report'
AMAZON_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class SaleOrderReturnReport(models.Model):
    """
    Added class to import and process Sale Orders Return Report.
    """
    _name = "sale.order.return.report"
    _inherit = ['mail.thread', 'amazon.reports']
    _description = "Customer Return Report"
    _order = 'id desc'

    @api.depends('seller_id')
    def _compute_return_report_company(self):
        """
        Compute method for get company id based on seller id
        :return:
        """
        for record in self:
            company_id = record.seller_id.company_id.id if record.seller_id else False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    def _compute_total_returns(self):
        """
        Get total number of records which is processed in the current report
        :return:
        """
        stock_move_obj = self.env[STOCK_MOVE]
        records = stock_move_obj.search([('amz_return_report_id', '=', self.id)])
        self.return_count = len(records)

    def _compute_log_count(self):
        """
        This method will compute total logs for the current shipment report record.
        :return:
        """
        common_log_lines_obj = self.env['common.log.lines.ept']
        model_id = self.env[IR_MODEL]._get(SALE_ORDER_RETURN_REPORT).id
        log_ids = common_log_lines_obj.search([('res_id', '=', self.id), ('model_id', '=', model_id)]).ids
        self.log_count = log_ids.__len__()

        # Set the boolean field mismatch_details as True if found any mismatch details in log lines
        if common_log_lines_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id),
                                              ('mismatch_details', '=', True)]):
            self.mismatch_details = True
        else:
            self.mismatch_details = False

    name = fields.Char(size=256)
    attachment_id = fields.Many2one('ir.attachment', string="Attachment",
                                    help="Attachment Id for Customer Return csv file")
    return_count = fields.Integer(compute="_compute_total_returns", string="Returns")
    report_request_id = fields.Char(size=256, string='Report Request ID',
                                    help="Report request id to recognise unique request")
    report_document_id = fields.Char(string='Report Document ID',
                                     help="Report Document id to recognise unique request document reference")
    report_id = fields.Char(size=256, string='Report ID',
                            help="Unique Report id for recognise report in Odoo")
    report_type = fields.Char(size=256, help="Amazon Report Type")
    start_date = fields.Datetime(help="Report Start Date")
    end_date = fields.Datetime(help="Report End Date")
    requested_date = fields.Datetime(default=time.strftime(AMAZON_DATETIME_FORMAT),
                                     help="Report Requested Date")
    state = fields.Selection([('draft', 'Draft'), ('SUBMITTED', 'SUBMITTED'),
                              ('_SUBMITTED_', 'SUBMITTED'), ('IN_QUEUE', 'IN_QUEUE'),
                              ('IN_PROGRESS', 'IN_PROGRESS'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
                              ('DONE', 'DONE'), ('_DONE_', 'DONE'), ('_DONE_NO_DATA_', 'DONE_NO_DATA'),
                              ('imported', 'Imported'), ('FATAL', 'FATAL'),
                              ('partially_processed', 'Partially Processed'), ('processed', 'PROCESSED'),
                              ('closed', 'Closed'), ('CANCELLED', 'CANCELLED'), ('_CANCELLED_', 'CANCELLED')],
                             string='Report Status', default='draft', help="Report Processing States")
    seller_id = fields.Many2one(AMZ_SELLER_EPT, string='Seller', copy=False,
                                help="Select Seller id from you wanted to get Shipping report")
    user_id = fields.Many2one('res.users', string="Requested User",
                              help="Track which odoo user has requested report")
    company_id = fields.Many2one('res.company', string="Company", copy=False,
                                 compute="_compute_return_report_company",
                                 store=True)
    log_count = fields.Integer(compute="_compute_log_count",
                               help="Count number of created Stock Move")
    mismatch_details = fields.Boolean(compute="_compute_log_count", string="Mismatch Details",
                                      help="True if found mismatch details in log line")

    def unlink(self):
        """
        This Method if report is processed then raise UserError.
        """
        for report in self:
            if report.state == 'processed' or report.state == 'partially_processed':
                raise UserError(_('You cannot delete processed report.'))
        return super(SaleOrderReturnReport, self).unlink()

    @api.constrains('start_date', 'end_date')
    def _check_duration(self):
        """
        Compare Start date and End date, If End date is before start date rate warning.
        :return:
        """
        if self.start_date and self.end_date < self.start_date:
            raise UserError(_('Error!\nThe start date must be precede its end date.'))
        return True

    def list_of_return_orders(self):
        """
        List all Stock Move which is returned in the current report
        :return:
        """
        stock_move_obj = self.env[STOCK_MOVE]
        records = stock_move_obj.search([('amz_return_report_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(records.ids) + " )]",
            'name': 'Amazon FBA Order Return Stock Move',
            'view_mode': 'tree,form',
            'res_model': STOCK_MOVE,
            'type': 'ir.actions.act_window',
        }
        return action

    def list_of_process_logs(self):
        """
        List of Customer Return Report Log view
        :return:
        """
        model_id = self.env[IR_MODEL]._get(SALE_ORDER_RETURN_REPORT).id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + "), ('model_id','='," + str(model_id) + ")]",
            'name': 'Customer Return Report Logs',
            'view_mode': 'tree,form',
            'res_model': 'common.log.lines.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    @api.model
    def default_get(self, fields):
        """
        Set GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA to report type.
        :param fields:
        :return:
        """
        res = super(SaleOrderReturnReport, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': ReportType.GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """
        The below method sets name of a particular record as per the sequence.
        :param: vals_list: list of values []
        :return: sale.order.return.report() object
        """
        for vals in vals_list:
            sequence = self.env.ref('amazon_ept.seq_import_customer_return_report_job', raise_if_not_found=False)
            report_name = sequence.next_by_id() if sequence else '/'
            vals.update({'name': report_name})
        return super(SaleOrderReturnReport, self).create(vals_list)

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        """
        Automatically Set Start date and End date on selection of Seller
        :return:
        """
        if self.seller_id:
            self.start_date = self.seller_id.return_report_last_sync_on or\
                              (datetime.now() - timedelta(self.seller_id.shipping_report_days))
            self.end_date = datetime.now()

    def create_amazon_report_attachment(self, result):
        """
        Get Customer Return Orders Report as an attachment in Sale Orders Return
        Reports form view.
        :param : result : api response
        """
        result = result.get('document', '')
        result = base64.b64encode(result.encode())
        file_name = "Customer_return_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': result,
            'res_model': 'mail.compose.message',
            'type': 'binary'
        })
        self.message_post(body=_("<b>Customer Return Report Downloaded</b>"), attachment_ids=attachment.ids)
        self.write({'attachment_id': attachment.id})

    def check_return_report_configuration_ept(self):
        """
        Define method for check Sale Orders Return report attach or not in records.
        """
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_auto_process_customer_return_report_seller_', self.seller_id.id)
        if not self.attachment_id:
            raise UserError(_("There is no any report are attached with this record."))

    def check_amz_return_move_line_ept(self, line, fulfillment_warehouse):
        """
        Define method for check required details for return line.
        :param : line : return report line
        :param : fulfillment_warehouse : {fulfillment_center: warehouse}
        :return: True/False, sale.order.line(), dict {}
        """
        log_line_obj = self.env['common.log.lines.ept']
        sale_order_line_obj = self.env['sale.order.line']
        sale_order_obj = self.env['sale.order']
        amazon_product_obj = self.env['amazon.product.ept']
        amazon_order_id = line.get('order-id', '')
        sku = line.get('sku', '')
        fulfillment_center_id = line.get('fulfillment-center-id', '')
        amazon_orders = sale_order_obj.search([('amz_order_reference', '=', amazon_order_id)])
        if not amazon_orders:
            message = 'Order %s Is Skipped due to not found in ERP' % (amazon_order_id)
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=SALE_ORDER_RETURN_REPORT, module='amazon_ept', operation_type='import',
                res_id=self.id, mismatch_details=True, amz_seller_ept=self.seller_id and self.seller_id.id or False)
            return True, [], fulfillment_warehouse

        instance_ids = [amazon_order.amz_instance_id.id for amazon_order in amazon_orders]
        amazon_products = amazon_product_obj.search(
            [('seller_sku', '=', sku), ('instance_id', 'in', instance_ids)], limit=1)
        if not amazon_products:
            message = 'Order %s Is Skipped due to Product %s not found in ERP' % (
                amazon_order_id, sku)
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=SALE_ORDER_RETURN_REPORT, module='amazon_ept', operation_type='import',
                res_id=self.id, mismatch_details=True, amz_seller_ept=self.seller_id and self.seller_id.id or False)
            return True, [], fulfillment_warehouse

        amazon_order_lines = sale_order_line_obj.search(
            [('order_id', 'in', amazon_orders.ids),
             ('product_id', '=', amazon_products.product_id.id)],
            order="id")
        if not amazon_order_lines:
            message = 'Order line %s Is Skipped due to not found in ERP' % (sku)
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=SALE_ORDER_RETURN_REPORT, module='amazon_ept', operation_type='import',
                res_id=self.id, mismatch_details=True, amz_seller_ept=self.seller_id and self.seller_id.id or False)
            return True, [], fulfillment_warehouse

        if fulfillment_center_id not in fulfillment_warehouse:
            warehouse = self.get_warehouse(fulfillment_center_id, self.seller_id.id,
                                           amazon_orders[0])
            fulfillment_warehouse.update({fulfillment_center_id: warehouse})
        warehouse = fulfillment_warehouse.get(fulfillment_center_id)
        if not warehouse:
            message = 'Order %s Is Skipped due warehouse not found in ERP || ' \
                      'Fulfillment center %s ' % (amazon_order_id, fulfillment_center_id)
            log_line_obj.create_common_log_line_ept(
                message=message, model_name=SALE_ORDER_RETURN_REPORT, module='amazon_ept', operation_type='import',
                res_id=self.id, mismatch_details=True, amz_seller_ept=self.seller_id and self.seller_id.id or False)
            return True, [], fulfillment_warehouse
        return False, amazon_order_lines, fulfillment_warehouse

    def process_return_report_file(self):
        """
        Handle Customer return report file, find from data and create dictionary of final processing
        move records
        Test Cases:https://docs.google.com/spreadsheets/d/12XqQEheGpQ6c-JV3Ma3eY2MkCMGRaYgf0iht36Ps
        ZFc/edit?usp=sharing
        :return:
        """
        self.ensure_one()
        self.check_return_report_configuration_ept()
        move_obj = self.env[STOCK_MOVE]
        log_line_obj = self.env['common.log.lines.ept']
        fulfillment_warehouse = {}
        remaning_move_qty = {}
        return_move_dict = {}
        if log_line_obj.amz_find_mismatch_details_log_lines(self.id, SALE_ORDER_RETURN_REPORT):
            log_line_obj.amz_find_mismatch_details_log_lines(self.id, SALE_ORDER_RETURN_REPORT).unlink()
        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        for line in reader:
            status = line.get('status', '')
            return_date = datetime.strftime(parser.parse(line.get('return-date', '')), AMAZON_DATETIME_FORMAT)
            amazon_order_id = line.get('order-id', '')
            sku = line.get('sku', '')
            returned_qty = float(line.get('quantity', 0.0))
            disposition = line.get('detailed-disposition', '')
            reason = line.get('reason', '')
            fulfillment_center_id = line.get('fulfillment-center-id', '')
            skip_line, amazon_order_lines, fulfillment_warehouse = self.check_amz_return_move_line_ept(
                line, fulfillment_warehouse)
            if skip_line:
                continue
            warehouse = fulfillment_warehouse.get(fulfillment_center_id)
            move_lines = move_obj.search([('sale_line_id', 'in', amazon_order_lines.ids),
                                          ('product_id', '=', amazon_order_lines[0].product_id.id),
                                          ('state', '=', 'done')])
            if not move_lines:
                message = 'Move Line is not found for Order %s' % (amazon_order_id)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=SALE_ORDER_RETURN_REPORT, module='amazon_ept', operation_type='import',
                    res_id=self.id, amz_seller_ept=self.seller_id and self.seller_id.id or False)
                move_lines = move_obj.search([('sale_line_id', 'in', amazon_order_lines.ids),
                                              ('sale_line_id.product_id', '=', amazon_order_lines[0].product_id.id),
                                              ('state', '=', 'done')])
            already_processed = False
            for move_line in move_lines:
                if move_line.fba_returned_date and datetime.strftime(parser.parse(return_date), '%Y-%m-%d') == \
                            datetime.strftime(parser.parse(str(move_line.fba_returned_date)), '%Y-%m-%d'):
                    message = 'Skipped because return already processed for Order %s' % (
                        move_line.amazon_order_reference)
                    log_line_obj.create_common_log_line_ept(
                        message=message, model_name=SALE_ORDER_RETURN_REPORT, module='amazon_ept',
                        operation_type='import', res_id=self.id,
                        amz_seller_ept=self.seller_id and self.seller_id.id or False)
                    already_processed = True
                    break
            if already_processed:
                continue

            exclude_move_ids = []
            for move_id, qty in remaning_move_qty.items():
                if qty <= 0.0:
                    exclude_move_ids.append(move_id)

            move_lines = move_obj.search([('sale_line_id', 'in', amazon_order_lines.ids),
                                          ('product_id', '=', amazon_order_lines[0].product_id.id),
                                          ('state', '=', 'done'), ('id', 'not in', exclude_move_ids)],
                                         order='product_qty desc')
            if not move_lines:
                move_lines = move_obj.search(
                    [('sale_line_id', 'in', amazon_order_lines.ids),
                     ('sale_line_id.product_id', '=', amazon_order_lines[0].product_id.id),
                     ('state', '=', 'done'),
                     ('id', 'not in', exclude_move_ids)], order='product_qty desc')
                if move_lines:
                    return_move_dict, remaning_move_qty = self.process_kit_type_product(
                        amazon_order_lines[0].product_id, move_lines, returned_qty,
                        warehouse, return_date, sku, disposition, reason,
                        return_move_dict, status, fulfillment_center_id,
                        remaning_move_qty)
                    continue
            if not move_lines:
                message = 'Order %s Is Skipped due to delivery move not found either ' \
                          'move have already returned or move missing in the ERP ' % (amazon_order_id)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=SALE_ORDER_RETURN_REPORT, module='amazon_ept', operation_type='import',
                    res_id=self.id, mismatch_details=True, amz_seller_ept=self.seller_id and self.seller_id.id or False)
                continue
            return_move_dict, remaning_move_qty = self.get_required_moves_for_return_process(
                move_lines, warehouse, return_date, sku, disposition, reason, status, fulfillment_center_id,
                remaning_move_qty, return_move_dict, amazon_order_id, returned_qty)
        if return_move_dict:
            self._create_fba_returns(return_move_dict)
        self.write({'state': 'processed'})
        return True

    def get_required_moves_for_return_process(self, move_lines, warehouse, return_date, sku, disposition,
                                              reason, status, fulfillment_center_id, remaning_move_qty,
                                              return_move_dict, amazon_order_id, returned_qty):
        """
        Define method for prepare stock move and details for return line process.
        :param : move_lines : stock.move()
        :param : warehouse : stock.warehouse()
        :param : return_date : datetime object
        :param : sku : product reference
        :param : disposition : return line disposition
        :param : reason : return line reason
        :param : status : return line status
        :param : fulfillment_center_id : fulfillment center
        :param : remaning_move_qty : {move : remaining_qty}
        :param : return_move_dict : {move : {move: return_qty}}
        :param : amazon_order_id : amazon order reference
        :param : returned_qty : return line quantity
        :return: dict {}, dict{}
        """
        log_line_obj = self.env['common.log.lines.ept']
        for move in move_lines:
            qty = move.product_qty - sum(move.move_dest_ids.filtered(
                lambda m: m.state in ['partially_available', 'assigned', 'done']
            ).mapped('move_line_ids').mapped('reserved_qty'))
            if round(qty, 2) <= 0:
                message = 'Order %s Is Skipped due to not found quant qty from quant history ' % (amazon_order_id)
                log_line_obj.create_common_log_line_ept(
                    message=message, model_name=SALE_ORDER_RETURN_REPORT, module='amazon_ept', operation_type='import',
                    res_id=self.id, mismatch_details=True, amz_seller_ept=self.seller_id and self.seller_id.id or False)
                continue
            if move.id in remaning_move_qty:
                get_remain_qty = remaning_move_qty.get(move.id)
            else:
                get_remain_qty = move.product_qty
            remaning_move_qty.update({move.id: get_remain_qty - returned_qty})
            key = (
                move, warehouse, return_date, sku, disposition, reason, status,
                fulfillment_center_id)
            if get_remain_qty >= returned_qty:
                new_return_move_qty = returned_qty
            else:
                new_return_move_qty = get_remain_qty
            if move not in return_move_dict:
                return_move_dict.update({move: {key: new_return_move_qty}})
            else:
                qty = return_move_dict.get(move, {}).get(key, 0.0)
                return_move_dict[move][key] = qty + new_return_move_qty

            returned_qty = returned_qty - new_return_move_qty
            if returned_qty <= 0:
                break
        return return_move_dict, remaning_move_qty

    @api.model
    def _create_fba_returns(self, return_move_dict):
        """
        Process Stock Moves from return_move_dict and create returns in the same warehouse
         where shipped or in the reimbursment or in unsellable locations
        :param return_move_dict: {}
        :return: True
        """
        log_line_obj = self.env['common.log.lines.ept']
        reason_record_dict = {}
        fulfillment_center_dict = {}
        for moves, key_qty in return_move_dict.items():
            for key, qty in key_qty.items():
                move, warehouse, return_date, sku, disposition, reason, status, fulfillment_center_id = key
                location_dest_id, reason_record_dict, fulfillment_center_dict = \
                    self.update_reason_record_and_fulfillment_center_dict(key, reason_record_dict,
                                                                          fulfillment_center_dict)
                move.return_created = True
                new_move = move.copy(default={
                    'product_id': move.product_id.id,
                    'product_uom_qty': qty,
                    'state': 'confirmed',
                    'location_id': move.location_dest_id.id,
                    'location_dest_id': location_dest_id,
                    'warehouse_id': warehouse and warehouse.id,
                    'origin_returned_move_id': move.id,
                    'procure_method': 'make_to_stock',
                    'date': return_date,
                    'to_refund': True,
                    'return_reason_id': reason_record_dict.get(reason, False),
                    'fba_returned_date': return_date,
                    'detailed_disposition': disposition,
                    'status_ept': status,
                    'amz_return_report_id': self.id,
                    'fulfillment_center_id': fulfillment_center_dict.get(fulfillment_center_id, False)
                })
                new_move._action_assign()
                new_move._set_quantity_done(qty)
                # write lot_id if origin move quant location usage is customer and quantty > 0 and
                # lot_id found in the quant.
                origin_move_quant_ids = move.move_line_ids.lot_id.quant_ids.filtered(
                    lambda ql: ql.location_id.usage == 'customer' and ql.quantity > 0 and ql.lot_id)
                if origin_move_quant_ids and not new_move.move_line_ids.lot_id:
                    new_move.move_line_ids.write({'lot_id': origin_move_quant_ids[0].lot_id.id})
                new_move._action_done()
        message = 'Customer Return Process Completed.'
        log_line_obj.create_common_log_line_ept(
            message=message, model_name=SALE_ORDER_RETURN_REPORT, module='amazon_ept', operation_type='import',
            res_id=self.id, amz_seller_ept=self.seller_id and self.seller_id.id or False)
        return True

    def update_reason_record_and_fulfillment_center_dict(self, key, reason_record_dict, fulfillment_center_dict):
        """
        Define method for update Reason Record and Fulfillment center dict.
        :param : key : details of return stock move
        :param : reason_record_dict : {reason : reason_record_id}
        :param : fulfillment_center_fulfillment_center_dict : {fulfillment_center : fulfillment_center_id}
        :return: location_id (int), dict {}, dict {}
        """
        return_reason_obj = self.env['amazon.return.reason.ept']
        fulfillment_center_obj = self.env['amazon.fulfillment.center']
        disposition = key[4]
        warehouse = key[1]
        reason = key[5]
        fulfillment_center_id = key[7]
        location_dest_id = False
        if not location_dest_id and disposition == 'SELLABLE':
            location_dest_id = warehouse.lot_stock_id.id
        else:
            location_dest_id = warehouse.unsellable_location_id.id
        if reason not in reason_record_dict:
            reason_record = return_reason_obj.search([('name', '=', reason)], limit=1)
            if not reason_record:
                reason_record = return_reason_obj.create({'name': reason})
            reason_record_dict.update({reason: reason_record.id})
        if fulfillment_center_id not in fulfillment_center_dict:
            fulfillment_center = fulfillment_center_obj.search(
                [('center_code', '=', fulfillment_center_id),
                 ('seller_id', '=', self.seller_id.id)])
            fulfillment_center_dict.update({fulfillment_center_id: fulfillment_center.id})
        return location_dest_id, reason_record_dict, fulfillment_center_dict

    @api.model
    def get_warehouse(self, fulfillment_center_id, seller, amazon_order):
        """
        Find Warehouse from fulfillment center and seller id OR order id
        :param fulfillment_center_id: center_code
        :param seller: seller_id
        :param amazon_order:  sale.order(0
        :return: stock.warehouse()
        """
        fulfillment_center = self.env['amazon.fulfillment.center'].search(
            [('center_code', '=', fulfillment_center_id), ('seller_id', '=', seller)], limit=1)
        warehouse = fulfillment_center and fulfillment_center.warehouse_id or \
                    amazon_order.amz_instance_id and amazon_order.amz_instance_id.fba_warehouse_id \
                    or amazon_order.amz_instance_id.warehouse_id or False
        return warehouse

    def process_kit_type_product(self, sale_line_product, move_lines, returned_qty,
                                 warehouse, return_date, sku, disposition, reason,
                                 return_move_dict, status, fulfillment_center_id,
                                 remaning_move_qty):
        """
        Process BOM product's sale order line, get exploded products for KIT Type Products in
        order line
        :param sale_line_product: product.product()
        :param move_lines: stock.move()
        :param returned_qty:
        :param warehouse:
        :param return_date:
        :param sku:
        :param disposition:
        :param reason:
        :param return_move_dict:
        :param status:
        :param fulfillment_center_id:
        :param remaining_move_qty:
        :return:
        """
        skip_moves = []
        return_qty_dict = {}
        for move in move_lines:
            if move.product_id.id in skip_moves:
                continue
            one_set_product_dict = self.amz_return_report_get_set_product_ept(sale_line_product)
            if not one_set_product_dict:
                continue
            if returned_qty <= 0:
                continue
            bom_qty = 0.0
            for bom_line, line in one_set_product_dict:
                if bom_line.product_id.id == move.product_id.id:
                    bom_qty = line['qty']
                    break
            if bom_qty == 0.0:
                continue
            key = (
                move, warehouse, return_date, sku, disposition, reason, status,
                fulfillment_center_id)
            if move.product_id.id in return_qty_dict:
                new_returned_qty = return_qty_dict.get(move.product_id.id, 0.0)
            else:
                new_returned_qty = returned_qty
            final_return_qty = new_returned_qty * bom_qty
            if move.id in remaning_move_qty:
                get_remain_qty = remaning_move_qty.get(move.id, False)
            else:
                get_remain_qty = move.product_uom_qty
            if get_remain_qty >= final_return_qty:
                new_final_ret_qty = final_return_qty
                skip_moves.append(move.product_id.id)
            else:
                return_qty_dict.update({move.product_id.id: (final_return_qty - get_remain_qty) / bom_qty})
                new_final_ret_qty = get_remain_qty
            remaning_move_qty.update({move.id: get_remain_qty - new_final_ret_qty})
            if move not in return_move_dict:
                return_move_dict.update({move: {key: new_final_ret_qty}})
            else:
                qty = return_move_dict.get(move, {}).get(key, 0.0)
                return_move_dict[move][key] = qty + new_final_ret_qty
        return return_move_dict, remaning_move_qty

    def amz_return_report_get_set_product_ept(self, product):
        """
        Find BOM for phantom type only if Bill of Material type is Make to Order
        then for shipment report there are no logic to create Manufacturer Order.
        used to process FBM shipped orders
        :param product:
        :return:
        """
        try:
            bom_obj = self.env['mrp.bom']
            bom_point = bom_obj.sudo()._bom_find(products=product, company_id=self.company_id.id,
                                                 bom_type='phantom')
            bom_point = bom_point[product]
            from_uom = product.uom_id
            to_uom = bom_point.product_uom_id
            factor = from_uom._compute_quantity(1, to_uom) / bom_point.product_qty
            bom, lines = bom_point.explode(product, factor, picking_type=bom_point.picking_type_id)
            return lines
        except Exception:
            return {}

    @api.model
    def auto_import_return_report(self, args={}):
        """
        This method is used to import Sale Orders Return report via cron.
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env[AMZ_SELLER_EPT].browse(seller_id)
            if seller.return_report_last_sync_on:
                start_date = seller.return_report_last_sync_on
                start_date = datetime.strftime(start_date, AMAZON_DATETIME_FORMAT)
                start_date = datetime.strptime(str(start_date), AMAZON_DATETIME_FORMAT)
                start_date = start_date + timedelta(
                    days=seller.customer_return_report_days * -1 or -3)
            else:
                today = datetime.now()
                earlier = today - timedelta(days=30)
                start_date = earlier.strftime(AMAZON_DATETIME_FORMAT)
            date_end = datetime.now()
            date_end = date_end.strftime(AMAZON_DATETIME_FORMAT)

            return_report = self.create(
                {'report_type': 'GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA',
                 'seller_id': seller_id,
                 'start_date': start_date,
                 'end_date': date_end,
                 'state': 'draft',
                 'requested_date': datetime.now()
                 })
            return_report.with_context(is_auto_process=True).request_report()
            seller.write({'return_report_last_sync_on': date_end})
        return True

    @api.model
    def auto_process_return_order_report(self, args={}):
        """
        This method is used to process Sale Orders Return Report via cron.
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env[AMZ_SELLER_EPT].browse(seller_id)
            return_reports = self.search([('seller_id', '=', seller.id),
                                          ('state', 'in',
                                           ['_SUBMITTED_', '_IN_PROGRESS_', '_DONE_',
                                            'SUBMITTED', 'IN_PROGRESS', 'DONE', 'IN_QUEUE'])])
            for report in return_reports:
                if report.state not in ('_DONE_', 'DONE'):
                    report.with_context(is_auto_process=True).get_report_request_list()
                if report.report_document_id and report.state in ('_DONE_', 'DONE') and not report.attachment_id:
                    report.with_context(is_auto_process=True).get_report()
                if report.attachment_id:
                    report.with_context(is_auto_process=True).process_return_report_file()
                self.env.cr.commit()
        return True
