# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CancelMultiMpsOrdersWizard(models.TransientModel):
    _name = "cancel.multi.mps.order.wizard"
    _description = "Cancel Multi Mps Orders"

    def cancel_multiple_orders(self):
        for record in self._context.get('active_ids'):
            record = self.env[self._context.get('active_model')].browse(record)
            if record.state not in  ('cancel','done'):
                record.action_cancel()
                #try:
                    #if record.picking_ids:
                        #for picking in record.picking_ids:
                            #picking.action_cancel()
                    #if record.invoice_ids:
                        #for invoice in record.invoice_ids:
                            #invoice.action_cancel()
                    #record.action_cancel()
                #except Exception as e:
                    #raise UserError('{} \n Order Number : {}'.format(e,record.name))
            else:
                raise UserError(_('You can not delete Done Or Cancelled MO'))
        return True


