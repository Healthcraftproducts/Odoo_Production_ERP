# -*- coding: utf-8 -*-
from odoo import api, fields, models,  _
import time
from odoo.exceptions import UserError
from ast import literal_eval
# import json
import xlwt
from io import StringIO
import base64
import platform
from datetime import datetime, timedelta

class SoInvXls(models.Model):
    _name = 'so.inv.xls'
    _description = 'So Invoice Comparision Report'

    name_data = fields.Char('Name', size=256,invisible=1)
    file_name = fields.Binary('Click to download', readonly=True)
    
class SoInvReport(models.AbstractModel):
    _name = 'report.hcp_so_inv_report.report_print'
    _description = "Invoice SO difference report"

    def get_so_difference(self, data):
        return_list = {}
        product_list2 = []
        start_date = data['form']['start_date']
        a = str(start_date) + ' 00:00:00'
        end_date = data['form']['end_date']
        c = str(end_date) + ' 23:59:59'
        #self.env.cr.execute('''Select so.name,so.date_order,so.amount_total as sales_total,so.state,ac.name,ac.date,ac.invoice_origin,ac.amount_total as invoice_total,ac.state from sale_order so inner join account_move ac on ac.invoice_origin = so.name where date_order  between %s and %s order by so.name''',(a,c,))
        self.env.cr.execute('''select so.name,product_uom_qty,qty_delivered,qty_invoiced from sale_order_line sol inner join sale_order so on so.id = sol.order_id''')
        b = self.env.cr.fetchall()
        new_d = []
        for x in b:
            if x not in new_d:
                new_d.append(x)
        for data in new_d:
            product_detail2 = []
            #so_date = data[1]
            #so_actual_date = so_date.date()
            #invoice_date = data[5]
            product_detail2.append(data[0])
            product_detail2.append(data[1])
            #product_detail2.append(so_actual_date)
            product_detail2.append(data[2])
            product_detail2.append(data[3])
            #product_detail2.append(data[4])
            #product_detail2.append(invoice_date)
            #product_detail2.append(data[6])
            #product_detail2.append(data[7])
            #product_detail2.append(data[8])
            product_list2.append(product_detail2)
        return_list['quant_ids'] = product_list2
        return return_list


    def print_so_invoice_xls_report(self,data):
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("SO and Invoice Diff Report")
        format1 = xlwt.easyxf('font: bold 1, color white;\
                     pattern: pattern solid, fore_color black;')
        date_format = xlwt.XFStyle()
        date_format.num_format_str = 'dd/mm/yyyy'
        first_col = sheet.col(0)
        two_col = sheet.col(1)
        three_col = sheet.col(2)
        fourth_col = sheet.col(3)
        #fifth_col = sheet.col(4)
        #sixth_col = sheet.col(5)
        #seventh_col = sheet.col(6)
        #eight_col = sheet.col(7)
        #nine_col = sheet.col(8)
        
        sheet.write(0,0,'SO Name',format1)
        sheet.write(0,1,'Order Qty',format1)
        sheet.write(0,2,'Delivered Qty',format1)
        sheet.write(0,3,'Invoiced Qty',format1)
        #sheet.write(0,4,'Invoice #',format1)
        #sheet.write(0,5,'Invoice Date',format1)
        #sheet.write(0,6,'Invoice Origin',format1)
        #sheet.write(0,7,'Invoice Total',format1)
        #sheet.write(0,8,'Invoice State',format1)
        data = self.get_so_difference(data)
        dt = data.get('quant_ids')
        row_number = 1
        for value in dt:
            sheet.write(row_number,0,value[0])
            sheet.write(row_number,1,value[1])
            sheet.write(row_number,2,value[2])
            sheet.write(row_number,3,value[3])
            #sheet.write(row_number,4,value[4])
            #sheet.write(row_number,5,value[5],date_format)
            #sheet.write(row_number,6,value[6])
            #sheet.write(row_number,7,value[7])
            #sheet.write(row_number,8,value[8])
            row_number +=1
        output = StringIO()
        if platform.system() == 'Linux':
            filename = ('/tmp/Invoice SO Diff Report' +'.xls')
        else:
            filename = ('Invoice SO Diff Report' +'.xls')

        workbook.save(filename)
        fp = open(filename, "rb")
        file_data = fp.read()
        out = base64.encodebytes(file_data)
        # Files actions
        attach_vals = {
                'name_data': 'Invoice SO Diff Report'+ '.xls',
                'file_name': out,
        }
        act_id = self.env['so.inv.xls'].create(attach_vals)
        fp.close()
        return act_id


