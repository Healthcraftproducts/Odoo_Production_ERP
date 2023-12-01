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