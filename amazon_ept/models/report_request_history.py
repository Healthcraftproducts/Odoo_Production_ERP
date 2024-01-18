# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import time

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ReportRequestHistory(models.Model):
    _name = "report.request.history"
    _description = 'report.request.history'
    _rec_name = 'report_request_id'

    @api.depends('seller_id')
    def _compute_company(self):
        for record in self:
            company_id = record.seller_id and record.seller_id.company_id.id or False
            if not company_id:
                company_id = self.env.user.company_id.id
            record.company_id = company_id

    report_request_id = fields.Char(size=256, string='Report Request ID')
    report_id = fields.Char(size=256, string='Report ID')
    report_type = fields.Char(size=256)
    start_date = fields.Datetime()
    end_date = fields.Datetime()
    requested_date = fields.Datetime(default=time.strftime("%Y-%m-%d %H:%M:%S"))
    state = fields.Selection(
        [('draft', 'Draft'), ('_SUBMITTED_', 'SUBMITTED'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
         ('_CANCELLED_', 'CANCELLED'), ('_DONE_', 'DONE'),
         ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('processed', 'PROCESSED'), ('imported', 'Imported'),
         ('partially_processed', 'Partially Processed'), ('closed', 'Closed')
         ],
        string='Report Status', default='draft')
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', copy=False)
    user_id = fields.Many2one('res.users', string="Requested User")
    company_id = fields.Many2one('res.company', string="Company", copy=False,
                                 compute="_compute_company", store=True)
    instance_id = fields.Many2one('amazon.instance.ept', string='Marketplace')

    @api.constrains('start_date', 'end_date')
    def _check_description(self):
        if self.start_date and self.end_date < self.start_date:
            raise ValidationError("Error!\n The start date must be precede its end date.")
        return True
