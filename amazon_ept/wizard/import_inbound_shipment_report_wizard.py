# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added class to import inbound shipment report, read csv file and download sample CSV.
"""

import csv
import base64
import os
from datetime import datetime
from odoo import models, fields, _
from odoo.exceptions import UserError, ValidationError
from dateutil import parser

try:
    from io import StringIO
except ImportError:
    from StringIO import StringIO

DIMENSION_NAME = 'Dimension Name'
DIMENSION_TYPE = 'Dimension Type'
DIMENSION_UNIT = 'Dimension Unit'


class AmazonInboundShipmentReportWizard(models.TransientModel):
    """
    Added class to import inbound shipment report.
    """
    _name = "amazon.inbound.shipment.report.wizard"
    _description = 'Import In-bound Shipment Report Through CSV File'

    choose_file = fields.Binary(help="Select amazon In-bound shipment file.")
    file_name = fields.Char("Filename", help="File Name")
    delimiter = fields.Selection([('tab', 'Tab'), ('semicolon', 'Semicolon'), ('colon', 'Colon')],
                                 "Separator", default='colon',
                                 help="Select separator type for the separate file data and "
                                      "import into ERP.")

    def read_file(self):
        """
        Read selected file to import inbound shipment report and return Reader to the caller
        :return : reader object of selected file.
        """
        if os.path.splitext(self.file_name)[1].lower() != '.csv':
            raise ValidationError(_("Invalid file format. You are only allowed to upload .csv file."))
        try:
            data = StringIO(base64.b64decode(self.choose_file).decode())
        except Exception:
            data = StringIO(base64.b64decode(self.choose_file).decode('ISO-8859-1'))
        content = data.read()
        delimiter = ('\t', csv.Sniffer().sniff(content.splitlines()[0]).delimiter)[bool(content)]
        reader = csv.DictReader(content.splitlines(), delimiter=delimiter)
        return reader

    def download_inbound_shipment_sample_csv(self):
        """
        Download Sample Box Content file for Inbound Shipment Plan Products Import
        :return: Dict
        """
        attachment = self.env['ir.attachment'].search([('name', '=', 'amazon_inbound_shipment_box_content.csv'),
                                                       ('res_model', '=', 'amazon.inbound.shipment.wizard')])
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % (attachment.id),
            'target': 'new',
            'nodestroy': False,
        }

    def check_fields_validation(self, fields_name):
        """
            This import pattern requires few fields default, so check it first whether it's there or not.
        """
        # Modified line By: Dhaval Sanghani [29-May-2020]
        # Purpose: Add Weight as require field
        require_fields = ['Box No', 'Weight Unit', DIMENSION_NAME, DIMENSION_TYPE, 'Weight']
        missing = []
        for field in require_fields:
            if field not in fields_name:
                missing.append(field)
        if len(missing) > 0:
            raise UserError(_('Incorrect format found..!\nPlease provide all the required fields in file, '
                              'missing fields => %s.' % missing))
        return True

    def fill_dictionary_from_file(self, reader):
        """
        Will prepare the inbound_shipment_data_list from the file data.
        """
        inbound_shipment_data_list = []
        for row in reader:
            vals = {
                'box_no': row.get('Box No', ''),
                'weight_value': row.get('Weight', 0.0),
                'weight_unit': row.get('Weight Unit', ''),
                'dimension_name': row.get(DIMENSION_NAME, ''),
                'dimension_type': row.get(DIMENSION_TYPE, '').casefold(),
                'dimension_unit': row.get(DIMENSION_UNIT, '').casefold(),
                'hight': row.get('Height', ''),
                'width': row.get('Width', 0.0),
                'length': row.get('Length', 0.0),
                'seller_sku': row.get('Seller SKU', ''),
                'quantity': row.get('Quantity', 0.0),
            }
            inbound_shipment_data_list.append(vals)
        return inbound_shipment_data_list

    def import_inbound_shipment_report(self):
        """
        Use: Import inbound shipment excel report.
        Added By: Dhaval Sanghani [@Emipro Technologies]
        Added On: 25-May-2020
        @param: {}
        @return: {}
        """
        if not self.choose_file:
            raise UserError(_('Unable to process..!\nPlease Upload File to Process...'))

        amazon_inbound_shipment_obj = self.env["amazon.inbound.shipment.ept"]
        product_ul_ept_obj = self.env["product.ul.ept"]
        amazon_product_ept = self.env["amazon.product.ept"]

        active_ids = self._context.get('active_ids', [])
        inbound_shipment = amazon_inbound_shipment_obj.browse(active_ids)

        reader = self.read_file()
        fields_name = reader.fieldnames
        if self.check_fields_validation(fields_name):
            instance = inbound_shipment.instance_id_ept
            new_boxes = []
            parcel_list = []
            parcel_dict = {}
            for row in reader:
                box_no = row.get("Box No", "")
                seller_sku = row.get('Seller SKU', '')
                quantity = float(row.get('Quantity', 0.0)) if row.get('Quantity', 0.0) else 0.0
                amazon_product = amazon_product_ept.search_amazon_product(instance.id, seller_sku, 'FBA')
                if not amazon_product:
                    raise UserError(_('%s Amazon Product Not for %s Instance..!' % (seller_sku, instance.name)))
                carton_details_vals = {
                    'amazon_product_id': amazon_product.id,
                    'quantity': quantity
                }
                # Create a New Box Info
                if box_no not in new_boxes:
                    new_boxes.append(box_no)
                _dimension_domain = [
                    ("type", "=ilike", row.get(DIMENSION_TYPE, '').casefold()),
                    ("dimension_unit", "=ilike", row.get(DIMENSION_UNIT, '').casefold()),
                    ("height", "=", row.get('Height', 0.00)),
                    ("width", "=", row.get('Width', 0.00)),
                    ("length", "=", row.get('Length', 0.00)),
                ]
                product_ul = product_ul_ept_obj.search(_dimension_domain, limit=1)
                if not product_ul:
                    dimension_vals = {
                        'name': row.get(DIMENSION_NAME, ''),
                        'type': row.get(DIMENSION_TYPE, '').casefold(),
                        'dimension_unit': row.get(DIMENSION_UNIT, '').casefold(),
                        'height': row.get('Height', 0.00),
                        'width': row.get('Width', 0.00),
                        'length': row.get('Length', 0.00),
                    }
                    try:
                        product_ul = product_ul_ept_obj.create(dimension_vals)
                    except Exception as ex:
                        raise UserError(_(ex))
                vals = {
                    'ul_id': product_ul.id,
                    'box_no': box_no,
                    'weight_value': row.get("Weight", 0.0),
                    'weight_unit': row.get("Weight Unit", ""),
                    'box_expiration_date': parser.parse(row.get('Expiry Date', False))
                }
                if parcel_dict.get(box_no, False):
                    carton_info = parcel_dict.get(box_no, {}).get('carton_info_ids', [])
                    flag = True
                    for item in carton_info:
                        if item[2].get('amazon_product_id', False) == amazon_product.id:
                            total_qty = item[2].get('quantity', 0.0) + quantity
                            item[2].update({'quantity': total_qty})
                            flag = False
                    if flag:
                        parcel_dict.get(box_no, {}).get('carton_info_ids', []).append((0, 0, carton_details_vals))
                else:
                    vals.update({'carton_info_ids': [(0, 0, carton_details_vals)]})
                    parcel_dict.update({box_no: vals})
            for box_no in new_boxes:
                parcel_list.append((0, 0, parcel_dict.get(box_no)))
            if parcel_list:
                if inbound_shipment.transport_type in ['partnered_small_parcel_data', 'non_partnered_small_parcel_data',
                                                       'non_partnered_ltl_data']:
                    inbound_shipment.partnered_small_parcel_ids = parcel_list
                else:
                    inbound_shipment.partnered_ltl_ids = parcel_list
        return True
