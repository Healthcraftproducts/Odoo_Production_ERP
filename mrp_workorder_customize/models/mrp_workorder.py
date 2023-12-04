# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016-Today Geminate Consultancy Services (<http://geminatecs.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.tools import float_compare
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import pdb

class MrpProductionWorkcenterLine(models.Model):
    _inherit = 'mrp.workorder'

    def open_tablet_view(self):
        self.ensure_one()
        if not self.is_user_working and self.working_state != 'blocked' and self.state in ('ready', 'waiting', 'progress', 'pending'):
            self.button_start()
        action = self.env["ir.actions.actions"]._for_xml_id("mrp_workorder.tablet_client_action")
        action['target'] = 'fullscreen'
        action['res_id'] = self.id
        # pdb.set_trace()
        self.qty_producing_custom = self.qty_remaining
        self.qty_producing = self.qty_remaining
        self.allow_record_qty=True
        action['context'] = {
            'active_id': self.id,
            # 'qty_producing_custom': self.qty_remaining,
            'from_production_order': self.env.context.get('from_production_order'),
            'from_manufacturing_order': self.env.context.get('from_manufacturing_order')
        }
        return action

    # @api.onchange('qty_remaining')
    # def _qty_producing_custom12(self):
    #     for line in self:
    #         if line.qty_remaining >=0:
    #             line.qty_producing_custom = line.qty_remaining

    qty_producing_custom = fields.Float(string='Current Quantity', digits='Product Unit of Measure', copy=False)
    record_qty_production = fields.Float(string='Produced', digits='Product Unit of Measure', copy=False)
    record_qty_production1 = fields.Float(string='Produced1', digits='Product Unit of Measure', copy=False)
    allow_record_qty = fields.Boolean(string="Allow To Record Production Quantity", default=False)

    # @api.depends('production_id.qty_producing')
    # def _compute_qty_producing_custom1(self):
    #     for workorder in self:
    #         workorder.qty_producing_custom = workorder.qty_remaining

    # @api.depends('qty_production', 'qty_reported_from_previous_wo', 'qty_produced', 'production_id.product_uom_id')
    # def _compute_qty_remaining(self):
    #     for wo in self:
    #         if wo.production_id.product_uom_id:
    #             x=wo.production_id.product_uom_id.rounding
    #             val=max(float_round(wo.qty_production - wo.qty_reported_from_previous_wo - wo.qty_produced, precision_rounding=x), 0)
    #             wo.qty_remaining = val
    #         else:
    #             wo.qty_remaining = 0

    def record_production(self):
        if not self:
            return True
        self.qty_producing = self.qty_producing_custom
        self.ensure_one()
        self._check_sn_uniqueness()
        self._check_company()
        if any(x.quality_state == 'none' for x in self.check_ids if x.test_type != 'instructions'):
            raise UserError(_('You still need to do the quality checks!'))
        if float_compare(self.qty_producing, 0, precision_rounding=self.product_uom_id.rounding) <= 0:
            raise UserError(_('Alert !! Please set the quantity you are currently producing. It should be different from zero.'))
        if self.production_id.product_id.tracking != 'none' and not self.finished_lot_id and self.move_raw_ids:
            raise UserError(_('You should provide a lot/serial number for the final product'))
        self.button_finish()
        return True

    def button_finish(self):
        end_date = datetime.now()
        for workorder in self:
            if workorder.state in ('done', 'cancel'):
                continue
            workorder.end_all()
            # my_list = []
            # for line in workorder.production_id.workorder_ids.filtered(lambda x:x.qty_produced > 0):
            #     my_list.append(line.qty_produced)
            # if my_list != []:
            #     final_quantity = min(my_list)
            #     workorder.production_id.write({'qty_producing':final_quantity})
            workorder.qty_producing = workorder.qty_producing_custom
            # pdb.set_trace()
            if workorder.qty_produced ==0:
                # value = workorder.production_id.qty_producing or workorder.qty_produced or workorder.qty_producing or workorder.qty_production
                value = workorder.qty_produced or workorder.qty_producing or workorder.qty_production
            if workorder.qty_produced >0 and workorder.qty_producing_custom>0:
                # value = (workorder.qty_produced + workorder.qty_producing)
                value = (workorder.qty_produced + workorder.qty_producing_custom)
            else:
                value = workorder.record_qty_production
            vals = {
                'qty_produced': value,
                # 'record_qty_production': value,
                'state': 'done',
                'date_finished': end_date,
                'date_planned_finished': end_date,
                'costs_hour': workorder.workcenter_id.costs_hour
            }
            if workorder.production_id.product_qty - workorder.qty_produced != workorder.qty_producing:
                del vals['state']
            if not workorder.date_start:
                vals['date_start'] = end_date
            if not workorder.date_planned_start or end_date < workorder.date_planned_start:
                vals['date_planned_start'] = end_date
            if workorder.allow_record_qty ==True:
                vals['record_qty_production'] = value
                vals['allow_record_qty'] = False
            workorder.write(vals)
        return True

    @api.depends('qty_producing_custom', 'qty_remaining')
    def _compute_is_last_lot(self):
        for wo in self:
            precision = wo.production_id.product_uom_id.rounding
            wo.is_last_lot = float_compare(wo.qty_producing_custom,wo.qty_remaining, precision_rounding=precision) >= 0

# change in base code by geminatecs
# file location of change code :-
# enterprise/mrp_workorder/models/quality.py", line 386, in _create_extra_move_lines
#  **** base original code ****
# quantity = self.product_id.uom_id._compute_quantity(quantity, self.product_uom_id, rounding_method='HALF-UP')
# **************************** #
# change by geminatecs
# quantity = self.product_id.uom_id._compute_quantity(quantity, self.move_id.product_uom.id, rounding_method='HALF-UP')
#######################
