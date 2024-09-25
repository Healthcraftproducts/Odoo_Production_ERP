import logging
import requests
import binascii
import xml.etree.ElementTree as etree
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.purolator_shipping_integration.models.purolator_response import Response
import hashlib
from requests.auth import HTTPBasicAuth
import time
import base64
import re
import uuid

_logger = logging.getLogger("Purolator")


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(selection_add=[("purolator", "Purolator")],
                                     ondelete={'purolator': 'set default'})
    purolator_package_type = fields.Selection([("ExpressEnvelope", "ExpressEnvelope"),
                                               ("ExpressPack", "ExpressPack"),
                                               ("CustomerPackaging", "CustomerPackaging"),
                                               ("ExpressBox", "ExpressBox")], default='CustomerPackaging')
    weight_unit = fields.Selection([("lb", "lb - pounds"),
                                    ("kg", "kg - kilogram")], string="Weight Unit", default='kg')
    purolator_provider_package_id = fields.Many2one('stock.package.type', string="Package",
                                                    help="Default Package")
    dimension_unit = fields.Selection([('in', 'Inch'), ('cm', 'centimetres')], string="Dimension Unit", default='cm')
    purolator_pickup_type = fields.Selection([('DropOff', 'DropOff'),
                                              ('PreScheduled', 'PreScheduled')], string="Pickup Type",
                                             default='DropOff')
    purolator_payment_type = fields.Selection([('Sender', 'Sender'),
                                               ('Receiver', 'Receiver'),
                                               ('ThirdParty', 'ThirdParty')],
                                              string="Payment Type", default="Sender")
    printer_type = fields.Selection([('Regular', 'Regular'), ('Thermal', 'Thermal')], string="Printer Type",
                                    default="Regular")

    def purolator_rate_shipment(self, orders):
        "This Method Is Used For Get Rate"
        sender_address = orders.warehouse_id and orders.warehouse_id.partner_id
        # sender_address = orders.partner_return_id if orders.partner_return_id else orders.warehouse_id and orders.warehouse_id.partner_id
        receiver_address = orders.partner_shipping_id

        if not sender_address.zip or not sender_address.city or not sender_address.country_id:
            return {'success': False, 'price': 0.0,
                    'error_message': ("Please Define Proper Sender Address!"),
                    'warning_message': False}

        if not receiver_address.zip or not receiver_address.city or not receiver_address.country_id:
            return {'success': False, 'price': 0.0,
                    'error_message': ("Please Define Proper Recipient Address!"),
                    'warning_message': False}
        weight = sum(
            [(line.product_id.weight * line.product_uom_qty) for line in orders.order_line if not line.is_delivery])
        # if weight < 1.0:
        #     weight = "1.0"

        root_element = etree.Element("soapenv:Envelope")

        root_element.attrib['xmlns:soapenv'] = "http://schemas.xmlsoap.org/soap/envelope/"
        root_element.attrib['xmlns:v2'] = "http://purolator.com/pws/datatypes/v2"

        root_header = etree.SubElement(root_element, "soapenv:Header")
        request_context = etree.SubElement(root_header, "v2:RequestContext")
        etree.SubElement(request_context, "v2:Version").text = "2.2"
        etree.SubElement(request_context, "v2:Language").text = "en"
        etree.SubElement(request_context, "v2:GroupID").text = str((uuid.uuid4().int))[:4]
        etree.SubElement(request_context, "v2:RequestReference").text = "rate"

        root_body = etree.SubElement(root_element, "soapenv:Body")
        root_getquickestimateRequest = etree.SubElement(root_body, "v2:GetQuickEstimateRequest")
        if self.purolator_payment_type != 'SENDER':
            etree.SubElement(root_getquickestimateRequest,
                             "v2:BillingAccountNumber").text = orders.purolator_third_party_account_number_sale_order
        else:
            etree.SubElement(root_getquickestimateRequest,
                             "v2:BillingAccountNumber").text = self.company_id.purolator_account_number
        # etree.SubElement(root_getquickestimateRequest,
        #                  "v2:BillingAccountNumber").text = self.company_id and self.company_id.purolator_account_number
        etree.SubElement(root_getquickestimateRequest, "v2:SenderPostalCode").text = sender_address.zip or ''
        root_receiveraddress = etree.SubElement(root_getquickestimateRequest, "v2:ReceiverAddress")
        etree.SubElement(root_receiveraddress, "v2:City").text = receiver_address.city or ''
        etree.SubElement(root_receiveraddress,
                         "v2:Province").text = receiver_address.state_id and receiver_address.state_id.code or ''
        etree.SubElement(root_receiveraddress,
                         "v2:Country").text = receiver_address.country_id and receiver_address.country_id.code or ''
        etree.SubElement(root_receiveraddress, "v2:PostalCode").text = receiver_address.zip or ''

        etree.SubElement(root_getquickestimateRequest, "v2:PackageType").text = self.purolator_package_type

        root_totalweight = etree.SubElement(root_getquickestimateRequest, "v2:TotalWeight")
        etree.SubElement(root_totalweight, "v2:Value").text = str(weight)
        etree.SubElement(root_totalweight, "v2:WeightUnit").text = self.weight_unit

        try:
            headers = {
                'Content-Type': "text/xml;  charset=utf-8",
                'SOAPAction': 'http://purolator.com/pws/service/v2/GetQuickEstimate'
            }
            username = self.company_id.purolator_username
            password = self.company_id.purolator_password
            url = "{0}/v2/Estimating/EstimatingService.asmx".format(
                self.company_id and self.company_id.purolator_api_url)
            _logger.info("Request Data Of Rate::::%s" % etree.tostring(root_element))
            response_data = requests.request(method="POST", url=url, headers=headers,
                                             auth=HTTPBasicAuth(username=username, password=password),
                                             data=etree.tostring(root_element))
            _logger.info("Response Data Of Rate::::%s" % response_data.content)
            if response_data.status_code in [200, 201]:
                api = Response(response_data)
                response_data = api.dict()
                _logger.info("JSON Response Data Of Rate::::%s" % response_data)
                common_response = response_data.get('Envelope').get('Body').get('GetQuickEstimateResponse')
                check_errors = common_response.get('ResponseInformation').get('Errors')
                if check_errors:
                    raise ValidationError(check_errors)

                purolator_shipping_charge_obj = self.env['purolator.shipping.charge']

                existing_records = purolator_shipping_charge_obj.search([('sale_order_id', '=', orders and orders.id)])
                existing_records.sudo().unlink()
                if common_response.get('ShipmentEstimates').get('ShipmentEstimate'):
                    rate_response_dicts = common_response.get('ShipmentEstimates').get('ShipmentEstimate')
                else:
                    raise ValidationError("Response Data : %s" % (response_data))
                if isinstance(rate_response_dicts, dict):
                    rate_response_dicts = [rate_response_dicts]
                for response_dict in rate_response_dicts:
                    purolator_service_id = response_dict.get('ServiceID')
                    expected_delivery_date = response_dict.get('ExpectedDeliveryDate')
                    estimated_transit_days = response_dict.get('EstimatedTransitDays')
                    purolator_total_charge = response_dict.get('TotalPrice')
                    purolator_shipping_charge_obj.sudo().create(
                        {
                            'purolator_service_id': purolator_service_id,
                            'expected_delivery_date': expected_delivery_date,
                            'estimated_transit_days': estimated_transit_days,
                            'purolator_total_charge': purolator_total_charge,
                            'sale_order_id': orders and orders.id
                        }
                    )
                purolator_charge_id = purolator_shipping_charge_obj.search(
                    [('sale_order_id', '=', orders and orders.id)], order='purolator_total_charge', limit=1)
                orders.purolator_shipping_charge_id = purolator_charge_id and purolator_charge_id.id
                return {'success': True,
                        'price': purolator_charge_id and purolator_charge_id.purolator_total_charge or 0.0,
                        'error_message': False, 'warning_message': False}
            else:
                return {'success': False, 'price': 0.0,
                        'error_message': "%s %s" % (response_data, response_data.text),
                        'warning_message': False}
        except Exception as e:
            raise ValidationError(e)

    def purolator_send_shipping(self, pickings):
        """This Method Is Used For Send The Shipping Request To Shipper"""
        response = []
        for picking in pickings:
            recipient_address = picking.partner_id
            recipient_name = recipient_address.parent_id and recipient_address.parent_id.name or ''
            cleaned_name = re.sub(r'[^A-Za-z0-9]+', ' ', recipient_name)
            if len(cleaned_name) > 30:
                company_name = cleaned_name[:30].strip()  # First 30 characters for Company
                department_name = cleaned_name[30:50].strip()  # Next 20 characters for Department
            else:
                company_name = cleaned_name
                department_name = ''  # No department name if total characters are <= 30

            # je shipper address comment karelu che ene uncomment karvu and niche nu comment karvu jyare third party
            shipper_address = picking.picking_type_id and picking.picking_type_id.warehouse_id and picking.picking_type_id.warehouse_id.partner_id
            # shipper_address = picking.sale_id.partner_return_id if picking.sale_id.partner_return_id else picking.picking_type_id and picking.picking_type_id.warehouse_id and picking.picking_type_id.warehouse_id.partner_id
            total_bulk_weight = picking.weight_bulk

            if not shipper_address.zip or not shipper_address.city or not shipper_address.country_id:
                raise ValidationError("Please define  proper sender addres")

            shipper_address_phone_number = shipper_address.phone and shipper_address.phone.replace(' ', '').replace('+',
                                                                                                                    '').replace(
                '(', '').replace(')', '').replace('-', '')
            if shipper_address_phone_number and len(shipper_address_phone_number) < 10:
                raise ValidationError("Please Check Shipper Phone Number Properly")

            shipper_country_code = '' if not shipper_address_phone_number else (
                shipper_address_phone_number[0] if '+1' in shipper_address.phone else '1')
            shipper_area_code = ' ' if not shipper_address_phone_number else (
                shipper_address_phone_number[1:4] if '+1' in shipper_address.phone else shipper_address_phone_number[
                                                                                        0:3])
            shipper_phone = ' ' if not shipper_address_phone_number else shipper_address_phone_number[
                                                                         4:11] if '+1' in shipper_address.phone else shipper_address_phone_number[
                                                                                                                     3:10]

            sender_phone_extension = shipper_address_phone_number[
                                     -3:] if shipper_address_phone_number and 'ext' in shipper_address_phone_number else ' '

            # check Receiver Address
            if not recipient_address.zip or not recipient_address.city or not recipient_address.country_id:
                raise ValidationError("Please define  proper receiver address")

            receipient_phone_number = recipient_address.phone and recipient_address.phone.replace(' ', '').replace('+',
                                                                                                                   '').replace(
                '(', '').replace(')', '').replace('-', '')
            if receipient_phone_number and len(receipient_phone_number) < 10:
                raise ValidationError("Please Check Customer Phone Number Properly")

            receiver_country_code = '' if not receipient_phone_number else (
                receipient_phone_number[0] if '+1' in recipient_address.phone else '1')
            receiver_area_code = ' ' if not receipient_phone_number else (
                receipient_phone_number[1:4] if '+1' in recipient_address.phone else receipient_phone_number[0:3])
            receiver_phone = ' ' if not receipient_phone_number else receipient_phone_number[
                                                                     4:11] if '+1' in recipient_address.phone else receipient_phone_number[
                                                                                                                   3:10]

            receiver_phone_extension = receipient_phone_number[
                                       -3:] if receipient_phone_number and 'ext' in receipient_phone_number else ' '

            root_element = etree.Element("soapenv:Envelope")
            root_element.attrib['xmlns:soapenv'] = "http://schemas.xmlsoap.org/soap/envelope/"
            root_element.attrib['xmlns:v2'] = "http://purolator.com/pws/datatypes/v2"

            root_header = etree.SubElement(root_element, "soapenv:Header")
            request_context = etree.SubElement(root_header, "v2:RequestContext")
            etree.SubElement(request_context, "v2:Version").text = "2.2"
            etree.SubElement(request_context, "v2:Language").text = "en"
            etree.SubElement(request_context, "v2:GroupID").text = "1"
            etree.SubElement(request_context, "v2:RequestReference").text = "Shipping Request"

            root_body = etree.SubElement(root_element, "soapenv:Body")
            root_createshipment = etree.SubElement(root_body, "v2:CreateShipmentRequest")
            root_shipment = etree.SubElement(root_createshipment, "v2:Shipment")
            root_senderinformation = etree.SubElement(root_shipment, "v2:SenderInformation")
            root_address = etree.SubElement(root_senderinformation, "v2:Address")

            etree.SubElement(root_address, "v2:Name").text = shipper_address.name or ''
            etree.SubElement(root_address,
                             "v2:Company").text = shipper_address.parent_id and shipper_address.parent_id.name or ''
            etree.SubElement(root_address, "v2:StreetNumber").text = shipper_address.street2 or ''
            etree.SubElement(root_address, "v2:StreetName").text = shipper_address.street or ''
            etree.SubElement(root_address, "v2:City").text = shipper_address.city or ''
            etree.SubElement(root_address,
                             "v2:Province").text = shipper_address.state_id and shipper_address.state_id.code
            etree.SubElement(root_address,
                             "v2:Country").text = shipper_address.country_id and shipper_address.country_id.code
            etree.SubElement(root_address, "v2:PostalCode").text = shipper_address.zip or ''

            root_phonenumber = etree.SubElement(root_address, "v2:PhoneNumber")
            etree.SubElement(root_phonenumber,
                             "v2:CountryCode").text = shipper_country_code  # shipper_address_phone_number[0] if '+1' in shipper_address.phone else '1'
            etree.SubElement(root_phonenumber,
                             "v2:AreaCode").text = shipper_area_code  # shipper_address_phone_number[1:4]
            etree.SubElement(root_phonenumber, "v2:Phone").text = shipper_phone  # shipper_address_phone_number[4:11]
            etree.SubElement(root_phonenumber,
                             "v2:Extension").text = sender_phone_extension  # shipper_address_phone_number[-3:] if 'ext' in shipper_address_phone_number else ''

            root_receiverinformation = etree.SubElement(root_shipment, "v2:ReceiverInformation")
            root_recaddress = etree.SubElement(root_receiverinformation, "v2:Address")

            etree.SubElement(root_recaddress, "v2:Name").text = recipient_address.name or ''
            etree.SubElement(root_recaddress,
                             "v2:Company").text = company_name
            etree.SubElement(root_recaddress,
                             "v2:Department").text = department_name

            etree.SubElement(root_recaddress, "v2:StreetNumber").text = recipient_address.street2 or ' '
            etree.SubElement(root_recaddress, "v2:StreetName").text = recipient_address.street or ''
            # etree.SubElement(root_recaddress, "v2:Suite").text = recipient_address.suite or ''
            # etree.SubElement(root_recaddress, "v2:Floor").text = recipient_address.floor or ''
            etree.SubElement(root_recaddress, "v2:StreetAddress2").text = recipient_address.street2 or ''
            etree.SubElement(root_recaddress, "v2:City").text = recipient_address.city or ''
            etree.SubElement(root_recaddress,
                             "v2:Province").text = recipient_address.state_id and recipient_address.state_id.code or ''
            etree.SubElement(root_recaddress,
                             "v2:Country").text = recipient_address.country_id and recipient_address.country_id.code or ''
            etree.SubElement(root_recaddress, "v2:PostalCode").text = recipient_address.zip or ''

            root_recphonenumber = etree.SubElement(root_recaddress, "v2:PhoneNumber")
            etree.SubElement(root_recphonenumber,
                             "v2:CountryCode").text = receiver_country_code  # receipient_phone_number[0] if '+1' in  recipient_address.phone else '1'
            etree.SubElement(root_recphonenumber,
                             "v2:AreaCode").text = receiver_area_code  # receipient_phone_number[1:4] if '+1' in recipient_address.phone else receipient_phone_number[0:3]
            etree.SubElement(root_recphonenumber,
                             "v2:Phone").text = receiver_phone  # receipient_phone_number[4:11] if '+1' in recipient_address.phone else receipient_phone_number[3:10]
            etree.SubElement(root_recphonenumber,
                             "v2:Extension").text = receiver_phone_extension  # receipient_phone_number[-3:] if 'ext' in receipient_phone_number else ''

            etree.SubElement(root_shipment, "v2:ShipmentDate").text = picking.scheduled_date.strftime("%Y-%m-%d")

            root_package_information = etree.SubElement(root_shipment, "v2:PackageInformation")
            etree.SubElement(root_package_information,
                             "v2:ServiceID").text = picking.sale_id and picking.sale_id.purolator_shipping_charge_id and picking.sale_id.purolator_shipping_charge_id.purolator_service_id or ''
            root_total_weight = etree.SubElement(root_package_information, "v2:TotalWeight")
            etree.SubElement(root_total_weight, "v2:Value").text = str(picking.shipping_weight) or ''
            etree.SubElement(root_total_weight, "v2:WeightUnit").text = self.weight_unit or ''

            etree.SubElement(root_package_information, "v2:TotalPieces").text = str(
                len(picking.package_ids) + (1 if picking.weight_bulk else 0))
            pieces_information = etree.SubElement(root_package_information, "v2:PiecesInformation")
            for package_id in picking.package_ids:
                piece_node = etree.SubElement(pieces_information, "v2:Piece")
                weight_node = etree.SubElement(piece_node, "v2:Weight")
                etree.SubElement(weight_node, "v2:Value").text = str(package_id.shipping_weight)
                etree.SubElement(weight_node, "v2:WeightUnit").text = self.weight_unit

                length_node = etree.SubElement(piece_node, "v2:Length")
                etree.SubElement(length_node, "v2:Value").text = str(package_id.package_type_id.packaging_length or 0)
                etree.SubElement(length_node, "v2:DimensionUnit").text = self.dimension_unit

                width_node = etree.SubElement(piece_node, "v2:Width")
                etree.SubElement(width_node, "v2:Value").text = str(package_id.package_type_id.width or 0)
                etree.SubElement(width_node, "v2:DimensionUnit").text = self.dimension_unit

                height_node = etree.SubElement(piece_node, "v2:height")
                etree.SubElement(height_node, "v2:Value").text = str(package_id.package_type_id.height or 0)
                etree.SubElement(height_node, "v2:DimensionUnit").text = self.dimension_unit

            if total_bulk_weight:
                piece_node = etree.SubElement(pieces_information, "v2:Piece")
                weight_node = etree.SubElement(piece_node, "v2:Weight")
                etree.SubElement(weight_node, "v2:Value").text = str(total_bulk_weight)
                etree.SubElement(weight_node, "v2:WeightUnit").text = self.weight_unit

                length_node = etree.SubElement(piece_node, "v2:Length")
                etree.SubElement(length_node, "v2:Value").text = str(
                    self.purolator_provider_package_id.packaging_length or 0)
                etree.SubElement(length_node, "v2:DimensionUnit").text = self.dimension_unit

                width_node = etree.SubElement(piece_node, "v2:Width")
                etree.SubElement(width_node, "v2:Value").text = str(self.purolator_provider_package_id.width or 0)
                etree.SubElement(width_node, "v2:DimensionUnit").text = self.dimension_unit

                height_node = etree.SubElement(piece_node, "v2:height")
                etree.SubElement(height_node, "v2:Value").text = str(self.purolator_provider_package_id.height or 0)
                etree.SubElement(height_node, "v2:DimensionUnit").text = self.dimension_unit

            root_payment_information = etree.SubElement(root_shipment, "v2:PaymentInformation")
            etree.SubElement(root_payment_information, "v2:PaymentType").text = self.purolator_payment_type
            etree.SubElement(root_payment_information,
                             "v2:RegisteredAccountNumber").text = self.company_id.purolator_account_number

            if self.purolator_payment_type != 'SENDER':
                etree.SubElement(root_payment_information,
                                 "v2:BillingAccountNumber").text = picking.sale_id.purolator_third_party_account_number_sale_order
            else:
                etree.SubElement(root_payment_information,
                                 "v2:BillingAccountNumber").text = self.company_id.purolator_account_number

            root_pickup_information = etree.SubElement(root_shipment, "v2:PickupInformation")
            etree.SubElement(root_pickup_information, "v2:PickupType").text = self.purolator_pickup_type

            root_notification_information = etree.SubElement(root_shipment, "v2:NotificationInformation")
            etree.SubElement(root_notification_information, "v2:ConfirmationEmailAddress").text = ""

            etree.SubElement(root_createshipment, "v2:PrinterType").text = self.printer_type

            try:
                headers = {
                    'Content-Type': "text/xml;  charset=utf-8",
                    'SOAPAction': "http://purolator.com/pws/service/v2/CreateShipment"
                }
                username = self.company_id.purolator_username
                password = self.company_id.purolator_password
                url = "{0}/v2/Shipping/ShippingService.asmx".format(
                    self.company_id and self.company_id.purolator_api_url)
                _logger.info("Request Data Of Shipping::::%s" % etree.tostring(root_element))
                response_data = requests.request(method="POST", url=url, headers=headers,
                                                 auth=HTTPBasicAuth(username=username, password=password),
                                                 data=etree.tostring(root_element))
                _logger.info("Response Data Of Shipping::::%s" % response_data.content)
                if response_data.status_code in [200, 201]:
                    api = Response(response_data)
                    response_data = api.dict()
                    _logger.info("JSON Response Data Of Shipping::::%s" % response_data)
                    common_response_data = response_data.get('Envelope').get('Body').get('CreateShipmentResponse')
                    check_errors = common_response_data.get('ResponseInformation').get('Errors')
                    if check_errors:
                        raise ValidationError(check_errors)
                    purolator_pieces_pin = []
                    purolator_shipment_pin = common_response_data.get('ShipmentPIN').get('Value')
                    piece_pins = common_response_data.get('PiecePINs').get('PIN')
                    if isinstance(piece_pins, dict):
                        piece_pins = [piece_pins]
                    for piece_pin in piece_pins:
                        purolator_pieces_pin.append(piece_pin.get('Value'))
                    label_response_data = self.purolator_get_label_using_shipment_pin(picking, purolator_shipment_pin)
                    picking.carrier_tracking_ref = purolator_shipment_pin
                    picking.purolator_piece_pin = ','.join(purolator_pieces_pin)
                    headers = {'Content-Type': "application/x-www-form-urlencoded", 'Accept': "application/pdf"}
                    common_response_of_label_data = label_response_data.get('Envelope') and label_response_data.get(
                        'Envelope').get(
                        'Body') and label_response_data.get('Envelope').get('Body').get(
                        'GetDocumentsResponse') and label_response_data.get('Envelope').get('Body').get(
                        'GetDocumentsResponse').get('Documents') and label_response_data.get('Envelope').get(
                        'Body').get('GetDocumentsResponse').get('Documents').get(
                        'Document') and label_response_data.get('Envelope').get('Body').get('GetDocumentsResponse').get(
                        'Documents').get('Document')

                    # if isinstance(common_response_of_label_data, dict):
                    #     common_response_of_label_data = [common_response_of_label_data]

                    # for piece_pdf_url in common_response_of_label_data:
                    pdf_label_url = common_response_of_label_data.get('DocumentDetails').get('DocumentDetail').get(
                        'URL')
                    time.sleep(3)
                    pdf_response = requests.request("GET", url=pdf_label_url, headers=headers)
                    logmessage = ("Tracking Numbers: %s") % (purolator_shipment_pin)
                    pickings.message_post(body=logmessage,
                                          attachments=[
                                              ("%s.pdf" % (common_response_of_label_data.get('PIN').get('Value')),
                                               pdf_response.content)])
                    shipping_data = {'exact_price': 0.0, 'tracking_number': purolator_shipment_pin}
                    response += [shipping_data]
                    return response

                else:
                    raise ValidationError(response_data.text)
            except Exception as e:
                raise ValidationError(e)

    def purolator_cancel_shipment(self, picking):
        """This Method Used For Cancel The Shipment"""

        cancel_request = etree.Element("soapenv:Envelope")
        cancel_request.attrib['xmlns:soapenv'] = "http://schemas.xmlsoap.org/soap/envelope/"
        cancel_request.attrib['xmlns:v2'] = "http://purolator.com/pws/datatypes/v2"

        header_node = etree.SubElement(cancel_request, "soapenv:Header")

        request_context_node = etree.SubElement(header_node, "v2:RequestContext")
        etree.SubElement(request_context_node, "v2:Version").text = "2.2"
        etree.SubElement(request_context_node, "v2:Language").text = "en"
        etree.SubElement(request_context_node, "v2:GroupID").text = "123"
        etree.SubElement(request_context_node, "v2:RequestReference").text = "Cancel Request"

        body_node = etree.SubElement(cancel_request, "soapenv:Body")

        void_shipment_request_node = etree.SubElement(body_node, "v2:VoidShipmentRequest")
        pin_node = etree.SubElement(void_shipment_request_node, "v2:PIN")

        etree.SubElement(pin_node, 'v2:Value').text = picking.carrier_tracking_ref

        try:
            headers = {
                'Content-Type': "text/xml;  charset=utf-8",
                'SOAPAction': "http://purolator.com/pws/service/v2/VoidShipment"
            }
            username = self.company_id.purolator_username
            password = self.company_id.purolator_password
            url = "{0}/v2/Shipping/ShippingService.asmx".format(
                self.company_id and self.company_id.purolator_api_url)
            _logger.info("Request Data Of Cancel::::%s" % etree.tostring(cancel_request))
            response_data = requests.request(method="POST", url=url, headers=headers,
                                             auth=HTTPBasicAuth(username=username, password=password),
                                             data=etree.tostring(cancel_request))
            _logger.info("Response Data Of Cancel::::%s" % response_data.content)
            if response_data.status_code in [200, 201]:
                api = Response(response_data)
                response_data = api.dict()
                _logger.info(response_data)
                common_response = response_data.get('Envelope').get('Body').get('VoidShipmentResponse')
                if common_response.get('ShipmentVoided') == 'true':
                    return True
                else:
                    raise ValidationError(common_response.get('ResponseInformation').get('Errors'))
        except Exception as e:
            raise ValidationError(e)

    def purolator_get_tracking_link(self, pickings):
        """This Method is used for tracking parcel"""
        return "https://www.purolator.com/en/shipping/tracker?pins={}".format(pickings.purolator_piece_pin)

    def purolator_get_label_using_shipment_pin(self, picking, purolator_shipment_pin):

        root_element = etree.Element("SOAP-ENV:Envelope")
        root_element.attrib["xmlns:SOAP-ENV"] = "http://schemas.xmlsoap.org/soap/envelope/"
        root_element.attrib["xmlns:ns1"] = "http://purolator.com/pws/datatypes/v1"
        root_header = etree.SubElement(root_element, "SOAP-ENV:Header")
        request_context = etree.SubElement(root_header, "ns1:RequestContext")
        etree.SubElement(request_context, "ns1:Version").text = "1.3"
        etree.SubElement(request_context, "ns1:Language").text = "en"
        etree.SubElement(request_context, "ns1:GroupID").text = "123"
        etree.SubElement(request_context, "ns1:RequestReference").text = "Get Label Request"

        root_body = etree.SubElement(root_element, "SOAP-ENV:Body")
        root_get_document_request = etree.SubElement(root_body, "ns1:GetDocumentsRequest")
        root_document_criterium = etree.SubElement(root_get_document_request, "ns1:DocumentCriterium")
        # if isinstance(purolator_shipment_pin, dict):
        #     purolator_shipment_pin = [purolator_shipment_pin]
        # for piece_pin in purolator_shipment_pin:
        root_document_criteria = etree.SubElement(root_document_criterium, "ns1:DocumentCriteria")
        root_pin = etree.SubElement(root_document_criteria, "ns1:PIN")
        etree.SubElement(root_pin, "ns1:Value").text = purolator_shipment_pin

        try:
            headers = {
                'Content-Type': "text/xml;  charset=utf-8",
                'SOAPAction': "http://purolator.com/pws/service/v1/GetDocuments"
            }
            username = self.company_id.purolator_username
            password = self.company_id.purolator_password
            url = "{0}/v1/ShippingDocuments/ShippingDocumentsService.asmx".format(
                self.company_id and self.company_id.purolator_api_url)
            _logger.info("Request Data Of label::::%s" % etree.tostring(root_element))
            response_data = requests.request(method="POST", url=url, headers=headers,
                                             auth=HTTPBasicAuth(username=username, password=password),
                                             data=etree.tostring(root_element))
            _logger.info("Response Data Of label::::%s" % response_data.content)
            if response_data.status_code in [200, 201]:
                api = Response(response_data)
                response_data = api.dict()
                return response_data
        except Exception as e:
            raise Warning(e)
