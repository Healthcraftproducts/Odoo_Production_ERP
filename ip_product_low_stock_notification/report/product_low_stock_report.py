# -*- coding: utf-8 -*-
import time
from odoo import api, models, _
from odoo.exceptions import UserError
from ast import literal_eval
# import json


class ProductLowStockReport(models.AbstractModel):
    _name = 'report.ip_product_low_stock_notification.report_stock_menu'
    _description = "product low stock report"

    def get_low_stock_products(self, data):
        domain = []
        product_list = []
        product_list2 = []
        product_list3 =[]
        product_list4 =[]
        return_list = {}
        StockQuantObj = self.env['stock.quant']
        stock_notification_type = data['form']['stock_notification']
        min_qty = data['form']['minimum_qty']
        company_ids = data['form']['company_ids']
        location_ids = data['form']['stock_lctn_id']
        return_list['type'] = stock_notification_type
        return_list['min_qty'] = min_qty

        if company_ids and company_ids:
            domain += [('company_id', 'in', company_ids)]
        if location_ids:
            loc = location_ids[0]
            domain += ['|', ('location_id', '=', loc), ('location_id', 'child_of', loc)]
        # if stock_notification_type == 'global':
        #     product_ids = self.env['product.product'].search([('type', 'not in', ['service'])])
        #     for product_id in product_ids:
        #         product_domain = [('product_id', '=', product_id.id)]
        #         quant_ids = StockQuantObj.search(domain + product_domain)
        #         for quant_id in quant_ids:
        #             if quant_id.quantity < min_qty:
        #                 product_list.append(quant_id)
        #         return_list['quant_ids'] = product_list
        if stock_notification_type == 'individual':
            product_ids = self.env['product.product'].search([('type', 'not in', ['service'])])
            for product_id in product_ids:
                product_domain = [('product_id', '=', product_id.id)]
                quant_ids = StockQuantObj.search(domain + product_domain)
                tot_qty = sum(quant_id.quantity for quant_id in quant_ids)
                
                for quant_id in quant_ids:
                    if tot_qty < product_id.minimum_qty:
                        c=quant_id.product_id.id
                        d=[quant_id.product_id.display_name,tot_qty,product_id.minimum_qty,quant_id.product_uom_id.name]
                        product_detail1 = {'id':c,'values':d}
                        product_list3.append(product_detail1)
            list_quant = product_list3
            new_v =[]
            for y in list_quant:
                if y not in new_v:
                    new_v.append(y)
            for dt in new_v:
                product_detail3 = []
                product_detail3.append(dt['values'][0])
                product_detail3.append(dt['values'][1])
                product_detail3.append(dt['values'][2])
                product_detail3.append(dt['values'][3])
                product_list4.append(product_detail3)
            return_list['quant_ids'] = product_list4
            return_list['location_ids'] = location_ids[1]
    
                       
                        
                # return_list['quant_ids'] = product_list
        if stock_notification_type == 'reorder':
            # raise UserError("reorder")
            # if location_ids:
            #     raise UserError(location_ids)
            reordering_rule_ids = self.env['stock.warehouse.orderpoint'].search([])
            for rule_id in reordering_rule_ids:
                product_domain = [('product_id', '=', rule_id.product_id.id)]
                quant_ids = StockQuantObj.search(domain + product_domain)
                total_qty = sum(quant_id.quantity for quant_id in quant_ids)
                # total_qty = -(total_qty)
                for quant_id in quant_ids:
                    if total_qty < rule_id.product_min_qty:
                        a=quant_id.product_id.id
                        b=[quant_id.product_id.display_name,total_qty,rule_id.product_min_qty,quant_id.product_uom_id.name]
                        product_detail = {'id':a,'values':b}
                        product_list.append(product_detail)
            list_quants = product_list
            # if product_list:
            #     raise UserError(product_list)
            new_d = []
            for x in list_quants:
                if x not in new_d:
                    new_d.append(x)

            for data in new_d:
                product_detail2 = []
                product_detail2.append(data['values'][0])
                product_detail2.append(data['values'][1])
                product_detail2.append(data['values'][2])
                product_detail2.append(data['values'][3])
                product_list2.append(product_detail2)
            return_list['quant_ids'] = product_list2
            return_list['location_ids'] = location_ids[1]
        return return_list

    def get_low_stock_products_mail(self):
        domain = []
        product_list = []
        return_list = {}
        StockQuantObj = self.env['stock.quant']

        get_param = self.env['ir.config_parameter'].sudo().get_param
        stock_notification_type = get_param('ip_product_low_stock_notification.stock_notification')
        min_qty = float(get_param('ip_product_low_stock_notification.minimum_qty'))
        company_ids = literal_eval(get_param('ip_product_low_stock_notification.company_ids'))
        location_ids = literal_eval(get_param('ip_product_low_stock_notification.location_ids'))
        return_list['type'] = stock_notification_type
        return_list['min_qty'] = min_qty

        if company_ids and company_ids:
            domain += [('company_id', 'in', company_ids)]
        if location_ids and location_ids:
            domain += ['|', ('location_id', 'in', location_ids), ('location_id', 'child_of', location_ids)]
        # if stock_notification_type == 'global':
        #     product_ids = self.env['product.product'].search([('type', 'not in', ['service'])])
        #     for product_id in product_ids:
        #         product_domain = [('product_id', '=', product_id.id)]
        #         quant_ids = StockQuantObj.search(domain + product_domain)
        #         for quant_id in quant_ids:
        #             if quant_id.quantity < min_qty:
        #                 product_list.append(quant_id)
        #         return_list['quant_ids'] = product_list
        if stock_notification_type == 'individual':
            product_ids = self.env['product.product'].search([('type', 'not in', ['service'])])
            for product_id in product_ids:
                product_domain = [('product_id', '=', product_id.id)]
                quant_ids = StockQuantObj.search(domain + product_domain)
                for quant_id in quant_ids:
                    if quant_id.quantity < product_id.minimum_qty:
                        product_list.append(quant_id)
                return_list['quant_ids'] = product_list
        if stock_notification_type == 'reorder':
            reordering_rule_ids = self.env['stock.warehouse.orderpoint'].search([])
            for rule_id in reordering_rule_ids:
                product_domain = [('product_id', '=', rule_id.product_id.id)]
                quant_ids = StockQuantObj.search(domain + product_domain)
                for quant_id in quant_ids:
                    if quant_id.quantity < rule_id.product_min_qty:
                        product_detail = []
                        product_detail.append(quant_id.product_id.display_name)
                        product_detail.append(quant_id.location_id.display_name)
                        product_detail.append(quant_id.quantity)
                        product_detail.append(rule_id.product_min_qty)
                        product_detail.append(quant_id.product_uom_id.name)
                        product_list.append(product_detail)
        return_list['quant_ids'] = product_list
        return return_list

    @api.model
    def _get_report_values(self, docids, data=None):
        low_product = []
        if self.env.context.get('send_email', False):
            self.model = 'stock.quant'
            low_product = self.get_low_stock_products_mail()
        else:
            if not data.get('form'):
                raise UserError(_("Content is missing, this report cannot be printed."))
            self.model = self.env.context.get('active_model')
            low_product = self.get_low_stock_products(data)
        return {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'time': time,
            'low_stock': low_product,
        }
