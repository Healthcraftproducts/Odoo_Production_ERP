# -*- coding: utf-8 -*-

from odoo import models, fields
from datetime import datetime
from dateutil.relativedelta import relativedelta


class hrAttendanceReport(models.TransientModel):
    _name = "hr.attendance.report.wizard"
    _description = "HR Attendance Report wizard"

    from_date = fields.Date("From Date", default=datetime.today().date() + relativedelta(day=1), required=True)
    to_date = fields.Date("To Date", default=datetime.today().date() + relativedelta(day=1, months=+1, days=-1), required=True)
    employee_id = fields.Many2many(
        "hr.employee", 'hr_attendance_summary_report_rel', 'employee_id', 'attendance_id', string="Employees")
    report_options = fields.Selection(
        [('summary', 'Summery'), ('Summary_with_horurs', 'Summary with Hours')], string="Options", default="summary")

    def attendance_report(self):
        data = {
            'model': 'hr.attendance',
            'from_date': self.from_date,
            'to_date': self.to_date,
            'employee_id': self.employee_id.ids,
            'report_options': self.report_options,
        }
        return self.env.ref('hr_attendance_summary_report.report_employee_attendance').report_action(self, data=data)
