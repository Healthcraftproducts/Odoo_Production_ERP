from urllib import response
import json
import io
from odoo import api, fields, models, _
import time, re, xlwt, base64, math, itertools
import dateutil.parser
from datetime import datetime, timedelta,date
from io import BytesIO
from dateutil.relativedelta import relativedelta
import logging
import re
from odoo.exceptions import ValidationError, RedirectWarning, UserError

class OperatorBOMEfficiencyReport(models.TransientModel):
    _name = 'operator.bom.efficiency.report'

    file_name = fields.Binary('BOM Efficiency Report', readonly=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)

    state = fields.Selection([('choose', 'choose'), ('get', 'get')],
                             default='choose')
    summary_data = fields.Char('Name', size=256)
    attachment_id = fields.Many2one('ir.attachment', 'Attachment')

    def print_operator_bom_efficiency_report(self):
        # lines = self.get_lines()
        workbook = xlwt.Workbook()
        worksheet1 = workbook.add_sheet('BOM Efficiency')
        
        file_name = 'BOM Efficiency Report.xls'

        field_heading = ["User Name",
                         "Workcenter", "Department", "MO #", "Expected time(in min)",
                         "Real Time(in min)", 'User time(in min)',"BOM Efficiency"]
        headertext = xlwt.easyxf(
            "font: name Times New Roman, bold on,height 400;align:horizontal center,indent 1,vertical center, wrap 1; "
            "pattern: pattern solid, fore_colour white; borders: left thin, right thin, top thin, bottom thin;")
        headertext1 = xlwt.easyxf(
            "font: name Times New Roman, bold on,height 350;align:horizontal center,indent 1,vertical center, wrap 1; "
            "pattern: pattern solid, fore_colour white; borders: left thin, right thin, top thin, bottom thin,")
        subheadertext = xlwt.easyxf(
            "font: name Times New Roman, bold on,height 350;align:horizontal center,indent 1,vertical center, wrap 1; "
            "pattern: pattern solid, fore_colour white; borders: left thin, right thin, top thin, bottom thin;")
        filter_criteria = xlwt.easyxf(
            "font: name Times New Roman, bold on,height 300;align:horizontal center,indent 1,vertical center, wrap 1; "
            "pattern: pattern solid, fore_colour white; borders: left thin, right thin, top thin, bottom thin,"
            "left_color black,right_color black,top_color black,bottom_color black,;")
        format3 = xlwt.easyxf('align: horiz center; borders: \
                             left thin, right thin, top thin, bottom thin;')
        format6 = xlwt.easyxf('align: horiz right; borders: \
                             left thin, right thin, top thin, bottom thin;font: bold on,height 280;')
        format4 = xlwt.easyxf('align: horiz center; borders: \
                             left thin, right thin, top thin, bottom thin;pattern: pattern solid, fore_colour pink;')
        format5 = xlwt.easyxf('align: horiz center; borders: \
                             left thin, right thin, top thin, bottom thin;pattern: pattern solid, fore_colour green;')
        start_date = self.start_date.strftime("%Y-%m-%d")
        end_date = self.end_date.strftime("%Y-%m-%d")
        header = "BOM Efficiency Report(" +  start_date + ' to ' + end_date + ')'
        worksheet1.write_merge(1, 1, 1, 8, header, headertext1)
        worksheet1.col(1).width = 8000
        worksheet1.col(2).width = 8000
        worksheet1.col(3).width = 8000
        worksheet1.col(4).width = 8000
        worksheet1.col(5).width = 8000
        worksheet1.col(6).width = 8000
        worksheet1.col(7).width = 8000
        worksheet1.col(8).width = 8000
        worksheet1.row(1).height_mismatch = True
        worksheet1.row(1).height = 435
        worksheet1.row(2).height_mismatch = True
        worksheet1.row(2).height = 375
        worksheet1.set_panes_frozen(True)
        worksheet1.set_horz_split_pos(3)
        for index, header in enumerate(field_heading, start=1):
            worksheet1.write(2, index, header, filter_criteria)
        cr = self._cr
        query = '''select productivity.user_id,workorder.id as workorder_id,sum(productivity.duration) as user_duration
					from mrp_workcenter_productivity productivity 
					join mrp_workorder workorder on workorder.id=productivity.workorder_id
					where productivity.date_start >= '%s' and productivity.date_end <= '%s'
					group by productivity.user_id,workorder.id
					order by workorder.id'''%(self.start_date,self.end_date)
        cr.execute(query)
        wo_records = self.env.cr.dictfetchall()
        #user_ids = wo_records = self.env['mrp.workcenter.productivity'].sudo().search([('date_start','>=',self.start_date),('date_end','<=',self.end_date)]).user_id
        #user_ids = list(set(user_ids))
        for index,wo_record in enumerate(wo_records):
            user_name = self.env['res.users'].sudo().search([('id','=',wo_record['user_id'])]).name
            workorder_record = self.env['mrp.workorder'].sudo().search([('id','=',wo_record['workorder_id'])])
            worksheet1.write(index+3, 1, user_name or '',format3)
            worksheet1.write(index+3, 2, workorder_record.workcenter_id.code or '',format3)
            worksheet1.write(index+3, 3, workorder_record.workcenter_department.capitalize() if workorder_record.workcenter_department else '',format3)
            worksheet1.write(index+3, 4, workorder_record.production_id.name or '',format3)
            worksheet1.write(index+3, 5, (workorder_record.duration_expected) or 0,format3)
            worksheet1.write(index+3, 6, (workorder_record.duration) or 0,format3)
            worksheet1.write(index+3, 7, (wo_record['user_duration']) or 0,format3)
            efficiency = 0
            if (workorder_record.duration_expected) != 0  and (workorder_record.duration) != 0:
               efficiency = (workorder_record.duration_expected) / (workorder_record.duration)
            worksheet1.write(index+3, 8, round(efficiency, 2)or 0,format3)
        fp = io.BytesIO()
        workbook.save(fp)
        self.write({'state': 'get', 'file_name': base64.encodestring(fp.getvalue()), 'summary_data': file_name})
        fp.close()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'operator.bom.efficiency.report',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'target': 'new',
        }