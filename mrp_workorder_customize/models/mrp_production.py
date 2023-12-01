# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import datetime
import math
import re

from ast import literal_eval
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
from odoo.tools.misc import OrderedSet, format_date, groupby as tools_groupby

from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES

SIZE_BACK_ORDER_NUMERING = 3
import pdb

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    original_quantity_production = fields.Float(string='Original Quantity', digits='Product Unit of Measure', copy=True)

    # def _split_productions(self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False):
    #     """ Splits productions into productions smaller quantities to produce, i.e. creates
    #     its backorders.

    #     :param dict amounts: a dict with a production as key and a list value containing
    #     the amounts each production split should produce including the original production,
    #     e.g. {mrp.production(1,): [3, 2]} will result in mrp.production(1,) having a product_qty=3
    #     and a new backorder with product_qty=2.
    #     :param bool cancel_remaining_qty: whether to cancel remaining quantities or generate
    #     an additional backorder, e.g. having product_qty=5 if mrp.production(1,) product_qty was 10.
    #     :param bool set_consumed_qty: whether to set qty_done on move lines to the reserved quantity
    #     or the initial demand if no reservation, except for the remaining backorder.
    #     :return: mrp.production records in order of [orig_prod_1, backorder_prod_1,
    #     backorder_prod_2, orig_prod_2, backorder_prod_2, etc.]
    #     """
    #     def _default_amounts(production):
    #         return [production.qty_producing, production._get_quantity_to_backorder()]

    #     if not amounts:
    #         amounts = {}
    #     has_backorder_to_ignore = defaultdict(lambda: False)
    #     for production in self:
    #         mo_amounts = amounts.get(production)
    #         if not mo_amounts:
    #             amounts[production] = _default_amounts(production)
    #             continue
    #         total_amount = sum(mo_amounts)
    #         diff = float_compare(production.product_qty, total_amount, precision_rounding=production.product_uom_id.rounding)
    #         if diff > 0 and not cancel_remaining_qty:
    #             amounts[production].append(production.product_qty - total_amount)
    #             has_backorder_to_ignore[production] = True
    #         elif not self.env.context.get('allow_more') and (diff < 0 or production.state in ['done', 'cancel']):
    #             raise UserError(_("Unable to split with more than the quantity to produce."))

    #     backorder_vals_list = []
    #     initial_qty_by_production = {}

    #     # Create the backorders.
    #     for production in self:
    #         initial_qty_by_production[production] = production.product_qty
    #         if production.backorder_sequence == 0:  # Activate backorder naming
    #             production.backorder_sequence = 1
    #         production.name = self._get_name_backorder(production.name, production.backorder_sequence)
    #         (production.move_raw_ids | production.move_finished_ids).name = production.name
    #         (production.move_raw_ids | production.move_finished_ids).origin = production._get_origin()
    #         backorder_vals = production.copy_data(default=production._get_backorder_mo_vals())[0]
    #         backorder_qtys = amounts[production][1:]
    #         production.product_qty = amounts[production][0]

    #         next_seq = max(production.procurement_group_id.mrp_production_ids.mapped("backorder_sequence"), default=1)

    #         for qty_to_backorder in backorder_qtys:
    #             next_seq += 1
    #             backorder_vals_list.append(dict(
    #                 backorder_vals,
    #                 product_qty=qty_to_backorder,
    #                 name=production._get_name_backorder(production.name, next_seq),
    #                 backorder_sequence=next_seq
    #             ))

    #     backorders = self.env['mrp.production'].with_context(skip_confirm=True).create(backorder_vals_list)

    #     index = 0
    #     production_to_backorders = {}
    #     production_ids = OrderedSet()
    #     for production in self:
    #         number_of_backorder_created = len(amounts.get(production, _default_amounts(production))) - 1
    #         production_backorders = backorders[index:index + number_of_backorder_created]
    #         production_to_backorders[production] = production_backorders
    #         production_ids.update(production.ids)
    #         production_ids.update(production_backorders.ids)
    #         index += number_of_backorder_created

    #     # Split the `stock.move` among new backorders.
    #     new_moves_vals = []
    #     moves = []
    #     move_to_backorder_moves = {}
    #     for production in self:
    #         for move in production.move_raw_ids | production.move_finished_ids:
    #             if move.additional:
    #                 continue
    #             move_to_backorder_moves[move] = self.env['stock.move']
    #             unit_factor = move.product_uom_qty / initial_qty_by_production[production]
    #             initial_move_vals = move.copy_data(move._get_backorder_move_vals())[0]
    #             move.with_context(do_not_unreserve=True).product_uom_qty = production.product_qty * unit_factor

    #             for backorder in production_to_backorders[production]:
    #                 move_vals = dict(
    #                     initial_move_vals,
    #                     product_uom_qty=backorder.product_qty * unit_factor
    #                 )
    #                 if move.raw_material_production_id:
    #                     move_vals['raw_material_production_id'] = backorder.id
    #                 else:
    #                     move_vals['production_id'] = backorder.id
    #                 new_moves_vals.append(move_vals)
    #                 moves.append(move)

    #     backorder_moves = self.env['stock.move'].create(new_moves_vals)
    #     # Split `stock.move.line`s. 2 options for this:
    #     # - do_unreserve -> action_assign
    #     # - Split the reserved amounts manually
    #     # The first option would be easier to maintain since it's less code
    #     # However it could be slower (due to `stock.quant` update) and could
    #     # create inconsistencies in mass production if a new lot higher in a
    #     # FIFO strategy arrives between the reservation and the backorder creation
    #     for move, backorder_move in zip(moves, backorder_moves):
    #         move_to_backorder_moves[move] |= backorder_move

    #     move_lines_vals = []
    #     assigned_moves = set()
    #     partially_assigned_moves = set()
    #     move_lines_to_unlink = set()

    #     for initial_move, backorder_moves in move_to_backorder_moves.items():
    #         # Create `stock.move.line` for consumed but non-reserved components and for by-products
    #         if (initial_move.raw_material_production_id or (initial_move.production_id and initial_move.product_id != production.product_id))\
    #             and not initial_move.move_line_ids and set_consumed_qty:
    #             ml_vals = initial_move._prepare_move_line_vals()
    #             backorder_move_to_ignore = backorder_moves[-1] if has_backorder_to_ignore[initial_move.raw_material_production_id] else self.env['stock.move']
    #             for move in list(initial_move + backorder_moves - backorder_move_to_ignore):
    #                 new_ml_vals = dict(
    #                     ml_vals,
    #                     qty_done=move.product_uom_qty,
    #                     move_id=move.id
    #                 )
    #                 move_lines_vals.append(new_ml_vals)

    #     for initial_move, backorder_moves in move_to_backorder_moves.items():
    #         ml_by_move = []
    #         product_uom = initial_move.product_id.uom_id
    #         for move_line in initial_move.move_line_ids:
    #             available_qty = move_line.product_uom_id._compute_quantity(move_line.reserved_uom_qty, product_uom)
    #             if float_compare(available_qty, 0, precision_rounding=move_line.product_uom_id.rounding) <= 0:
    #                 continue
    #             ml_by_move.append((available_qty, move_line, move_line.copy_data()[0]))

    #         initial_move.move_line_ids.with_context(bypass_reservation_update=True).write({'reserved_uom_qty': 0})
    #         moves = list(initial_move | backorder_moves)

    #         move = moves and moves.pop(0)
    #         move_qty_to_reserve = move.product_qty

    #         for index, (quantity, move_line, ml_vals) in enumerate(ml_by_move):
    #             taken_qty = min(quantity, move_qty_to_reserve, move_line.product_uom_id._compute_quantity(move_line.qty_done, product_uom))
    #             taken_qty_uom = product_uom._compute_quantity(taken_qty, move_line.product_uom_id)
    #             if float_is_zero(taken_qty_uom, precision_rounding=move_line.product_uom_id.rounding):
    #                 continue
    #             move_line.with_context(bypass_reservation_update=True).reserved_uom_qty = taken_qty_uom
    #             move_qty_to_reserve -= taken_qty
    #             ml_by_move[index] = (quantity - taken_qty, move_line, ml_vals)

    #             if float_compare(move_qty_to_reserve, 0, precision_rounding=move.product_uom.rounding) <= 0:
    #                 assigned_moves.add(move.id)
    #                 move = moves and moves.pop(0)
    #                 move_qty_to_reserve = move and move.product_qty or 0

    #         for quantity, move_line, ml_vals in ml_by_move:
    #             while float_compare(quantity, 0, precision_rounding=product_uom.rounding) > 0 and move:
    #                 # Do not create `stock.move.line` if there is no initial demand on `stock.move`
    #                 taken_qty = min(move_qty_to_reserve, quantity)
    #                 taken_qty_uom = product_uom._compute_quantity(taken_qty, move_line.product_uom_id)
    #                 if move == initial_move:
    #                     move_line.with_context(bypass_reservation_update=True).reserved_uom_qty += taken_qty_uom
    #                     if set_consumed_qty and not move.production_id:
    #                         move_line.qty_done += taken_qty_uom
    #                 elif not float_is_zero(taken_qty_uom, precision_rounding=move_line.product_uom_id.rounding):
    #                     new_ml_vals = dict(
    #                         ml_vals,
    #                         reserved_uom_qty=taken_qty_uom,
    #                         move_id=move.id
    #                     )
    #                     if set_consumed_qty and not move.production_id:
    #                         new_ml_vals['qty_done'] = taken_qty_uom
    #                     move_lines_vals.append(new_ml_vals)
    #                 quantity -= taken_qty
    #                 move_qty_to_reserve -= taken_qty

    #                 if float_compare(move_qty_to_reserve, 0, precision_rounding=move.product_uom.rounding) <= 0:
    #                     assigned_moves.add(move.id)
    #                     move = moves and moves.pop(0)
    #                     move_qty_to_reserve = move and move.product_qty or 0

    #             # Unreserve the quantity removed from initial `stock.move.line` and
    #             # not assigned to a move anymore. In case of a split smaller than initial
    #             # quantity and fully reserved
    #             if quantity:
    #                 self.env['stock.quant']._update_reserved_quantity(
    #                     move_line.product_id, move_line.location_id, -quantity,
    #                     lot_id=move_line.lot_id, package_id=move_line.package_id,
    #                     owner_id=move_line.owner_id, strict=True)

    #         if move and move_qty_to_reserve != move.product_qty:
    #             partially_assigned_moves.add(move.id)

    #         move_lines_to_unlink.update(initial_move.move_line_ids.filtered(
    #             lambda ml: not ml.reserved_uom_qty and not ml.qty_done).ids)

    #     self.env['stock.move'].browse(assigned_moves).write({'state': 'assigned'})
    #     self.env['stock.move'].browse(partially_assigned_moves).write({'state': 'partially_available'})
    #     # Avoid triggering a useless _recompute_state
    #     self.env['stock.move.line'].browse(move_lines_to_unlink).write({'move_id': False})
    #     self.env['stock.move.line'].browse(move_lines_to_unlink).unlink()
    #     self.env['stock.move.line'].create(move_lines_vals)

    #     workorders_to_cancel = self.env['mrp.workorder']
    #     for production in self:
    #         initial_qty = initial_qty_by_production[production]
    #         initial_workorder_remaining_qty = []
    #         bo = production_to_backorders[production]

    #         # Adapt duration
    #         for workorder in bo.workorder_ids:
    #             workorder.duration_expected = workorder._get_duration_expected()

    #         # Adapt quantities produced
    #         for workorder in production.workorder_ids:
    #             initial_workorder_remaining_qty.append(max(initial_qty - workorder.qty_reported_from_previous_wo - workorder.qty_produced, 0))
    #             workorder.qty_produced = min(workorder.qty_produced, workorder.qty_production)
    #         workorders_len = len(production.workorder_ids)
    #         for index, workorder in enumerate(bo.workorder_ids):
    #             remaining_qty = initial_workorder_remaining_qty[index % workorders_len]
    #             # workorder.qty_reported_from_previous_wo = max(workorder.qty_production - remaining_qty, 0)
    #             workorder.qty_reported_from_previous_wo = remaining_qty
    #             # print('Sumit11', workorder.name, workorder.qty_reported_from_previous_wo, remaining_qty)
    #             if remaining_qty:
    #                 initial_workorder_remaining_qty[index % workorders_len] = max(remaining_qty - workorder.qty_produced, 0)
    #             else:
    #                 workorders_to_cancel += workorder
    #     workorders_to_cancel.action_cancel()
    #     backorders._action_confirm_mo_backorders()

    # def button_mark_done(self):
    #     res = super(MrpProduction, self).button_mark_done()
    #     for mrp in self:
    #         if mrp.original_quantity_production ==0:
    #             mrp.write({'original_quantity_production': mrp.product_uom_qty})
    #     return res

    # def _split_productions(self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False):
    #     """ Splits productions into productions smaller quantities to produce, i.e. creates
    #     its backorders.

    #     :param dict amounts: a dict with a production as key and a list value containing
    #     the amounts each production split should produce including the original production,
    #     e.g. {mrp.production(1,): [3, 2]} will result in mrp.production(1,) having a product_qty=3
    #     and a new backorder with product_qty=2.
    #     :param bool cancel_remaining_qty: whether to cancel remaining quantities or generate
    #     an additional backorder, e.g. having product_qty=5 if mrp.production(1,) product_qty was 10.
    #     :param bool set_consumed_qty: whether to set qty_done on move lines to the reserved quantity
    #     or the initial demand if no reservation, except for the remaining backorder.
    #     :return: mrp.production records in order of [orig_prod_1, backorder_prod_1,
    #     backorder_prod_2, orig_prod_2, backorder_prod_2, etc.]
    #     """
    #     def _default_amounts(production):
    #         return [production.qty_producing, production._get_quantity_to_backorder()]

    #     if not amounts:
    #         amounts = {}
    #     has_backorder_to_ignore = defaultdict(lambda: False)
    #     for production in self:
    #         mo_amounts = amounts.get(production)
    #         if not mo_amounts:
    #             amounts[production] = _default_amounts(production)
    #             continue
    #         total_amount = sum(mo_amounts)
    #         diff = float_compare(production.product_qty, total_amount, precision_rounding=production.product_uom_id.rounding)
    #         if diff > 0 and not cancel_remaining_qty:
    #             amounts[production].append(production.product_qty - total_amount)
    #             has_backorder_to_ignore[production] = True
    #         elif not self.env.context.get('allow_more') and (diff < 0 or production.state in ['done', 'cancel']):
    #             raise UserError(_("Unable to split with more than the quantity to produce."))

    #     backorder_vals_list = []
    #     initial_qty_by_production = {}

    #     # Create the backorders.
    #     for production in self:
    #         initial_qty_by_production[production] = production.product_qty
    #         if production.backorder_sequence == 0:  # Activate backorder naming
    #             production.backorder_sequence = 1
    #         production.name = self._get_name_backorder(production.name, production.backorder_sequence)
    #         (production.move_raw_ids | production.move_finished_ids).name = production.name
    #         (production.move_raw_ids | production.move_finished_ids).origin = production._get_origin()
    #         backorder_vals = production.copy_data(default=production._get_backorder_mo_vals())[0]
    #         backorder_qtys = amounts[production][1:]
    #         production.product_qty = amounts[production][0]

    #         next_seq = max(production.procurement_group_id.mrp_production_ids.mapped("backorder_sequence"), default=1)

    #         for qty_to_backorder in backorder_qtys:
    #             next_seq += 1
    #             backorder_vals_list.append(dict(
    #                 backorder_vals,
    #                 product_qty=qty_to_backorder,
    #                 name=production._get_name_backorder(production.name, next_seq),
    #                 backorder_sequence=next_seq
    #             ))

    #     backorders = self.env['mrp.production'].with_context(skip_confirm=True).create(backorder_vals_list)

    #     index = 0
    #     production_to_backorders = {}
    #     production_ids = OrderedSet()
    #     for production in self:
    #         number_of_backorder_created = len(amounts.get(production, _default_amounts(production))) - 1
    #         production_backorders = backorders[index:index + number_of_backorder_created]
    #         production_to_backorders[production] = production_backorders
    #         production_ids.update(production.ids)
    #         production_ids.update(production_backorders.ids)
    #         index += number_of_backorder_created

    #     # Split the `stock.move` among new backorders.
    #     new_moves_vals = []
    #     moves = []
    #     move_to_backorder_moves = {}
    #     for production in self:
    #         for move in production.move_raw_ids | production.move_finished_ids:
    #             if move.additional:
    #                 continue
    #             move_to_backorder_moves[move] = self.env['stock.move']
    #             unit_factor = move.product_uom_qty / initial_qty_by_production[production]
    #             initial_move_vals = move.copy_data(move._get_backorder_move_vals())[0]
    #             move.with_context(do_not_unreserve=True).product_uom_qty = production.product_qty * unit_factor

    #             for backorder in production_to_backorders[production]:
    #                 move_vals = dict(
    #                     initial_move_vals,
    #                     product_uom_qty=backorder.product_qty * unit_factor
    #                 )
    #                 if move.raw_material_production_id:
    #                     move_vals['raw_material_production_id'] = backorder.id
    #                 else:
    #                     move_vals['production_id'] = backorder.id
    #                 new_moves_vals.append(move_vals)
    #                 moves.append(move)

    #     backorder_moves = self.env['stock.move'].create(new_moves_vals)
    #     # Split `stock.move.line`s. 2 options for this:
    #     # - do_unreserve -> action_assign
    #     # - Split the reserved amounts manually
    #     # The first option would be easier to maintain since it's less code
    #     # However it could be slower (due to `stock.quant` update) and could
    #     # create inconsistencies in mass production if a new lot higher in a
    #     # FIFO strategy arrives between the reservation and the backorder creation
    #     for move, backorder_move in zip(moves, backorder_moves):
    #         move_to_backorder_moves[move] |= backorder_move

    #     move_lines_vals = []
    #     assigned_moves = set()
    #     partially_assigned_moves = set()
    #     move_lines_to_unlink = set()

    #     for initial_move, backorder_moves in move_to_backorder_moves.items():
    #         # Create `stock.move.line` for consumed but non-reserved components and for by-products
    #         if (initial_move.raw_material_production_id or (initial_move.production_id and initial_move.product_id != production.product_id))\
    #             and not initial_move.move_line_ids and set_consumed_qty:
    #             ml_vals = initial_move._prepare_move_line_vals()
    #             backorder_move_to_ignore = backorder_moves[-1] if has_backorder_to_ignore[initial_move.raw_material_production_id] else self.env['stock.move']
    #             for move in list(initial_move + backorder_moves - backorder_move_to_ignore):
    #                 new_ml_vals = dict(
    #                     ml_vals,
    #                     qty_done=move.product_uom_qty,
    #                     move_id=move.id
    #                 )
    #                 move_lines_vals.append(new_ml_vals)

    #     for initial_move, backorder_moves in move_to_backorder_moves.items():
    #         ml_by_move = []
    #         product_uom = initial_move.product_id.uom_id
    #         for move_line in initial_move.move_line_ids:
    #             available_qty = move_line.product_uom_id._compute_quantity(move_line.reserved_uom_qty, product_uom)
    #             if float_compare(available_qty, 0, precision_rounding=move_line.product_uom_id.rounding) <= 0:
    #                 continue
    #             ml_by_move.append((available_qty, move_line, move_line.copy_data()[0]))

    #         initial_move.move_line_ids.with_context(bypass_reservation_update=True).write({'reserved_uom_qty': 0})
    #         moves = list(initial_move | backorder_moves)

    #         move = moves and moves.pop(0)
    #         move_qty_to_reserve = move.product_qty

    #         for index, (quantity, move_line, ml_vals) in enumerate(ml_by_move):
    #             taken_qty = min(quantity, move_qty_to_reserve, move_line.product_uom_id._compute_quantity(move_line.qty_done, product_uom))
    #             taken_qty_uom = product_uom._compute_quantity(taken_qty, move_line.product_uom_id)
    #             if float_is_zero(taken_qty_uom, precision_rounding=move_line.product_uom_id.rounding):
    #                 continue
    #             move_line.with_context(bypass_reservation_update=True).reserved_uom_qty = taken_qty_uom
    #             move_qty_to_reserve -= taken_qty
    #             ml_by_move[index] = (quantity - taken_qty, move_line, ml_vals)

    #             if float_compare(move_qty_to_reserve, 0, precision_rounding=move.product_uom.rounding) <= 0:
    #                 assigned_moves.add(move.id)
    #                 move = moves and moves.pop(0)
    #                 move_qty_to_reserve = move and move.product_qty or 0

    #         for quantity, move_line, ml_vals in ml_by_move:
    #             while float_compare(quantity, 0, precision_rounding=product_uom.rounding) > 0 and move:
    #                 # Do not create `stock.move.line` if there is no initial demand on `stock.move`
    #                 taken_qty = min(move_qty_to_reserve, quantity)
    #                 taken_qty_uom = product_uom._compute_quantity(taken_qty, move_line.product_uom_id)
    #                 if move == initial_move:
    #                     move_line.with_context(bypass_reservation_update=True).reserved_uom_qty += taken_qty_uom
    #                     if set_consumed_qty and not move.production_id:
    #                         move_line.qty_done += taken_qty_uom
    #                 elif not float_is_zero(taken_qty_uom, precision_rounding=move_line.product_uom_id.rounding):
    #                     new_ml_vals = dict(
    #                         ml_vals,
    #                         reserved_uom_qty=taken_qty_uom,
    #                         move_id=move.id
    #                     )
    #                     if set_consumed_qty and not move.production_id:
    #                         new_ml_vals['qty_done'] = taken_qty_uom
    #                     move_lines_vals.append(new_ml_vals)
    #                 quantity -= taken_qty
    #                 move_qty_to_reserve -= taken_qty

    #                 if float_compare(move_qty_to_reserve, 0, precision_rounding=move.product_uom.rounding) <= 0:
    #                     assigned_moves.add(move.id)
    #                     move = moves and moves.pop(0)
    #                     move_qty_to_reserve = move and move.product_qty or 0

    #             # Unreserve the quantity removed from initial `stock.move.line` and
    #             # not assigned to a move anymore. In case of a split smaller than initial
    #             # quantity and fully reserved
    #             if quantity:
    #                 self.env['stock.quant']._update_reserved_quantity(
    #                     move_line.product_id, move_line.location_id, -quantity,
    #                     lot_id=move_line.lot_id, package_id=move_line.package_id,
    #                     owner_id=move_line.owner_id, strict=True)

    #         if move and move_qty_to_reserve != move.product_qty:
    #             partially_assigned_moves.add(move.id)

    #         move_lines_to_unlink.update(initial_move.move_line_ids.filtered(
    #             lambda ml: not ml.reserved_uom_qty and not ml.qty_done).ids)

    #     self.env['stock.move'].browse(assigned_moves).write({'state': 'assigned'})
    #     self.env['stock.move'].browse(partially_assigned_moves).write({'state': 'partially_available'})
    #     # Avoid triggering a useless _recompute_state
    #     self.env['stock.move.line'].browse(move_lines_to_unlink).write({'move_id': False})
    #     self.env['stock.move.line'].browse(move_lines_to_unlink).unlink()
    #     self.env['stock.move.line'].create(move_lines_vals)

    #     workorders_to_cancel = self.env['mrp.workorder']
    #     for production in self:
    #         initial_qty = initial_qty_by_production[production]
    #         initial_workorder_remaining_qty = []
    #         bo = production_to_backorders[production]

    #         # Adapt duration
    #         for workorder in bo.workorder_ids:
    #             workorder.duration_expected = workorder._get_duration_expected()

    #         # Adapt quantities produced
    #         for workorder in production.workorder_ids:
    #             initial_workorder_remaining_qty.append(max(initial_qty - workorder.qty_reported_from_previous_wo - workorder.qty_produced, 0))
    #             workorder.qty_produced = min(workorder.qty_produced, workorder.qty_production)
    #         workorders_len = len(production.workorder_ids)
    #         for index, workorder in enumerate(bo.workorder_ids):
    #             # remaining_qty = initial_workorder_remaining_qty[index % workorders_len]
    #             # backorder_ids = self.procurement_group_id.mrp_production_ids.ids
    #             # total_qty_produced=0
    #             # for mrp_line in backorder_ids:
    #             #     mrp_production = self.sudo().search([('id', '=', mrp_line)])
    #             #     mrp_workorder = self.env['mrp.workorder'].sudo().search([('production_id', '=', mrp_production.id)])
    #             #     for workorder_line1 in mrp_workorder:
    #             #         total_qty_produced += workorder_line1.qty_produced
    #             # pdb.set_trace()
    #             # remaining_qty = max(workorder.production_id.original_quantity_production - total_qty_produced, 0)
    #             remaining_qty = initial_workorder_remaining_qty[index % workorders_len]
    #             workorder.qty_reported_from_previous_wo = max(workorder.qty_production - remaining_qty, 0)
    #             print('Sumit11', workorder.name, workorder.qty_reported_from_previous_wo, remaining_qty)
    #             if remaining_qty:
    #                 initial_workorder_remaining_qty[index % workorders_len] = max(remaining_qty - workorder.qty_produced, 0)
    #             else:
    #                 workorders_to_cancel += workorder
    #     workorders_to_cancel.action_cancel()
    #     backorders._action_confirm_mo_backorders()