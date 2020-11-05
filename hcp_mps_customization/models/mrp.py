# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import namedtuple, OrderedDict, defaultdict
from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, registry, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import split_every
from psycopg2 import OperationalError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_is_zero, float_round



from werkzeug.urls import url_encode

class MrpBOM(models.Model):
    _inherit = 'mrp.bom'
    
    is_main_bom = fields.Boolean('Is this main BOM?')

class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'    
    
    Procurement = namedtuple('Procurement', ['product_id', 'product_qty',
        'product_uom', 'location_id', 'name', 'origin', 'company_id', 'values','mo_reference'])
    
class MrpProduction(models.Model):
    _inherit = 'mrp.production'
    
    mo_reference = fields.Char('MPS Reference')

class MrpProductionSchedule(models.Model):
    _inherit = 'mrp.production.schedule'
    

    def action_replenish(self, based_on_lead_time=False):
        """ Run the procurement for production schedule in self. Once the
        procurements are launched, mark the forecast as launched (only used
        for state 'to_relaunch')

        :param based_on_lead_time: 2 replenishment options exists in MPS.
        based_on_lead_time means that the procurement for self will be launched
        based on lead times.
        e.g. period are daily and the product have a manufacturing period
        of 5 days, then it will try to run the procurements for the 5 first
        period of the schedule.
        If based_on_lead_time is False then it will run the procurement for the
        first period that need a replenishment
        """
        production_schedule_states = self.get_production_schedule_view_state()
        production_schedule_states = {mps['id']: mps for mps in production_schedule_states}
        procurements = []
        forecasts_values = []
        forecasts_to_set_as_launched = self.env['mrp.product.forecast']
        for production_schedule in self:
            production_schedule_state = production_schedule_states[production_schedule.id]
            # Cells with values 'to_replenish' means that they are based on
            # lead times. There is at maximum one forecast by schedule with
            # 'forced_replenish', it's the cell that need a modification with
            #  the smallest start date.
            replenishment_field = based_on_lead_time and 'to_replenish' or 'forced_replenish'
            forecasts_to_replenish = filter(lambda f: f[replenishment_field], production_schedule_state['forecast_ids'])
            for forecast in forecasts_to_replenish:
                existing_forecasts = production_schedule.forecast_ids.filtered(lambda p:
                    p.date >= forecast['date_start'] and p.date <= forecast['date_stop']
                )
                extra_values = production_schedule._get_procurement_extra_values(forecast)
                next_sequence= self.env['ir.sequence'].with_context(force_company=self.company_id.id).next_by_code(
                    'mrp.production.schedule') or _('New')
                procurements.append(self.env['procurement.group'].Procurement(
                    production_schedule.product_id,
                    forecast['replenish_qty'] - forecast['incoming_qty'],
                    production_schedule.product_uom_id,
                    production_schedule.warehouse_id.lot_stock_id,
                    production_schedule.product_id.name,
                    'MPS', production_schedule.company_id, extra_values,next_sequence
                ))

                if existing_forecasts:
                    forecasts_to_set_as_launched |= existing_forecasts
                else:
                    forecasts_values.append({
                        'forecast_qty': 0,
                        'date': forecast['date_stop'],
                        'procurement_launched': True,
                        'production_schedule_id': production_schedule.id
                    })
        if procurements:
            self.env['procurement.group'].with_context(skip_lead_time=True).run(procurements)

        forecasts_to_set_as_launched.write({
            'procurement_launched': True,
        })
        if forecasts_values:
            self.env['mrp.product.forecast'].create(forecasts_values)
            
