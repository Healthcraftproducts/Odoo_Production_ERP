# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
inherited class and added method to Updates the VAT number of warehouse's partner as per the VAT
configuration.
"""

from odoo import api, models, fields


class StockWarehouse(models.Model):
    """
    Inherited class to Updates the VAT number of warehouse's partner as per the VAT configuration.
    """
    _inherit = "stock.warehouse"

    seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller')
    fulfillment_center_ids = fields.One2many('amazon.fulfillment.center', 'warehouse_id',
                                             string='Fulfillment Centers')
    is_fba_warehouse = fields.Boolean("Is FBA Warehouse ?")
    unsellable_location_id = fields.Many2one('stock.location', string="Unsellable Location",
                                             help="Amazon unsellable location")

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """
        Inherited for updating the VAT number of the partner as per the VAT configuration.
        @author: Maulik Barad on Date 13-Jan-2020.
        """
        if self.partner_id:
            self.update_partner_vat()

    @api.model_create_multi
    def create(self, vals_list):
        """
        Inherited for updating the VAT number of warehouse's partner as per the VAT configuration.
        @author: Maulik Barad on Date 13-Jan-2020.
        """
        results = super(StockWarehouse, self).create(vals_list)

        for result in results:
            if result.partner_id:
                result.update_partner_vat()
        return results

    def update_partner_vat(self):
        """
        Updates the VAT number of warehouse's partner as per the VAT configuration.
        @author: Maulik Barad on Date 13-Jan-2020.
        """
        vat_config = self.env["vat.config.ept"].search([("company_id", "=", self.company_id.id)])
        vat_config_line = vat_config.vat_config_line_ids.filtered( \
            lambda x: x.country_id == self.partner_id.country_id)
        if vat_config_line and not self.partner_id.vat:
            self.partner_id.write({"vat": vat_config_line.vat})
        return True
