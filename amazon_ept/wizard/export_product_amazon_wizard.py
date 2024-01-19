# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class and method to update price, image, export stock, product related operations.
"""

from odoo import models, fields, api

AMZ_INSTANCE_EPT = 'amazon.instance.ept'
AMZ_PRODUCT_EPT = 'amazon.product.ept'


class ExportAmazonProductWizard(models.TransientModel):
    """
    Added class to export product , update price and image in amazon.
    """
    _name = 'amazon.product.wizard'
    _description = 'amazon.product.wizard'

    instance_id = fields.Many2one(AMZ_INSTANCE_EPT, "Marketplace")
    amazon_product_ids = fields.Many2many(AMZ_PRODUCT_EPT, 'amazon_product_copy_rel',
                                          'wizard_id', 'amazon_product_id', "Amazon Product")
    from_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, "From Marketplace")
    to_instance_id = fields.Many2one(AMZ_INSTANCE_EPT, "To Marketplace")
    copy_all_products = fields.Boolean("Copy All Products?", default=True)
    datas = fields.Binary('File')

    fulfillment_by = fields.Selection([('FBM', 'Manufacturer Fulfillment Network'), ('FBA', 'Amazon Fulfillment Network')],
                                      default='FBM', help="Amazon Fulfillment Type")

    @api.onchange("from_instance_id")
    def on_change_instance(self):
        """
        on changes to update to instance id based on changes of  "from instance id".
        """
        for record in self:
            record.to_instance_id = False

    def export_product_in_amazon(self):
        """
        This Method Relocates export amazon product listing in amazon.
        :return: This Method return Boolean(True/False).
        """
        amazon_product_obj = self.env[AMZ_PRODUCT_EPT]
        active_ids = self._context.get('active_ids', [])
        amazon_product = amazon_product_obj.browse(active_ids)
        amazon_product_instance = amazon_product.mapped('instance_id')
        for instance in amazon_product_instance:
            amazon_products = amazon_product.filtered(
                lambda l, instance=instance: l.instance_id.id == instance.id and l.exported_to_amazon)
            if not amazon_products:
                continue
            amazon_products.export_product_amazon(instance)
        return True

    def update_stock_ept(self):
        """
        This Method relocates update stock of amazon.
        :return: This Method return boolean(True/False).
        """
        product_obj = self.env[AMZ_PRODUCT_EPT]
        product_ids = self._context.get('active_ids', False)
        amazon_product = product_obj.browse(product_ids)
        amazon_product_instance = amazon_product.mapped('instance_id')
        for instance in amazon_product_instance:
            amazon_products = amazon_product.filtered(
                lambda l, instance=instance:
                l.instance_id.id == instance.id and l.fulfillment_by == 'FBM' and l.exported_to_amazon)
            if amazon_products:
                amazon_products.export_stock_levels(instance)
        return True

    def update_price(self):
        """
        This Method relocates update price of amazon.
        :return: This Method return boolean(True/False).
        """
        product_obj = self.env[AMZ_PRODUCT_EPT]
        product_ids = self._context.get('active_ids', False)
        amazon_product = product_obj.browse(product_ids)
        amazon_product_instance = amazon_product.mapped('instance_id')
        for instance in amazon_product_instance:
            amazon_products = amazon_product.filtered(
                lambda l, instance=instance: l.instance_id.id == instance.id and l.exported_to_amazon)
            amazon_products.update_price(instance)
        return True

    def update_image(self):
        """
        This Method relocates update image of amazon.
        :return: This Method return boolean(True/False).
        """
        product_obj = self.env[AMZ_PRODUCT_EPT]
        product_ids = self._context.get('active_ids', False)
        amazon_product = product_obj.browse(product_ids)
        amazon_product_instance = amazon_product.mapped('instance_id')

        for instance in amazon_product_instance:
            amazon_products = amazon_product.filtered(
                lambda l, instance=instance:
                l.instance_id.id == instance.id and l.fulfillment_by == 'FBM' and l.exported_to_amazon)
            amazon_products.update_images(instance)
        return True
