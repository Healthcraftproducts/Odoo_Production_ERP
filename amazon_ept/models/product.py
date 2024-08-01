# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class and
"""

import html
import math
import time
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError

from ..endpoint import DEFAULT_ENDPOINT

PRODUCT_PRODUCT = 'product.product'
AMAZON_PRODUCT_EPT = 'amazon.product.ept'
FEED_SUBMISSION_HISTORY = 'feed.submission.history'
STOCK_HEIGHTS = "Stock Height"
DATE_YMDHMS = "%Y-%m-%d %H:%M:%S"

fix_stock_type_help = """
Fix = The fix stock (Set in the field Fix Stock Value) will be exported form your odoo stock.
Percentage = The percentage (Set in the field Fix Stock Value) of stock will be exported form your odoo stock.
"""

fix_stock_value_help = """
Stock value to be exported to amazon (Fixed or Percentage depending on the field Fix Stock Type
For Example
Fixed stock Value: 25
Stock in odoo: 200
Example 1:
If Fixed stock Type: fix
Only 25 quantity will be exported to the Amazon
Example 2:
If Fixed stock Type: Percentage
In this case 50 quantity will be exported to Amazon
Because 25% of 200 is 50

Note: Calculation of stock is made related to odoo stock.
"""


class AmazonProductEpt(models.Model):
    """
    Added class to manage amazon product in odoo.
    """
    _name = "amazon.product.ept"
    _description = "Amazon Product Mapping with Odoo Products"

    name = fields.Char(string='Product Title')
    product_id = fields.Many2one(PRODUCT_PRODUCT, string='Odoo Product', ondelete="cascade",
                                 help="ERP Product Reference")
    instance_id = fields.Many2one('amazon.instance.ept', string='Marketplace', required=True,
                                  copy=False, help="Recognise Products to unique Amazon Instances")
    product_asin = fields.Char(copy=False, help="Amazon Product ASIN")
    asin_qty = fields.Integer("Number Of Items In One Package", default=1,
                              help="Amazon Product's Number of Quantity in One Packet")
    product_upc = fields.Char("UPC", copy=False)
    fulfillment_by = fields.Selection(
        [('FBM', 'Manufacturer Fulfillment Network'), ('FBA', 'Amazon Fulfillment Network')],
        default='FBM', help="Amazon Fulfillment Type")
    fix_stock_type = fields.Selection([('fix', 'Fix'), ('percentage', 'Percentage')], help=fix_stock_type_help)
    fix_stock_value = fields.Float(digits="Product UoS", help=fix_stock_value_help)
    exported_to_amazon = fields.Boolean(default=False, copy=False,
                                        help="True:Product exported to Amazon or False: "
                                             "Product is not exported to Amazon.")
    seller_sku = fields.Char(help="Amazon Seller SKU")
    barcode = fields.Char(related="product_id.barcode")
    long_description = fields.Text("Product Description", help="Long description of the product")
    active = fields.Boolean("Active", related="product_id.active")
    fulfillment_channel_sku = fields.Char()
    last_feed_submission_id = fields.Char(readonly=True, copy=False)
    error_in_export_product = fields.Boolean(default=False, copy=False)
    company_id = fields.Many2one('res.company', string="Company", copy=False,
                                 compute="_compute_company", store=True, help='ID of company')
    _sql_constraints = [('amazon_instance_seller_sku_unique_constraint',
                         'unique(instance_id,seller_sku,fulfillment_by)',
                         "Seller sku must be unique per instance & Fulfillment By")]

    @api.model
    @api.depends('instance_id')
    def _compute_company(self):
        """
        The below method sets company for a particular record
        """
        for record in self:
            company_id = record.instance_id.seller_id.company_id.id if record.instance_id.seller_id else False
            if not company_id:
                company_id = self.env.company.id
            record.company_id = company_id

    @api.model
    def search_product(self, seller_sku):
        """
        Define method which help to search Odoo product based on seller sku.
        """
        product_obj = self.env[PRODUCT_PRODUCT]
        dublicate_message = 'Duplicate Product Found For Sku (%s)' % seller_sku
        if self.env.ref('product.product_comp_rule').active:
            cur_usr = self.env.user
            company_id = cur_usr.company_id.id or False
            product = product_obj.search(
                ['|', ('company_id', '=', False), ('company_id', '=', company_id),
                 ('default_code', '=', seller_sku)])
            if len(product) > 1:
                raise UserError(_(dublicate_message))
            if not product:
                product = product_obj.search( \
                    ['|', ('company_id', '=', False), ('company_id', '=', company_id),
                     ('default_code', '=', seller_sku), ('active', '=', False)])
                if len(product) > 1:
                    raise UserError(_(dublicate_message))
                if product and not product.active:
                    product.write({'active': True})
            return product or False
        product = product_obj.search([('default_code', '=', seller_sku)])
        if len(product) > 1:
            raise UserError(_(dublicate_message))
        if not product:
            product = product_obj.search([('default_code', '=', seller_sku), ('active', '=', False)])
            if len(product) > 1:
                raise UserError(_(dublicate_message))
            if product and not product.active:
                product.write({'active': True})
        return product or False

    @api.model
    def search_amazon_product(self, instance_id, seller_sku, fulfillment_by='FBM'):
        """
        This method will find the amazon product
        """
        seller_sku = seller_sku.strip()
        amazon_product = self.search(['|', ('active', '=', False), ('active', '=', True),
                                      ('seller_sku', '=', seller_sku), ('instance_id', '=', instance_id),
                                      ('fulfillment_by', '=', fulfillment_by)], limit=1)
        if not amazon_product:
            return False
        if amazon_product.product_id and not amazon_product.product_id.active:
            amazon_product.product_id.write({'active': True})
        return amazon_product

    standard_product_id_type = fields.Selection(
        [('EAN', 'EAN'), ('ASIN', 'ASIN'), ('GTIN', 'GTIN'), ('UPC', 'UPC')],
        string="Standard Product ID", default='ASIN')
    related_product_type = fields.Selection([('UPC', 'UPC'), ('EAN', 'EAN'), ('GTIN', 'GTIN')])
    related_product_value = fields.Char()
    launch_date = fields.Datetime(help="Controls when the product appears in search and "
                                       "browse on the Amazon website")
    release_date = fields.Datetime(help="The date a product is released for sale")
    discontinue_date = fields.Datetime(help="The date a product is Discontinue for sale")
    condition = fields.Selection([('New', 'New (DEPRECATED)'), ('NewItem', 'NewItem'),
                                  ('NewWithWarranty', 'NewWithWarranty'), ('NewOEM', 'NewOEM'),
                                  ('NewOpenBox', 'NewOpenBox'), ('UsedLikeNew', 'UsedLikeNew'),
                                  ('UsedVeryGood', 'UsedVeryGood'), ('UsedGood', 'UsedGood'),
                                  ('UsedAcceptable', 'UsedAcceptable'), ('UsedPoor', 'UsedPoor'),
                                  ('UsedRefurbished', 'UsedRefurbished'),
                                  ('CollectibleLikeNew', 'CollectibleLikeNew'),
                                  ('CollectibleVeryGood', 'CollectibleVeryGood'),
                                  ('CollectibleGood', 'CollectibleGood'),
                                  ('CollectibleAcceptable', 'CollectibleAcceptable'),
                                  ('CollectiblePoor', 'CollectiblePoor'),
                                  ('RefurbishedWithWarranty', 'RefurbishedWithWarranty'),
                                  ('Refurbished', 'Refurbished'), ('Club', 'Club')], default='NewItem', copy=False)

    item_package_qty = fields.Integer(string="Package Quantity", default=1,
                                      help="Number of the same product contained within"
                                           "one package. "
                                           "For example, "
                                           "if you are selling a case of 10 packages of socks, "
                                           "ItemPackageQuantity would be 10.")

    # brand = fields.Char(string="Product Brand",
    #                     related='product_id.product_tmpl_id.product_brand_id.name', readonly=True)
    designer = fields.Char(help="Designer of the product")

    bullet_point_ids = fields.One2many('amazon.product.bullet.description', 'amazon_product_id',
                                       string="Bullet Point Description")

    package_weight = fields.Float(help="Weight of the package", digits="Stock Weight")
    shipping_weight = fields.Float(help="Weight of the product when packaged to ship",
                                   digits="Stock Weight")
    max_order_quantity = fields.Integer("Maximum Order Quantity",
                                        help="Maximum quantity of the product that a customer can "
                                             "order")
    # manufacturer = fields.Char(related='product_id.product_tmpl_id.product_brand_id.partner_id.name',
    #                            readonly=True, string="Manufacturer")
    search_term_ids = fields.One2many('amazon.product.search.term', 'amazon_product_id',
                                      string="Search Term")
    is_gift_wrap_available = fields.Boolean("Is Gift Wrap Available ?",
                                            help="Indicates whether gift wrapping is available for "
                                                 "the product")

    is_gift_message_available = fields.Boolean("Is Gift Message Available ?",
                                               help="Indicates whether gift messaging is available "
                                                    "for the product")
    gtin_exemption_reason = fields.Selection([('bundle', 'Bundle'), ('part', 'Part')],
                                             string="GtinExemptionReason")
    package_weight_uom = fields.Selection(
        [('GR', 'GR'), ('KG', 'KG'), ('OZ', 'OZ'), ('LB', 'LB'), ('MG', 'MG')], default='KG')

    shipping_weight_uom = fields.Selection(
        [('GR', 'GR'), ('KG', 'KG'), ('OZ', 'OZ'), ('LB', 'LB'), ('MG', 'MG')], default='KG')
    item_dimensions_uom = fields.Selection(
        [('CM', 'CM'), ('FT', 'FT'), ('M', 'M'), ('IN', 'IN'), ('MM', 'MM')],
        string="Item Dimension", default='CM')

    item_height = fields.Float(help="Height of the item dimension", digits=STOCK_HEIGHTS)
    item_length = fields.Float(help="Length of the item dimension", digits=STOCK_HEIGHTS)
    item_width = fields.Float(help="Width of the item dimension", digits=STOCK_HEIGHTS)

    package_dimensions_uom = fields.Selection(
        [('CM', 'CM'), ('FT', 'FT'), ('M', 'M'), ('IN', 'IN'), ('MM', 'MM')],
        string="Package Dimension", default='CM')
    package_height = fields.Float(help="Height of the package dimension", digits=STOCK_HEIGHTS)
    package_length = fields.Float(help="Length of the package dimension", digits=STOCK_HEIGHTS)
    package_width = fields.Float(help="Width of the package dimension", digits=STOCK_HEIGHTS)
    allow_package_qty = fields.Boolean(default=False)
    fulfillment_latency = fields.Integer()

    def get_amazon_product_request_data_ept(self, instance, data, emipro_api):
        """
        Defined common method to prepare the amazon product request data
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')

        kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                  'app_name': 'amazon_ept_spapi',
                  'account_token': account.account_token,
                  'emipro_api': emipro_api,
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                             instance.country_id.code,
                  'data': data,
                  'marketplaceids': [instance.market_place_id],
                  'instance_id': instance.id, }
        return kwargs

    def export_product_amazon(self, instance):
        """
        This Method Relocates export amazon product listing in amazon.
        :param instance:This argument relocates instance of amazon.
        :return: This Method return Boolean(True/False).
        """
        data = self.create_product_envelope(instance)
        kwargs = self.get_amazon_product_request_data_ept(instance, data, 'amazon_submit_feeds_sp_api')
        kwargs.update({'feed_type': 'POST_PRODUCT_DATA'})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('error', False):
            raise UserError(_(response.get('error', {})))
        results = response.get('results', {})
        self.process_export_product_amazon_result(instance, data, results)
        return True

    def process_export_product_amazon_result(self, instance, data, results):
        """
        Define method which help to create feed history for exported Products in Amazon.
        """
        feed_submission_obj = self.env[FEED_SUBMISSION_HISTORY]
        if results.get('feed_result', {}).get('feedId', False):
            feed_document_id = results.get('result', {}).get('feedDocumentId', '')
            last_feed_submission_id = results.get('feed_result', {}).get('feedId', False)
            for amazon_product in self:
                amazon_product.write({'exported_to_amazon': True, 'last_feed_submission_id': last_feed_submission_id,
                                      'error_in_export_product': False})

            vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                    'feed_submit_date': time.strftime(DATE_YMDHMS),
                    'instance_id': instance.id, 'user_id': self._uid,
                    'feed_type': 'export_product', 'feed_document_id':feed_document_id,
                    'seller_id': instance.seller_id.id}
            feed_submission_obj.create(vals)
        return True

    def create_product_envelope(self, instance):
        """
        This Method relocates prepare envelope for amazon.
        :param amazon_products: This arguments relocates product listing of amazon.
        :param instance: This argument relocates instance of amazon.
        :return: This argument return envelope of amazon.
        """
        message_id = 0
        messages = ''
        for product in self:
            message_id = message_id + 1
            messages = "%s %s" % (messages, self.get_message(message_id, product))
        header = self.get_header(instance)
        data = "%s %s %s" % (header, messages, '</AmazonEnvelope>')
        return data

    def get_message(self, message_id, product):
        """
        This Method relocates prepare envelop message for amazon product.
        :param message_id:This argument relocates message id of amazon because of amazon
        depends on message id.
        :param product:This arguments relocates product listing of amazon
        :return: This Method return amazon envelope message.
        """
        message = """
                <MessageID>%s</MessageID>
                <OperationType>PartialUpdate</OperationType>
                <Product>""" % (message_id)
        message = "%s %s" % (message, self.standard_product_code(product))
        if product.standard_product_id_type == 'GTIN':
            message = "%s %s" % (message, "<GtinExemptionReason>%s</GtinExemptionReason>" % ( \
                product.gtin_exemption_reason))
        if product.related_product_type:
            message = "%s %s" % (message, self.get_related_product_type(product))

        luanch_date = self.get_lanuch_date(product)
        if luanch_date:
            message = "%s %s" % (message, luanch_date)
        discontinue_date = self.get_discontinue_date(product)
        if discontinue_date:
            message = "%s %s" % (message, discontinue_date)
        release_date = self.get_release_date(product)
        if release_date:
            message = "%s %s" % (message, release_date)
        condition = self.get_condition(product)
        if condition:
            message = "%s %s" % (message, condition)
        message = "%s %s" % (message, self.item_package_qty_and_no_of_items(product))
        description_data = self.get_description_data(product)
        message = "%s %s" % (message, description_data)
        amazon_only = "<Amazon-Only>"
        if len(amazon_only) > 14:
            amazon_only = "%s %s" % (amazon_only, "</Amazon-Only>")
            message = "%s %s" % (message, amazon_only)
        message = "%s </Product>" % (message)
        return "<Message>%s</Message>" % (message)

    def get_header(self, instnace):
        """
        This Method relocates prepare header of envelope for amazon product listing.
        :param instnace: This argument relocates instance of amazon.
        :return: This Method return header of envelope for amazon product listing.
        """
        return """<?xml version="1.0"?>
            <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
            xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
            <Header>
                <DocumentVersion>1.01</DocumentVersion>
                <MerchantIdentifier>%s</MerchantIdentifier>
            </Header>
            <MessageType>Product</MessageType>
            <PurgeAndReplace>false</PurgeAndReplace>
         """ % (instnace.merchant_id)

    def standard_product_code(self, product):
        """
        This Method prepare envelope message of standard product type for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return standard product type envelope message for amazon.
        """
        product_code, product_type = '', ''
        if product.standard_product_id_type in ['GTIN']:
            return """<SKU>%s</SKU>""" % product.seller_sku
        if product.standard_product_id_type == 'ASIN':
            product_code, product_type = product.product_asin, 'ASIN'
        elif product.standard_product_id_type == 'EAN':
            product_code, product_type = product.barcode, 'EAN'
        elif product.standard_product_id_type == 'GTIN':
            product_code, product_type = product.product_upc, 'GTIN'
        elif product.standard_product_id_type == 'UPC':
            product_code, product_type = product.product_upc, 'UPC'
        return """<SKU>%s</SKU>
                         <StandardProductID>
                             <Type>%s</Type>
                             <Value>%s</Value>
                         </StandardProductID>
                       """ % (product.seller_sku, product_type, product_code)

    def get_lanuch_date(self, product):
        """
        This Method prepare envelope message of lunch date for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return lunch date envelope message for amazon.
        """
        launch_date = product.launch_date and datetime.strftime(product.launch_date,
                                                                DATE_YMDHMS) or False
        return launch_date and " <LaunchDate>%s</LaunchDate>" % (launch_date) or False

    def get_related_product_type(self, product):
        """
        This Method prepare envelope message of related product type for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return related product type envelope message for amazon.
        """
        return """<RelatedProductID>
                          <Type>%s</Type>
                          <Value>%s</Value>
                      </RelatedProductID>""" % ( \
            product.related_product_type, product.related_product_value)

    def get_discontinue_date(self, product):
        """
        This Method prepare envelope message of discontinue date for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return discontinue date envelope message for amazon.
        """
        discontinue_date = product.discontinue_date and datetime.strftime( \
            product.discontinue_date, DATE_YMDHMS) or False
        return discontinue_date and " <DiscontinueDate>%s</DiscontinueDate>" % ( \
            discontinue_date) or False

    def get_release_date(self, product):
        """
        This Method prepare envelope message of release date for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return release date envelope message for amazon.
        """
        release_date = product.release_date and datetime.strftime( \
            product.release_date, DATE_YMDHMS) or False
        return release_date and " <ReleaseDate>%s</ReleaseDate>" % release_date or False

    def get_item_dimension(self, product):
        """
        This Method prepare envelope message of item dimension for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return item dimension envelope message for amazon.
        """
        if product.item_dimensions_uom:
            return """
                    <ItemDimensions>
                        <Length unitOfMeasure='%s'>%s</Length>
                        <Width unitOfMeasure='%s'>%s</Width>
                        <Height unitOfMeasure='%s'>%s</Height>

                    </ItemDimensions>
                    """ % ( \
                product.item_dimensions_uom, str(round(float(product.item_length), 2)),
                product.item_dimensions_uom, \
                str(round(float(product.item_width), 2)), product.item_dimensions_uom, \
                str(round(float(product.item_width), 2)))

    def get_package_dimension(self, product):
        """
        This Method prepare envelope message of package dimension for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return package dimension envelope message for amazon.
        """
        if product.package_dimensions_uom:
            return """
                    <PackageDimensions>
                        <Length unitOfMeasure='%s'>%s</Length>
                        <Width unitOfMeasure='%s'>%s</Width>
                        <Height unitOfMeasure='%s'>%s</Height>

                    </PackageDimensions>
                    """ % ( \
                product.package_dimensions_uom, str(round(float(product.package_length), 2)),
                product.item_dimensions_uom,
                str(round(float(product.package_width), 2)), product.item_dimensions_uom,
                str(round(float(product.package_width), 2)))

    def get_condition(self, product):
        """
        This Method prepare envelope message of condition for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return condition envelope message for amazon.
        """
        if product.condition:
            product.condition = 'New' if product.condition == 'NewItem' else product.condition
            return """<Condition>
                            <ConditionType>%s</ConditionType>
                      </Condition>""" % product.condition
        return False

    def item_package_qty_and_no_of_items(self, product):
        """
        This Method prepare envelope message of item package qty and no of items for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return item package qty and no of items envelope message for amazon.
        """
        item_pack = ''
        if product.item_package_qty > 0:
            item_pack = "%s %s" % (
                item_pack,
                "<ItemPackageQuantity>%s</ItemPackageQuantity>" % (product.item_package_qty))
        if product.asin_qty > 0:
            item_pack = "%s %s" % (
                item_pack, "<NumberOfItems>%s</NumberOfItems>" % (product.asin_qty))
        return item_pack

    def get_description_data(self, product):
        """
        This Method prepare envelope message of description data for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return description data envelope message for amazon.
        """
        data = []
        data.append("<Title>%s</Title>" % (html.escape(product.name)))  # .encode("utf-8")
        # product.brand and data.append(
        #     "<Brand>%s</Brand>" % (html.escape(product.brand)))  # .encode("utf-8")
        product.designer and data.append(
            "<Designer>%s</Designer>" % (html.escape(product.designer)))  # .encode("utf-8")
        description = product.long_description or False
        description and data.append("<Description>%s</Description>" % (html.escape(description)))

        product.bullet_point_ids and data.append(self.get_bullet_points(product))
        item_dimension = self.get_item_dimension(product)
        if item_dimension:
            data.append(item_dimension)
        package_dimension = self.get_package_dimension(product)
        if package_dimension:
            data.append(package_dimension)
        if product.package_weight > 0.0:
            data.append("""<PackageWeight unitOfMeasure='%s'>%s</PackageWeight>""" % (
                product.package_weight_uom, str(round(float(product.package_weight), 2))))

        if product.shipping_weight > 0.0:
            data.append("""<ShippingWeight unitOfMeasure='%s'>%s</ShippingWeight>""" % ( \
                product.shipping_weight_uom, str(round(float(product.shipping_weight), 2))))
        if product.max_order_quantity > 0:
            data.append("<MaxOrderQuantity>%s</MaxOrderQuantity>" % product.max_order_quantity)
        # product.manufacturer and data.append(
        #     "<Manufacturer>%s</>" % (html.escape(product.manufacturer)))
        product.search_term_ids and data.append(self.get_search_terms(product))
        data.append("<IsGiftWrapAvailable>%s</IsGiftWrapAvailable>" % (
            str(product.is_gift_wrap_available).lower()))
        data.append("<IsGiftMessageAvailable>%s</IsGiftMessageAvailable>" % (
            str(product.is_gift_message_available).lower()))

        description_data = ''
        for tag in data:
            description_data = "%s %s" % (description_data, tag)
        return "<DescriptionData>%s</DescriptionData>" % (str(description_data))

    def get_search_terms(self, product):
        """
        This Method prepare envelope message of search term for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return search term envelope message for amazon.
        """
        search_terms = ''
        for search_term in product.search_term_ids:
            search_term = """<SearchTerms>%s</SearchTerms>""" % (html.escape(search_term.name))
            search_terms = "%s %s" % (search_terms, search_term)
        return search_terms

    def get_bullet_points(self, product):
        """
        This Method prepare envelope message of bullet points description for amazon.
        :param product: This arguments relocates product of amazon.
        :return: This method return bullet points description envelope message for amazon.
        """
        bullet_points = ''
        for bullet in product.bullet_point_ids:
            bullet_point = """<BulletPoint>%s</BulletPoint>""" % (html.escape(bullet.name))
            bullet_points = '%s %s' % (bullet_points, bullet_point)
        return bullet_points

    def export_stock_levels(self, instance):
        """
        This method used to export product stock to amazon
        :param : instance : This arguments relocates instance of amazon
        :return : return Boolean(True/False)
        :Migration done by kishan sorani on date 27-Sep-2021
        """
        warehouse_ids = self.get_warehouses_for_export_stock(instance)
        product_ids = self.mapped('product_id')
        amazon_products = self.ids
        message_information = self.process_export_stock_message_info_ept(instance, product_ids.ids,
                                                                         amazon_products, warehouse_ids)
        if message_information:
            self.process_amazon_export_stock_dict_ept(instance, message_information)
        return True

    def get_warehouses_for_export_stock(self, instance):
        """
        Define method which help to get warehouses of instance for update stock
        in amazon.
        :param : instance : This arguments relocates instance of amazon
        :return : list of warehouses
        @author : kishan sorani on date 27-Sep-2021
        """
        warehouse_ids = instance.warehouse_id.ids
        if instance.stock_update_warehouse_ids:
            warehouse_ids += instance.stock_update_warehouse_ids.ids
            warehouse_ids = list(set(warehouse_ids))
        return warehouse_ids

    def export_amazon_stock_levels_operation(self, instance):
        """
        This Method relocates prepare envelop for inventory.
        :param : instance : This arguments relocates instance of amazon
        :return: This Method return Boolean(True/False).
        """
        prod_obj = self.env[PRODUCT_PRODUCT]
        from_datetime = instance.inventory_last_sync_on
        company = instance.company_id

        warehouse_ids = self.get_warehouses_for_export_stock(instance)

        if not from_datetime:
            from_datetime = datetime.today() - timedelta(days=365)
        product_ids = prod_obj.get_products_based_on_movement_date_ept(from_datetime, company)
        amazon_products = self.env[AMAZON_PRODUCT_EPT].search([('exported_to_amazon', '=', True),
                                                                 ('instance_id', '=', instance.id),
                                                                 ('fulfillment_by', '=', 'FBM'),
                                                                 ('product_id', 'in', product_ids)])
        product_ids = amazon_products.mapped('product_id')
        message_information = self.process_export_stock_message_info_ept(instance, product_ids.ids,
                                                                         amazon_products.ids, warehouse_ids)
        if message_information:
            self.process_amazon_export_stock_dict_ept(instance, message_information)
        return True

    def process_export_stock_message_info_ept(self, instance, product_ids, amazon_products_ids,
                                              warehouse_ids):
        """
        Define method for process products stock and export in amazon.
        :param : instance : This arguments relocates instance of amazon
        :param : product_ids : This arguments relocates product listing id of odoo
        :param : amazon_products_ids : This arguments relocates product listing id of amazon
        :param : warehouse_ids : This arguments relocates warehouses of amazon
        :return : prepare message for export stock
        """
        product_listing_stock = self.check_stock_type(instance, product_ids, warehouse_ids)
        message_information = ''
        if product_listing_stock:
            message_id = 1
            for amazon_product_id in amazon_products_ids:
                amazon_product = self.browse(amazon_product_id)
                stock = product_listing_stock.get(amazon_product.product_id.id)
                message_information = self.prepare_export_stock_level_dict_operation(
                    amazon_product, instance, stock, message_information, message_id)
                message_id += 1
        return message_information

    def process_amazon_export_stock_dict_ept(self, instance, message_information):
        """
        This method will prepare the message information
        """
        merchant_string = "<MerchantIdentifier>%s</MerchantIdentifier>" % (instance.merchant_id)
        data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi=
        "http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
        <Header><DocumentVersion>1.01</DocumentVersion>""" + merchant_string + """</Header>
        <MessageType>Inventory</MessageType>""" + message_information + """</AmazonEnvelope>"""
        kwargs = self.get_amazon_product_request_data_ept(instance, data, 'amazon_submit_feeds_sp_api')
        kwargs.update({'feed_type': 'POST_INVENTORY_AVAILABILITY_DATA'})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
        self.process_amazon_export_stock_response_ept(instance, data, response)
        return True

    def process_amazon_export_stock_response_ept(self, instance, data, response):
        """
        Define method for process Amazon response from exported products stock and
        create feed history.
        """
        common_log_line_obj = self.env['common.log.lines.ept']
        amazon_feed_submit_history = self.env[FEED_SUBMISSION_HISTORY]

        if response.get('error', False):
            common_log_line_obj.create_common_log_line_ept(
                message=response.get('error', {}),
                model_name=AMAZON_PRODUCT_EPT, fulfillment_by='FBM', module='amazon_ept',
                operation_type='export', res_id=self.id,
                amz_instance_ept=instance and instance.id or False,
                amz_seller_ept=instance.seller_id and instance.seller_id.id or False)
        else:
            results = response.get('results', {})
            seller_id = self._context.get('seller_id', False) or instance.seller_id
            if seller_id and results.get('feed_result', {}).get('feedId', False):
                feed_document_id = results.get('result', {}).get('feedDocumentId', '')
                last_feed_submission_id = results.get('feed_result', {}).get('feedId', False)
                vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                        'feed_submit_date': time.strftime(DATE_YMDHMS),
                        'instance_id': instance.id, 'user_id': self._uid,
                        'feed_type': 'export_stock', 'feed_document_id' : feed_document_id,
                        'seller_id': instance.seller_id.id}
                amazon_feed_submit_history.create(vals)
        return True

    def check_stock_type(self, instance, product_ids, warehouse_ids):
        """
        This Method relocates check type of stock.
        :param instance: This arguments relocates instance of amazon.
        :param product_ids: This arguments product listing id of odoo.
        :param warehouse_ids:This arguments relocates warehouses of amazon.
        :return: This Method return product listing stock.
        """
        product_listing_stock = []
        prod_obj = self.env[PRODUCT_PRODUCT]
        ware_obj = self.env['stock.warehouse']
        if product_ids:
            warehouses = ware_obj.browse(warehouse_ids)
            if instance.stock_field == 'free_qty':
                product_listing_stock = prod_obj.get_free_qty_ept(warehouses, product_ids)
            elif instance.stock_field == 'virtual_available':
                product_listing_stock = prod_obj.get_forecasted_qty_ept(warehouses, product_ids)
        return product_listing_stock

    def prepare_export_stock_level_dict_operation(self, amazon_product, instance, actual_stock,
                                                  message_information, message_id):

        """
        This Method relocates prepare envelope of export stock value.
        :param amazon_product: This arguments relocates product of amazon.
        :param instance: This arguments relocates instance of amazon.
        :param actual_stock : stock
        :param message_information: This arguments relocates message information.
        :param message_id: This arguments relocates message id of amazon envelope.
        :return: This method return message envelope for amazon.
        """
        seller_sku = html.escape(amazon_product['seller_sku'])
        stock = self.stock_ept_calculation(actual_stock,
                                           amazon_product['fix_stock_type'],
                                           amazon_product['fix_stock_value'])

        if amazon_product['allow_package_qty']:
            asin_qty = amazon_product['asin_qty']
            stock = math.floor(stock / asin_qty) if asin_qty > 0.0 else stock

        stock = 0 if int(stock) < 1 else int(stock)
        fullfillment_latency = amazon_product.product_id.sale_delay or amazon_product['fulfillment_latency'] or \
                               instance.seller_id.fulfillment_latency
        message_information += """<Message><MessageID>%s</MessageID>
        <OperationType>Update</OperationType>
        <Inventory><SKU>%s</SKU><Quantity>%s</Quantity><FulfillmentLatency>%s</FulfillmentLatency></Inventory>
        </Message>""" % (message_id, seller_sku, stock, int(fullfillment_latency))
        return message_information

    def stock_ept_calculation(self, actual_stock, fix_stock_type=False, fix_stock_value=0):
        """
        This mehod relocates calculate stock.
        :param actual_stock: This arguments relocates actual stock.
        :param fix_stock_type: This arguments relocates type of stock type.
        :param fix_stock_value: This arguments relocates value of stock value.
        :return:
        """
        try:
            if actual_stock >= 1.00:
                if fix_stock_type == 'fix':
                    if fix_stock_value >= actual_stock:
                        return actual_stock
                    return fix_stock_value

                if fix_stock_type == 'percentage':
                    quantity = int((actual_stock * fix_stock_value) / 100.0)
                    if quantity >= actual_stock:
                        return actual_stock
                    return quantity
            return actual_stock
        except Exception as e:
            raise UserError(e)

    def update_price(self, instance):
        """
        This Method relocates create envelope for update price in amazon.
        :param instance: This arguments relocates instance of amazon.
        :return:This Method return boolean(True/False).
        """
        message_id = 1
        message_information = ''
        merchant_string = "<MerchantIdentifier>%s</MerchantIdentifier>" % instance.merchant_id
        message_type = """<MessageType>Price</MessageType>"""
        for amazon_products in self:
            message_information = self.update_price_dict(instance, amazon_products,
                                                         message_information, message_id)
            message_id += 1
        if message_information:
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi=
            "http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
            <Header><DocumentVersion>1.01</DocumentVersion>""" + merchant_string + """
            </Header>""" + message_type + """""" + message_information + """</AmazonEnvelope>"""
            kwargs = self.get_amazon_product_request_data_ept(instance, data, 'amazon_submit_feeds_sp_api')
            kwargs.update({'feed_type': 'POST_PRODUCT_PRICING_DATA'})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                raise UserError(_(response.get('error', {})))
            results = response.get('results', {})
            self.process_amazon_update_price_result(instance, data, results)
        return True

    def process_amazon_update_price_result(self, instance, data, results):
        """
        Define method for create feed history for Updated Products Price in Amazon.
        """
        amazon_feed_submit_history = self.env[FEED_SUBMISSION_HISTORY]

        if results.get('feed_result', {}).get('feedId', False):
            feed_document_id = results.get('result', {}).get('feedDocumentId', '')
            last_feed_submission_id = results.get('feed_result', {}).get('feedId', False)
            self.write({'last_feed_submission_id': last_feed_submission_id})
            vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                    'feed_submit_date': time.strftime(DATE_YMDHMS),
                    'instance_id': instance.id, 'user_id': self._uid,
                    'feed_type': 'export_price', 'feed_document_id': feed_document_id,
                    'seller_id': instance.seller_id.id}
            amazon_feed_submit_history.create(vals)
        return True

    @staticmethod
    def update_price_dict(instance, amazon_product, message_information, message_id):
        """
        This Method relocates Prepare price dictionary for amazon.
        :param instance: This arguments relocates instance of amazon.
        :param amazon_product: This arguments relocates product listing of amazon.
        :param message_information: This arguments prepare message envelope of amazon.
        :param message_id: This arguments relocates message of amazon.
        :return:This Method return envelope message of amazon.
        """
        product = amazon_product.product_id
        price = instance.pricelist_id._get_product_price(product=product, quantity=1.0,
                                                         uom=product.uom_id)
        price = price and round(price, 2) or 0.0
        seller_sku = html.escape(amazon_product.seller_sku)
        price_string = """<Message><MessageID>%(message_id)s</MessageID><Price><SKU>%(sku)s</SKU>
        <StandardPrice currency="%(currency)s">%(price)s</StandardPrice></Price></Message>"""
        price_string = price_string % {'currency': instance.pricelist_id.currency_id.name,
                                       'message_id': message_id, 'sku': seller_sku, 'price': price}
        message_information += price_string
        return message_information

    def update_images(self, instance):
        """
        This Method relocates prepare image envelope for amazon.
        :param instance: This arguments relocates instance of amazon.
        :return: This Method return boolean(True/False).
        """
        message_id = 1
        merchant_string = "<MerchantIdentifier>%s</MerchantIdentifier> " % (instance.merchant_id)
        message_information = ''
        for amazon_product in self:
            if not amazon_product.exported_to_amazon:
                continue
            for image_obj in amazon_product.product_id.ept_image_ids:
                message_information = self.create_image_dict(amazon_product, image_obj,
                                                             message_information, message_id)
                message_id += 1
        if message_information:
            data = """<?xml version="1.0" encoding="utf-8"?>
            <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
            xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01
            </DocumentVersion>""" + merchant_string + """</Header><MessageType>
            ProductImage</MessageType>""" + message_information + """</AmazonEnvelope> """
            kwargs = self.get_amazon_product_request_data_ept(instance, data, 'amazon_submit_feeds_sp_api')
            kwargs.update({'feed_type': 'POST_PRODUCT_IMAGE_DATA'})
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT, params=kwargs, timeout=1000)
            if response.get('error', False):
                raise UserError(_(response.get('error', {})))
            results = response.get('results', {})
            self.process_amazon_update_image_result(instance, results, data)
        return True

    def process_amazon_update_image_result(self, instance, results, data):
        """
        Define method for create feed history for Updated Products Image in Amazon.
        """
        amazon_process_job_log_obj = self.env['common.log.book.ept']
        feed_submission_obj = self.env[FEED_SUBMISSION_HISTORY]

        if results.get('feed_result', {}).get('feedId', False):
            feed_document_id = results.get('result', {}).get('feedDocumentId', '')
            last_feed_submission_id = results.get('feed_result', {}).get('feedId', False)
            self.write({'error_in_export_image': False,
                        'last_feed_submission_id': last_feed_submission_id})
            vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                    'feed_submit_date': time.strftime(DATE_YMDHMS),
                    'instance_id': instance.id, 'user_id': self._uid,
                    'feed_type': 'export_image', 'feed_document_id':feed_document_id,
                    'seller_id': instance.seller_id.id}
            feed = feed_submission_obj.create(vals)
            amazon_process_job_log_obj.create({
                'module': 'amazon_ept',
                'type': 'import',
                'res_id': self.id,
                'model_id': self.env['ir.model']._get(AMAZON_PRODUCT_EPT).id,
                'active': True,
                'log_lines': [(0, 0, {'message': 'Requested Feed Id' + feed and feed.id or False,
                                      'amz_seller_ept': instance.seller_id and instance.selller_id.id or False,
                                      'amz_instance_ept': instance and instance.id or False})]
            })
        return True

    def create_image_dict(self, amazon_product, image_obj, message_information, message_id):
        """
        This Method relocates prepare image envelope for amazon.
        :param amazon_product: This arguments relocates product listing of amazon.
        :param image_obj: This arguments relocates image object of amazon.
        :param message_information: This arguments prepare message envelope of amazon.
        :param message_id:This arguments relocates message of amazon.
        :return: This Method return envelope message of amazon.
        """
        seller_sku = amazon_product.seller_sku
        amazon_image_type = 'Main'
        amazon_image_url = image_obj.url

        message_information += """<Message><MessageID>%s</MessageID>
        <OperationType>Update</OperationType>
        <ProductImage><SKU>%s</SKU><ImageType>%s</ImageType><ImageLocation>%s</ImageLocation></ProductImage>
        </Message>""" % (message_id, seller_sku, amazon_image_type, amazon_image_url)
        return message_information

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """
        By inheriting this method now the users will search the product
        with name of amazon product and odoo product, also by seller sku and odoo default code
        :param name: value to search from search bar
        :param args: searching domain
        :param operator: comparison operator
        :param limit: search limit
        :return: call the _search method with updated args
        """
        args = list(args or [])
        if name:
            args.extend(['|', '|', '|', ('seller_sku', operator, name), ('name', operator, name),
                         ('product_id.name', operator, name), ('product_id.default_code', operator, name)])
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)

class ProductProduct(models.Model):
    """
    Added class for map amazon products with odoo products .
    """
    _inherit = 'product.product'

    is_mapped_with_amz = fields.Boolean(compute="_compute_is_amazon_mapped")

    def _compute_is_amazon_mapped(self):
        """
        Define method which help to map odoo products with amazon products..
        """
        amz_product_obj = self.env[AMAZON_PRODUCT_EPT]
        desired_user_gr = self.env.user.has_group('amazon_ept.group_amazon_user_ept')
        for product in self:
            product.is_mapped_with_amz = True if desired_user_gr and amz_product_obj.search(
                [('product_id', '=', product.id)]) else False

    def action_view_amazon_product_ept(self):
        """
        This method return action which load amazon products.
        """
        self.ensure_one()
        action = self.env.ref('amazon_ept.action_amazon_product_ept').sudo().read()[0]
        action['domain'] = [('product_id', '=', self.id)]
        return action
