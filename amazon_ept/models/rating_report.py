# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class and methods to get Seller Rating Report from Amazon.
"""
import time
import base64
import csv
from io import StringIO
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .. reportTypes import ReportType

COMMON_LOG_LINES_EPT = 'common.log.lines.ept'
SALE_ORDER = 'sale.order'
IR_MODEL = 'ir.model'
RATING_RATING = 'rating.rating'
AMZ_SELLER_EPT = 'amazon.seller.ept'
RATING_REPORT_HISTORY = 'rating.report.history'
AMZ_SHIPPING_REPORT_REQUEST_HISTORY = 'shipping.report.request.history'
DATE_YMDHMS = "%Y-%m-%d %H:%M:%S"
DATE_YMDTHMS = "%Y-%m-%dT%H:%M:%S"


class RatingReportHistory(models.Model):
    """
    Added class to get seller rating report
    """
    _name = "rating.report.history"
    _description = "Rating Report History"
    _inherit = ['mail.thread', 'amazon.reports']
    _order = 'id desc'

    @api.depends('seller_id')
    def _compute_company(self):
        for record in self:
            company_id = record.seller_id.company_id.id if record.seller_id else False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    def _compute_rating_count(self):
        rating_obj = self.env[RATING_RATING]
        self.rating_count = rating_obj.search_count([('amz_rating_report_id', '=', self.id)])

    def _compute_log_count(self):
        """
        Find all log associated with this report
        :return:
        """
        log_lines_obj = self.env[COMMON_LOG_LINES_EPT]
        model_id = self.env[IR_MODEL]._get(RATING_REPORT_HISTORY).id
        self.log_count = log_lines_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id)])

    name = fields.Char(size=256)
    state = fields.Selection(
        [('draft', 'Draft'), ('SUBMITTED', 'SUBMITTED'), ('_SUBMITTED_', 'SUBMITTED'),
         ('IN_QUEUE', 'IN_QUEUE'), ('IN_PROGRESS', 'IN_PROGRESS'),
         ('_IN_PROGRESS_', 'IN_PROGRESS'), ('DONE', 'DONE'), ('_DONE_', 'Report Received'),
         ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('FATAL', 'FATAL'),
         ('processed', 'PROCESSED'),  ('CANCELLED', 'CANCELLED'), ('_CANCELLED_', 'CANCELLED')],
        string='Report Status', default='draft')
    seller_id = fields.Many2one(AMZ_SELLER_EPT, string='Seller', copy=False,
                                help="Select Seller id from you wanted to get Rating Report.")
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")
    instance_id = fields.Many2one("amazon.instance.ept", string="Marketplace")
    report_id = fields.Char('Report ID', readonly='1')
    report_type = fields.Char(size=256, help="Amazon Report Type")
    report_request_id = fields.Char('Report Request ID', readonly='1')
    report_document_id = fields.Char(string='Report Document ID',
                                     help="Report Document id to recognise unique request document reference")
    start_date = fields.Datetime(help="Report Start Date")
    end_date = fields.Datetime(help="Report End Date")
    requested_date = fields.Datetime(default=time.strftime(DATE_YMDHMS), help="Report Requested Date")
    user_id = fields.Many2one('res.users', string="Requested User",
                              help="Track which odoo user has requested report")
    company_id = fields.Many2one('res.company', string="Company", copy=False,
                                 compute="_compute_company", store=True)
    rating_count = fields.Integer(compute="_compute_rating_count", store=False)
    log_count = fields.Integer(compute="_compute_log_count", store=False)
    amz_rating_report_ids = fields.One2many(RATING_RATING, 'amz_rating_report_id', string="Ratings")

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        """
        This Method relocates check seller and write start date and end date.
        :return: This Method return updated value.
        """
        if self.seller_id:
            self.start_date = datetime.now() - timedelta(self.seller_id.rating_report_days)
            self.end_date = datetime.now()

    def unlink(self):
        """
        This Method if report is processed then raise UserError.
        """
        for report in self:
            if report.state == 'processed':
                raise UserError(_('You cannot delete processed report.'))
        return super(RatingReportHistory, self).unlink()

    @api.model
    def default_get(self, fields):
        """
        Inherited method which help to get default fields values.
        """
        res = super(RatingReportHistory, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': ReportType.GET_SELLER_FEEDBACK_DATA})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """
        Inherited method which help to get and set Rating Report sequence.
        """
        for vals in vals_list:
            sequence_id = self.env.ref('amazon_ept.seq_rating_report_job', raise_if_not_found=False)
            report_name = self.env['ir.sequence'].get_id(sequence_id.ids[0]) if sequence_id else '/'
            vals.update({'name': report_name})
        return super(RatingReportHistory, self).create(vals_list)

    def list_of_process_logs(self):
        """
        List All Mismatch Details for Rating Report.
        :return:
        """
        model_id = self.env[IR_MODEL]._get(RATING_REPORT_HISTORY).id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + "), ('model_id','='," + str(model_id) + ")]",
            'name': 'Rating Report Logs',
            'view_mode': 'tree,form',
            'res_model': COMMON_LOG_LINES_EPT,
            'type': 'ir.actions.act_window',
        }
        return action

    @api.model
    def auto_import_rating_report(self, args={}):
        """
        This Method relocate import rating using crone.
        :param args: This Argument relocate seller id when the crone run in this argument given amazon seller id
        :return: This Method Return Boolean(True).
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env[AMZ_SELLER_EPT].browse(seller_id)
            if seller.rating_report_last_sync_on:
                start_date = seller.rating_report_last_sync_on
                start_date = datetime.strftime(start_date, DATE_YMDHMS)
                start_date = datetime.strptime(str(start_date), DATE_YMDHMS)
                start_date = start_date + timedelta(days=seller.rating_report_days * -1 or -3)

            else:
                start_date = datetime.now() - timedelta(days=30)
                start_date = start_date.strftime(DATE_YMDHMS)
            date_end = datetime.now()
            date_end = date_end.strftime(DATE_YMDHMS)
            report_type = ReportType.GET_SELLER_FEEDBACK_DATA
            rating_report = self.create({'report_type': report_type,
                                         'seller_id': seller_id,
                                         'start_date': start_date,
                                         'end_date': date_end,
                                         'state': 'draft',
                                         'requested_date': time.strftime(DATE_YMDHMS)
                                         })
            rating_report.with_context(is_auto_process=True).request_report()
            seller.write({'rating_report_last_sync_on': date_end})
        return True

    @api.model
    def auto_process_rating_report(self, args={}):
        """
        This Method Relocate auto process rating rating using crone.
        :param args: This Argument relocate seller id when the crone run in this argument given amazon seller id
        :return: This Method Return Boolean(True).
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env[AMZ_SELLER_EPT].browse(seller_id)
            rating_report = self.search([('seller_id', '=', seller.id),
                                         ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_', '_DONE_',
                                                          'SUBMITTED', 'IN_PROGRESS', 'DONE','IN_QUEUE'])])
            for report in rating_report:
                if report.state not in ('_DONE_', 'DONE'):
                    report.with_context(is_auto_process=True).get_report_request_list()
                if report.report_document_id and report.state in ('_DONE_', 'DONE') and not report.attachment_id:
                    report.with_context(is_auto_process=True).get_report()
                if report.attachment_id:
                    report.with_context(is_auto_process=True).process_rating_report()
                self._cr.commit()
        return True

    def list_of_rating(self):
        """
        This Method relocate list of amazon rating.
        :return:
        """
        rating_obj = self.env[RATING_RATING]
        records = rating_obj.search([('amz_rating_report_id', '=', self.id)])
        action = {
            'domain': "[('id', 'in', " + str(records.ids) + " )]",
            'name': 'Amazon Rating',
            'view_mode': 'tree,form',
            'res_model': RATING_RATING,
            'type': 'ir.actions.act_window',
        }
        return action

    def create_amazon_report_attachment(self, result):
        """
        Get Rating Report as an attachment in Rating reports form view.
        """
        seller = self.seller_id
        result = result.get('document', '')
        result = result.encode()
        result = base64.b64encode(result)
        file_name = "Rating_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'

        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': result,
            'res_model': 'mail.compose.message',
            'type': 'binary'
        })
        self.message_post(body=_("<b>Rating Report Downloaded</b>"),
                          attachment_ids=attachment.ids)
        self.write({'attachment_id': attachment.id})
        seller.write({'rating_report_last_sync_on': datetime.now()})

    def check_rating_report_configuration_ept(self):
        """
        Define method for check rating report attachment and seller
        configured in rating report record.
        """
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers(
                'ir_cron_process_rating_request_report_seller_', self.seller_id.id)
        if not self.attachment_id:
            raise UserError(_("There is no any report are attached with this record."))
        if not self.seller_id:
            raise UserError(_("Seller is not defind for processing report"))

    def process_rating_report(self):
        """
        This Method process rating report.
        :return:This Method return boolean(True/False).
        """
        self.ensure_one()
        self.check_rating_report_configuration_ept()
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        sale_order_obj = self.env[SALE_ORDER]
        rating_obj = self.env[RATING_RATING]
        ir_model = self.env[IR_MODEL]
        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')
        model_id = self.env[IR_MODEL]._get(RATING_REPORT_HISTORY).id
        ir_model = ir_model.search([('model', '=', SALE_ORDER)])
        for row in reader:
            amz_order_id = row.get('Order ID', '')
            amz_rating_value = row.get('Rating', '')
            amz_rating_comment = row.get('Comments', '')
            amz_your_response = row.get('Your Response', '')
            amz_rating_date = row.get('Date', '')
            try:
                amz_rating_date = datetime.strptime(amz_rating_date, '%m/%d/%y')
            except Exception:
                amz_rating_date = datetime.strptime(amz_rating_date, '%d/%m/%y')
            amazon_sale_order = sale_order_obj.search(
                [('amz_order_reference', '=', amz_order_id),
                 ('amz_instance_id', 'in', self.seller_id.instance_ids.ids)])
            if not amazon_sale_order:
                message = 'This Order %s does not exist in odoo' % (amz_order_id)
                common_log_line_obj.create_common_log_line_ept(
                    message=message, model_name='rating.report.history', module='amazon_ept', operation_type='import',
                    res_id=self.id, mismatch_details=True, order_ref=amz_order_id,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False)
                continue
            amazon_order_rating = rating_obj.search(
                [('res_model', '=', SALE_ORDER), ('res_id', '=', amazon_sale_order.id)])
            if not amazon_order_rating:
                rating_obj.create({
                    'rating': float(amz_rating_value) if amz_rating_value is not None else False,
                    'feedback': amz_rating_comment,
                    'res_model_id': ir_model.id,
                    'res_id': amazon_sale_order.id,
                    'consumed': True,
                    'partner_id': amazon_sale_order.partner_id.id,
                    'amz_instance_id': amazon_sale_order.amz_instance_id.id,
                    'amz_fulfillment_by': amazon_sale_order.amz_fulfillment_by,
                    'amz_rating_report_id': self.id,
                    'publisher_comment': amz_your_response,
                    'amz_rating_submitted_date': amz_rating_date
                })
            else:
                message = 'For This Order %s rating already exist in odoo' % amz_order_id
                common_log_line_obj.create_common_log_line_ept(
                    message=message, model_name='rating.report.history', module='amazon_ept', operation_type='import',
                    res_id=self.id, order_ref=amz_order_id,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False)
        self.write({'state': 'processed'})
        return True