class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values, mo_reference, bom):
        date_deadline = fields.Datetime.to_string(self._get_date_planned(product_id, company_id, values))
        if origin != 'MPS':
            mrp_obj = self.env['mrp.production'].search([('name','=', origin)])
            mps_origin = mrp_obj.mo_reference
            if mps_origin:
                mo_reference = mps_origin
        return {
            'origin': origin,
            'product_id': product_id.id,
            'product_qty': product_qty,
            'product_uom_id': product_uom.id,
            'location_src_id': self.location_src_id.id or self.picking_type_id.default_location_src_id.id or location_id.id,
            'location_dest_id': location_id.id,
            'bom_id': bom.id,
            'date_deadline': date_deadline,
            'date_planned_finished': fields.Datetime.from_string(values['date_planned']),
            'date_planned_start': date_deadline,
            'procurement_group_id': False,
            'propagate_cancel': self.propagate_cancel,
            'propagate_date': self.propagate_date,
            'propagate_date_minimum_delta': self.propagate_date_minimum_delta,
            'orderpoint_id': values.get('orderpoint_id', False) and values.get('orderpoint_id').id,
            'picking_type_id': self.picking_type_id.id or values['warehouse_id'].manu_type_id.id,
            'company_id': company_id.id,
            'move_dest_ids': values.get('move_dest_ids') and [(4, x.id) for x in values['move_dest_ids']] or False,
            'user_id': False,
            'mo_reference':mo_reference
        }

    @api.model
    def _merge_procurements(self, procurements_to_merge):
        """ Merge the quantity for procurements requests that could use the same
        order line.
        params similar_procurements list: list of procurements that have been
        marked as 'alike' from _get_procurements_to_merge method.
        return a list of procurements values where values of similar_procurements
        list have been merged.
        """
        merged_procurements = []
        for procurements in procurements_to_merge:
            quantity = 0
            move_dest_ids = self.env['stock.move']
            orderpoint_id = self.env['stock.warehouse.orderpoint']
            for procurement in procurements:
                if procurement.values.get('move_dest_ids'):
                    move_dest_ids |= procurement.values['move_dest_ids']
                if not orderpoint_id and procurement.values.get('orderpoint_id'):
                    orderpoint_id = procurement.values['orderpoint_id']
                quantity += procurement.product_qty
            # The merged procurement can be build from an arbitrary procurement
            # since they were mark as similar before. Only the quantity and
            # some keys in values are updated.
            values = dict(procurement.values)
            values.update({
                'move_dest_ids': move_dest_ids,
                'orderpoint_id': orderpoint_id,
            })
            mo_reference = False
            merged_procurement = self.env['procurement.group'].Procurement(
                procurement.product_id, quantity, procurement.product_uom,
                procurement.location_id, procurement.name, procurement.origin,
                procurement.company_id, values, mo_reference
            )
            merged_procurements.append(merged_procurement)
        return merged_procurements

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values,mo_reference):
        ''' Returns a dictionary of values that will be used to create a stock move from a procurement.
        This function assumes that the given procurement has a rule (action == 'pull' or 'pull_push') set on it.

        :param procurement: browse record
        :rtype: dictionary
        '''
        group_id = False
        if self.group_propagation_option == 'propagate':
            group_id = values.get('group_id', False) and values['group_id'].id
        elif self.group_propagation_option == 'fixed':
            group_id = self.group_id.id

        date_expected = fields.Datetime.to_string(
            fields.Datetime.from_string(values['date_planned']) - relativedelta(days=self.delay or 0)
        )
        # it is possible that we've already got some move done, so check for the done qty and create
        # a new move with the correct qty
        qty_left = product_qty
        move_values = {
            'name': name[:2000],
            'company_id': self.company_id.id or self.location_src_id.company_id.id or self.location_id.company_id.id or company_id.id,
            'product_id': product_id.id,
            'product_uom': product_uom.id,
            'product_uom_qty': qty_left,
            'partner_id': self.partner_address_id.id or (values.get('group_id', False) and values['group_id'].partner_id.id) or False,
            'location_id': self.location_src_id.id,
            'location_dest_id': location_id.id,
            'move_dest_ids': values.get('move_dest_ids', False) and [(4, x.id) for x in values['move_dest_ids']] or [],
            'rule_id': self.id,
            'procure_method': self.procure_method,
            'origin': origin,
            'picking_type_id': self.picking_type_id.id,
            'group_id': group_id,
            'route_ids': [(4, route.id) for route in values.get('route_ids', [])],
            'warehouse_id': self.propagate_warehouse_id.id or self.warehouse_id.id,
            'date': date_expected,
            'date_expected': date_expected,
            'propagate_cancel': self.propagate_cancel,
            'propagate_date': self.propagate_date,
            'propagate_date_minimum_delta': self.propagate_date_minimum_delta,
            'description_picking': product_id._get_description(self.picking_type_id),
            'priority': values.get('priority', "1"),
            'delay_alert': self.delay_alert,
        }
        for field in self._get_custom_move_fields():
            if field in values:
                move_values[field] = values.get(field)
        return move_values    
    
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    def _find_candidate(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values,mo_reference):
        """ Return the record in self where the procument with values passed as
        args can be merged. If it returns an empty record then a new line will
        be created.
        """
        lines = self.filtered(lambda l: l.propagate_date == values['propagate_date'] and l.propagate_date_minimum_delta == values['propagate_date_minimum_delta'] and l.propagate_cancel == values['propagate_cancel'])
        return lines and lines[0] or self.env['purchase.order.line']

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def _action_confirm(self, merge=True, merge_into=False):
        """ Confirms stock move or put it in waiting if it's linked to another move.
        :param: merge: According to this boolean, a newly confirmed move will be merged
        in another move of the same picking sharing its characteristics.
        """
        move_create_proc = self.env['stock.move']
        move_to_confirm = self.env['stock.move']
        move_waiting = self.env['stock.move']

        to_assign = {}
        for move in self:
            # if the move is preceeded, then it's waiting (if preceeding move is done, then action_assign has been called already and its state is already available)
            if move.move_orig_ids:
                move_waiting |= move
            else:
                if move.procure_method == 'make_to_order':
                    move_create_proc |= move
                else:
                    move_to_confirm |= move
            if move._should_be_assigned():
                key = (move.group_id.id, move.location_id.id, move.location_dest_id.id)
                if key not in to_assign:
                    to_assign[key] = self.env['stock.move']
                to_assign[key] |= move

        # create procurements for make to order moves
        procurement_requests = []
        for move in move_create_proc:
            values = move._prepare_procurement_values()
            mo_reference = False
            origin = (move.group_id and move.group_id.name or (move.origin or move.picking_id.name or "/"))
            procurement_requests.append(self.env['procurement.group'].Procurement(
                move.product_id, move.product_uom_qty, move.product_uom,
                move.location_id, move.rule_id and move.rule_id.name or "/",
                origin, move.company_id, values, mo_reference))
        self.env['procurement.group'].run(procurement_requests)

        move_to_confirm.write({'state': 'confirmed'})
        (move_waiting | move_create_proc).write({'state': 'waiting'})

        # assign picking in batch for all confirmed move that share the same details
        for moves in to_assign.values():
            moves._assign_picking()
        self._push_apply()
        self._check_company()
        if merge:
            return self._merge_moves(merge_into=merge_into)
        return self


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
        Launch procurement group run method with required/custom fields genrated by a
        sale order line. procurement group will launch '_run_pull', '_run_buy' or '_run_manufacture'
        depending on the sale order line product rule.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        procurements = []
        for line in self:
            if line.state != 'sale' or not line.product_id.type in ('consu','product'):
                continue
            qty = line._get_qty_procurement(previous_product_uom_qty)
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) >= 0:
                continue

            group_id = line._get_procurement_group()
            if not group_id:
                group_id = self.env['procurement.group'].create(line._prepare_procurement_group_vals())
                line.order_id.procurement_group_id = group_id
            else:
                # In case the procurement group is already created and the order was
                # cancelled, we need to update certain values of the group.
                updated_vals = {}
                if group_id.partner_id != line.order_id.partner_shipping_id:
                    updated_vals.update({'partner_id': line.order_id.partner_shipping_id.id})
                if group_id.move_type != line.order_id.picking_policy:
                    updated_vals.update({'move_type': line.order_id.picking_policy})
                if updated_vals:
                    group_id.write(updated_vals)

            values = line._prepare_procurement_values(group_id=group_id)
            product_qty = line.product_uom_qty - qty

            line_uom = line.product_uom
            quant_uom = line.product_id.uom_id
            product_qty, procurement_uom = line_uom._adjust_uom_quantities(product_qty, quant_uom)
            mo_reference = False
            procurements.append(self.env['procurement.group'].Procurement(
                line.product_id, product_qty, procurement_uom,
                line.order_id.partner_shipping_id.property_stock_customer,
                line.name, line.order_id.name, line.order_id.company_id, values,mo_reference))
        if procurements:
            self.env['procurement.group'].run(procurements)
        return True
