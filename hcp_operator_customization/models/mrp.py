# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict, namedtuple
from math import log10

from odoo import api, fields, models, _
from odoo.tools.date_utils import add, subtract
from odoo.tools.float_utils import float_round
from odoo.osv.expression import OR, AND
from odoo.exceptions  import UserError

import logging
import threading
from odoo.exceptions import AccessError, ValidationError, MissingError

_logger = logging.getLogger(__name__)

class MrpProduction(models.Model):
    _inherit = 'mrp.production'
    
    #def action_replenish(self, based_on_lead_time=False):
        #self.env['procurement.group'].run_scheduler()
        #super(MrpProductionSchedule, self).action_replenish()
    def button_mark_done(self):
        #for workorder in self.workorder_ids:
            #if workorder.state != "done":
                #raise ValidationError("Some of your work orders are still pending")
        self._button_mark_done_sanity_checks()
        if not self.env.context.get('button_mark_done_production_ids'):
            self = self.with_context(button_mark_done_production_ids=self.ids)
        res = self._pre_button_mark_done()
        if res is not True:
            return res

        if self.env.context.get('mo_ids_to_backorder'):
            productions_to_backorder = self.browse(self.env.context['mo_ids_to_backorder'])
            productions_not_to_backorder = self - productions_to_backorder
        else:
            productions_not_to_backorder = self
            productions_to_backorder = self.env['mrp.production']

        self.workorder_ids.button_finish()

        backorders = productions_to_backorder and productions_to_backorder._split_productions()
        backorders = backorders - productions_to_backorder

        productions_not_to_backorder._post_inventory(cancel_backorder=True)
        productions_to_backorder._post_inventory(cancel_backorder=True)

        # if completed products make other confirmed/partially_available moves available, assign them
        done_move_finished_ids = (
                    productions_to_backorder.move_finished_ids | productions_not_to_backorder.move_finished_ids).filtered(
            lambda m: m.state == 'done')
        done_move_finished_ids._trigger_assign()

        # Moves without quantity done are not posted => set them as done instead of canceling. In
        # case the user edits the MO later on and sets some consumed quantity on those, we do not
        # want the move lines to be canceled.
        (productions_not_to_backorder.move_raw_ids | productions_not_to_backorder.move_finished_ids).filtered(
            lambda x: x.state not in ('done', 'cancel')).write({
            'state': 'done',
            'product_uom_qty': 0.0,
        })
        for production in self:
            production.write({
                'date_finished': fields.Datetime.now(),
                'product_qty': production.qty_produced,
                'priority': '0',
                'is_locked': True,
                'state': 'done',
            })

        if not backorders:
            if self.env.context.get('from_workorder'):
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'mrp.production',
                    'views': [[self.env.ref('mrp.mrp_production_form_view').id, 'form']],
                    'res_id': self.id,
                    'target': 'main',
                }
            if self.user_has_groups(
                    'mrp.group_mrp_reception_report') and self.picking_type_id.auto_show_reception_report:
                lines = self.move_finished_ids.filtered(lambda
                                                            m: m.product_id.type == 'product' and m.state != 'cancel' and m.quantity_done and not m.move_dest_ids)
                if lines:
                    if any(mo.show_allocation for mo in self):
                        action = self.action_view_reception_report()
                        return action
            return True
        context = self.env.context.copy()
        context = {k: v for k, v in context.items() if not k.startswith('default_')}
        for k, v in context.items():
            if k.startswith('skip_'):
                context[k] = False
        action = {
            'res_model': 'mrp.production',
            'type': 'ir.actions.act_window',
            'context': dict(context, mo_ids_to_backorder=None, button_mark_done_production_ids=None)
        }
        if len(backorders) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': backorders[0].id,
            })
        else:
            action.update({
                'name': _("Backorder MO"),
                'domain': [('id', 'in', backorders.ids)],
                'view_mode': 'tree,form',
            })
        return action

    def update_workorder_qty1(self):
        for mrp in self:
            for workorder in mrp.workorder_ids.filtered(lambda x:x.state != 'cancel'):
                backorder_ids = self.procurement_group_id.mrp_production_ids.ids
                total_qty_produced=0
                # pdb.set_trace()
                for mrp_line in backorder_ids:
                    mrp_production = self.sudo().search([('id', '=', mrp_line)])
                    domain11 = [('production_id', '=', mrp_production.id), ('workcenter_id', '=', workorder.id)]
                    mrp_workorder = self.env['mrp.workorder'].sudo().search(domain11)
                    for workorder_line1 in mrp_workorder:
                        pdb.set_trace()
                        total_qty_produced += workorder_line1.qty_produced
                # value = workorder.production_id.original_quantity_production - workorder.production_id.product_uom_qty
                workorder.write({'qty_reported_from_previous_wo': total_qty_produced})
                    
