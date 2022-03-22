# -*- coding:utf-8 -*-

import base64
import xlrd

from odoo import models, fields
from odoo.exceptions import ValidationError

class ImportProductValuationDifference(models.TransientModel):
    _name = 'import.product.valuation.difference'

    files = fields.Binary(string="Import Excel File")
    datas_fname = fields.Char('Import File Name')

    def import_file(self):
        stock_valuation_layer_obj = self.env['stock.valuation.layer']
        product_obj = self.env['product.product']
        try:
            workbook = xlrd.open_workbook(file_contents=base64.decodestring(self.files))
        except:
            raise ValidationError("Please select .xls/xlsx file...")
        Sheet_name = workbook.sheet_names()
        sheet = workbook.sheet_by_name(Sheet_name[0])
        number_of_rows = sheet.nrows
        row = 1
        while(row < number_of_rows):
            sub_string = sheet.cell(row,0).value
            if sub_string:
                left = '['
                right = ']'
                default_code = sub_string[sub_string.index(left)+len(left):sub_string.index(right)]
                product_id = product_obj.sudo().search([('default_code', '=', default_code)])
                if product_id:
                    vals = {
                            'product_id' : product_id.id,
                            'quantity' : sheet.cell(row,1).value,
                            'value' : sheet.cell(row,2).value,
                            'company_id': self.env.user.company_id.id,
                            }
                    stock_valuation_layer_obj.sudo().create(vals)
            row = row+1
        return True
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
