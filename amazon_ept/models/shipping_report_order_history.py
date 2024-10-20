# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ShippingReportOrderHistory(models.Model):
    _name = "shipping.report.order.history"
    _description = "Shipment Orders Process History"

    instance_id = fields.Many2one("amazon.instance.ept", string="Marketplace", index=True)
    amazon_order_ref = fields.Char("Amazon Order Ref", index=True, help="Amazon Order Reference")
    order_line_ref = fields.Char("Order Line Ref", help="Amazon Order line reference")
    shipment_id = fields.Char(string="Shipment ID", help="Amazon Shipment Id")
    shipment_line_id = fields.Char("Shipment Line ID", help="Amazon Shipment line reference")

    def verify_outbound_order_processed(self, row, instance_id):
        """
        If search result is true in this method, it means that order line is processed and not process again.
        :param row: dict{}
        :param instance: amazon.instance.ept()
        :return: Boolean (True / False)
        """
        record = self.search([('instance_id', '=', instance_id),
                              ('amazon_order_ref', '=', row.get('amazon-order-id', ''))
                              ]).filtered(lambda l: l.order_line_ref == row.get('amazon-order-item-id', '')
                                                    and l.shipment_id == row.get('shipment-id', '')
                                                    and l.shipment_line_id == row.get('shipment-item-id', ''))
        if record:
            return True
        return False
