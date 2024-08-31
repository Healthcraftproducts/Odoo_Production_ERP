from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    fedex_third_party_account_number_sale_order = fields.Char(copy=False, string='FexEx Third-Party Account Number',
                                                              help="Please Enter the Third Party account number ")
    fedex_bill_by_third_party_sale_order = fields.Boolean(string="FedEx Third Party Payment", copy=False, default=False,
                                                          help="when this fields is true,then we can visible fedex_third party account number")


    @api.onchange("carrier_id","partner_shipping_id")
    def _onchange_carrier_id(self):
        if self.carrier_id:
            if self.carrier_id.fedex_payment_type == "THIRD_PARTY":
                self.fedex_bill_by_third_party_sale_order = True
            else:
                self.fedex_bill_by_third_party_sale_order = False
        if self.partner_shipping_id:
            if self.fedex_bill_by_third_party_sale_order == True and self.partner_shipping_id.hcp_ship_via_description:
                self.fedex_third_party_account_number_sale_order = self.partner_shipping_id.hcp_ship_via_description
            else:
                self.fedex_third_party_account_number_sale_order = ""