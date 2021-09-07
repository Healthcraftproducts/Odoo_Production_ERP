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

    def action_validate(self):
        if self.env.user.has_group('hcp_operator_customization.group_mrp_operator'):
            raise UserError(_("Operator Don't Have access to Validate"))
        else:
            return super(StockScrap,self).action_validate()