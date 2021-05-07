# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from ast import literal_eval
from datetime import datetime, timedelta

class SoInvDiff(models.TransientModel):
    _name = "so.inv.diff"
    _description = "So Invoice Difference"

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    def print_so_notification_report_xls(self):
        data = {}
        data['form'] = (self.read(['start_date', 'end_date'])[0])
        res=self.env['report.hcp_so_inv_report.report_print'].sudo().print_so_invoice_xls_report(data=data)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'so.inv.xls',
            'res_id': res.id,
            'view_type': 'form',
            'view_mode': 'form',
            'context': self.env.context,
            'target': 'new',
            }
