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

from odoo import models, _
from odoo.tools import float_compare
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import pdb

class MrpProductionWorkcenterLine(models.Model):
    _inherit = 'mrp.workorder'

    def record_production(self):
        if not self:
            return True
        self.ensure_one()
        self._check_sn_uniqueness()
        self._check_company()
        if any(x.quality_state == 'none' for x in self.check_ids if x.test_type != 'instructions'):
            raise UserError(_('You still need to do the quality checks!'))
        if float_compare(self.qty_producing, 0, precision_rounding=self.product_uom_id.rounding) <= 0:
            raise UserError(_('Please set the quantity you are currently producing. It should be different from zero.'))
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
            # pdb.set_trace()
            if workorder.qty_produced ==0:
                value = workorder.qty_produced or workorder.qty_producing or workorder.qty_production
            if workorder.qty_produced >0:
                value = (workorder.qty_produced + workorder.qty_producing)
            vals = {
                'qty_produced': value,
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
            workorder.write(vals)
        return True




# change in base code by geminatecs
# file location of change code :-
# enterprise/mrp_workorder/models/quality.py", line 386, in _create_extra_move_lines
#  **** base original code ****
# quantity = self.product_id.uom_id._compute_quantity(quantity, self.product_uom_id, rounding_method='HALF-UP')
# **************************** #
# change by geminatecs
# quantity = self.product_id.uom_id._compute_quantity(quantity, self.move_id.product_uom.id, rounding_method='HALF-UP')
#######################
