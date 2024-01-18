# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added shipped order data queue class to check the imported shipped order data and processed orders
from the shipped queue record.
"""

from odoo import models, fields, api

IR_MODEL = 'ir.model'
SHIPPED_ORDER_DATA_QUEUE_EPT = 'shipped.order.data.queue.ept'


class ShippedOrderDataQueue(models.Model):
    """
    Added class to store the shipped order information and process  shipped orders via created via
    """
    _name = "shipped.order.data.queue.ept"
    _description = 'Shipped Order Data Queue Ept'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"

    def _compute_queue_line_record(self):
        """
        This is used for count of total record of product queue line.
        :return: count
        """
        for order_queue in self:
            order_queue.queue_line_total_record = len(order_queue.shipped_order_data_queue_lines)
            order_queue.queue_line_draft_record = len(
                order_queue.shipped_order_data_queue_lines.filtered(lambda x: x.state == 'draft'))
            order_queue.queue_line_fail_record = len(
                order_queue.shipped_order_data_queue_lines.filtered(lambda x: x.state == 'failed'))
            order_queue.queue_line_done_record = len(
                order_queue.shipped_order_data_queue_lines.filtered(lambda x: x.state == 'done'))

    def _compute_total_logs(self):
        """
        Find all stock moves associated with this report
        :return:
        """
        log_lines_obj = self.env['common.log.lines.ept']
        model_id = self.env[IR_MODEL]._get(SHIPPED_ORDER_DATA_QUEUE_EPT).id
        self.log_count = log_lines_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id)])

    name = fields.Char(size=120, string='Name')
    amz_seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller',
                                    help="Unique Amazon Seller name")
    state = fields.Selection(
        [('draft', 'Draft'), ('partially_completed', 'Partially Completed'),
         ('completed', 'Completed')],
        default='draft')
    shipped_order_data_queue_lines = fields.One2many('shipped.order.data.queue.line.ept',
                                                     'shipped_order_data_queue_id',
                                                     string="Shipped Order Queue Lines")
    log_lines = fields.One2many('common.log.lines.ept', 'order_queue_data_id',
                                compute="_compute_log_lines", string="Log Lines")

    queue_line_total_record = fields.Integer(string='Total Records',
                                             compute='_compute_queue_line_record')
    queue_line_draft_record = fields.Integer(string='Draft Records',
                                             compute='_compute_queue_line_record')
    queue_line_fail_record = fields.Integer(string='Fail Records',
                                            compute='_compute_queue_line_record')
    queue_line_done_record = fields.Integer(string='Done Records',
                                            compute='_compute_queue_line_record')
    log_count = fields.Integer(compute="_compute_total_logs", string="Move Count",
                               help="Count number of created Stock Move", store=False)
    company_id = fields.Many2one('res.company', string="Company", copy=False,
                                 compute="_compute_company", store=True, help='ID of company')

    @api.model
    @api.depends('amz_seller_id')
    def _compute_company(self):
        """
        The below method sets company for a particular record
        """
        for record in self:
            company_id = record.amz_seller_id.company_id.id if record.amz_seller_id else False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    @api.model_create_multi
    def create(self, vals_list):
        """
        This method used to create a sequence for Shipped Order data.
        :param vals_list: value from base method
        :return: True
        """
        for vals in vals_list:
            seq = self.env['ir.sequence'].next_by_code('fbm_shipped_order_data_queue_ept_sequence') or '/'
            vals['name'] = seq
        return super(ShippedOrderDataQueue, self).create(vals_list)

    def _compute_log_lines(self):
        """
        List Shipped Orders Logs
        @author: Twinkal Chandarana
        :return:
        """
        for queue in self:
            log_lines_obj = self.env['common.log.lines.ept']
            model_id = self.env[IR_MODEL]._get(SHIPPED_ORDER_DATA_QUEUE_EPT).id
            domain = [('res_id', '=', queue.id), ('model_id', '=', model_id)]
            log_lines = log_lines_obj.search(domain)
            queue.log_lines = log_lines.ids if log_lines else False

    def process_amazon_shipped_order_data_queues(self, shipped_order_data_queues):
        """
        This method will process the shipped order data queues to create amazon orders
        """
        sale_order_obj = self.env['sale.order']
        for data_queue in shipped_order_data_queues:
            sale_order_obj.amz_create_sales_order(data_queue)
            self.amz_delete_processed_data_queue_lines(data_queue)
            self._cr.commit()
        return True

    def amz_delete_processed_data_queue_lines(self, data_queue):
        """
        Define this method for delete processed fbm orders data queue lines.
        :param: data_queue: shipped.order.data.queue.ept()
        :return : True
        """
        mail_activity_obj = self.env['mail.activity']
        model_id = self.env[IR_MODEL]._get(SHIPPED_ORDER_DATA_QUEUE_EPT).id
        status = data_queue.shipped_order_data_queue_lines.filtered(lambda x: x.state != 'done')
        if status:
            # Delete Done data queue lines for compliance of Amazon Rules
            data_queue.shipped_order_data_queue_lines.filtered(lambda x: x.state == 'done').unlink()
            data_queue.write({'state': 'partially_completed'})
        else:
            # Delete scheduled activity for the respective data queue record
            if mail_activity_obj.search([('res_model_id', '=', model_id), ('res_id', '=', data_queue.id)]):
                mail_activity_obj.search([('res_model_id', '=', model_id), ('res_id', '=', data_queue.id)]).unlink()
            # Delete Processed Data Queue
            data_queue.unlink()
        return True

    def process_orders(self):
        """
        This method is process the orders that are in queue.
        :return: True
        """
        shipped_order_data_queues = self if self else self.search([('state', '=', 'draft')])
        if shipped_order_data_queues:
            seller_ids = shipped_order_data_queues.mapped('amz_seller_id')
            for seller_id in seller_ids:
                cron_id = self.env.ref('amazon_ept.%s%d' % ("ir_cron_process_amazon_unshipped_orders_seller_",
                                                            seller_id.id), raise_if_not_found=False)
                if cron_id and cron_id.sudo().active:
                    res = cron_id.sudo().try_cron_lock()
                    if res and res.get('reason', {}):
                        shipped_order_data_queues = []
                        break
        if shipped_order_data_queues:
            self.process_amazon_shipped_order_data_queues(shipped_order_data_queues)
        return True
