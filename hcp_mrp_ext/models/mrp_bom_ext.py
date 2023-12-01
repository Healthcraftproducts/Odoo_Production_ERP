# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from collections import defaultdict
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import date_utils, float_compare, float_round, float_is_zero
import logging


class MrpBomInherit(models.Model):
    _inherit = 'mrp.bom'

    # bom_cost_total = fields.Monetary(string='Bom Cost', compute='_bom_cost_total')
    # bom_cost = fields .Float(string='Bom Cost1')
    currency_id = fields.Many2one('res.currency', compute='_compute_currency')

    @api.model
    def _compute_currency(self):
        for rec in self:
            company_id = self.env.company
            if company_id:
                rec.currency_id = company_id.currency_id.id

    # def _bom_cost_total(self):
    #     for bom in self:
    #         for bom_line in bom.bom_line_ids:
    #             company = bom.company_id or self.env.company
    #             bom_quantity = bom.product_qty
    #             if bom_line:
    #                 current_line = self.env['mrp.bom.line'].browse(int(bom_line))
    #                 bom_quantity = current_line.product_uom_id._compute_quantity(bom.product_qty,
    #                                                                              bom.product_uom_id,
    #                                                                              raise_if_failure=False) or 0
    #             # Display bom components for current selected product variant
    #             if bom.product_id:
    #                 product = bom.product_id
    #             else:
    #                 product = bom.product_id or bom.product_tmpl_id.product_variant_id
    #             if product:
    #                 price = product.uom_id._compute_price(product.with_context(force_company=company.id).standard_price,
    #                                                       bom.product_uom_id) * bom_quantity
    #                 attachments = self.env['mrp.document'].search(['|', '&', ('res_model', '=', 'product.product'),
    #                                                                ('res_id', '=', product.id), '&',
    #                                                                ('res_model', '=', 'product.template'),
    #                                                                ('res_id', '=', product.product_tmpl_id.id)])
    #             else:
    #                 # Use the product template instead of the variant
    #                 price = bom.product_tmpl_id.uom_id._compute_price(
    #                     bom.product_tmpl_id.with_context(force_company=company.id).standard_price,
    #                     bom.product_uom_id) * bom_quantity
    #                 attachments = self.env['mrp.document'].search(
    #                     [('res_model', '=', 'product.template'), ('res_id', '=', bom.product_tmpl_id.id)])
    #             operations = []
    #             if bom.product_qty > 0:
    #                 operations = self._get_operation_line(bom.routing_id,
    #                                                       float_round(bom_quantity / bom.product_qty,
    #                                                                   precision_rounding=1,
    #                                                                   rounding_method='UP'), 0)
    #             lines = {
    #                 'bom': bom,
    #                 'bom_qty': bom_quantity,
    #                 'bom_prod_name': product.display_name,
    #                 'currency': company.currency_id,
    #                 'product': product,
    #                 'code': bom and bom.display_name or '',
    #                 'price': price,
    #                 'total': sum([op['total'] for op in operations]),
    #                 'operations': operations,
    #                 'operations_cost': sum([op['total'] for op in operations]),
    #                 'attachments': attachments,
    #                 'operations_time': sum([op['duration_expected'] for op in operations])
    #             }
    #             components, total = self._get_bom_lines(bom, bom_quantity, product)
    #             lines['components'] = components
    #             lines['total'] += total
    #             # b = bom.write({'bom_cost': lines['total']})
    #             # print('bom cost', b)
    #             bom.bom_cost_total = lines['total']
    #             return lines
    #
    # def _get_bom_lines(self, bom, bom_quantity, product):
    #     components = []
    #     total = 0
    #     for line in bom.bom_line_ids:
    #         line_quantity = (bom_quantity / (bom.product_qty or 1.0)) * line.product_qty
    #         if line._skip_bom_line(product):
    #             continue
    #         company = bom.company_id or self.env.company
    #         price = line.product_id.uom_id._compute_price(
    #             line.product_id.with_context(force_company=company.id).standard_price,
    #             line.product_uom_id) * line_quantity
    #         if line.child_bom_id:
    #             factor = line.product_uom_id._compute_quantity(line_quantity,
    #                                                            line.child_bom_id.product_uom_id) / line.child_bom_id.product_qty
    #             sub_total = self._get_price(line.child_bom_id, factor, line.product_id)
    #         else:
    #             sub_total = price
    #         sub_total = self.env.company.currency_id.round(sub_total)
    #         components.append({
    #             'prod_id': line.product_id.id,
    #             'prod_name': line.product_id.display_name,
    #             'code': line.child_bom_id and line.child_bom_id.display_name or '',
    #             'prod_qty': line_quantity,
    #             'prod_uom': line.product_uom_id.name,
    #             'prod_cost': company.currency_id.round(price),
    #             'parent_id': bom.id,
    #             'line_id': line.id,
    #             'total': sub_total,
    #             'child_bom': line.child_bom_id.id,
    #             'phantom_bom': line.child_bom_id and line.child_bom_id.type == 'phantom' or False,
    #             'attachments': self.env['mrp.document'].search(['|', '&',
    #                                                             ('res_model', '=', 'product.product'),
    #                                                             ('res_id', '=', line.product_id.id), '&',
    #                                                             ('res_model', '=', 'product.template'),
    #                                                             ('res_id', '=', line.product_id.product_tmpl_id.id)]),
    #
    #         })
    #         total += sub_total
    #     return components, total
    #
    # def _get_operation_line(self, routing, qty, level):
    #     operations = []
    #     total = 0.0
    #     for operation in routing.operation_ids:
    #         operation_cycle = float_round(qty / operation.workcenter_id.capacity, precision_rounding=1,
    #                                       rounding_method='UP')
    #         duration_expected = operation_cycle * operation.time_cycle + operation.workcenter_id.time_stop + operation.workcenter_id.time_start
    #         total = ((duration_expected / 60.0) * operation.workcenter_id.costs_hour)
    #         operations.append({
    #             'level': level or 0,
    #             'operation': operation,
    #             'name': operation.name + ' - ' + operation.workcenter_id.name,
    #             'duration_expected': duration_expected,
    #             'total': self.env.company.currency_id.round(total),
    #         })
    #     return operations
    #
    # def _get_price(self, bom, factor, product):
    #     price = 0
    #     if bom.routing_id:
    #         operation_cycle = float_round(factor, precision_rounding=1, rounding_method='UP')
    #         operations = self._get_operation_line(bom.routing_id, operation_cycle, 0)
    #         price += sum([op['total'] for op in operations])
    #
    #     for line in bom.bom_line_ids:
    #         if line._skip_bom_line(product):
    #             continue
    #         if line.child_bom_id:
    #             qty = line.product_uom_id._compute_quantity(line.product_qty * factor,
    #                                                         line.child_bom_id.product_uom_id) / line.child_bom_id.product_qty
    #             sub_price = self._get_price(line.child_bom_id, qty, line.product_id)
    #             price += sub_price
    #         else:
    #             prod_qty = line.product_qty * factor
    #             company = bom.company_id or self.env.company
    #             not_rounded_price = line.product_id.uom_id._compute_price(
    #                 line.product_id.with_context(force_company=company.id).standard_price,
    #                 line.product_uom_id) * prod_qty
    #             price += company.currency_id.round(not_rounded_price)
    #     return price


class MrpBomLineInherit(models.Model):
    _inherit = 'mrp.bom.line'

    purchase_cost = fields.Float(string='Purchase Cost', compute='_total_purchase_cost')
    # currency_id = fields.Many2one('res.currency', realated='bom_id.currency_id', string='Currency')
    v = fields.Float(string='Component Cost', compute='_total_component_cost', store=True)
    m = fields.Float(string='Total Component Cost', compute='_total_component_cost', store=True)

    @api.depends('product_id', 'product_qty')
    def _total_component_cost(self):
        for bom_line in self:
            bom_line.v = bom_line.product_id.standard_price
            bom_line.m = bom_line.product_qty * bom_line.v

    def _total_purchase_cost(self):
        for bom_line in self:
            if bom_line.product_tmpl_id.seller_ids:
                for product in bom_line.product_tmpl_id.seller_ids:
                    if product.check_bom_cost == True:
                        bom_line.purchase_cost = product.price
                    else:
                        bom_line.purchase_cost = 0
            else:
                bom_line.purchase_cost = 0


class ProductSupplierInfoInherit(models.Model):
    _inherit = 'product.supplierinfo'

    check_bom_cost = fields.Boolean(string='Check Bom Cost')
