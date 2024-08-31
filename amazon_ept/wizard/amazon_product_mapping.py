# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class and method to process for prepare export amazon product.
"""

import csv
import base64
from odoo import models, fields


class AmazonProductMapping(models.TransientModel):
    """
    Added class to prepare CSV file to export amazon product.
    """
    _name = 'amazon.prepare.export.product.ept'
    _description = "amazon.prepare.export.product.ept"

    seller_id = fields.Many2one('amazon.seller.ept',
                                string='Seller',
                                help="Select Seller Account to associate with this Instance")
    datas = fields.Binary(string="Choose File")
    delimiter = fields.Selection([('tab', 'Tab'), ('semicolon', 'Semicolon'), ('comma', 'Comma')],
                                 string="Separator", default='comma', required=True)
    instance_ids = fields.Many2many("amazon.instance.ept", string="Marketplaces")
    amazon_selling = fields.Selection([('FBA', 'FBA'),
                                       ('FBM', 'FBM'),
                                       ('Both', 'FBA & FBM')],
                                      string='Fulfillment By ?',
                                      default='FBM',
                                      help='Use to Prepare file for Amazon selling fulfillment')

    def prepare_product_for_export(self):
        """
        This method relocates product csv export and download.
        :return: This method return product csv file.
        """
        product_product_obj = self.env['product.product']
        variant_ids = self._context.get('active_ids', [])
        odoo_product_ids = product_product_obj.search([('id', 'in', variant_ids),
                                                       ('type', '!=', 'service')])
        amazon_product_export_file_path = '/tmp/amazon_product_export.csv'
        with open(amazon_product_export_file_path, 'w') as csv_file:
            file_writer = self.get_delimiter_wise_file_writer(csv_file)
            file_writer.writerow([
                'Title',
                'Internal Reference',
                'Seller SKU',
                'Marketplace',
                'Fulfillment'])
            for odoo_product in odoo_product_ids:
                product_dict = self.prepare_product_value_for_export(odoo_product)
                self.process_product_dict_to_export_product(file_writer, product_dict)

        csv_file.close()
        self.read_amazon_product_csv(amazon_product_export_file_path)
        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=amazon.prepare.export.product.ept&field=datas&download=true&id=%s&filename=amazon_product_export.csv' % (
                self.id),
            'target': 'self',
        }

    def get_delimiter_wise_file_writer(self, csv_file):
        """
        Based on selected delimiter it will return the file_writer.
        """
        if self.delimiter == "tab":
            file_writer = csv.writer(
                csv_file,
                delimiter="\t",
                quotechar='|',
                quoting=csv.QUOTE_MINIMAL)
        elif self.delimiter == "semicolon":
            file_writer = csv.writer(
                csv_file,
                delimiter=";",
                quotechar='|',
                quoting=csv.QUOTE_MINIMAL)
        else:
            file_writer = csv.writer(
                csv_file,
                delimiter=",", )
        return file_writer

    def process_product_dict_to_export_product(self, file_writer, product_dict):
        """
        It will process product dict based on amazon selling to export product.
        """
        product_name = product_dict['product_name']
        amazon_marketplace_id = product_dict['amazon_marketplace_id']
        internal_reference = product_dict['internal_reference']
        for amazon_marketplace in amazon_marketplace_id:
            if self.amazon_selling in ['FBM', 'Both']:
                file_writer.writerow([
                    product_name,
                    internal_reference,
                    '',
                    amazon_marketplace,
                    'FBM'])
            if self.amazon_selling in ['FBA', 'Both']:
                file_writer.writerow([
                    product_name,
                    internal_reference,
                    '',
                    amazon_marketplace,
                    'FBA'])
        return True

    def prepare_product_value_for_export(self, product):
        """
        This Method relocates prepare product value for export.
        :param product_template: This argument relocates browse object of the product template.
        :return: This Method return the product dictionary.
        """
        product_name = product.name
        amazon_marketplace_id = self.instance_ids.mapped("marketplace_id.name")
        internal_reference = product.default_code or product.barcode
        product_template_dictionary = {
            'product_name': product_name,
            'internal_reference': internal_reference,
            'amazon_marketplace_id': amazon_marketplace_id}
        return product_template_dictionary

    def read_amazon_product_csv(self, amazon_product_export_file_path):
        """
        This Method read export product csv.
        :param amazon_product_export_file_path:
        This argument relocates export product csv file path.
        :return:This method return boolean(True/False)
        """
        amazon_product_export_file_path = open(amazon_product_export_file_path, "r+")
        amazon_product_export_read_file = amazon_product_export_file_path.read()
        amazon_product_export_file_encoded = base64.b64encode(
            amazon_product_export_read_file.encode()
        )
        self.write({'datas': amazon_product_export_file_encoded})
        return True
