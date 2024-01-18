# -*- coding: utf-8 -*-pack
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class to configure the fulfillment center.
"""

from odoo import models, fields, api


class ShipmentReportConfigureFulfillmentCenterEPT(models.TransientModel):
    """
    Added class to configure the shipment fulfillment center.
    """
    _name = "shipment.report.configure.fulfillment.center.ept"
    _description = "Configure Fulfillment Center in Shipment Report"

    shipment_report_configure_line_ids = fields.One2many(
        'shipment.report.configure.fulfillment.center.lines.ept',
        'shipment_report_configure_id',
        string="Configure Fees Lines")

    @api.model
    def default_get(self, field):
        """
        Load data in wizard of Missing Fulfillment Center
        """
        res = super(ShipmentReportConfigureFulfillmentCenterEPT, self).default_get(field)
        result_data = []
        shipment_report = self._context.get('shipment_report_id', [])
        shipment_report_id = self.env['shipping.report.request.history'].browse(shipment_report)
        country_ids = tuple(self._context.get('country_ids', False))
        fulfillment_center_list = shipment_report_id.get_missing_fulfillment_center(
            shipment_report_id.attachment_id)

        for fulfillment_center in fulfillment_center_list:
            result_data.append((0, 0, {'fulfillment_center': fulfillment_center,
                                       'country_ids': [(6, 0, country_ids or False)]}))
        res.update({'shipment_report_configure_line_ids': result_data})
        return res

    def configure_shipment_fulfillment_center(self):
        """
        Save Fulfillment Center in seller's warehouse on basis of country selected from wizard
        @author: Deval Jagad (08/01/2020)
        """
        amazon_fulfillment_obj = self.env['amazon.fulfillment.center']
        shipment_report = self._context.get('shipment_report_id', False)
        shipment_report_id = self.env['shipping.report.request.history'].browse(shipment_report)
        seller_id = shipment_report_id.seller_id
        warehouse_country_dict = {}
        for warehouse_id in seller_id.amz_warehouse_ids:
            warehouse_country_dict.update({warehouse_id.partner_id.country_id.id: warehouse_id.id})

        for configure_line in self.shipment_report_configure_line_ids:
            country_id = configure_line.country_id
            if not country_id:
                continue
            warehouse_id = warehouse_country_dict.get(country_id.id)
            if warehouse_id:
                vals = {'center_code': configure_line.fulfillment_center,
                        'seller_id': seller_id.id,
                        'warehouse_id': warehouse_id}
                amazon_fulfillment_obj.create(vals)

        is_fulfillment_center = False
        if seller_id.is_fulfilment_center_configured:
            fulfillment_center_list = shipment_report_id.get_missing_fulfillment_center(
                shipment_report_id.attachment_id)
            if fulfillment_center_list:
                is_fulfillment_center = True
        shipment_report_id.write({'is_fulfillment_center': is_fulfillment_center})
        return True


class ShipmentReportConfigureFulfillmentCenterLinesEPT(models.TransientModel):
    """
    Added class to configure the fulfillment center line and related with the shipment report
    configurations.
    """
    _name = "shipment.report.configure.fulfillment.center.lines.ept"
    _description = "Shipment Report Configuration Fulfillment Center Line"

    country_ids = fields.Many2many('res.country', 'country_fulfillment_center_line_rel', \
                                   'country_id', 'fulfillment_center_line_id', string='Country IDS')

    fulfillment_center = fields.Char()
    country_id = fields.Many2one('res.country', string='Country')
    shipment_report_configure_id = fields.Many2one(
        'shipment.report.configure.fulfillment.center.ept',
        string='Shipment Report Configure')
