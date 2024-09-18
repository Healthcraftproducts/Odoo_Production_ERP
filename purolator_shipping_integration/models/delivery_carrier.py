import logging
import requests
import binascii
import xml.etree.ElementTree as etree
from odoo import models, fields, api, _
from odoo.exceptions import Warning, ValidationError, UserError
from odoo.addons.purolator_shipping_integration.models.purolator_response import Response
import hashlib
from requests.auth import HTTPBasicAuth

import base64
import uuid

_logger = logging.getLogger("Purolator")


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(selection_add=[("purolator", "Purolator")],
                                     ondelete={'purolator': 'set default'})
    purolator_package_type = fields.Selection([("ExpressEnvelope", "ExpressEnvelope"),
                                               ("ExpressPack", "ExpressPack"),
                                               ("CustomerPackaging", "CustomerPackaging"),
                                               ("ExpressBox", "ExpressBox")])
    weight_unit = fields.Selection([("lb", "lb - pounds"),
                                    ("kg", "kg - kilogram")])

    def purolator_rate_shipment(self, orders):
        "This Method Is Used For Get Rate"

        sender_address = orders.warehouse_id and orders.warehouse_id.partner_id
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
        etree.SubElement(root_getquickestimateRequest,
                         "v2:BillingAccountNumber").text = self.company_id and self.company_id.purolator_account_number
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

        print(etree.tostring(root_element))

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
            _logger.info("Response Data Of Rate%s" % response_data.content)
            if response_data.status_code in [200, 201]:
                api = Response(response_data)
                response_data = api.dict()
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
            shipper_address = picking.picking_type_id.warehouse_id.partner_id
            total_bulk_weight = picking.weight_bulk

            if not shipper_address.zip or not shipper_address.city or not shipper_address.country_id:
                raise ValidationError("Please define  proper sender addres")

            # check Receiver Address
            if not recipient_address.zip or not recipient_address.city or not recipient_address.country_id:
                raise ValidationError("Please define  proper receiver address")

            root_element = etree.Element("soapenv:Envelope")
            root_element.attrib['xmlns:soapenv'] = "http://schemas.xmlsoap.org/soap/envelope/"
            root_element.attrib['xmlns:v2'] = "http://purolator.com/pws/datatypes/v2"

            root_header = etree.SubElement(root_element, "soapenv:Header")
            request_context = etree.SubElement(root_header, "v2:RequestContext")
            etree.SubElement(request_context, "v2:Version").text = "2.2"
            etree.SubElement(request_context, "v2:Language").text = "en"
            etree.SubElement(request_context, "v2:GroupID").text = "1"
            etree.SubElement(request_context, "v2:RequestReference").text = "Shipping Request123"
            # etree.SubElement(request_context, "v2:UserToken").text = "b4a9f14b1dfd4315902eef4e0c4da56a"

            root_body = etree.SubElement(root_element, "soapenv:Body")
            root_createshipment = etree.SubElement(root_body, "v2:CreateShipmentRequest")
            root_shipment = etree.SubElement(root_createshipment, "v2:Shipment")
            root_senderinformation = etree.SubElement(root_shipment, "v2:SenderInformation")
            root_address = etree.SubElement(root_senderinformation, "v2:Address")

            etree.SubElement(root_address, "v2:Name").text = shipper_address.name or ''
            etree.SubElement(root_address, "v2:StreetNumber").text = shipper_address.street2 or ''
            etree.SubElement(root_address, "v2:StreetName").text = shipper_address.street or ''
            etree.SubElement(root_address, "v2:City").text = shipper_address.city or ''
            etree.SubElement(root_address,
                             "v2:Province").text = shipper_address.state_id and shipper_address.state_id.code
            etree.SubElement(root_address,
                             "v2:Country").text = shipper_address.country_id and shipper_address.country_id.code
            etree.SubElement(root_address, "v2:PostalCode").text = shipper_address.zip or ''

            root_phonenumber = etree.SubElement(root_address, "v2:PhoneNumber")
            etree.SubElement(root_phonenumber, "v2:CountryCode").text = "1"
            etree.SubElement(root_phonenumber, "v2:AreaCode").text = "905"
            etree.SubElement(root_phonenumber, "v2:Phone").text = "5555555"

            root_receiverinformation = etree.SubElement(root_shipment, "v2:ReceiverInformation")
            root_recaddress = etree.SubElement(root_receiverinformation, "v2:Address")

            etree.SubElement(root_recaddress, "v2:Name").text = recipient_address.name or ''
            etree.SubElement(root_recaddress, "v2:StreetNumber").text = recipient_address.street2 or ''
            etree.SubElement(root_recaddress, "v2:StreetName").text = recipient_address.street or ''
            etree.SubElement(root_recaddress, "v2:City").text = recipient_address.city or ''
            etree.SubElement(root_recaddress,
                             "v2:Province").text = recipient_address.state_id and recipient_address.state_id.code or ''
            etree.SubElement(root_recaddress,
                             "v2:Country").text = recipient_address.country_id and recipient_address.country_id.code or ''
            etree.SubElement(root_recaddress, "v2:PostalCode").text = recipient_address.zip or ''

            root_recphonenumber = etree.SubElement(root_recaddress, "v2:PhoneNumber")
            etree.SubElement(root_recphonenumber, "v2:CountryCode").text = "1"
            etree.SubElement(root_recphonenumber, "v2:AreaCode").text = "604"
            etree.SubElement(root_recphonenumber, "v2:Phone").text = "2982181"

            etree.SubElement(root_shipment, "v2:ShipmentDate").text = picking.scheduled_date.strftime("%Y-%m-%d")

            root_package_information = etree.SubElement(root_shipment, "v2:PackageInformation")
            etree.SubElement(root_package_information,
                             "v2:ServiceID").text = picking.sale_id and picking.sale_id.purolator_shipping_charge_id and picking.sale_id.purolator_shipping_charge_id.purolator_service_id or ''
            root_total_weight = etree.SubElement(root_package_information, "v2:TotalWeight")
            etree.SubElement(root_total_weight, "v2:Value").text = str(picking.shipping_weight) or ''
            etree.SubElement(root_total_weight, "v2:WeightUnit").text = self.weight_unit or ''

            etree.SubElement(root_package_information, "v2:TotalPieces").text = "1"

            root_payment_information = etree.SubElement(root_shipment, "v2:PaymentInformation")
            etree.SubElement(root_payment_information, "v2:PaymentType").text = "Sender"
            etree.SubElement(root_payment_information, "v2:RegisteredAccountNumber").text = "9999999999"
            etree.SubElement(root_payment_information, "v2:BillingAccountNumber").text = "9999999999"

            root_pickup_information = etree.SubElement(root_shipment, "v2:PickupInformation")
            etree.SubElement(root_pickup_information, "v2:PickupType").text = "DropOff"

            root_notification_information = etree.SubElement(root_shipment, "v2:NotificationInformation")
            etree.SubElement(root_notification_information, "v2:ConfirmationEmailAddress").text = "abc@abc.com"

            etree.SubElement(root_createshipment, "v2:PrinterType").text = "Regular"
            request_data = etree.tostring(root_element)
            _logger.info("=====>Request data of shipment%s" % request_data)

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
                _logger.info("Response Data Of Rate%s" % response_data.content)
                if response_data.status_code in [200, 201]:
                    api = Response(response_data)
                    response_data = api.dict()
                    common_response_data = response_data.get('Envelope').get('Body').get('CreateShipmentResponse')
                    check_errors = common_response_data.get('ResponseInformation').get('Errors')
                    if check_errors:
                        raise ValidationError(check_errors)
                    purolator_shipment_pin = common_response_data.get('ShipmentPIN').get('Value')
                    label_response_data = self.purolator_get_label_using_shipment_pin(picking, purolator_shipment_pin)
                    picking.carrier_tracking_ref = purolator_shipment_pin

                    pdf_label_url = label_response_data.get('Envelope') and label_response_data.get('Envelope').get(
                        'Body') and label_response_data.get('Envelope').get('Body').get(
                        'GetDocumentsResponse') and label_response_data.get('Envelope').get('Body').get(
                        'GetDocumentsResponse').get('Documents') and label_response_data.get('Envelope').get(
                        'Body').get('GetDocumentsResponse').get('Documents').get(
                        'Document') and label_response_data.get('Envelope').get('Body').get('GetDocumentsResponse').get(
                        'Documents').get('Document').get('DocumentDetails').get('DocumentDetail').get('URL')

                    headers = {'Content-Type': "application/x-www-form-urlencoded", 'Accept': "application/pdf"}
                    pdf_response = requests.request("GET", url=pdf_label_url, headers=headers)
                    logmessage = ("<b>Tracking Numbers:</b> %s") % (purolator_shipment_pin)
                    pickings.message_post(body=logmessage,
                                          attachments=[
                                              ("%s.pdf" % (purolator_shipment_pin), pdf_response.content)])
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
        _logger.info("Cancel request data %s" % etree.tostring(cancel_request))
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
            _logger.info("Response Data Of Rate%s" % response_data.content)
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
        return "https://www.purolator.com/en/shipping/tracker?pins={}".format(pickings.purolator_shipment_pin)

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
        root_document_criteria = etree.SubElement(root_document_criterium, "ns1:DocumentCriteria")
        root_pin = etree.SubElement(root_document_criteria, "ns1:PIN")
        etree.SubElement(root_pin, "ns1:Value").text = purolator_shipment_pin
        _logger.info(etree.tostring(root_element))

        try:
            headers = {
                'Content-Type': "text/xml;  charset=utf-8",
                'SOAPAction': "http://purolator.com/pws/service/v1/GetDocuments"
            }
            username = self.company_id.purolator_username
            password = self.company_id.purolator_password
            url = "{0}/v1/ShippingDocuments/ShippingDocumentsService.asmx".format(
                self.company_id and self.company_id.purolator_api_url)
            _logger.info("Request Data Of Rate::::%s" % etree.tostring(root_element))
            response_data = requests.request(method="POST", url=url, headers=headers,
                                             auth=HTTPBasicAuth(username=username, password=password),
                                             data=etree.tostring(root_element))
            _logger.info("Response Data Of Rate%s" % response_data.content)
            if response_data.status_code in [200, 201]:
                api = Response(response_data)
                response_data = api.dict()
                return response_data
        except Exception as e:
            raise Warning(e)
