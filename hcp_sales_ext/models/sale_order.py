import re
from odoo import api, exceptions, fields, models, _
from html import unescape


class SaleOrderInherit(models.Model):
    _inherit = "sale.order"

    comment_internal_notes = fields.Html(string='Customer Internal Notes',placeholder="Displayed if customer has internal notes or remarks")

    @api.onchange('partner_id')
    def _onchange_partner_id_notes(self):
        if self.partner_id and self.partner_id.comment:
            # Replace <br> and <p> tags with newlines to preserve the formatting
            formatted_comment = re.sub(r'<br\s*/?>|</p>|<p>', '\n', self.partner_id.comment)

            # Strip remaining HTML tags
            clean_comment = re.sub(r'<.*?>', '', formatted_comment)

            # Unescape any HTML entities
            clean_comment = unescape(clean_comment)
            self.comment_internal_notes = self.partner_id.comment
            print("Partner ID has changed")
            return {
                'warning': {
                    'title': _('Internal Notes!'),
                    'message': _(
                        'Please take the following note into consideration for this customer:\n%s' % clean_comment
                    )
                }
            }
