from odoo import models, api, _
from odoo.exceptions import UserError

class AccountInvoiceToDraft(models.TransientModel):
    """
    This wizard will cancel the all the selected invoices.
    If in the journal, the option allow cancelling entry is not selected then it will give warning message.
    """

    _name = "account.invoice.to.draft"
    _description = "Set to Draft the Selected Invoices"

    def invoice_to_draft(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['account.move'].browse(active_ids):
            if record.state == 'draft':
                raise UserError(_("Selected invoice(s) cannot be draft as they are already in 'Draft' state."))
            record.button_draft()
        return {'type': 'ir.actions.act_window_close'}
    
# class UnpostAccountMove(models.TransientModel):
#     _name = "unpost.account.move"
#     _description = "Unpost Account Move"
# 
#     def cancel_move(self):
#         context = dict(self._context or {})
#         moves = self.env['account.move'].browse(self.env.context['active_ids'])
#         move_to_cancel = self.env['account.move']
#         for move in moves:
#             if move.state == 'posted':
#                 move_to_cancel += move
#         if not move_to_cancel:
#             raise UserError(_('There is no journal items in posted state to cancel.'))
#         move_to_cancel.button_cancel()
#         return {'type': 'ir.actions.act_window_close'}
