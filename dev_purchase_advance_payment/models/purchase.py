# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, _
from odoo.exceptions import ValidationError


class Purchase(models.Model):
    _inherit = 'purchase.order'

    def get_purchase_advance_paid_amount(self):
        for purchase in self:
            paid_amount = 0
            payment_ids = self.env['account.payment'].search([('state', '=', 'posted'),
                                                              ('purchase_id', '=', purchase.id)
                                                              ])
            if payment_ids:
                for payment in payment_ids:
                    paid_amount += payment.amount
            purchase.advance_payment_amount = paid_amount

    def make_purchase_advance_payment(self):
        if self.invoice_ids:
            raise ValidationError(_('''You can not make advance payment once Vendor Bill is generated'''))
        form_id = self.env.ref('dev_purchase_advance_payment.form_dev_purchase_advance_payment').id
        ctx = {'default_payment_type': 'outbound', 'default_partner_type': 'supplier', 'default_partner_id': self.partner_id.id, 'default_purchase_id': self.id}
        return {'name': 'Advance Payment',
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.payment',
                'views': [(form_id, 'form')],
                'target': 'new',
                'context': ctx
                }

    def view_purchase_advance_payments(self):
        payment_ids = self.env['account.payment'].search([('state', '=', 'posted'), ('purchase_id', '=', self.id)])
        if payment_ids:
            tree_id = self.env.ref('account.view_account_supplier_payment_tree').id
            form_id = self.env.ref('account.view_account_payment_form').id
            if len(payment_ids) == 1:
                return {'name': 'Payment',
                        'type': 'ir.actions.act_window',
                        'view_mode': 'form',
                        'res_model': 'account.payment',
                        'views': [(form_id, 'form')],
                        'target': 'current',
                        'res_id': payment_ids.id
                        }
            if len(payment_ids) > 1:
                return {'name': 'Payments',
                        'type': 'ir.actions.act_window',
                        'view_mode': 'tree, form',
                        'res_model': 'account.payment',
                        'views': [(tree_id, 'tree'), (form_id, 'form')],
                        'target': 'current',
                        'domain': [('id', 'in', payment_ids.ids)]}
        else:
            raise ValidationError(_('''There are no advance payments for this Purchase Order'''))

    advance_payment_amount = fields.Float(string='Advance Paid Amount', compute='get_purchase_advance_paid_amount')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: