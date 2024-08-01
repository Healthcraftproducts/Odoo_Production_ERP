# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class and methods to request for VCS tax report, import and process that report.
"""

import time
import base64
from io import StringIO
import csv
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.iap.tools import iap_tools
from ..endpoint import DECODE_ENDPOINT

_logger = logging.getLogger("Amazon")
AMZ_SELLER_EPT = 'amazon.seller.ept'
COMMON_LOG_LINES_EPT = 'common.log.lines.ept'
DATE_YMDHMS = "%Y-%m-%d %H:%M:%S"
ORDER_ID = 'Order ID'


class VcsTaxReport(models.Model):
    """
    Added class to import amazon VCS tax report.
    """
    _name = 'amazon.vcs.tax.report.ept'
    _description = 'Amazon VCS Tax Report'
    _inherit = ['mail.thread', 'amazon.reports']
    _order = 'id desc'

    def _compute_log_count(self):
        """
        Sets count of log lines for the VCS report.
        """
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        model_name = self._table.replace('_', '.')
        model_id = self.env['ir.model']._get(model_name).id
        self.log_count = common_log_line_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id)])

    def _compute_no_of_invoices(self):
        """
        This method is used to count the number of invoices created via VCS tax report.
        """
        for record in self:
            record.invoice_count = len(record.invoice_ids)

    name = fields.Char(size=256)
    start_date = fields.Datetime(help="Report Start Date")
    end_date = fields.Datetime(help="Report End Date")
    report_request_id = fields.Char(size=256, string='Report Request ID',
                                    help="Report request id to recognise unique request")
    report_document_id = fields.Char(string='Report Document ID',
                                     help="Report Document id to recognise unique request document reference")
    report_id = fields.Char(size=256, string='Report ID',
                            help="Unique Report id for recognise report in Odoo")
    report_type = fields.Char(size=256, help="Amazon Report Type")
    seller_id = fields.Many2one(AMZ_SELLER_EPT, string='Seller', copy=False)
    state = fields.Selection([('draft', 'Draft'), ('SUBMITTED', 'SUBMITTED'),
                              ('_SUBMITTED_', 'SUBMITTED'), ('IN_QUEUE', 'IN_QUEUE'),
                              ('IN_PROGRESS', 'IN_PROGRESS'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
                              ('DONE', 'DONE'), ('_DONE_', 'DONE'), ('_DONE_NO_DATA_', 'DONE_NO_DATA'),
                              ('FATAL', 'FATAL'), ('partially_processed', 'Partially Processed'),
                              ('processed', 'PROCESSED'), ('CANCELLED', 'CANCELLED'),
                              ('_CANCELLED_', 'CANCELLED')], string='Report Status', default='draft')
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")
    auto_generated = fields.Boolean('Auto Generated Record ?', default=False)
    log_count = fields.Integer(compute="_compute_log_count")
    invoice_count = fields.Integer(compute="_compute_no_of_invoices",
                                   string="Invoices Count")
    invoice_ids = fields.Many2many('account.move', 'vcs_processed_invoices', string="Invoices")

    def unlink(self):
        """
        This method is inherited to do not allow to delete te processed report.
        """
        for report in self:
            if report.state == 'processed':
                raise UserError(_('You cannot delete processed report.'))
        return super(VcsTaxReport, self).unlink()

    @api.model
    def default_get(self, fields):
        """
        inherited to update the report type.
        """
        res = super(VcsTaxReport, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': 'SC_VAT_TAX_REPORT', })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """
        inherited to update the name of VCS tax report.
        """
        for vals in vals_list:
            sequence = self.env.ref('amazon_ept.seq_import_vcs_report_job', raise_if_not_found=False)
            report_name = sequence.next_by_id() if sequence else '/'
            vals.update({'name': report_name})
        return super(VcsTaxReport, self).create(vals_list)

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        """
        Based on seller it will update the start and end date.
        """
        value = {}
        if self.seller_id:
            start_date = datetime.now() + timedelta(
                days=self.seller_id.fba_vcs_report_days * -1 or -3)
            value.update({'start_date': start_date, 'end_date': datetime.now()})
        return {'value': value}

    def list_of_logs(self):
        """
        This method is used to display the number of logs from the VCS tax report.
        """
        log_line_obj = self.env['common.log.lines.ept']
        model_id = self.env['ir.model']._get('amazon.vcs.tax.report.ept').id
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + " ), ('model_id','='," + str(model_id) + ")]",
            'name': 'VCS Report Logs',
            'view_mode': 'tree,form',
            'res_model': COMMON_LOG_LINES_EPT,
            'type': 'ir.actions.act_window',
        }
        return action

    def create_amazon_report_attachment(self, result):
        """
        This method will create an VCS tax report based on the response
        """
        if result:
            file_name = "VCS_Tax_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
            attachment = self.env['ir.attachment'].create({
                'name': file_name,
                'datas': result.encode(),
                'res_model': 'mail.compose.message',
                'type': 'binary'
            })
            self.message_post(body=_("<b>VCS Tax Report Downloaded</b>"),
                              attachment_ids=attachment.ids)
            self.write({'attachment_id': attachment.id})
        return True

    def auto_import_vcs_tax_report(self, args={}):
        """
        Define method to auto process for import vcs tax report.
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env[AMZ_SELLER_EPT].search([('id', '=', seller_id)])
            start_date = datetime.now() + timedelta(days=seller.fba_vcs_report_days * -1 or -3)
            start_date = start_date.strftime(DATE_YMDHMS)
            date_end = datetime.now()
            date_end = date_end.strftime(DATE_YMDHMS)
            vcs_report = self.create({'report_type': 'SC_VAT_TAX_REPORT',
                                      'seller_id': seller_id,
                                      'start_date': start_date,
                                      'end_date': date_end,
                                      'state': 'draft',
                                      'auto_generated': True,
                                      })
            vcs_report.with_context(is_auto_process=True).request_report()
            seller.write({'vcs_report_last_sync_on': date_end})
        return True

    def check_amazon_vcs_required_records(self, row, amazon_seller, country_dict, instance_dict, ship_from_country_dict,
                                          warehouse_country_dict, line_no):
        """
        This method is used to check the required records to process the VCS reports.
        """
        marketplace_id = row.get('Marketplace ID', '')
        order_id = row.get(ORDER_ID, '')
        country = self.find_vcs_country_ept(country_dict, marketplace_id)
        if not country:
            message = 'Country with code %s not found in line %d' % (marketplace_id, line_no)
            return message, False, False

        instance = self.find_vcs_instance_ept(country, amazon_seller, instance_dict)
        if not instance:
            message = 'Instance with %s Country and %s Seller not found in line %d' \
                      % (country.name, amazon_seller.name, line_no)
            return message, False, False

        sale_order = self.find_amazon_vcs_sale_order_ept(row, instance, \
                                                         ship_from_country_dict,
                                                         warehouse_country_dict)
        if not sale_order:
            message = 'Sale Order - %s not found in line %d' % (order_id, line_no)
            return message, False, False

        if sale_order.state == 'draft':
            message = "Sale Order isn't Confirmed, Draft Quotation - %s found in line %d" \
                      % (order_id, line_no)
            return message, False, False

        return '', sale_order, instance

    def check_amz_vcs_attachment(self):
        """
        This method will check is vcs record contains the attachment
        """
        if not self.attachment_id:
            raise UserError(_("There is no any report are attached with this record."))
        return True

    def process_vcs_tax_report_file(self):
        """
        Updated code to set an invoice url and VCS invoice number into the invoice and refund
        """
        self.ensure_one()
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        model_name = self._table.replace('_', '.')
        previous_log_lines = common_log_line_obj.amz_find_mismatch_details_log_lines(self.id, model_name)
        if previous_log_lines:
            previous_log_lines.unlink()
        country_dict = {}
        instance_dict = {}
        ship_from_country_dict = {}
        warehouse_country_dict = {}
        amazon_prod_dict = {}
        vcs_invoice_ids = []
        line_no = 1
        commit_flag = 1
        transaction_line_ids = []
        amazon_seller = self.seller_id or False
        self.check_amz_vcs_attachment()

        imp_file = self.decode_amazon_encrypted_vcs_attachments_data(self.attachment_id)
        reader = csv.DictReader(imp_file, delimiter=',')
        for row in reader:
            line_no += 1
            order_id = row.get(ORDER_ID, '')
            sku = row.get('SKU', '')

            message = self.check_vcs_report_file_data_ept(row, line_no)
            if message:
                common_log_line_obj.create_common_log_line_ept(
                    message=message, model_name='amazon.vcs.tax.report.ept', default_code=sku, module='amazon_ept',
                    operation_type='import', res_id=self.id, mismatch_details=True,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False)
                continue

            message, sale_order, instance = self.check_amazon_vcs_required_records(
                row, amazon_seller, country_dict, instance_dict, ship_from_country_dict, warehouse_country_dict,
                line_no)
            if message:
                common_log_line_obj.create_common_log_line_ept(
                    message=message, model_name='amazon.vcs.tax.report.ept', default_code=sku, module='amazon_ept',
                    operation_type='import', res_id=self.id, mismatch_details=True,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False)
                continue

            fulfillment_by = sale_order.amz_fulfillment_by
            amz_prod = self.find_amazon_vcs_product_ept(amazon_prod_dict, sku, instance, fulfillment_by)
            if not amz_prod:
                message = 'Amazon Product not found with %s Seller SKU in line %d' % (sku, line_no)
                common_log_line_obj.create_common_log_line_ept(
                    message=message, model_name='amazon.vcs.tax.report.ept', default_code=sku, module='amazon_ept',
                    operation_type='import', res_id=self.id, mismatch_details=True,
                    amz_seller_ept=self.seller_id and self.seller_id.id or False)
                continue

            odoo_product_id = amz_prod.product_id.id if amz_prod.product_id else False
            if not odoo_product_id:
                continue

            vcs_invoice_ids, transaction_line_ids = self.process_vcs_report_data_ept(row, sale_order, odoo_product_id,
                                                                                     vcs_invoice_ids,
                                                                                     transaction_line_ids)
            if commit_flag == 10:
                self.env.cr.commit()
                commit_flag = 0
            commit_flag += 1

        self.write({'invoice_ids': [(4, vcs_invoice.id) for vcs_invoice in vcs_invoice_ids]})
        if not common_log_line_obj.amz_find_mismatch_details_log_lines(self.id, model_name, True):
            self.write({'state': 'processed'})
        else:
            self.write({'state': 'partially_processed'})
        return True

    def process_vcs_report_data_ept(self, row, sale_order, product_id, vcs_invoice_ids, transaction_line_ids):
        """
        This method will find the invoices or refunds and update the invoice details.
        """
        vcs_invoice_number = row.get('VAT Invoice Number', '')
        transaction_type = row.get('Transaction Type', '')
        invoice_type = 'out_invoice' if transaction_type == 'SHIPMENT' else 'out_refund'
        mismatch_str = 'Invoice' if invoice_type == 'out_invoice' else 'Refund invoice'
        _logger.info("Processing Sale Order %s" % (sale_order.name))
        invoices = sale_order.invoice_ids.filtered(
            lambda x: x.move_type == invoice_type and x.state != 'cancel' and not x.vcs_invoice_number)
        if not invoices:
            message = '%s not found for order %s' % (mismatch_str, sale_order.name)
            transaction_line_ids.append((0, 0, {'message': message, 'order_ref': sale_order.name}))
            return vcs_invoice_ids, transaction_line_ids

        invoices = invoices.filtered(lambda x: x.vcs_invoice_number != vcs_invoice_number)
        if len(invoices) > 1:
            invoices = invoices.invoice_line_ids.filtered( \
                lambda l: l.product_id.id == product_id).mapped('move_id')
            if len(invoices) > 1:
                invoices = invoices[0]

        if invoices and not invoices.vcs_invoice_number:
            invoices.write({'invoice_url': row.get('Invoice Url', ''),
                            'vcs_invoice_number': vcs_invoice_number})
            vcs_invoice_ids.append(invoices)
        return vcs_invoice_ids, transaction_line_ids

    def find_vcs_instance_ept(self, country, amazon_seller, instance_dict):
        """
        :param country: country record
        :param amazon_seller : amazon seller record
        :param instance_dict : instance dict
        This method will find the instance based on passed country.
        """
        instance_obj = self.env['amazon.instance.ept']
        instance = instance_obj.browse(instance_dict.get((country.id, amazon_seller.id), False))
        if not instance:
            instance = amazon_seller.instance_ids.filtered(lambda x: x.country_id.id == country.id)
            if instance:
                instance_dict.update({(country.id, amazon_seller.id): instance.id})
        return instance

    def check_vcs_report_file_data_ept(self, row, line_no):
        """
        :param row: VCS file data
        :param log_line_vals : log lines dict
        :param line_no : processing line no of file
        :return: This method will check the required data exist to process for
        update taxes in order and invoice lines.
        """
        marketplace_id = row.get('Marketplace ID', '')
        invoice_type = row.get('Transaction Type', '')
        order_id = row.get(ORDER_ID, '')
        sku = row.get('SKU', '')
        qty = int(row.get('Quantity', 0)) if row.get('Quantity', 0) else 0.0
        ship_from_country = row.get('Ship From Country', False)
        message = ''

        if not order_id:
            message = 'Order Id not found in line %d' % line_no
            return message

        if not marketplace_id:
            message = 'Marketplace Id not found for order reference %s in line %d' % (order_id, line_no)
            return message

        if not invoice_type:
            message = 'Invoice Type not found in line %d' % line_no
            return message

        if not sku:
            message = 'SKU not found for order reference %s in line %d' % (order_id, line_no)
            return message

        if invoice_type != 'SHIPMENT' and not qty:
            message = 'Qty to refund not found for order reference %s in line %d' % (order_id, line_no)
            return message

        if not ship_from_country:
            message = 'Ship from country not found for order reference %s in line %d' % (order_id, line_no)
            return message

        return message

    def find_vcs_country_ept(self, country_dict, marketplace_id):
        """
        :param country_dict : country dict
        :param marketplace_id: marketplace id
        :param  log_line_vals : log line data
        :param line_no : processing line no of file
        :return: This method wil find the country based on amazon_marketplace_code
         and also update the country dict.
        """

        res_country_obj = self.env['res.country']
        country = res_country_obj.browse(country_dict.get(marketplace_id, False))
        if not country:
            country = res_country_obj.search([('amazon_marketplace_code', '=', marketplace_id)], limit=1)
            if not country:
                country = res_country_obj.search([('code', '=', marketplace_id)], limit=1)
            if country:
                country_dict.update({marketplace_id: country.id})
        return country

    def find_amazon_vcs_product_ept(self, amazon_prod_dict, sku, instance, fulfillment_by):
        """
        :param amazon_prod_dict : product data dict.
        :param sku: sku
        :param  instance : instance recorc
        :param fulfillment_by : fulfillment_by
        This method will fine tha amazon product based on instance, sku
        and fulfillment_by and update the amazon product dict
        """

        amz_prod_obj = self.env['amazon.product.ept']
        amz_prod = amz_prod_obj.browse( \
            amazon_prod_dict.get((sku, instance.id, fulfillment_by), False))
        if not amz_prod:
            amz_prod = amz_prod_obj.search([('seller_sku', '=', sku), ('instance_id', '=', instance.id),
                                            ('fulfillment_by', '=', fulfillment_by)], limit=1)
            if amz_prod:
                amazon_prod_dict.update( \
                    {(sku, instance.id, fulfillment_by): amz_prod.id})
        return amz_prod

    def find_amazon_vcs_sale_order_ept(self, row, instance, ship_from_country_dict,
                                       warehouse_country_dict):
        """
        :param row : file line data
        :param ship_from_country_dict: ship from country dict
        :param  warehouse_country_dict : warehouse data dict based
        on ship from country
        This method will find the sale order.
        return : sale order record.
        """

        res_country_obj = self.env['res.country']
        order_id = row.get(ORDER_ID, False)
        sale_order_obj = self.env['sale.order']
        stock_warehouse_obj = self.env['stock.warehouse']

        ship_from_country = row.get('Ship From Country', False)

        sale_order = sale_order_obj.search(
            [('amz_instance_id', '=', instance.id),
             ('amz_order_reference', '=', order_id)])
        if len(sale_order) > 1:
            country = res_country_obj.browse(
                ship_from_country_dict.get(ship_from_country, False))
            if not country:
                country = res_country_obj.search([('code', '=', ship_from_country)], limit=1)
                if country:
                    ship_from_country_dict.update({ship_from_country: country.id})

            warehouses = stock_warehouse_obj.browse(warehouse_country_dict.get(country.id, False))
            if not warehouses:
                warehouses = stock_warehouse_obj.search([('partner_id.country_id', '=', country.id)])
                if warehouses:
                    warehouse_country_dict.update({country.id: warehouses.ids})

            sale_order = sale_order_obj.search([('amz_instance_id', '=', instance.id),
                                                ('amz_order_reference', '=', order_id),
                                                ('warehouse_id', 'in', warehouses.ids)],
                                               limit=1)

        return sale_order

    def auto_process_vcs_tax_report(self, args={}):
        """
        This method is used to auto process the vcs tax report.
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            vcs_reports = self.search(
                [('seller_id', '=', seller_id), ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_',
                                                                 'SUBMITTED', 'IN_PROGRESS','IN_QUEUE'])])
            for report in vcs_reports:
                if report.state not in ['_DONE_', 'DONE']:
                    report.with_context(
                        is_auto_process=True, amz_report_type='vcs_tax_report_spapi').get_report_request_list()
                if report.report_document_id and report.state in ['_DONE_', 'DONE'] and not report.attachment_id:
                    report.with_context(is_auto_process=True, amz_report_type='vcs_tax_report_spapi').get_report()
                    time.sleep(2)
                if report.attachment_id:
                    report.with_context(is_auto_process=True).process_vcs_tax_report_file()
                self._cr.commit()
                time.sleep(3)
        return True

    def get_amz_vcs_invoices(self):
        """
        Opens the tree view of Invoices.
        """
        return {
            'domain': "[('id', 'in', " + str(self.invoice_ids.ids) + " )]",
            'name': 'Invoices',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
        }

    def decode_amazon_encrypted_vcs_attachments_data(self, attachment_id):
        """
        Added method to decode the encrypted VCS attachments data.
        """
        common_log_line_obj = self.env[COMMON_LOG_LINES_EPT]
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        req = {'dbuuid': dbuuid, 'report_id': self.report_id, 'report_document_id': self.report_document_id,
               'datas': attachment_id.datas.decode(), 'amz_report_type': 'vcs_tax_report_spapi',
               'merchant_id': self.seller_id.merchant_id}
        response = iap_tools.iap_jsonrpc(DECODE_ENDPOINT, params=req, timeout=1000)
        if response.get('result', False):
            try:
                imp_file = StringIO(base64.b64decode(response.get('result')).decode())
            except Exception:
                imp_file = StringIO(base64.b64decode(response.get('result')).decode('ISO-8859-1'))
        elif self._context.get('is_auto_process', False):
            common_log_line_obj.create_common_log_line_ept(
                message='Error found in Decryption of Data %s' % response.get('error', ''),
                model_name='amazon.vcs.tax.report.ept', module='amazon_ept', operation_type='import', res_id=self.id,
                amz_seller_ept=self.seller_id and self.seller_id.id or False)
            return {}
        else:
            raise UserError(_(response.get('error', '')))
        return imp_file
