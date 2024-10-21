# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Inherited class to display the shipment amazon product's.
"""
from odoo import models, fields, api


class StockQuantPackage(models.Model):
    """
    inherited class to display the amazon product from the shipment lines.
    """
    _inherit = 'stock.quant.package'

    @api.model
    def default_get(self, fields):
        """
        Use: Used for Add domain in Amazon Product field while enter Carton Information,
        display only Amazon Products which are in Shipment Lines
        @:param: self -> stock.quant.package, fields -> {}
        @:return: {} => dict
        ----------------------------------------------
        Added by: Dhaval Sanghani @Emipro Technologies
        Added on: 30-May-2020
        """
        res = super(StockQuantPackage, self).default_get(fields)
        active_id = self._context.get('inbound_shipment', False)

        if active_id:
            inbound_shipment = self.env['amazon.inbound.shipment.ept'].browse(active_id)

            product_ids = self.get_amazon_products(inbound_shipment) if inbound_shipment else []

            res.update({'amazon_product_ids': product_ids})
        return res

    def _compute_amazon_products(self):
        # Added By: Dhaval Sanghani [30-May-2020]
        """
        Added method to compute amazon products based on shipment record.
        """
        res = {}
        for record in self:

            shipment = record.partnered_ltl_shipment_id \
                if record.partnered_ltl_shipment_id else record.partnered_small_parcel_shipment_id

            if shipment:
                record.amazon_product_ids = record.get_amazon_products(shipment)
        return res

    def get_amazon_products(self, inbound_shipment):
        """
        Use: Return Amazon Products which are in Shipment Lines
        @:param: self -> stock.quant.package, inbound_shipment -> amazon.inbound.shipment.ept record
        @:return:
        ----------------------------------------------
        Added by: Dhaval Sanghani @Emipro Technologies
        Added on: 30-May-2020
        """
        product_ids = inbound_shipment.mapped('odoo_shipment_line_ids').mapped(\
            'amazon_product_id').ids
        return product_ids

    box_no = fields.Char()
    carton_info_ids = fields.One2many("amazon.carton.content.info.ept", "package_id",
                                      string="Carton Info")
    amazon_product_ids = fields.One2many("amazon.product.ept", compute="_compute_amazon_products")
    partnered_small_parcel_shipment_id = fields.Many2one("amazon.inbound.shipment.ept",
                                                         "Small Parcel Shipment")
    is_update_inbound_carton_contents = fields.Boolean(default=False, copy=False)
    partnered_ltl_shipment_id = fields.Many2one("amazon.inbound.shipment.ept", "LTL Shipment")
    package_status = fields.Selection([('SHIPPED', 'SHIPPED'),
                                       ('IN_TRANSIT', 'IN_TRANSIT'),
                                       ('DELIVERED', 'DELIVERED'),
                                       ('CHECKED_IN', 'CHECKED_IN'),
                                       ('RECEIVING', 'RECEIVING'),
                                       ('CLOSED', 'CLOSED'),
                                       ('DELETED', 'DELETED')])
    weight_unit = fields.Selection([('pounds', 'Pounds'), ('kilograms', 'Kilograms'), ])
    weight_value = fields.Float()
    ul_id = fields.Many2one('product.ul.ept', string="Logistic Unit")
    is_stacked = fields.Boolean()
    box_expiration_date = fields.Date(copy=False)
