# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from collections import defaultdict
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import date_utils, float_compare, float_round, float_is_zero


class AccountMoveInheritModel(models.Model):
    _inherit = 'account.move'

    tracking_number = fields.Char(string='Tracking Number', compute='_tracking_delivery_numbers')

    @api.depends('invoice_origin')
    def _tracking_delivery_numbers(self):
        for rec in self:
            order_id = self.env['sale.order'].search([('name', '=', rec.invoice_origin)], order='date_order asc')
            for order in order_id:
                stock_id = self.env['stock.picking'].search([('origin', '=', order.invoice_origin)],
                                                            order='date_done asc')
                tracking = ''
                for stock in stock_id:
                    if tracking:
                        if tracking != stock.name:
                            tracking = tracking + ',' + stock.name
                    else:
                        tracking = stock.name
                rec.tracking_number = tracking
