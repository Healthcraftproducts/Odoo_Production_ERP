from odoo import models, fields, api
import io  # To handle in-memory streams
import base64  # To encode the Excel file for download
import xlsxwriter  # To create Excel files
from odoo.tools import date_utils


class SaleExcelReport(models.TransientModel):
    _name = "sale.excel.report.wizard"
    _description = "Excel Report Wizard"

    current_date = fields.Date(
        string="Invoice Date",
        default=lambda self: fields.Date.context_today(self)
    )

    invoice_id = fields.Many2many(
        'account.move',
        string="Invoices",
    )

    user_id = fields.Many2one(
        'res.users',
        string='Prepared By',
        readonly=False,
        store=True,
        default=lambda self: self.env.user,
    )

    @api.onchange('current_date')
    def _onchange_current_date(self):
        if self.current_date:
            invoices = self.env['account.move'].search([
                ('invoice_date', '=', self.current_date),
                ('state', '=', 'posted'), ('move_type', 'in', ['out_invoice', 'out_receipt']),
                ('partner_shipping_id.country_id.code', '=', 'US')])
            self.invoice_id = invoices
        else:
            self.invoice_id = False

    def action_print_excel_report(self, ):
        workbook_stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(workbook_stream)
        worksheet = workbook.add_worksheet("CrossBorderReport")
        date_format = workbook.add_format({'num_format': 'mm/dd/yyyy'})

        worksheet.set_column(1, 3, 14)
        worksheet.set_column(1, 10, 14)

        bold_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'border': True,
            'align': 'centre',
            'valign': 'vcenter',
        })
        merge_formats = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bold': True,
            'border': True,
        })
        bold_format_small = workbook.add_format({
            'bold': True,
            'align': 'left',
            'valign': 'top',
            'font_size': 11,
            'border': True,
            'num_format': 'mm/dd/yyyy'
        })
        format_small = workbook.add_format({
            'align': 'left',
            'valign': 'top',
            'font_size': 11,
            'border': True,
            'num_format': 'mm/dd/yyyy'
        })
        bold_format_right_align = workbook.add_format({
            'bold': True,
            'align': 'right',
            'font_size': 11,
            'border': True,
        })
        bold_format_left_align = workbook.add_format({
            'align': 'left',
            'border': True,
        })
        bold_align = workbook.add_format({
            'bold': True,
            'align': 'right',
            'border': True,
        })
        merge_format = workbook.add_format({
            'align': 'left',
            'font': 'Arial',
            'valign': 'vcenter',
            'border': True,
            'text_wrap': True,
            'font_size': 11, })
        merge_formates = workbook.add_format({
            'align': 'center',
            'border': True, })
        border_format = workbook.add_format({
            'border': True,
        })
        title = "Cross Border Report"
        worksheet.merge_range('B1:I2', title, bold_format)
        address = ''
        if self.env.user.company_id.name:
            address += self.env.user.company_id.name + '\n'
        if self.env.user.company_id.street:
            address += self.env.user.company_id.street + '\n'
        if self.env.user.company_id.street2:
            address += self.env.user.company_id.street2 + '\n'
        if self.env.user.company_id.city:
            address += self.env.user.company_id.city + '\n'
        if self.env.user.company_id.state_id:
            address += self.env.user.company_id.state_id.name + '\n'
        if self.env.user.company_id.country_id:
            address += self.env.user.company_id.country_id.name

        consignee = "A. N. DERINGER" + '\n' + "835 Commerce Park Drive" + '\n' + 'Ogdensburg NY 13669'
        pickup_date = self.current_date
        prepared_by = self.user_id.name

        worksheet.merge_range('C4:D8', '', merge_format)
        worksheet.write('B4', "Shipper:", bold_format_small)
        worksheet.write('C4', address, merge_format)
        worksheet.merge_range('C11:D13', '', merge_format)
        worksheet.write('B11', "Consignee:", bold_format_small)
        worksheet.write('C11', consignee, merge_format)
        worksheet.write('H4', "PICKUP DATE:", bold_format_small)
        worksheet.write('I4', pickup_date, format_small)
        worksheet.write('H7', "PREPARED BY:", bold_format_small)
        worksheet.write('I7', prepared_by, format_small)
        worksheet.write('B16', "B/L:", bold_format_small)
        worksheet.write('C16', " ", format_small)
        worksheet.write('E16', "PCS:", bold_format_small)
        worksheet.write('F16', " ", format_small)
        worksheet.write('H16', "WEIGHT:", bold_format_small)
        worksheet.write('I16', " ", format_small)

        # Write the column headers
        worksheet.write('B21', "SNO", bold_format_small)
        worksheet.write('C21', "INVOICE ID", bold_format_small)
        worksheet.write('D21', "SUB TOTAL", bold_format_right_align)
        worksheet.set_column("B:B", 10)
        worksheet.set_column("C:D", 13)
        worksheet.set_column("E:F", 20)
        worksheet.set_column("G:H", 15)
        worksheet.set_column("I:J", 15)
        worksheet.write('E21', "SHIPPING CHARGE", bold_format_right_align)
        worksheet.write('F21', "TOTAL NOT INC.SHIP", bold_format_right_align)

        row = 21
        s_no = 1
        total_amount = 0
        shipping_amount = 0
        total_shipping_amount = 0
        for invoice in self.invoice_id:
            worksheet.write(row, 1, s_no, bold_format_left_align)
            worksheet.write(row, 2, invoice.name, border_format)
            worksheet.write(row, 3, invoice.amount_total, border_format)
            vat = 0
            for line in invoice.invoice_line_ids:
                if line.account_id.code == '31900':
                    vat = line.inv_line_amount
            sat = invoice.amount_total - vat
            sat = abs(sat)
            worksheet.write(row, 4, vat, border_format)
            worksheet.write(row, 5, sat, border_format)
            total_amount += invoice.amount_total
            shipping_amount += vat
            total_shipping_amount += sat
            row += 1
            s_no += 1
        worksheet.write(row, 2, "TOTAL", bold_align)
        worksheet.write(row, 3, total_amount, bold_align)
        worksheet.write(row, 4, shipping_amount, bold_align)
        worksheet.write(row, 5, total_shipping_amount, bold_align)
        worksheet.write('B47', " ", bold_align)

        s_no -= 1
        worksheet.merge_range('D18:E18', "TOTAL # OF ORDERS:", merge_formats)
        worksheet.write('F18', s_no, merge_formates)

        workbook.close()
        workbook_stream.seek(0)
        workbook_data = workbook_stream.read()

        attachment_data = {
            'name': "Cross Border Report.xlsx",
            'datas': base64.b64encode(workbook_data),
            'res_model': 'sale.excel.report.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }

        attachment = self.env['ir.attachment'].create(attachment_data)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
