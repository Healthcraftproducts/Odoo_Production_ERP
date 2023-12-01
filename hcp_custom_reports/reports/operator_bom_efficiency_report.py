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
    _description = 'Operator Bom Efficiency Report'

    def get_defalut_today_date(self):
        today = datetime.today().date()
        time = datetime.strptime('00:00', '%H:%M').time()
        custm_date = datetime.combine(today, time) + timedelta(hours=5, minutes=0)
        return custm_date

    def get_defalut_to_date(self):
        today = datetime.today().date()
        time = datetime.strptime('23:59:59', '%H:%M:%S').time()
        custm_date = datetime.combine(today, time) + timedelta(hours=5, minutes=0)
        return custm_date
    
    file_name = fields.Binary('BOM Efficiency Report', readonly=True)
    start_date = fields.Datetime(string='Start Date',default=get_defalut_today_date, required=True)
    end_date = fields.Datetime(string='End Date',default=get_defalut_to_date, required=True)

    state = fields.Selection([('choose', 'choose'), ('get', 'get')],
                             default='choose')
    summary_data = fields.Char('Name', size=256)
    attachment_id = fields.Many2one('ir.attachment', 'Attachment')

    def print_operator_bom_efficiency_report(self):
        # lines = self.get_lines()
        workbook = xlwt.Workbook()
        worksheet1 = workbook.add_sheet('BOM Efficiency')
        
        file_name = 'BOM Efficiency Report.xls'

        field_heading = ["S.no","User Name",
                         "Work Center", "Department", "MO #", "Item Code", "Qty Produced", "Operations",
                         "Setup Time(in mm : ss)", "Cycle Time(in mm : ss)", "Total Cycle Time(in mm : ss)",
                         "Real Time(in mm : ss)","User Spent Time(in mm : ss)","Efficiency"]
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
        format3 = xlwt.easyxf(
            "font: name Times New Roman,height 220;align:horizontal center,indent 1,vertical center, wrap 1; "
            "pattern: pattern solid, fore_colour white; borders: left thin, right thin, top thin, bottom thin,"
            "left_color black,right_color black,top_color black,bottom_color black,;")
        # format3 = xlwt.easyxf('align: horiz center; borders: \
        #                      left thin, right thin, top thin, bottom thin;')
        format6 = xlwt.easyxf('align: horiz right; borders: \
                             left thin, right thin, top thin, bottom thin;font: name Times New Roman,height 220;')
        format4 = xlwt.easyxf('align: horiz center; borders: \
                             left thin, right thin, top thin, bottom thin;pattern: pattern solid, fore_colour pink;')
        format5 = xlwt.easyxf('align: horiz center; borders: \
                             left thin, right thin, top thin, bottom thin;pattern: pattern solid, fore_colour green;')
        start_date = self.start_date - timedelta(hours=5, minutes=0)
        end_date = self.end_date - timedelta(hours=5, minutes=0)
        header = "BOM Efficiency Report(" + str(start_date) + ' to ' + str(end_date) + ')'
        worksheet1.write_merge(0, 0, 0, 13, header, headertext1)
        worksheet1.col(0).width = 8000
        worksheet1.col(1).width = 8000
        worksheet1.col(2).width = 8000
        worksheet1.col(3).width = 8000
        worksheet1.col(4).width = 8000
        worksheet1.col(5).width = 8000
        worksheet1.col(6).width = 8000
        worksheet1.col(7).width = 8000
        worksheet1.col(8).width = 8000
        worksheet1.col(9).width = 8000
        worksheet1.col(10).width = 10000
        worksheet1.col(11).width = 8000
        worksheet1.col(12).width = 10000
        worksheet1.col(13).width = 8000
        worksheet1.col(14).width = 8000
        worksheet1.col(15).width = 8000
        #worksheet1.col(16).width = 8000
        worksheet1.row(0).height_mismatch = True
        worksheet1.row(0).height = 435
        worksheet1.row(1).height_mismatch = True
        worksheet1.row(1).height = 375
        worksheet1.set_panes_frozen(True)
        #worksheet1.set_horz_split_pos(2)
        style1 = xlwt.XFStyle()
        style1.num_format_str = '#,##0.00'
        borders = xlwt.Borders()
        borders.left = 1
        borders.right = 1
        borders.top = 1
        borders.bottom = 1
        style1.borders = borders
        alignment = xlwt.Alignment()  # Create Alignment
        alignment.horz = xlwt.Alignment.HORZ_RIGHT
        alignment.vert = xlwt.Alignment.VERT_CENTER
        style1.alignment = alignment
        font = xlwt.Font()  # Create the Font
        font.name = 'Times New Roman'
        font.height = 220  # 16 * 20, for 16 point
        style1.font = font
        for index, header in enumerate(field_heading, start=0):
            worksheet1.write(1, index, header, filter_criteria)
        cr = self._cr
        query = '''select productivity.user_id,workorder.id as workorder_id,sum(productivity.duration) as user_duration
					from mrp_workcenter_productivity productivity 
					join mrp_workorder workorder on workorder.id=productivity.workorder_id
					where productivity.date_start >= '%s' and productivity.date_end <= '%s'
					group by productivity.user_id,workorder.id
					order by workorder.id''' % (self.start_date, self.end_date)
        cr.execute(query)
        wo_records = self.env.cr.dictfetchall()
        # user_ids = wo_records = self.env['mrp.workcenter.productivity'].sudo().search([('date_start','>=',self.start_date),('date_end','<=',self.end_date)]).user_id
        # user_ids = list(set(user_ids))
        s_no = 1
        for index, wo_record in enumerate(wo_records):
            user_obj = self.env['res.users'].sudo().search([('id', '=', wo_record['user_id'])])
            user_name = user_obj.name
            user_id = user_obj.id
            workorder_record = self.env['mrp.workorder'].sudo().search([('id', '=', wo_record['workorder_id'])])
            work_order_productivity = self.env['mrp.workcenter.productivity'].sudo().search([('workorder_id', '=', workorder_record.id),('user_id','=',user_id)])
            total_duration = 0
            for records in work_order_productivity:
                total_duration += records.duration
            #HEM NEW
            expected_duration = '{0:02.0f}:{1:02.0f}'.format(*divmod(float(workorder_record.duration_expected) * 60, 60))
            setup_time_per_unit = '{0:02.0f}:{1:02.0f}'.format(*divmod(float(workorder_record.operation_id.setuptime_per_unit) * 60, 60))
            total_time = '{0:02.0f}:{1:02.0f}'.format(*divmod(float(workorder_record.operation_id.total_time) * 60, 60))
            setup_time_per_unit = '{0:02.0f}:{1:02.0f}'.format(*divmod(float(workorder_record.operation_id.setuptime_per_unit) * 60, 60))
            total_cycle_time = workorder_record.qty_produced * workorder_record.operation_id.total_time
            total_cy_tym_mins = '{0:02.0f}:{1:02.0f}'.format(*divmod(float(total_cycle_time) * 60, 60))
            overall_real_duration = '{0:02.0f}:{1:02.0f}'.format(*divmod(float(workorder_record.duration) * 60, 60))
            real_duration = '{0:02.0f}:{1:02.0f}'.format(*divmod(float(total_duration) * 60, 60))
            #HEM NEW END
            worksheet1.write(index + 2, 0,s_no or '', format3)
            worksheet1.write(index + 2, 1,user_name or '', format3)
            worksheet1.write(index + 2, 2,workorder_record.workcenter_id.code or '', format3)
            worksheet1.write(index + 2, 3,workorder_record.workcenter_department.capitalize() if workorder_record.workcenter_department else '',
                             format3)
            worksheet1.write(index + 2, 4,workorder_record.production_id.name or '', format3)
            product_item_code = self.env['product.product'].sudo().search([('id', '=', workorder_record.production_id.product_id.id)]).default_code
            #Item Code
            worksheet1.write(index + 2, 5,product_item_code or '', format3)
            #Quantity Produced
            worksheet1.write(index + 2, 6,workorder_record.qty_produced, style1)
            #Work Order Name
            worksheet1.write(index + 2, 7,workorder_record.name or '', format3)
            #Setup Time
            worksheet1.write(index + 2, 8,setup_time_per_unit or '00:00',style1)
            #Cycle Time
            worksheet1.write(index + 2, 9,total_time or '00:00', style1)
            #Total Cycle Time
            worksheet1.write(index + 2, 10,total_cy_tym_mins or '00:00', style1)
            #Expected Duration
            # worksheet1.write(index + 2, 11,expected_duration or '00:00', style1)
            #User Real Time
            worksheet1.write(index + 2, 12,real_duration or '00;00', style1)
            #Overall Real Time
            worksheet1.write(index + 2, 11,overall_real_duration or '00;00', style1)
            # worksheet1.write(index + 3, 13, (wo_record['user_duration']) or 0.00, style1)
            #bom_efficiency = 0.00
            #if (workorder_record.duration_expected) != 0.00 and (workorder_record.duration) != 0.00:
                #bom_efficiency = (workorder_record.duration_expected) / (workorder_record.duration) * 100
            #worksheet1.write(index + 2, 14, bom_efficiency or 0.00, style1)
            efficiency_per = 0.00
            if (total_cycle_time) != 0.00 and (workorder_record.duration) != 0.00:
                #efficiency = (workorder_record.duration) / (total_cycle_time) * 100
                efficiency = (total_cycle_time) / (workorder_record.duration) * 100
                efficiency_per = "%.2f" % round(efficiency, 2)
            worksheet1.write(index + 2, 13, str(efficiency_per) +'%', format6)
            s_no+=1

        fp = io.BytesIO()
        workbook.save(fp)

        self.write({'state': 'get', 'file_name': base64.encodebytes(fp.getvalue()), 'summary_data': file_name})
        fp.close()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'operator.bom.efficiency.report',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'target': 'new',
        }
