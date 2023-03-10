# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2020-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Nimisha Muralidhar (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import models, fields, api, _

class MrpProduction(models.Model):
    _inherit = 'stock.picking'

    def action_product_availability_produce(self):
        stock_ids = self.env['stock.picking'].browse(self._context.get('active_ids', False))
        for line in stock_ids:
            line.with_context({'active_id': line.id,
                               'active_ids': [line.id],
                               }).action_assign()
            
    def action_product_do_unreserve(self):
        stock_ids = self.env['stock.picking'].browse(self._context.get('active_ids', False))
        for line in stock_ids:
            line.with_context({'active_id': line.id,
                            'active_ids': [line.id],
                            }).do_unreserve()

