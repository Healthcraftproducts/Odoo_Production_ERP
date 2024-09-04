import requests
import binascii
import json
import logging
from datetime import datetime
from odoo.exceptions import Warning, ValidationError
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(selection_add=[('fedex_shipping_provider', 'Fedex')],
                                     ondelete={'fedex_shipping_provider': 'set default'})
    fedex_request_type = fields.Selection([('LIST', 'LIST'),
                                           ('INCENTIVE', 'INCENTIVE'),
                                           ('ACCOUNT', 'ACCOUNT'),
                                           ('PREFERRED', 'PREFERRED')],
                                          string="FedEx Request Type",
                                          default='ACCOUNT',
                                          help="LIST - Returns FedEx published list rates in addition to account-specific rates (if applicable). PREFERRED - Returns rates in the preferred currency specified in the element preferredCurrency. ACCOUNT - Returns account specific rates (Default). INCENTIVE - This is one-time discount for incentivising the customer. For more information, contact your FedEx representative.")
    fedex_weight_uom = fields.Selection([('LB', 'LB'),
                                         ('KG', 'KG')], default='LB', string="Weight UoM",
                                        help="Weight UoM of the Shipment")

    fedex_service_type = fields.Selection(
        [('FEDEX_2_DAY', 'Fedex 2 Day'),  # for US Use: 33122 Florida Doral
         ('FEDEX_2_DAY_AM', 'Fedex 2 Day AM'),  # for US Use: 33122 Florida Doral
         ('FEDEX_INTERNATIONAL_PRIORITY_EXPRESS', 'FEDEX_INTERNATIONAL_PRIORITY_EXPRESS'),
         # ('FEDEX_INTERNATIONAL_PRIORITY', 'FEDEX_INTERNATIONAL_PRIORITY'),
         # ('FEDEX_CUSTOM_CRITICAL_CHARTER_AIR', 'FedEx Custom Critical Air'),
         # ('FEDEX_CUSTOM_CRITICAL_AIR_EXPEDITE', 'FedEx Custom Critical Air Expedite'),
         # ('FEDEX_CUSTOM_CRITICAL_AIR_EXPEDITE_EXCLUSIVE_USE', 'FedEx Custom Critical Air Expedite Exclusive Use'),
         # ('FEDEX_CUSTOM_CRITICAL_AIR_EXPEDITE_NETWORK', 'FedEx Custom Critical Air Expedite Network'),
         # ('FEDEX_CUSTOM_CRITICAL_POINT_TO_POINT', 'FedEx Custom Critical Point To Point'),
         # ('FEDEX_CUSTOM_CRITICAL_SURFACE_EXPEDITE', 'FedEx Custom Critical Surface Expedite'),
         # ('FEDEX_CUSTOM_CRITICAL_SURFACE_EXPEDITE_EXCLUSIVE_USE',
         #  'FedEx Custom Critical Surface Expedite Exclusive Use'),
         ('FEDEX_EXPRESS_SAVER', 'Fedex Express Saver'),  # for US Use: 33122 Florida Doral
         ('FIRST_OVERNIGHT', 'First Overnight'),  # for US
         ('FEDEX_FIRST_OVERNIGHT_EXTRA_HOURS', 'FedEx First Overnight® EH'),
         ('FEDEX_GROUND', 'Fedex Ground'),  # When Call the service given the error "Customer not eligible for service"
         ('GROUND_HOME_DELIVERY', 'Ground Home Delivery'),
         # ('FEDEX_CARGO_AIRPORT_TO_AIRPORT', 'FedEx International Airport-to-Airport'),
         ('FEDEX_INTERNATIONAL_CONNECT_PLUS', 'FedEx International Connect Plus®'),
         ('INTERNATIONAL_ECONOMY', 'International Economy'),
         # ('INTERNATIONAL_ECONOMY_DISTRIBUTION', 'FedEx International Economy DirectDistributionSM'),
         ('INTERNATIONAL_FIRST', 'International First'),
         # ('FEDEX_CARGO_MAIL', 'FedEx International MailService®'),
         # ('FEDEX_CARGO_INTERNATIONAL_PREMIUM', 'FedEx International Premium™'),
         # ('INTERNATIONAL_PRIORITY_DISTRIBUTION', 'FedEx International Priority DirectDistribution®'),
         ('FEDEX_INTERNATIONAL_PRIORITY', 'FedEx International Priority® (New IP Service)'),
         ('FEDEX_INTERNATIONAL_PRIORITY_PLUS', 'FedEx International Priority Plus®'),
         ('PRIORITY_OVERNIGHT', 'Priority Overnight'),  # for US
         # ('PRIORITY_OVERNIGHT_EXTRA_HOURS', 'FedEx Priority Overnight® EH'),
         ('SAME_DAY', 'FedEx SameDay®'),
         ('SAME_DAY_CITY', 'FedEx SameDay® City'),
         ('SMART_POST', 'Smart Post'),  # When Call the service given the error "Customer not eligible for service"
         ('FEDEX_STANDARD_OVERNIGHT_EXTRA_HOURS', 'FedEx Standard Overnight® EH'),  # WORKING FOR us ADDRESS
         ('STANDARD_OVERNIGHT', 'Standard Overnight'),  # for US Use: 33122 Florida Doral
         ('TRANSBORDER_DISTRIBUTION_CONSOLIDATION', 'Temp-Assure Air®'),
         # ('FEDEX_CUSTOM_CRITICAL_TEMP_ASSURE_VALIDATED_AIR', 'Temp-Assure Validated Air®'),
         # ('FEDEX_CUSTOM_CRITICAL_WHITE_GLOVE_SERVICES', 'White Glove Services®'),
         ('FEDEX_REGIONAL_ECONOMY', 'FEDEX_REGIONAL_ECONOMY'),
         ('FEDEX_REGIONAL_ECONOMY_FREIGHT', 'FEDEX_REGIONAL_ECONOMY_FREIGHT'),
         ('INTERNATIONAL_PRIORITY', 'International Priority'),
         ('EUROPE_FIRST_INTERNATIONAL_PRIORITY', 'Europe First International Priority'),
         ('FEDEX_DISTANCE_DEFERRED', 'Fedex Distance Deferred'),
         # for domestic UK pickup  Error : Customer is eligible.
         ('FEDEX_NEXT_DAY_AFTERNOON', 'Fedex Next Day Afternoon'),  # for domestic UK pickup
         ('FEDEX_NEXT_DAY_EARLY_MORNING', 'Fedex Next Day Early Morning'),  # for domestic UK pickup
         ('FEDEX_NEXT_DAY_END_OF_DAY', 'Fedex Next Day End of Day'),  # for domestic UK pickup
         ('FEDEX_NEXT_DAY_FREIGHT', 'Fedex Next Day Freight'),  # for domestic UK pickup
         ('FEDEX_NEXT_DAY_MID_MORNING', 'Fedex Next Day Mid Morning'),  # for domestic UK pickup
         ], string="Service Type", help="Shipping Services those are accepted by Fedex")
    fedex_default_product_packaging_id = fields.Many2one('stock.package.type', string="Default Package Type")
    fedex_pickup_type = fields.Selection([('CONTACT_FEDEX_TO_SCHEDULE', 'CONTACT_FEDEX_TO_SCHEDULE'),
                                          ('DROPOFF_AT_FEDEX_LOCATION', 'DROPOFF_AT_FEDEX_LOCATION'),
                                          ('USE_SCHEDULED_PICKUP', 'USE_SCHEDULED_PICKUP')],
                                         string="Pickup Type",
                                         default='USE_SCHEDULED_PICKUP',
                                         help="Identifies the method by which the package is to be tendered to FedEx.")
    fedex_shipping_label_stock_type = fields.Selection([
        # These values display a thermal format label
        ('PAPER_4X6', 'Paper 4X6 '),
        ('PAPER_4X8', 'Paper 4X8'),
        ('PAPER_4X9', 'Paper 4X9'),
        ('PAPER_4X675', 'PAPER_4X675'),
        ('PAPER_7X47', 'PAPER_7X47'),
        ('PAPER_85X11_BOTTOM_HALF_LABEL', 'PAPER_85X11_BOTTOM_HALF_LABEL'),
        ('PAPER_85X11_TOP_HALF_LABEL', 'PAPER_85X11_TOP_HALF_LABEL'),
        ('PAPER_LETTER', 'PAPER_LETTER'), ('STOCK_4X6', 'STOCK_4X6'),
        ('STOCK_4X675_LEADING_DOC_TAB', 'STOCK_4X675_LEADING_DOC_TAB'),
        ('STOCK_4X675_TRAILING_DOC_TAB', 'STOCK_4X675_TRAILING_DOC_TAB'),
        ('STOCK_4X8', 'STOCK_4X8'),
        ('STOCK_4X9', 'STOCK_4X9'),
        ('STOCK_4X9_LEADING_DOC_TAB', 'STOCK_4X9_LEADING_DOC_TAB'),
        ('STOCK_4X9_TRAILING_DOC_TAB', 'STOCK_4X9_TRAILING_DOC_TAB'),
        ('STOCK_4X85_TRAILING_DOC_TAB', 'STOCK_4X85_TRAILING_DOC_TAB'),
        ('STOCK_4X105_TRAILING_DOC_TAB', 'STOCK_4X105_TRAILING_DOC_TAB')], string="Label Stock Type",
        help="1)Specifies the type of paper on which a document will be printed.2)For ZPL you can only use STOCK")
    fedex_shipping_label_file_type = fields.Selection([('PDF', 'PDF'),
                                                       ('PNG', 'PNG'), ('ZPLII', 'ZPLII')], string="Label File Type")

    fedex_droppoff_type = fields.Selection([('BUSINESS_SERVICE_CENTER', 'Business Service Center'),
                                            ('DROP_BOX', 'Drop Box'),
                                            ('REGULAR_PICKUP', 'Regular Pickup'),
                                            ('REQUEST_COURIER', 'Request Courier'),
                                            ('STATION', 'Station')],
                                           string="Drop-off Type",
                                           default='REGULAR_PICKUP',
                                           help="Identifies the method by which the package is to be tendered to FedEx.")
    fedex_collection_type = fields.Selection([('ANY', 'ANY'),
                                              ('CASH', 'CASH'),
                                              ('COMPANY_CHECK', 'COMPANY_CHECK'),
                                              ('GUARANTEED_FUNDS', 'GUARANTEED_FUNDS'),
                                              ('PERSONAL_CHECK', 'PERSONAL_CHECK'),
                                              ], default='ANY', string="FedEx Collection Type",
                                             help="FedEx Collection Type")
    fedex_payment_type = fields.Selection([('SENDER', 'SENDER'),
                                           ('RECIPIENT', 'RECIPIENT'),
                                           ('THIRD_PARTY', 'THIRD_PARTY')], default='SENDER',
                                          string="FedEx Payment Type",
                                          help="FedEx Payment Type")
    fedex_onerate = fields.Boolean("Want To Use FedEx OneRate Service?", default=False)
    is_cod = fields.Boolean('COD')
    is_signature_required = fields.Boolean(string="Signature")
    signature_options = fields.Selection([('INDIRECT', 'INDIRECT'),
                                          ('DIRECT', 'DIRECT'),
                                          ('ADULT', 'ADULT')], string="Signature Options")
    insured_request = fields.Boolean(string="Insured Request",
                                     help="Use this Insured Request required.",
                                     default=False)
    fedex_hub_id = fields.Selection([('5015', 'NOMA Northborough - 5015'),
                                     ('5061', 'WICT Windsor - 5061'),
                                     ('5087', 'EDNJ Edison - 5087'),
                                     ('5095', 'NENJ Newark - 5095'),
                                     ('5097', 'SBNJ South Brunswick - 5097'),
                                     ('5110', 'NENY Newburgho - 5110'),
                                     ('5150', 'PTPA Pittsburgh - 5150'),
                                     ('5183', 'MAPA Macungie - 5183'),
                                     ('5185', 'ALPA Allentown - 5185'),
                                     ('5186', 'SCPA Scranton - 5186'),
                                     ('5194', 'PHPA Philadelphia - 5194'),
                                     ('5213', 'BAMD Baltimore - 5213'),
                                     ('5254', 'MAWV Martinsburg - 5254'),
                                     ('5281', 'CHNC Charlotte - 5281'),
                                     ('5303', 'ATGA Atlanta - 5303'),
                                     ('5327', 'ORFL Orlando - 5327'),
                                     ('5345', 'TAFL Tampa - 5345'),
                                     ('5379', 'METN Memphis - 5379'),
                                     ('5431', 'GCOH Grove City - 5431'),
                                     ('5436', 'GPOH Groveport Ohio - 5436'),
                                     ('5465', 'ININ Indianapolis - 5465'),
                                     ('5481', 'DTMI Detroit - 5481'),
                                     ('5531', 'NBWI New Berlin - 5531'),
                                     ('5552', 'MPMN Minneapolis - 5552'),
                                     ('5602', 'WHIL Wheeling - 5602'),
                                     ('5631', 'STMO St. Louis - 5631'),
                                     ('5648', 'KCKS Kansas City - 5648'),
                                     ('5751', 'DLTX Dallas - 5751'),
                                     ('5771', 'HOTX Houston - 5771'),
                                     ('5802', 'DNCO Denver - 5802'),
                                     ('5843', 'SCUT Salt Lake City - 5843'),
                                     ('5854', 'PHAZ Phoenix - 5854'),
                                     ('5893', 'RENV Reno - 5893'),
                                     ('5902', 'LACA Los Angeles - 5902'),
                                     ('5929', 'COCA Chino - 5929'),
                                     ('5958', 'SACA Sacramento - 5958'),
                                     ('5983', 'SEWA Seattle - 5983')],string="Fedex Hub ID")
    fedex_indicia = fields.Selection([('MEDIA_MAIL', 'MEDIA_MAIL'),
                                      ('PARCEL_SELECT', 'PARCEL_SELECT'),
                                      ('PRESORTED_BOUND_PRINTED_MATTER', 'PRESORTED_BOUND_PRINTED_MATTER'),
                                      ('PRESORTED_STANDARD', 'PRESORTED_STANDARD')],string="Fedex Indicia")

    def get_fedex_address_dict(self, address_id):
        return {
            "address": {
                "city": address_id.city or "",
                "stateOrProvinceCode": address_id.state_id and address_id.state_id.code or "",
                "postalCode": "{0}".format(address_id.zip or ""),
                "countryCode": address_id.country_id and address_id.country_id.code or "",
                "residential": "true" if self.fedex_service_type in ['GROUND_HOME_DELIVERY','SMART_POST'] else "false"
            }
        }

    def fedex_shipping_provider_rate_shipment(self, order):
        order_lines_without_weight = order.order_line.filtered(
            lambda line_item: not line_item.product_id.type in ['service',
                                                                'digital'] and not line_item.product_id.weight and not line_item.is_delivery)
        for order_line in order_lines_without_weight:
            raise ValidationError("Please define weight in product : \n %s" % (order_line.product_id.name))

        # Shipper and Recipient Address
        shipper_address_id = order.warehouse_id.partner_id
        recipient_address_id = order.partner_shipping_id
        company_id = self.company_id

        # check sender Address
        if not shipper_address_id.zip or not shipper_address_id.city or not shipper_address_id.country_id:
            raise ValidationError("Please Define Proper Sender Address!")

        # check Receiver Address
        if not recipient_address_id.zip or not recipient_address_id.city or not recipient_address_id.country_id:
            raise ValidationError("Please Define Proper Recipient Address!")

        total_weight = sum([(line.product_id.weight * line.product_uom_qty) for line in order.order_line]) or 0.0
        if not company_id.fedex_access_token:
            raise ValidationError("Please enter correct credentials data!")
        try:
            api_url = "{0}/rate/v1/rates/quotes".format(company_id.fedex_api_url)
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': 'Bearer {0}'.format(company_id.fedex_access_token)
            }
            request_data = {
                "accountNumber": {"value": "{0}".format(company_id.fedex_account_number)},
                "requestedShipment": {
                    "shipper": self.get_fedex_address_dict(shipper_address_id),
                    "recipient": self.get_fedex_address_dict(recipient_address_id),
                    "pickupType": self.fedex_pickup_type,
                    "serviceType": self.fedex_service_type,
                    "packagingType": self.fedex_default_product_packaging_id.shipper_package_code,
                    "rateRequestType": ["{0}".format(self.fedex_request_type)],
                    "shipDateStamp": datetime.now().strftime('%Y-%m-%d'),
                    "totalWeight": ((total_weight) or 0),
                    "requestedPackageLineItems": [
                        {
                            "weight": {
                                "units": "{0}".format(self.fedex_weight_uom),
                                "value": (total_weight)
                            },"dimensions": {
                            "length": self.fedex_default_product_packaging_id.packaging_length or '',
                            "width": self.fedex_default_product_packaging_id.width or '',
                            "height": self.fedex_default_product_packaging_id.height or '',
                            "units": 'IN' if self.fedex_weight_uom == 'LB' else 'CM'
                        }
                        }
                    ]
                }
            }
            if self.fedex_service_type == 'SMART_POST':
                request_data.get("requestedShipment").update({"smartPostInfoDetail": {
                    "indicia": self.fedex_indicia,
                    "hubId": self.fedex_hub_id
                }}),
            if self.fedex_onerate:
                request_data.get("requestedShipment").update(
                    {"shipmentSpecialServices": {"specialServiceTypes": ["FEDEX_ONE_RATE"]}})
            if self.is_cod:
                request_data.get("requestedShipment").update(
                    {"shipmentSpecialServices": {"specialServiceTypes": ["COD"],
                                                 "shipmentCODDetail": {
                                                     "codCollectionType": self.fedex_collection_type,
                                                     "codCollectionAmount": {
                                                         "amount": order.amount_total,
                                                         "currency": order.company_id.currency_id.name or "USD"
                                                     }}}})

            response_data = requests.request("POST", api_url, headers=headers, data=json.dumps(request_data))
            if response_data.status_code in [200, 201]:
                response_data = response_data.json()
                if response_data.get('output') and response_data.get('output').get('rateReplyDetails'):
                    for rateReplyDetail in response_data.get('output').get('rateReplyDetails'):
                        if self.fedex_service_type == rateReplyDetail.get("serviceType"):
                            for rate_info in rateReplyDetail.get('ratedShipmentDetails'):
                                return {'success': True, 'price': float(rate_info.get('totalNetFedExCharge')) or 0.0,
                                        'error_message': False, 'warning_message': False}
                else:
                    return {'success': False, 'price': 0.0, 'error_message': response_data,
                            'warning_message': False}
            else:
                return {'success': False, 'price': 0.0, 'error_message': response_data.text,
                        'warning_message': False}
        except Exception as e:
            return {'success': False, 'price': 0.0, 'error_message': e, 'warning_message': False}

    def get_fedex_shipp_address_dict(self, address_id):
        address_dict = self.get_fedex_address_dict(address_id)
        address_dict.update({"contact": {"personName": "",
                                         "emailAddress": address_id.email or "",
                                         "phoneNumber": "%s" % (address_id.phone or ""),
                                         "companyName": address_id.name}})
        address_dict.get("address").update({"streetLines": [address_id.street]})
        return address_dict

    def manage_fedex_packages(self, package_count=False, shipping_weight=False, packaging_length=False, width=False,
                              height=False, package_desscription=False):
        return {
            "sequenceNumber": "%s" % (package_count),
            "weight": {
                "units": "{0}".format(self.fedex_weight_uom),
                "value": shipping_weight
            },
            "dimensions": {
                "length": packaging_length or "",
                "width": width or "",
                "height": height or "",
                "units": 'IN' if self.fedex_weight_uom == 'LB' else 'CM'
            },
            "groupPackageCount": 1,
            "itemDescription": "%s" % (package_desscription),
        }

    def fedex_shipping_provider_send_shipping(self, pickings):
        shipper_address_id = pickings.picking_type_id and pickings.picking_type_id.warehouse_id and pickings.picking_type_id.warehouse_id.partner_id
        receiver_id = pickings.partner_id
        company_id = self.company_id
        package_list = []
        package_count = 0
        total_bulk_weight = pickings.weight_bulk
        for package_id in pickings.package_ids:
            package_count = package_count + 1
            length = package_id.package_type_id.packaging_length if package_id.package_type_id.packaging_length else self.fedex_default_product_packaging_id.packaging_length or ""
            width = package_id.package_type_id.width if package_id.package_type_id.width else self.fedex_default_product_packaging_id.width or ""
            height = package_id.package_type_id.height if package_id.package_type_id.height else self.fedex_default_product_packaging_id.height or ""
            package_list.append(
                self.manage_fedex_packages(package_count, package_id.shipping_weight, length, width, height,
                                           package_id.name))
            if self.is_signature_required:
                package_list[-1].update({"packageSpecialServices": {
                    "specialServiceTypes": [
                        "SIGNATURE_OPTION"
                    ],
                    "signatureOptionType": self.signature_options or ''
                }})
        if total_bulk_weight:
            package_count = package_count + 1
            length = self.fedex_default_product_packaging_id.packaging_length or ""
            width = self.fedex_default_product_packaging_id.width or ""
            height = self.fedex_default_product_packaging_id.height or ""
            package_list.append(
                self.manage_fedex_packages(package_count, total_bulk_weight, length, width, height, pickings.name))
            if self.is_signature_required:
                package_list[-1].update({"packageSpecialServices": {
                    "specialServiceTypes": [
                        "SIGNATURE_OPTION"
                    ],
                    "signatureOptionType": self.signature_options or ''
                }})

        try:
            order = pickings.sale_id
            request_data = {
                "mergeLabelDocOption": "LABELS_AND_DOCS",
                "labelResponseOptions": "LABEL",
                "accountNumber": {"value": "{0}".format(company_id.fedex_account_number)},
                "shipAction": "CONFIRM",
                "requestedShipment": {
                    "shipper": self.get_fedex_shipp_address_dict(shipper_address_id),
                    "recipients": [self.get_fedex_shipp_address_dict(receiver_id)],
                    "pickupType": self.fedex_pickup_type,
                    "serviceType": self.fedex_service_type,
                    "packagingType": self.fedex_default_product_packaging_id.shipper_package_code,
                    "totalWeight": pickings.shipping_weight,
                    "shippingChargesPayment": {
                        "paymentType": self.fedex_payment_type},
                    "labelSpecification": {
                        "labelFormatType": "COMMON2D",
                        "labelOrder": "SHIPPING_LABEL_FIRST",
                        "labelStockType": self.fedex_shipping_label_stock_type,
                        "imageType": self.fedex_shipping_label_file_type
                    },
                    # Insurance And Declared Value

                    "rateRequestType": ["{0}".format(self.fedex_request_type)],
                    "preferredCurrency": pickings.sale_id.company_id.currency_id.name,
                    "totalPackageCount": package_count,
                    "requestedPackageLineItems": package_list
                }}
            # Insurance And Declared Value
            if self.insured_request:
                request_data.get("requestedShipment").update({"customsClearanceDetail": {
                    "commodities": [
                        {
                            "totalCustomsValue": {
                                "amount": order.tax_totals.get('amount_total'),
                                "currency": pickings.sale_id and pickings.sale_id.company_id.currency_id.name or "USD"
                            }
                        }
                    ],
                    "insuranceCharge": {
                        "amount": order.tax_totals.get('amount_total'),
                        "currency": pickings.sale_id and pickings.sale_id.company_id.currency_id.name or "USD"
                    }
                }, })
            if self.fedex_service_type == 'SMART_POST':
                request_data.get("requestedShipment").update({"smartPostInfoDetail": {
                    "hubId": self.fedex_hub_id,
                    "indicia": self.fedex_indicia
                }}),
            if self.fedex_payment_type != 'SENDER':
                request_data.get("requestedShipment").get('shippingChargesPayment').update(
                    {"payor": {"responsibleParty": {"accountNumber": {
                        "value": order.fedex_third_party_account_number_sale_order}}}})
            if self.fedex_onerate:
                request_data.get("requestedShipment").update(
                    {"shipmentSpecialServices": {"specialServiceTypes": ["FEDEX_ONE_RATE"]}})
            if self.is_cod:
                request_data.get("requestedShipment").update(
                    {"shipmentSpecialServices": {"specialServiceTypes": ["COD"],
                                                 "shipmentCODDetail": {
                                                     "codCollectionType": self.fedex_collection_type,
                                                     "codCollectionAmount": {
                                                         "amount": pickings.sale_id and pickings.sale_id.amount_total,
                                                         "currency": pickings.sale_id and pickings.sale_id.company_id.currency_id.name or "USD"
                                                     }}}})
            if shipper_address_id.country_id.code != receiver_id.country_id.code:
                comodities_packages = []

                for package_id in pickings.package_ids:
                    for stock_quant_package in package_id.quant_ids:
                        product_id = stock_quant_package.product_id
                        # move_line_id = self.env['stock.move.line'].search([('product_id', '=', product_id.id)])
                        find_sale_line_id = pickings.sale_id.order_line.filtered(
                            lambda x: x.product_template_id.product_variant_id == product_id)

                        comodities_packages.append({
                            "description": "%s" % (package_id.name),
                            "countryOfManufacture": self.company_id and self.company_id.country_id.code,
                            "quantity": stock_quant_package.quantity,
                            "quantityUnits": "PCS",
                            "unitPrice": {
                                "amount": find_sale_line_id.price_subtotal / find_sale_line_id.product_qty,
                                "currency": self.company_id and self.company_id.currency_id.name
                            },
                            "customsValue": {
                                "amount": find_sale_line_id.price_subtotal / find_sale_line_id.product_qty,
                                "currency": self.company_id and self.company_id.currency_id.name
                            },
                            "weight": {
                                "units": self.fedex_weight_uom,
                                "value": stock_quant_package.quantity * product_id.weight
                            }
                        })
                if total_bulk_weight:
                    for move_line in pickings.move_line_ids:
                        if move_line.product_id and not move_line.result_package_id:
                            product_id = move_line.product_id
                            # move_line_id = self.env['stock.move.line'].search([('product_id', '=', product_id.id)])
                            find_sale_line_id = pickings.sale_id.order_line.filtered(
                                lambda x: x.product_template_id.product_variant_id == product_id)
                            comodities_packages.append({
                                "description": "%s" % (pickings.name),
                                "countryOfManufacture": self.company_id and self.company_id.country_id.code,
                                "quantity": move_line.qty_done,
                                "quantityUnits": "PCS",
                                "unitPrice": {
                                    "amount": find_sale_line_id.price_subtotal / find_sale_line_id.product_qty,
                                    "currency": self.company_id and self.company_id.currency_id.name
                                },
                                "customsValue": {
                                    "amount": find_sale_line_id.price_subtotal / find_sale_line_id.product_qty,
                                    "currency": self.company_id and self.company_id.currency_id.name
                                },
                                "weight": {
                                    "units": self.fedex_weight_uom,
                                    "value": move_line.qty_done * product_id.weight

                                }
                            })
                request_data.get("requestedShipment").update({"customsClearanceDetail": {
                    "dutiesPayment": {
                        "paymentType": "SENDER"
                    },
                    "isDocumentOnly": True,
                    "commodities": comodities_packages
                },
                    "shippingDocumentSpecification": {
                        "shippingDocumentTypes": [
                            "COMMERCIAL_INVOICE"
                        ],
                        "commercialInvoiceDetail": {
                            "documentFormat": {
                                "docType": "PDF",
                                "stockType": "PAPER_LETTER"
                            }
                        }
                    }
                })
            api_url = "{0}/ship/v1/shipments".format(company_id.fedex_api_url)
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': 'Bearer {0}'.format(company_id.fedex_access_token)
            }
            response_data = requests.request("POST", api_url, headers=headers, data=json.dumps(request_data))
            attachments = []
            exact_charge = 0.0
            if response_data.status_code in [200, 201]:
                response_data = response_data.json()
                _logger.info("Shipment Response Data %s" % response_data)
                if response_data.get('output') and response_data.get('output').get('transactionShipments'):
                    for transaction_shipment in response_data.get('output').get('transactionShipments'):
                        carrier_tracking_ref = transaction_shipment.get('masterTrackingNumber')
                        for piece_respone in transaction_shipment.get('pieceResponses'):
                            for package_document in piece_respone.get('packageDocuments'):
                                if package_document.get('contentType') == 'ACCEPTANCE_LABEL':
                                    label_type = 'Fedex_Return'
                                else:
                                    label_type = 'Fedex'
                                label_binary_data = binascii.a2b_base64(package_document.get('encodedLabel'))
                                attachments.append(
                                    ('%s.%s.%s' % (label_type,
                                                   piece_respone.get('packageSequenceNumber') or carrier_tracking_ref,
                                                   self.fedex_shipping_label_file_type),
                                     label_binary_data))
                                exact_charge += piece_respone.get('baseRateAmount')
                        if shipper_address_id.country_id.code != receiver_id.country_id.code:
                            commercial_label = binascii.a2b_base64(
                                response_data.get('output').get('transactionShipments')[0].get('shipmentDocuments')[
                                    0].get(
                                    'encodedLabel'))
                            if commercial_label:
                                attachments.append(
                                    ('commercial invoice -%s.%s' % (
                                        carrier_tracking_ref,
                                        self.fedex_shipping_label_file_type),
                                     commercial_label))
                        msg = (_('<b>Shipment created!</b><br/>'))
                        pickings.message_post(body=msg, attachments=attachments)
                        return [{'exact_price': exact_charge,
                                 'tracking_number': carrier_tracking_ref}]
                else:
                    raise ValidationError(response_data)
            else:
                raise ValidationError(response_data.text)
        except Exception as e:
            raise ValidationError(e)

    def fedex_shipping_provider_get_tracking_link(self, pickings):
        res = ""
        for picking in pickings:
            link = "https://www.fedex.com/apps/fedextrack/?action=track&trackingnumber="
            res = '%s %s' % (link, picking.carrier_tracking_ref)
        return res

    def fedex_shipping_provider_cancel_shipment(self, picking):
        try:
            request_data = {"accountNumber": {
                "value": self.company_id.fedex_account_number
            },
                "senderCountryCode": "US",
                "deletionControl": "DELETE_ALL_PACKAGES",
                "trackingNumber": "%s" % (picking.carrier_tracking_ref)
            }
            api_url = "{0}/ship/v1/shipments/cancel".format(self.company_id.fedex_api_url)
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': 'Bearer {0}'.format(self.company_id.fedex_access_token)
            }
            response_data = requests.request("PUT", api_url, headers=headers, data=json.dumps(request_data))
            if response_data.status_code in [200, 201]:
                response_data = response_data.json()
                if response_data.get('output') and response_data.get('output').get('cancelledShipment'):
                    return True
                else:
                    raise ValidationError(response_data)
            else:
                raise ValidationError(response_data.text)
        except Exception as e:
            raise ValidationError(e)