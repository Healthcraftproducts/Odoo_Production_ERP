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


class Payment(models.Model):
    _inherit = 'account.payment'

    def post(self):
        if self.purchase_id:
            if self.purchase_id.advance_payment_amount == 0:
                if self.amount > self.purchase_id.amount_total:
                    raise ValidationError(_('''You can not pay more than %s''') % (self.purchase_id.amount_total))
            if self.purchase_id.advance_payment_amount == self.purchase_id.amount_total:
                raise ValidationError(_('''Purchase Order is fully paid, please check the attached Payments'''))
            if self.purchase_id.advance_payment_amount > 0:
                remaining_amount = self.purchase_id.amount_total - self.purchase_id.advance_payment_amount
                if self.amount > remaining_amount:
                    raise ValidationError(_('''You have already advance paid %s out of %s now you can only pay %s''') % (self.purchase_id.advance_payment_amount, self.purchase_id.amount_total, remaining_amount))
        super(Payment, self).post()

    purchase_id = fields.Many2one('purchase.order', string='Purchase Order', copy=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: