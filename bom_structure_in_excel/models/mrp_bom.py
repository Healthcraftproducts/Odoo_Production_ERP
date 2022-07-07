# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import xlwt
import io
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_round


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def custom_print_bom_structure_excel(self):
        active_ids = self._context.get('active_ids')
        if len(active_ids) != 1:
            raise UserError(_("You are not print multiple report in excel."))
        workbook = xlwt.Workbook()
        title_style_comp_left = xlwt.easyxf('font: name Times New Roman,bold off, italic off, height 450')
        title_style = xlwt.easyxf('align: horiz center ;font: name Times New Roman,bold off, italic off, height 350')
        title_style2 = xlwt.easyxf('font: name Times New Roman, height 200')
        title_style1 = xlwt.easyxf(
            'font: name Times New Roman,bold on, italic off, height 190; borders: top thin, bottom thin, left thin, right thin;')
        title_style1_table_head = xlwt.easyxf('font: name Times New Roman, bold on, italic off, height 200;')
        title_style1_table_head_left = xlwt.easyxf('font: name Times New Roman,bold on, italic off, height 200')
        title_style1_table_head_right = xlwt.easyxf(
            'align: horiz right; font: name Times New Roman,bold on, italic off, height 200')
        title_style1_table_value_left = xlwt.easyxf('font: name Times New Roman,bold off, italic off, height 200')
        title_style1_table_value_right = xlwt.easyxf(
            'align: horiz right; font: name Times New Roman,bold off, italic off, height 200')

        borders = xlwt.easyxf('font: name Times New Roman,bold on, italic off, height 200; borders: top thin;')

        sheet_name = 'BOM Structure'
        sheet = workbook.add_sheet(sheet_name)

        bom_id = self.env['mrp.bom'].browse(int(active_ids[0]))
        candidates = bom_id.product_id or bom_id.product_tmpl_id.product_variant_ids
        quantity = bom_id.product_qty
        data = {}
        docs = []
        # for product_variant_id in candidates:
        for product_variant_id in candidates.ids:
            data = self.env['report.mrp.report_bom_structure']._get_pdf_line(bom_id.id, product_id=product_variant_id,
                                                                             qty=quantity, unfolded=True)
            docs.append(data)
        row = 0
        for line in docs:
            if line and line.get('components') or line.get('lines'):
                sheet.write_merge(row, row + 1, 0, 6, 'BoM Structure & Cost', title_style_comp_left)
                sheet.write_merge(row + 3, row + 3, 0, 6, line['bom_prod_name'], title_style1_table_head)
                row += 4
                if line['bom'].code:
                    sheet.write(row, 0, 'Reference:', title_style1_table_head)
                    sheet.write_merge(row, row, 1, 6, line['bom'].code, title_style1_table_value_left)
                    row += 1
                currency_id = line['currency']

                # Table
                sheet.write(row, 0, 'Product Code', title_style1_table_head_left)
                sheet.write_merge(row, row, 1, 2, 'Product Description', title_style1_table_head_left)
                sheet.write(row, 3, 'BoM', title_style1_table_head_left)
                sheet.write(row, 4, 'Quantity', title_style1_table_head_right)
                sheet.write(row, 5, 'BoM Version', title_style1_table_head_left)
                sheet.write(row, 6, 'ECOs', title_style1_table_head_left)
                sheet.write(row, 7, 'Unit of Measure', title_style1_table_head_left)
                sheet.write(row, 8, 'Product Cost', title_style1_table_head_right)
                sheet.write(row, 9, 'BoM Cost', title_style1_table_head_right)

                row += 1
                sheet.write(row, 0, line['product'].code, title_style1_table_value_left)
                variant = ''
                for rec in line['product'].product_template_attribute_value_ids:
                    if variant:
                        variant += ', ' + rec.name
                    else:
                        variant = rec.name
                product_variant = line['product'].name + ' (' + variant + ')'
                # print('product', line['bom_prod_name'])
                # print('product', line['product'].code)
                # print('product', product_variant)
                # print('product', (rec.name for rec in line['product'].product_template_attribute_value_ids))
                # print('product', line['code'])
                sheet.write_merge(row, row, 1, 2, product_variant, title_style1_table_value_left)
                sheet.write(row, 3, line['code'], title_style1_table_value_left)
                bom_qty = format(line['bom_qty'], '.2f')
                sheet.write(row, 4, bom_qty, title_style1_table_value_right)
                sheet.write(row, 5, line['version'], title_style1_table_value_right)
                sheet.write(row, 6, line['ecos'], title_style1_table_value_right)
                sheet.write(row, 7, line['bom'].product_uom_id.name, title_style1_table_value_left)
                price_unit = format(line['price'], '.2f')
                total_price = format(line['total'], '.2f')
                if currency_id and currency_id.position == 'after':
                    price_unit = str(price_unit) + ' ' + currency_id.symbol
                    total_price = str(total_price) + ' ' + currency_id.symbol
                if currency_id and currency_id.position == 'before':
                    price_unit = currency_id.symbol + ' ' + str(price_unit)
                    total_price = currency_id.symbol + ' ' + str(total_price)
                sheet.write(row, 8, price_unit, title_style1_table_value_right)
                sheet.write(row, 9, total_price, title_style1_table_value_right)

                row += 1
                for l in line['lines']:
                    if l['level'] != 0:
                        space_td = '    ' * (l['level'])
                    else:
                        space_td = '    '
                    product_name = ''
                    # product_code = ''
                    if l['type'] == 'bom':
                        pr = self.env['product.product'].search([('id', '=', l['prod_id'])])
                        # print('pr', pr)
                        # print('3333', pr.name)
                        # print('44444', pr.code)
                        product_name = pr.name
                        code = pr.code
                        product_code = space_td + ' ' + code
                        # product_name = space_td + ' ' + product_id
                    else:
                        product_code = space_td + ' ' + l['name']
                    print('l', l)
                    # print('level', l['level'])
                    # print('name', l['name'])
                    sheet.write(row, 0, product_code, title_style1_table_value_left)
                    sheet.write_merge(row, row, 1, 2, product_name, title_style1_table_value_left)
                    if l.get('code'):
                        sheet.write(row, 3, l['code'], title_style1_table_value_left)
                    quantity = format(l['quantity'], '.2f')
                    sheet.write(row, 4, quantity, title_style1_table_value_right)
                    if self.user_has_groups('uom.group_uom'):
                        sheet.write(row, 5, l['version'] if l['version'] else '', title_style1_table_value_right)
                        sheet.write(row, 6, l['ecos'] if l['ecos'] else '', title_style1_table_value_right)
                        sheet.write(row, 7, l['uom'], title_style1_table_value_left)
                    if 'prod_cost' in l:
                        price_unit = format(l['prod_cost'], '.2f')
                        if currency_id and currency_id.position == 'after':
                            price_unit = str(price_unit) + ' ' + currency_id.symbol
                        if currency_id and currency_id.position == 'before':
                            price_unit = currency_id.symbol + ' ' + str(price_unit)
                        sheet.write(row, 8, price_unit, title_style1_table_value_right)

                    total_price = format(l['bom_cost'], '.2f')
                    if currency_id and currency_id.position == 'after':
                        total_price = str(total_price) + ' ' + currency_id.symbol
                    if currency_id and currency_id.position == 'before':
                        total_price = currency_id.symbol + ' ' + str(total_price)
                    sheet.write(row, 9, total_price, title_style1_table_value_right)
                    row += 1

                row += 1
                sheet.write_merge(row, row, 0, 7, 'Unit Cost', title_style1_table_head_right)
                product_cost_total = line['price'] / line['bom_qty']
                product_cost_total = format(product_cost_total, '.2f')
                if currency_id and currency_id.position == 'after':
                    product_cost_total = str(product_cost_total) + ' ' + currency_id.symbol
                if currency_id and currency_id.position == 'before':
                    product_cost_total = currency_id.symbol + ' ' + str(product_cost_total)
                sheet.write(row, 8, product_cost_total, title_style1_table_value_right)
                bom_cost_total = line['total'] / line['bom_qty']
                bom_cost_total = format(bom_cost_total, '.2f')
                if currency_id and currency_id.position == 'after':
                    bom_cost_total = str(bom_cost_total) + ' ' + currency_id.symbol
                if currency_id and currency_id.position == 'before':
                    bom_cost_total = currency_id.symbol + ' ' + str(bom_cost_total)
                sheet.write(row, 9, bom_cost_total, title_style1_table_value_right)
                row += 4
            else:
                sheet.write_merge(0, 1, 0, 6, 'No data available.', title_style_comp_left)
                row += 4

        # row = 0
        # if data and data.get('components') or data.get('lines'):
        #     sheet.write_merge(row, row+1, 0, 6, 'BoM Structure & Cost' , title_style_comp_left)
        #     sheet.write_merge(row+3, row+3, 0, 6, data['bom_prod_name'], title_style1_table_head)
        #     row += 4
        #     if data['bom'].code:
        #         sheet.write(row, 0, 'Reference:', title_style1_table_head)
        #         sheet.write_merge(row, row, 1, 6, data['bom'].code, title_style1_table_value_left)
        #         row += 1
        #     currency_id = data['currency']

        #     #Table
        #     sheet.write_merge(row, row, 0, 1, 'Product' , title_style1_table_head_left)
        #     sheet.write(row, 2, 'BoM', title_style1_table_head_left)
        #     sheet.write(row, 3, 'Quantity', title_style1_table_head_right)
        #     sheet.write(row, 4, 'Unit of Measure', title_style1_table_head_left)
        #     sheet.write(row, 5, 'Product Cost', title_style1_table_head_right)
        #     sheet.write(row, 6, 'BoM Cost', title_style1_table_head_right)

        #     row = 6
        #     sheet.write_merge(row, row, 0, 1, data['bom_prod_name'], title_style1_table_value_left)
        #     sheet.write(row, 2, data['code'], title_style1_table_value_left)
        #     bom_qty = format(data['bom_qty'], '.2f')
        #     sheet.write(row, 3, bom_qty, title_style1_table_value_right)
        #     sheet.write(row, 4, data['bom'].product_uom_id.name, title_style1_table_value_left)
        #     price_unit = format(data['price'], '.2f')
        #     total_price = format(data['total'], '.2f')
        #     if currency_id and currency_id.position == 'after':
        #         price_unit = str(price_unit) + ' ' + currency_id.symbol
        #         total_price = str(total_price) + ' ' + currency_id.symbol
        #     if currency_id and currency_id.position == 'before':
        #         price_unit = currency_id.symbol + ' ' + str(price_unit)
        #         total_price = currency_id.symbol + ' ' + str(total_price)
        #     sheet.write(row, 5, price_unit, title_style1_table_value_right)
        #     sheet.write(row, 6, total_price, title_style1_table_value_right)

        #     row += 1
        #     for l in data['lines']:
        #         if l['level'] != 0:
        #             space_td = '    '*(l['level'])
        #         else:
        #             space_td = '    '
        #         product_name = space_td + ' ' + l['name']
        #         sheet.write_merge(row, row, 0, 1, product_name, title_style1_table_value_left)
        #         if l.get('code'):
        #             sheet.write(row, 2, l['code'], title_style1_table_value_left)
        #         quantity = format(l['quantity'], '.2f')
        #         sheet.write(row, 3, quantity, title_style1_table_value_right)
        #         if self.user_has_groups('uom.group_uom'):
        #             sheet.write(row, 4, l['uom'], title_style1_table_value_left)
        #         if 'prod_cost' in l:
        #             price_unit = format(l['prod_cost'], '.2f')
        #             if currency_id and currency_id.position == 'after':
        #                 price_unit = str(price_unit) + ' ' + currency_id.symbol
        #             if currency_id and currency_id.position == 'before':
        #                 price_unit = currency_id.symbol + ' ' + str(price_unit)
        #             sheet.write(row, 5, price_unit, title_style1_table_value_right)

        #         total_price = format(l['bom_cost'], '.2f')
        #         if currency_id and currency_id.position == 'after':
        #             total_price = str(total_price) + ' ' + currency_id.symbol
        #         if currency_id and currency_id.position == 'before':
        #             total_price = currency_id.symbol + ' ' + str(total_price)
        #         sheet.write(row, 6, total_price, title_style1_table_value_right)
        #         row += 1

        #     sheet.write_merge(row, row, 0, 4, 'Unit Cost', title_style1_table_head_right)
        #     product_cost_total = data['price']/data['bom_qty']
        #     product_cost_total = format(product_cost_total, '.2f')
        #     if currency_id and currency_id.position == 'after':
        #         product_cost_total = str(product_cost_total) + ' ' + currency_id.symbol
        #     if currency_id and currency_id.position == 'before':
        #         product_cost_total = currency_id.symbol + ' ' + str(product_cost_total)
        #     sheet.write(row, 5, product_cost_total, title_style1_table_value_right)
        #     bom_cost_total = data['total']/data['bom_qty']
        #     bom_cost_total = format(bom_cost_total, '.2f')
        #     if currency_id and currency_id.position == 'after':
        #         bom_cost_total = str(bom_cost_total) + ' ' + currency_id.symbol
        #     if currency_id and currency_id.position == 'before':
        #         bom_cost_total = currency_id.symbol + ' ' + str(bom_cost_total)
        #     sheet.write(row, 6, bom_cost_total, title_style1_table_value_right)
        # else:
        #     sheet.write_merge(0, 1, 0, 6, 'No data available.' , title_style_comp_left)

        stream = io.BytesIO()
        workbook.save(stream)
        attach_id = self.env['custom.mrp.bom.structure.excel'].create(
            {'name': 'BOM Structure.xls', 'xls_output': base64.encodestring(stream.getvalue())})
        return {
            'context': self.env.context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'custom.mrp.bom.structure.excel',
            'res_id': attach_id.id,
            'type': 'ir.actions.act_window',
            'target': 'new'
        }


class MrpBomStructureExcel(models.Model):
    _name = 'custom.mrp.bom.structure.excel'
    _description = 'Wizard to store the Excel output'

    xls_output = fields.Binary(string='Excel Output',
                               readonly=True
                               )
    name = fields.Char(string='File Name',
                       help='Save report as .xls format',
                       default='BOM Structure.xls',
                       )

# #vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
