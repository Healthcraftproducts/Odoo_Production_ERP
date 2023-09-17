# -*- coding: utf-8 -*-
# Part of Kanak Infosystems LLP.
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_purchase_order_note = fields.Boolean(
        string='Default Terms & Conditions')
    purchase_order_note = fields.Text(
        string='Default Terms and Conditions', translate=True)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_purchase_order_note = fields.Boolean(
        related='company_id.use_purchase_order_note', readonly=False,
        string='Default Terms & Conditions')
    purchase_order_note = fields.Text(
        related='company_id.purchase_order_note', readonly=False,
        string="Terms & Conditions")


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.model
    def _default_note(self):
        if self.env.user.company_id.use_purchase_order_note:
            return self.env.user.company_id.purchase_order_note
        else:
            return ''

    notes = fields.Text('Terms and Conditions', default=_default_note)
