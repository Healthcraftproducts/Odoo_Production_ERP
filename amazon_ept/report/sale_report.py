# -*- coding: utf-8 -*-
"""
inherited sale report class and inherited method to update the query.
"""

from odoo import fields, models


class SaleReport(models.Model):
    """
    Added class to add fields to relate wth the instance, seller and selling on and
    updated query to get sale report with group by those fields.
    """
    _inherit = "sale.report"

    amz_instance_id = fields.Many2one('amazon.instance.ept', 'Marketplace', readonly=True)
    amz_seller_id = fields.Many2one('amazon.seller.ept', 'Amazon Sellers', readonly=True)
    amz_fulfillment_by = fields.Selection([('FBA', 'Fulfilled By Amazon'),
                                           ('FBM', 'Fulfilled By Merchant')],
                                          string='Fulfillment By', readonly=True)

    def _select_additional_fields(self):
        """
        Inherited Select method to Add Amazon fields filter in Reports
        :return:
        """
        res = super(SaleReport, self)._select_additional_fields()
        res['amz_instance_id'] = "s.amz_instance_id"
        res['amz_seller_id'] = "s.amz_seller_id"
        res['amz_fulfillment_by'] = 's.amz_fulfillment_by'
        return res

    def _group_by_sale(self):
        """
        Inherit group by for filter amazon data
        :return:
        """
        res = super(SaleReport, self)._group_by_sale()
        res += """, s.amz_instance_id, s.amz_seller_id, s.amz_fulfillment_by"""
        return res

