# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict, namedtuple
from math import log10

from odoo import api, fields, models, _
from odoo.tools.date_utils import add, subtract
from odoo.tools.float_utils import float_round
from odoo.osv.expression import OR, AND

import logging
import threading

_logger = logging.getLogger(__name__)

class MrpProductionSchedule(models.Model):
    _inherit = 'mrp.production.schedule'
    
    # def action_replenish(self, based_on_lead_time=False):
    #     self.env['procurement.group'].run_scheduler()
    #     super(MrpProductionSchedule, self).action_replenish()       