class StockScrap(models.Model):
    _inherit="stock.scrap"

    def do_scrap(self):
        if self.env.user.has_group('hcp_operator_customization.group_mrp_operator'):
            self._check_company()
            for scrap in self:
                scrap.name = self.env['ir.sequence'].next_by_code('stock.scrap') or _('New')
                # move = self.env['stock.move'].create(scrap._prepare_move_values())
                # # master: replace context by cancel_backorder
                # move.with_context(is_scrap=True)._action_assign()
                scrap.write({ 'state': 'draft'})
                scrap.date_done = fields.Datetime.now()
            return True
        else:
            return super(StockScrap,self).do_scrap()
			
class IrAttachment(models.Model):

      _inherit='ir.attachment'
      public = fields.Boolean('Is public document',readonly=False)
	  
      @api.model
      def check(self, mode, values=None):
        """Restricts the access to an ir.attachment, according to referred model
        In the 'document' module, it is overridden to relax this hard rule, since
        more complex ones apply there.
        """
        if self.env.is_superuser():
            return True
        # collect the records to check (by model)
        model_ids = defaultdict(set)            # {model_name: set(ids)}
        require_employee = False
        if self:
            # DLE P173: `test_01_portal_attachment`
            self.env['ir.attachment'].flush(['res_model', 'res_id', 'create_uid', 'public', 'res_field'])
            self._cr.execute('SELECT res_model, res_id, create_uid, public, res_field FROM ir_attachment WHERE id IN %s', [tuple(self.ids)])
            for res_model, res_id, create_uid, public, res_field in self._cr.fetchall():
                if public and mode == 'read':
                    continue
                logging.info('%s--------------res_id',not self.env.is_system())
                # if not self.env.is_system() and (res_field or (not res_id and create_uid != self.env.uid)):
                    # raise AccessError(_("Sorry, you are not allowed to access this document."))
                if not (res_model and res_id):
                    if create_uid != self._uid:
                        require_employee = True
                    continue
                model_ids[res_model].add(res_id)
        if values and values.get('res_model') and values.get('res_id'):
            model_ids[values['res_model']].add(values['res_id'])

        # check access rights on the records
        for res_model, res_ids in model_ids.items():
            # ignore attachments that are not attached to a resource anymore
            # when checking access rights (resource was deleted but attachment
            # was not)
            if res_model not in self.env:
                require_employee = True
                continue
            elif res_model == 'res.users' and len(res_ids) == 1 and self._uid == list(res_ids)[0]:
                # by default a user cannot write on itself, despite the list of writeable fields
                # e.g. in the case of a user inserting an image into his image signature
                # we need to bypass this check which would needlessly throw us away
                continue
            records = self.env[res_model].browse(res_ids).exists()
            if len(records) < len(res_ids):
                require_employee = True
            # For related models, check if we can write to the model, as unlinking
            # and creating attachments can be seen as an update to the model
            access_mode = 'write' if mode in ('create', 'unlink') else mode
            records.check_access_rights(access_mode)
            records.check_access_rule(access_mode)

        if require_employee:
            if not (self.env.is_admin() or self.env.user.has_group('base.group_user')):
                raise AccessError(_("Sorry, you are not allowed to access this document."))

    # def action_validate(self):
    #     if self.env.user.has_group('hcp_operator_customization.group_mrp_operator'):
    #         raise UserError(_("Operator Don't Have access to Validate"))
    #     else:
    #         return super(StockScrap,self).action_validate()
