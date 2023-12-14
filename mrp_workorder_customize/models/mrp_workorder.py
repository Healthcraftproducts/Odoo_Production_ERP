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

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from ast import literal_eval
from collections import defaultdict
import json

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from odoo.addons.web.controllers.utils import clean_action
from odoo.tools import float_compare, float_round, format_datetime,float_is_zero
from bisect import bisect_left
import pdb

class MrpProductionWorkcenterLine(models.Model):
    _inherit = 'mrp.workorder'

    def get_summary_data(self):
        self.ensure_one()
        # show rainbow man only the first time
        show_rainbow = any(not t.date_end for t in self.time_ids)
        self.end_all()
        if any(step.quality_state == 'none' for step in self.check_ids):
            raise UserError(_('You still need to do the quality checks!'))
        last30op = self.env['mrp.workorder'].search_read([
            ('operation_id', '=', self.operation_id.id),('qty_produced', '>', 0),
            ('date_finished', '>', fields.datetime.today() - relativedelta(days=30)),
        ], ['duration', 'qty_produced'])
        # pdb.set_trace()
        last30op = sorted([item['duration'] / item['qty_produced'] for item in last30op])
        # show rainbow man only for the best time in the last 30 days.
        if last30op:
            show_rainbow = show_rainbow and float_compare((self.duration / self.qty_producing), last30op[0], precision_digits=2) <= 0

        score = 3
        if self.check_ids:
            passed_checks = len(list(check for check in self.check_ids if check.quality_state == 'pass'))
            score = int(3.0 * passed_checks / len(self.check_ids))

        return {
            'duration': self.duration,
            'position': bisect_left(last30op, self.duration), # which position regarded other workorders ranked by duration
            'quality_score': score,
            'show_rainbow': show_rainbow,
        }

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
            # for line in workorder.production_id.workorder_ids.filtered(lambda x:x.record_qty_production > 0):
            #     my_list.append(line.record_qty_production)
            # pdb.set_trace()
            # if my_list != []:
            #     final_quantity = min(my_list)
            #     workorder.production_id.write({'qty_producing':final_quantity})
            workorder.qty_producing = workorder.qty_producing_custom
            # pdb.set_trace()
            # if workorder.qty_produced ==0:
            #     # value = workorder.production_id.qty_producing or workorder.qty_produced or workorder.qty_producing or workorder.qty_production
            #     value = workorder.qty_produced or workorder.qty_producing or workorder.qty_production
            if workorder.qty_produced >0 and workorder.qty_producing_custom>0:
                # value = (workorder.qty_produced + workorder.qty_producing)
                value = (workorder.qty_produced + workorder.qty_producing_custom)
            elif workorder.qty_produced ==0 and workorder.qty_producing_custom>0:
                value = workorder.qty_producing_custom
            else:
                value = workorder.record_qty_production or workorder.qty_produced or workorder.qty_producing or workorder.qty_production
            # pdb.set_trace()
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
                # pdb.set_trace()
                if vals.get('state') != 'done':
                    vals['state'] = 'progress'
            print("Test111111", vals)
            workorder.write(vals)
        return True

    @api.depends('qty_producing_custom', 'qty_remaining')
    def _compute_is_last_lot(self):
        for wo in self:
            precision = wo.production_id.product_uom_id.rounding
            wo.is_last_lot = float_compare(wo.qty_producing_custom,wo.qty_remaining, precision_rounding=precision) >= 0

    def action_back(self):
        self.ensure_one()
        if self.is_user_working and self.working_state != 'blocked':
            self.button_pending()
        domain = [('state', 'in', ['pending','ready','progress','waiting'])]
        if self.env.context.get('from_manufacturing_order'):
            # from workorder on MO
            action = self.env["ir.actions.actions"]._for_xml_id("mrp_workorder.mrp_workorder_action_tablet")
            action['domain'] = domain
            action['context'] = {
                'no_breadcrumbs': True,
                'search_default_production_id': self.production_id.id,
                'from_manufacturing_order': True,
            }
        elif self.env.context.get('from_production_order'):
            # from workorder list view
            action = self.env["ir.actions.actions"]._for_xml_id("mrp_workorder.mrp_workorder_action_tablet")
            action['target'] = 'main'
            action['context'] = dict(literal_eval(action['context']), no_breadcrumbs=True)
        else:
            # from workcenter kanban view
            action = self.env["ir.actions.actions"]._for_xml_id("mrp_workorder.mrp_workorder_action_tablet")
            action['domain'] = domain
            action['context'] = {
                'no_breadcrumbs': True,
                # 'search_default_workcenter_id': self.workcenter_id.id,
                'search_default_production_id': self.production_id.id,
                'from_manufacturing_order': True,
            }
        return clean_action(action, self.env)

    class QualityCheckInherit(models.Model):
        _inherit = "quality.check"
        @api.depends('workorder_id.state', 'quality_state', 'workorder_id.qty_producing_custom',
                     'component_tracking', 'test_type', 'component_id', 'move_line_id.lot_id'
                     )
        def _compute_component_data(self):
            self.component_remaining_qty = False
            self.component_uom_id = False
            # self.qty_done =False
            for check in self:
                if check.test_type in ('register_byproducts', 'register_consumed_materials'):
                    if check.quality_state == 'none':
                        completed_lines = check.workorder_id.move_line_ids.filtered(lambda l: l.lot_id) if check.component_id.tracking != 'none' else check.workorder_id.move_line_ids
                        if check.move_id.additional:
                            qty = check.workorder_id.qty_remaining
                        else:
                            qty = check.workorder_id.qty_producing_custom
                        check.component_remaining_qty = self._prepare_component_quantity(check.move_id, qty) - sum(completed_lines.mapped('qty_done'))
                        # check.qty_done = check.component_remaining_qty
                    check.component_uom_id = check.move_id.product_uom

        def _get_print_qty(self):
            if self.product_id.uom_id.category_id == self.env.ref('uom.product_uom_categ_unit'):
                qty = int(self.workorder_id.qty_producing_custom)
            else:
                qty = 1
            return qty

        @api.model
        def _prepare_component_quantity(self, move, qty_producing_custom):
            """ helper that computes quantity to consume (or to create in case of byproduct)
            depending on the quantity producing and the move's unit factor"""
            if move.product_id.tracking == 'serial':
                uom = move.product_id.uom_id
            else:
                uom = move.product_uom
            return move.product_uom._compute_quantity(
                qty_producing_custom * move.unit_factor,
                uom,
                round=False
            )

        def _next(self, continue_production=False):
            """ This function:

            - first: fullfill related move line with right lot and validated quantity.
            - second: Generate new quality check for remaining quantity and link them to the original check.
            - third: Pass to the next check or return a failure message.
            """
            self.ensure_one()
            rounding = self.workorder_id.product_uom_id.rounding
            if float_compare(self.workorder_id.qty_producing_custom, 0, precision_rounding=rounding) <= 0:
                raise UserError(_('Please ensure the quantity to produce is greater than 0.'))
            elif self.test_type in ('register_byproducts', 'register_consumed_materials'):
                # Form validation
                # in case we use continue production instead of validate button.
                # We would like to consume 0 and leave lot_id blank to close the consumption
                rounding = self.component_uom_id.rounding
                if self.component_tracking != 'none' and not self.lot_id and self.qty_done != 0:
                    raise UserError(_('Please enter a Lot/SN.'))
                if float_compare(self.qty_done, 0, precision_rounding=rounding) < 0:
                    raise UserError(_('Please enter a positive quantity.'))

                # Write the lot and qty to the move line
                if self.move_line_id:
                    # In case of a tracked component, another SML may already exists for
                    # the reservation of self.lot_id, so let's try to find and use it
                    if self.move_line_id.product_id.tracking != 'none':
                        self.move_line_id = next((sml
                                                  for sml in self.move_line_id.move_id.move_line_ids
                                                  if sml.lot_id == self.lot_id and float_is_zero(sml.qty_done, precision_rounding=sml.product_uom_id.rounding)),
                                                 self.move_line_id)
                    rounding = self.move_line_id.product_uom_id.rounding
                    if float_compare(self.qty_done, self.move_line_id.reserved_uom_qty, precision_rounding=rounding) >= 0:
                        self.move_line_id.write({
                            'qty_done': self.qty_done,
                            'lot_id': self.lot_id.id,
                        })
                    else:
                        new_qty_reserved = self.move_line_id.reserved_uom_qty - self.qty_done
                        default = {
                            'reserved_uom_qty': new_qty_reserved,
                            'qty_done': 0,
                        }
                        self.move_line_id.copy(default=default)
                        self.move_line_id.with_context(bypass_reservation_update=True).write({
                            'reserved_uom_qty': self.qty_done,
                            'qty_done': self.qty_done,
                        })
                        self.move_line_id.lot_id = self.lot_id
                else:
                    line = self.env['stock.move.line'].create(self._create_extra_move_lines())
                    self.move_line_id = line[:1]
                if continue_production:
                    self.workorder_id._create_subsequent_checks()

            if self.test_type == 'picture' and not self.picture:
                raise UserError(_('Please upload a picture.'))

            if self.quality_state == 'none':
                self.do_pass()

            self.workorder_id._change_quality_check(position='next')

        def _update_component_quantity(self):
            if self.component_tracking == 'serial':
                self._origin.qty_done = self.component_id.uom_id._compute_quantity(1, self.component_uom_id, rounding_method='HALF-UP')
                return
            move = self.move_id
            # Compute the new quantity for the current component
            rounding = move.product_uom.rounding
            new_qty = self._prepare_component_quantity(move, self.workorder_id.qty_producing_custom)
            qty_todo = float_round(new_qty, precision_rounding=rounding)
            qty_todo = qty_todo - move.quantity_done
            if self.move_line_id and self.move_line_id.lot_id:
                qty_todo = min(self.move_line_id.reserved_uom_qty, qty_todo)
            self.qty_done = qty_todo


# change in base code by geminatecs
# file location of change code :-
# enterprise/mrp_workorder/models/quality.py", line 386, in _create_extra_move_lines
#  **** base original code ****
# quantity = self.product_id.uom_id._compute_quantity(quantity, self.product_uom_id, rounding_method='HALF-UP')
# **************************** #
# change by geminatecs
# quantity = self.product_id.uom_id._compute_quantity(quantity, self.move_id.product_uom.id, rounding_method='HALF-UP')
#######################
