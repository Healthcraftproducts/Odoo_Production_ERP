from odoo import models, fields, api
import io  # To handle in-memory streams
import base64  # To encode the Excel file for download
import xlsxwriter  # To create Excel files
from odoo.tools import date_utils
from openpyxl.styles.builtins import normal


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
            sale_orders = self.env['sale.order'].search([
                ('state', 'in', ['sent', 'sale', 'done']),
                ('partner_shipping_id.country_id.code', '=', 'US'),
                ('amz_fulfillment_by', '!=', 'FBA')
            ])
            invoices = self.env['account.move'].search([
                ('invoice_date', '=', self.current_date),
                ('state', '=', 'posted'),
                ('move_type', 'in', ['out_invoice', 'out_receipt']),
                ('partner_shipping_id.country_id.code', '=', 'US'),
                ('invoice_origin', 'in', sale_orders.mapped('name'))
            ])
            self.invoice_id = invoices
        else:
            self.invoice_id = False

    def action_print_excel_report(self, ):
        workbook_stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(workbook_stream)
        worksheet = workbook.add_worksheet("CrossBorderReport")
        worksheet2 = workbook.add_worksheet("Additional Data")
        date_format = workbook.add_format({'num_format': 'mm/dd/yyyy'})

        worksheet.set_column(1, 3, 14)
        worksheet.set_column(1, 10, 14)

        worksheet2.set_column(0, 0, 22)
        worksheet2.set_column(1, 1, 22)
        worksheet2.set_column(2, 2, 30)
        worksheet2.set_column(3, 3, 18)
        worksheet2.set_column(4, 4, 15)
        worksheet2.set_column(5, 5, 15)
        worksheet2.set_column(6, 6, 13)
        worksheet2.set_column(7, 7, 13)
        worksheet2.set_column(8, 8, 13)
        worksheet2.set_column(9, 9, 13)
        worksheet2.set_column(10, 10, 13)
        worksheet2.set_column(11, 11, 15)
        worksheet2.set_column(12, 12, 15)
        worksheet2.set_column(13, 13, 13)
        worksheet2.set_column(14, 14, 13)
        worksheet2.set_column(15, 15, 18)
        worksheet2.set_column(16, 16, 15)
        worksheet2.set_column(17, 17, 15)
        worksheet2.set_column(18, 18, 15)
        worksheet2.set_column(19, 19, 15)
        worksheet2.set_column(20, 20, 15)
        worksheet2.set_column(21, 21, 15)
        worksheet2.set_column(22, 22, 15)

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

        normal_format_small_2 = workbook.add_format({
            'bold': False,
            'align': 'left',
            'valign': 'bottom',
            'font_size': 11,
            'border': True,
            'text_wrap': True,
        })
        normal_format_small_3 = workbook.add_format({
            'bold': False,
            'align': 'right',
            'valign': 'bottom',
            'font_size': 11,
            'border': True,
            'text_wrap': True,
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
        total_except_shipping = 0
        product_price_unit_total = 0
        price_shipping_subtotal = 0
        for invoice in self.invoice_id:
            worksheet.write(row, 1, s_no, bold_format_left_align)
            worksheet.write(row, 2, invoice.name, border_format)
            shipping_charge = 0
            product_price_subtotal = 0
            for line in invoice.invoice_line_ids:
                if line.product_id.detailed_type in ["product", "consu"]:
                    product_price_unit_total += line.inv_line_amount
                if line.account_id.code in ['31900']:
                    price_shipping_subtotal += line.price_subtotal
                product_price_subtotal = product_price_unit_total + price_shipping_subtotal
                if line.account_id.code in ['31900']:
                    shipping_charge = line.price_subtotal
            worksheet.write(row, 3, product_price_subtotal, border_format)
            total_not_inc_shipping = product_price_subtotal - shipping_charge
            total_not_inc_shipping = abs(total_not_inc_shipping)
            worksheet.write(row, 4, shipping_charge, border_format)
            worksheet.write(row, 5, total_not_inc_shipping, border_format)
            total_amount += product_price_subtotal
            shipping_amount += shipping_charge
            total_except_shipping += total_not_inc_shipping
            row += 1
            s_no += 1
        worksheet.write(row, 2, "TOTAL", bold_align)
        worksheet.write(row, 3, total_amount, bold_align)
        worksheet.write(row, 4, shipping_amount, bold_align)
        worksheet.write(row, 5, total_except_shipping, bold_align)
        worksheet.write('B47', " ", bold_align)

        s_no -= 1
        worksheet.merge_range('D18:E18', "TOTAL # OF ORDERS:", merge_formats)
        worksheet.write('F18', s_no, merge_formates)

        headers = [
            "INVOICE ID", "PART#", "TARIFF #", 'Nyrobi Protocol', 'Section 301', "WEIGHT (in lbs)", "UOM", "RELATED",
            "VALUE", "Discount %", "Subtotal", "SPI",
            "Parties Qualifier", "Entity Id Qualifier Code", "Entity Identifier",
            "Name", "Address 1", "City", "State Province", "Postal Code", "Country", "isSold To",
        ]

        # Write the headers on the second worksheet
        for col_num, header in enumerate(headers):
            worksheet2.write(0, col_num, header, bold_format_small)

        row = 1
        total_inv_line_amount = 0
        total_subtotal_amount = 0
        for data in self.invoice_id:
            for data_line in data.invoice_line_ids:
                currency_symbol = data.currency_id.symbol
                normal_format_small_3_currency_format = workbook.add_format({
                    'bold': False,
                    'align': 'right',
                    'valign': 'bottom',
                    'font_size': 11,
                    'border': True,
                    'text_wrap': True,
                    'num_format': f'"{currency_symbol}"#,##0.00'
                })
                bold_currency_format = workbook.add_format({
                    'bold': True,
                    'align': 'right',
                    'valign': 'bottom',
                    'font_size': 11,
                    'border': True,
                    'text_wrap': True,
                    'num_format': f'"{currency_symbol}"#,##0.00'
                })
                normal_format_small_3_discount_format = workbook.add_format({
                    'bold': False,
                    'align': 'right',
                    'valign': 'bottom',
                    'font_size': 11,
                    'border': True,
                    'text_wrap': True,
                    'num_format': '0.00%'  # Format for percentage
                })

                if data_line.product_id.detailed_type in ["product", "consu"]:
                    total_inv_line_amount += data_line.inv_line_amount
                    total_subtotal_amount += data_line.price_subtotal
                    spi = "S" if data_line.product_id.usmca_eligible == 'yes' else ""
                    worksheet2.write(row, 0, data.name, normal_format_small_2)
                    worksheet2.write(row, 1, data_line.product_id.default_code, normal_format_small_2)
                    worksheet2.write(row, 2, data_line.product_id.cust_fld2 or "", normal_format_small_2)
                    worksheet2.write(row, 3, data_line.product_id.nyrobi_protocal or "", normal_format_small_2)
                    worksheet2.write(row, 4, data_line.product_id.section_301 or "", normal_format_small_2)
                    worksheet2.write(row, 5, data_line.product_id.weight, normal_format_small_3)
                    worksheet2.write(row, 6, data_line.product_uom_id.name, normal_format_small_2)
                    worksheet2.write(row, 7, "N", normal_format_small_2)
                    worksheet2.write(row, 8, data_line.inv_line_amount, normal_format_small_3_currency_format)
                    worksheet2.write(row, 9, data_line.discount if data_line.discount else "No Discount" , normal_format_small_3_discount_format)
                    worksheet2.write(row, 10, data_line.price_subtotal, normal_format_small_3_currency_format)
                    worksheet2.write(row, 11, spi, normal_format_small_2)
                    worksheet2.write(row, 12, "CN", normal_format_small_2)
                    worksheet2.write(row, 13, "EI", normal_format_small_2)
                    worksheet2.write(row, 14, "", normal_format_small_2)
                    worksheet2.write(row, 15, data.partner_id.name, normal_format_small_2)
                    worksheet2.write(row, 16, data.partner_id.street, normal_format_small_2)
                    worksheet2.write(row, 17, data.partner_id.city, normal_format_small_2)
                    worksheet2.write(row, 18, data.partner_id.state_id.code, normal_format_small_2)
                    worksheet2.write(row, 19, data.partner_id.zip, normal_format_small_2)
                    worksheet2.write(row, 20, data.partner_id.country_id.code, normal_format_small_2)
                    worksheet2.write(row, 21, "Y", normal_format_small_2)
                    row += 1
                    worksheet2.write(row, 8, total_inv_line_amount, bold_currency_format)
                    worksheet2.write(row, 10, total_subtotal_amount, bold_currency_format)
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
