
from odoo import api, fields, models, _

# class AccountMove(models.Model):
#     _inherit = "account.move"
#
#     def action_post(self):
#         res = super(AccountMove,self).action_post()
#         so = self.line_ids.mapped('sale_line_ids').mapped('order_id')
#         pick_ids = so.mapped('picking_ids')
#         for pick in pick_ids:
#             pick.email_sent = True
#         return res

class Picking(models.Model):
    _inherit = "stock.picking"

    invoiced = fields.Boolean(string='Is Invoiced',compute='compute_is_invoiced',index=True)
    email_sent = fields.Boolean(string='Email sent?',default=False)



    def compute_is_invoiced(self):
        for rec in self:
            if rec.group_id.sale_id:
                sale_id = rec.group_id.sale_id
                invoice_ids = sale_id.mapped('invoice_ids')
                if invoice_ids:
                    if all(inv.state == 'posted' for inv in invoice_ids):
                        rec.invoiced = True
                    else:
                        rec.invoiced = False
                else:
                    rec.invoiced = False
            else:
                rec.invoiced = False