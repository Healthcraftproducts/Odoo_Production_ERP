# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.osv import expression
import requests, json
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
import logging
_logger = logging.getLogger(__name__)

class DeringerReport(models.TransientModel):
    _name = "deringer.report.download"
    _description = "Deringer Report Download"

    data = fields.Binary('Click to download file', required=True, attachment=False)
    filename = fields.Char('File Name', required=True,compute='_compute_mock_pdf_filename')

    @api.depends('data')
    def _compute_mock_pdf_filename(self):
        context = self._context
        deringer_res = self.env[context.get('active_model')].browse(int(context.get('active_id')))
        self.ensure_one()
        now = datetime.now()
        current_time = now.strftime("%d/%m/%Y %H:%M:%S")
        name = deringer_res.name +"-"+ str(current_time) + '.xml'
        self.filename = name

class FeePercentage(models.Model):
    _name = "fee.percentage"
    _description = "Fee Percentage"
    
    name = fields.Char('Fee Percentage')

class DeringerUom(models.Model):
    _name = "deringer.uom"
    _description = "Derinfer UOM"
    
    name = fields.Char('Deringer UOM')
     
class DeringerForm(models.Model):
    _name = "deringer.form"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Deringer Form"

    @api.model
    def _get_default_country(self):
        country = self.env['res.country'].search([('code', '=', 'CA')], limit=1)
        return country
    
    name = fields.Char('Name',readonly=True, required=True, copy=False, default='New')
    date = fields.Datetime(string='Create Date', required=True, index=True, copy=False, default=fields.Datetime.now)
    partner_id = fields.Many2one('res.partner','Deringer Contact')
    invoice_ids = fields.Many2many('account.move','account_move_deringer_rel','invoice_id','deringer_id','Invoices',domain=[("type","=","out_invoice")])
    state = fields.Selection([('draft','Draft'),('xml_created','XML Generated'),('sent_email','Sent Email'),('cancel','Cancelled')],'Status', readonly=True, copy=False, default='draft')
    #Fields Added Based On Deringer XML File
    fee_percentage = fields.Many2one('fee.percentage','Fee Percentage')
    arrival_date = fields.Date('Arrival Date',invisible=1)
    export_country_id = fields.Many2one('res.country','Country of Export',required=1,default=_get_default_country)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('deringer.form') or 'New'
        result = super(DeringerForm, self).create(vals)        
        return result

    @api.model
    def _get_shipment_details(self,source):
        res = {}
        shipping_obj = self.env['stock.picking'].search([('origin','=',source)])
        if not shipping_obj:
            raise UserError(_("There is no delivery line associated with the invoice!"))
        if shipping_obj:
            total_qty = 0
            moves_lines = self.env['stock.move.line'].search([('picking_id','=',shipping_obj[0].id)])
            for line in moves_lines:
                total_qty += line.qty_done
            res['total_qty'] = total_qty
            res['weight'] = shipping_obj[0].total_weight_for_shipping
            res['arrival_date'] = shipping_obj[0].date_done
        return res
    
    def print_report_xml(self):
        # self.write({'state': 'xml_created'})
        xml_data = ''
        for record in self.invoice_ids:
            company_name = record.company_id.name
            company_street = record.company_id.street or ""
            company_street2 = record.company_id.street2 or ""
            company_city = record.company_id.city or ""
            company_state_code = record.company_id.state_id.code or ""
            company_postal_code = record.company_id.zip or ""
            company_country_code =  record.company_id.country_id.code or ""
            company_phone = record.company_id.phone or ""
            company_mid = record.company_id.mid or ""
            company_irs = record.company_id.irs_number or ""
            billing_contact_name = record.partner_id.name or ""
            billing_contact_street = record.partner_id.street or ""
            billing_contact_street2 = record.partner_id.street2 or ""
            billing_contact_city = record.partner_id.city or ""
            billing_contact_state_code = record.partner_id.state_id.code or ""
            billing_contact_postal_code = record.partner_id.zip or ""
            billing_contact_country_code =  record.partner_id.country_id.code or ""
            billing_contact_phone = record.partner_id.phone or ""
            billing_contact_irs = record.partner_id.irs_number or ""
            delivery_contact_name = record.partner_shipping_id.name or ""
            delivery_contact_street = record.partner_shipping_id.street or ""
            delivery_contact_street2 = record.partner_shipping_id.street2 or ""
            delivery_contact_city = record.partner_shipping_id.city or ""
            delivery_contact_state_code = record.partner_shipping_id.state_id.code or ""
            delivery_contact_postal_code = record.partner_shipping_id.zip or ""
            delivery_contact_country_code =  record.partner_shipping_id.country_id.code or ""
            delivery_contact_phone = record.partner_shipping_id.phone or ""
            delivery_contact_irs = record.partner_shipping_id.irs_number or ""
            invoice_date = record.date or ""
            fee_percentage = self.fee_percentage.name or ""
            source = record.invoice_origin or ""
            shipping_details = self._get_shipment_details(source)
            weight = shipping_details['weight']
            arrival_date = self.arrival_date
            shipping_amount = 0
            for invoice_line in  record.invoice_line_ids:
                if invoice_line.invoice_ship_method == True:
                    shipping_amount = invoice_line.inv_line_amount
                    #print(shipping_amount,'SHIPPING AMOUNT **************************')
            total_amount = record.amount_total - shipping_amount
            #print(total_amount,'TOTAL AMOUNT *********************************')
            #date =  shipping_details['arrival_date']
            #if date:
                #arrival_date = date.date()
            #if not date:
                #arrival_date = ""
            #invoice_line = self._get_total_qty(record.id)
            total_qty = shipping_details['total_qty']
            country_of_export = self.export_country_id.code
            
            xml_data += "<Invoice>\n<Importer>HEAPRO0002</Importer>\n<Invoice_No>" +record.name +"<Invoice_No>\n<Invoice_Type>"+'PI'+"</Invoice_Type>\n<STCode/>\n<Supplier>\n<Name>"+company_name+"</Name>\n<Street1>"+company_street+"</Street1>\n<Street2>"+company_street2+"</Street2>\n<City>"+company_city+"</City>\n<State>"+company_state_code+"</State>\n<PostCode>"+company_postal_code+"</PostCode>\n<Country>"+company_country_code+"</Country>\n<Phone>"+company_phone+"</Phone>\n<IRS_No>"+company_irs+"</IRS_No>\n<MID>"+company_mid+"</MID>\n<Type/>\n<PNCEmail/>\n</Supplier>\n<Exporter>\n<Name>"+company_name+"</Name>\n<Street1>"+company_street+"</Street1>\n<Street2>"+company_street2+"</Stree2>\n<City>"+company_city+"</City>\n<State>"+company_state_code+"</State>\n<PostCode>"+company_postal_code+"</PostCode>\n<Country>"+company_country_code+"</Country>\n<Phone>"+company_phone+"</Phone>\n<IRS_No>"+company_irs+"</IRS_No>\n<MID>"+company_mid+"</MID>\n<Type/>\n<PNCEmail/>\n</Exporter>\n<UCons>\n<Name>"+delivery_contact_name+"</Name>\n<Street1>"+delivery_contact_street+"</Street1>\n<Street2>"+delivery_contact_street2+"</Stree2>\n<City>"+delivery_contact_city+"</City>\n<State>"+delivery_contact_state_code+"</State>\n<PostCode>"+delivery_contact_postal_code+"</PostCode>\n<Country>"+delivery_contact_country_code+"</Country>\n<Phone>"+delivery_contact_phone+"</Phone>\n<IRS_No>"+delivery_contact_irs+"</IRS_No>\n<MID>"+company_mid+"</MID>\n<Type/>\n<PNCEmail/>\n</UCons>\n<Buyer>\n<Name>"+billing_contact_name+"</Name>\n<Street1>"+billing_contact_street+"</Street1>\n<Street2>"+billing_contact_street2+"</Stree2>\n<City>"+billing_contact_city+"</City>\n<State>"+billing_contact_state_code+"</State>\n<PostCode>"+billing_contact_postal_code+"</PostCode>\n<Country>"+billing_contact_country_code+"</Country>\n<Phone>"+billing_contact_phone+"</Phone>\n<IRS_No>"+billing_contact_irs+"</IRS_No>\n<MID>"+company_mid+"</MID>\n<Type/>\n<PNCEmail/>\n</Buyer>\n<ReleasePort>"+"0701"+"</ReleasePort>\n<Invoice_Date>"+str(invoice_date)+"</Invoice_Date>\n<Currency>"+record.currency_id.name+"</Currency>\n<Entry_No/>\n<TransType>"+"PAPS-BCS"+"</TransType>\n<RefNum>"+record.name+"</RefNum>\n<PaymentTerms>"+""+"</PaymentTerms>\n<TotalAmount>"+str(total_amount)+"</TotalAmount>\n<GrossWeight>"+str(weight)+"</GrossWeight>\n<BillLading>"+"BOL20200911A"+"</BillLading>\n<FeePercent>"+str(fee_percentage)+"</FeePercent>\n<DiscountValue>"+"0"+"</DiscountValue>\n<Freight>"+"0"+"</Freight>\n<AdjustmentAmount/>\n<ArrivalDate>"+str(arrival_date)+"</ArrivalDate>\n<SCACCode>"+"DANQ"+"</SCACCode>\n<TotalUnitsShipped>"+str(total_qty)+"</TotalUnitsShipped>\n<DeliveryTerms/>\n<BrokerProductDesc/>\n<AdjustmentInfo>\n<AdjustmentCode>"+""+"</AdjustmentCode>\n<CurrencyCode>"+""+"</CurrencyCode>\n</AdjustmentInfo>\n<AdjustmentInfo>\n<AdjustmentCode>"+""+"</AdjustmentCode>\n<CurrencyCode>"+""+"</CurrencyCode>\n</AdjustmentInfo>\n<TotalDue>"+str(total_amount)+"</TotalDue>\n<UOM>"+"BX"+"</UOM>\n<RelatedParty>"+"N"+"</RelatedParty>\n<CountryOfExport>"+str(country_of_export)+"</CountryOfExport>\n<ExportDate>"+str(arrival_date)+"</ExportDate>\n<Charges>"+"10.00"+"</Charges>\n<RelatedDoc>\n<Id/>\n<Number/>\n</RelatedDoc>\n<VesselName/>\n<VesselNo/>\n<PortLading>"+""+"</PortLading>\n<ContainerNum/>\n<LocationQualifier/>\n<LocationIndicator/>\n<LocationCode/>\n<USCLocation>"+""+"</USCLocation>\n<MarksNumbers/>\n<PaymentBy/>\n<Insured>"+"N"+"</Insured>\n<IT>\n<Date/>\n<Number/>\n</IT>\n<DateSubmitted>"+str(arrival_date)+"<DateSubmitted>\n<DateCreated>"+str(arrival_date)+"</DateCreated>\n<UserName>"+"shipping@helathcraftsproducts.com"+"</UserName>\n<PNCImage/>\n<Template/>\n"
            
            count=1
            for line in  record.invoice_line_ids:
                if line.invoice_ship_method != True:
                    usmac_eligibility = ""
                    usmaca = line.product_id.usmca_eligible
                    if usmaca:
                        if usmaca == 'yes':
                            usmac_eligibility = 'S'
                        else:
                            usmac_eligibility =""
                    country_of_origin = line.product_id.cust_fld3.code or ""
                    binding_rule = line.product_id.binding_rule or ""
                    fda_desription = line.product_id.fda_listing or ""
                    hsc_code = line.product_id.cust_fld2 or ""
                    tariff_number = line.product_id.tarrif_number or ""
                    product_qty = line.quantity or ""
                    item_code = line.product_id.default_code or ""
                    pounds = round(product_qty/2.2046, 2)
                    xml_data += "<LineItem>\n<Description>"+str(line.product_id.name)+"</Description>\n<LineNumber>"+str(count)+"</LineNumber>\n<TotalLineItemValue>"+str(line.price_subtotal)+"</TotalLineItemValue>\n<RulingNo>"+str(binding_rule)+"</RulingNo>\n<UnitPrice>"+str(line.price_unit)+"</UnitPrice>\n<BasisOfUnitPrice>"+"PE"+"</BasisOfUnitPrice>\n<CountryOfOrigin>"+str(country_of_origin)+"</CountryOfOrigin>\n<UConsignee>\n<Name/>\n<Street1/>\n<Street2/>\n<City/>\n<State/>\n<PostCode/>\n<Country/>\n<Phone/>\n<IRS_No/>\n<MID/>\n<Type/>\n<PNCEmail/>\n</UConsignee>\n<SI>"+""+"</SI>\n<Softwood/>\n<AddNonReimbDeclareId/>\n<CvdNonReimbDeclareId/>\n<SWPermit/>\n<InvoiceQty>"+str(product_qty)+"</InvoiceQty>\n<InvoiceUOM>"+str(line.product_uom_id.name)+"</InvoiceUOM>\n<DeliveryTerms/>\n<PaymentTerms/>\n<ExportDate>"+str(arrival_date)+"</ExportDate>\n<Discount/>\n<Manufacturer>\n<Name>"+str(company_name)+"</Name>\n<Street1>"+str(company_street)+"</Street1>\n<Street2>"+str(company_street2)+"</Stree2>\n<City>"+str(company_city)+"</City>\n<State>"+str(company_state_code)+"</State>\n<PostCode>"+str(company_postal_code)+"</PostCode>\n<Country>"+str(company_country_code)+"</Country>\n<Phone>"+str(company_phone)+"</Phone>\n<IRS_No>"+company_irs+"</IRS_No>\n<MID>"+company_mid+"</MID>\n<Type/>\n<PNCEmail/>\n</Manufacturer>\n<Tariff>\n<PartNumber>"+str(item_code)+"</PartNumber>\n<Description>"+str(line.product_id.name)+"</Description>\n<Country>"+str(country_of_origin)+"</Country>\n<BindingRulingNo>"+str(binding_rule)+"</BindingRulingNo>\n<UnitPrice>"+str(line.price_unit)+"</UnitPrice>\n<ProductCode>"+str(item_code)+"</ProductCode>\n<FDADescription>"+str(fda_desription)+"</FDADescription>\n<LicensePermitNo/>\n<Manufacturer>\n<Name>"+company_name+"</Name>\n<Street1>"+company_street+"</Street1>\n<Street2>"+company_street2+"</Stree2>\n<City>"+company_city+"</City>\n<State>"+company_state_code+"</State>\n<PostCode>"+company_postal_code+"</PostCode>\n<Country>"+company_country_code+"</Country>\n<Phone>"+company_phone+"</Phone>\n<IRS_No>"+company_irs+"</IRS_No>\n<MID>"+company_mid+"</MID>\n<Type/>\n<PNCEmail/>\n</Manufacturer>\n"
                    if len(tariff_number) > 0:
                        for tariff in tariff_number:
                            tariff_count = 1
                            xml_data += "<ProductTariff>\n<Tariff>"+str(tariff.name)+"</Tariff>\n<InvoiceQty>"+str(product_qty)+"</InvoiceQty>\n<InvoiceUOM>"+str(line.product_uom_id.name)+"</InvoiceUOM>\n<NumUnitsShipped>"+str(product_qty)+"</NumUnitsShipped>\n<UnitsShippedUOM>"+""+"</UnitsShippedUOM>\n<NumUnitsShipped2>"+str(pounds)+"</NumUnitsShipped2>\n<UnitsShippedUOM2>"+"KG"+"</UnitsShippedUOM2>\n<SI>"+usmac_eligibility+"</SI>\n<SI2/>\n<Manufacturer>\n<Name>"+company_name+"</Name>\n<Street1>"+company_street+"</Street1>\n<Street2>"+company_street2+"</Stree2>\n<City>"+company_city+"</City>\n<State>"+company_state_code+"</State>\n<PostCode>"+company_postal_code+"</PostCode>\n<Country>"+company_country_code+"</Country>\n<Phone>"+company_phone+"</Phone>\n<IRS_No>"+company_irs+"</IRS_No>\n<MID>"+company_mid+"</MID>\n<Type/>\n<PNCEmail/>\n</Manufacturer>\n<ItemValue>"+""+"</ItemValue>\n<PG>\n<PGCode/>\n<Desc1Ci>"+""+"</Desc1Ci>\n<PGAgencyCode>"+""+"</PGAgencyCode>\n<PGProgramCode>"+""+"</PGProgramCode>\n<AgencyProcessingCode>"+""+"</AgencyProcessingCode>\n<ElectronicImageSubmitted/>\n<Confidential>"+""+"</Confidential>\n<GlobalProductIdQualifier/>\n<GlobalProductId/>\n<IntendedUseBaseCode/>\n<IntendedUseSubCode/>\n<IntendedUseAddCode/>\n<IntendedUseDesc/>\n<Disclaimer>"+""+"</Disclaimer>\n<DisclaimerTypeCode>"+""+"</DisclaimerTypeCode>\n<USCSPGSeqNo/>\n<DispositionActionDate/>\n<DispositionActionTime/>\n<DispositionActionCode/>\n<NarrativeMessage/>\n<DocumentTypeCode/>\n</PG>\n<PG_APHIS>\n<DetailedDescription>"+""+"</DetailedDescription>\n<LineValue>"+""+"</LineValue>"+""+"<UseQtyForSpeciesCountry/>\n<DeclarationEntityCode/>\n<DeclarationCode/>\n<DeclarationCert>"+""+"</DeclarationCert>\n<DateSignature/>\n<ImporterAddressNo/>\n<ImporterContactNo/>\n<ImporterIndividualName>"+""+"</ImporterIndividualName>\n<ImporterPhoneNo>"+""+"</ImporterPhoneNo>\n<ImporterFaxNo/>\n<ImporterEmailAddress>"+""+"</ImporterEmailAddress>\n<APHIS_CONTAINERS>\n<ContainerNo/>\n</APHIS_CONTAINERS>\n<PERMITS>\n<PermitType/>\n<PermitTypeCode/>\n<PermitNumber/>\n<PermintDateType/>\n<PermitDate/>\n</PERMITS>\n<COMPONENTS>\n<ComponentName>"+""+"</ComponentName>\n<ComponentUom>"+""+"</ComponentUom>\n<ScientificGenusName>"+""+"</ScientificGenusName>\n<ScientificSpeciesName>"+""+"</ScientificSpeciesName>\n<CountryHarvested>"+""+"</CountryHarvested>\n<PercentReycledMaterial>"+""+"</PercentReycledMaterial>\n<ComponentQty>"+""+"</ComponentQty>\n<UnknownHarvestSrcOrSpecies/>\n<ADDL_COUNTRIES>\n<CountryHarvested/>\n</ADDL_COUNTRIES>\n</COMPONENTS>\n</PG_APHIS>\n</PG>\n<PG>\n<PGCode/>\n<Desc1Ci>"+""+"</Desc1Ci>\n<PGAgencyCode>"+""+"</PGAgencyCode>\n<PGProgramCode>"+""+"</PGProgramCode>\n<AgencyProcessingCode/>\n<ElectronicImageSubmitted/>\n<Confidential/>\n<GlobalProductIdQualifier/>\n<GlobalProductId/>\n<IntendedUseBaseCode/>\n<IntendedUseSubCode/>\n<IntendedUseAddCode/>\n<IntendedUseDesc/>\n<Disclaimer>"+""+"</Disclaimer>\n<DisclaimerTypeCode/>\n<USCSPGSeqNo/>\n<DispositionActionDate>"+""+"</DispositionActionDate>\n<DispositionActionTime>"+""+"</DispositionActionTime>\n<DispositionActionCode/>\n<NarrativeMessage/>\n<DocumentTypeCode/>\n<PG_EPA>\n<ProductCodeQualifier/>\n<ProductCode/>\n<NetWeightUOM/>\n<NetWeight/>\n<DocumentCode/>\n<EntityRoleCode>"+""+"</EntityRoleCode>\n<DeclarationCd>"+""+"</DeclarationCd>\n<DeclarationCert>"+""+"</DeclarationCert>\n<ImportCode/>\n<IsExemptFromBond/>\n<IndustryCd/>\n<OtherExemptionRegulation/>\n<TradeBrandName/>\n<EpaRegistrationNo/>\n<ForeignProducerEstNo/>\n<DomesticProducerEstNo/>\n<CertifyIndividualRoleCd/>\n<NotifyPartyRoleCd/>\n<ActiveIngredient/>\n<IngredientName/>\n<IngredientPercent/>\n<PackagingQuantity1/>\n<PackagingUomCd1/>\n<PackagingIdentifier1/>\n<PackagingQuantity2/>\n<PackagingUomCd2/>\n<PackagingIdentifier2/>\n<PackagingQuantity3/>\n<PackagingUomCd3/>\n<PackagingIdentifier3/>\n<PackagingQuantity4/>\n<PackagingUomCd4/>\n<PackagingIdentifier4/>\n<PackagingQuantity5/>\n<PackagingUomCd5/>\n<PackagingIdentifier5/>\n<PackagingQuantity6/>\n<PackagingUomCd6/>\n<PackagingIdentifier6/>\n<Model/>\n<ModelYear/>\n<ManufacturerMonthYear/>\n<ManufacturerDateLocationCd/>\n<OtherLocationDesc/>\n<EnginePowerRatingType/>\n<BodyTypeUnder1Ton/>"+""+"<BodyTypeOver1Ton/>\n<MilitaryEquipment/>\n<DriveSide/>\n<TestGroupNameNo/>\n<BondPolicyNo/>\n<BondPolicyNoDuration/>\n<VneExceptionNo/>\n<ItemIdentityQual/>\n<ItemIdentityNbr/>\n<SendPgProgramCd/>\n<DateSignature/>\n<EPA_PARTIES>\n<PartyRole>"+""+"</PartyRole>\n<PartyCustNo/>\n<PartyAddressNo/>\n<PartyContactNo/>\n<PartyCarrierCd/>\n<PartyFirmsCd/>\n<PartyMidCd/>\n<PartyNumber/>\n<PartyName/>\n<PartyAddressLine1/>\n<PartyAddressLine2/>\n<PartyCity/>\n<PartyStateProvince/>\n<PartyCountry/>\n<PartyPostalCd/>\n<PartyIndividualName>"+""+"</PartyIndividualName>\n<PartyPhoneNo>"+""+"</PartyPhoneNo>\n<PartyFaxNo/>\n<PartyEmailAddress>"+""+"</PartyEmailAddress>\n</EPA_PARTIES>\n</PG_EPA>\n</PG>\n</ProductTariff>\n"
                            tariff_count = tariff_count + 1
                        #count = count + 1
                        xml_data += "</Tariff>\n</LineItem>\n"
                    else:
                            xml_data += "<ProductTariff>\n<Tariff>"+""+"</Tariff>\n<InvoiceQty>"+str(product_qty)+"</InvoiceQty>\n<InvoiceUOM>"+str(line.product_uom_id.name)+"</InvoiceUOM>\n<NumUnitsShipped>"+str(product_qty)+"</NumUnitsShipped>\n<UnitsShippedUOM>"+""+"</UnitsShippedUOM>\n<NumUnitsShipped2>"+str(pounds)+"</NumUnitsShipped2>\n<UnitsShippedUOM2>"+"KG"+"</UnitsShippedUOM2>\n<SI>"+usmac_eligibility+"</SI>\n<SI2/>\n<Manufacturer>\n<Name>"+company_name+"</Name>\n<Street1>"+company_street+"</Street1>\n<Street2>"+company_street2+"</Stree2>\n<City>"+company_city+"</City>\n<State>"+company_state_code+"</State>\n<PostCode>"+company_postal_code+"</PostCode>\n<Country>"+company_country_code+"</Country>\n<Phone>"+company_phone+"</Phone>\n<IRS_No>"+company_irs+"</IRS_No>\n<MID>"+company_mid+"</MID>\n<Type/>\n<PNCEmail/>\n</Manufacturer>\n<ItemValue>"+""+"</ItemValue>\n<PG>\n<PGCode/>\n<Desc1Ci>"+""+"</Desc1Ci>\n<PGAgencyCode>"+""+"</PGAgencyCode>\n<PGProgramCode>"+""+"</PGProgramCode>\n<AgencyProcessingCode>"+""+"</AgencyProcessingCode>\n<ElectronicImageSubmitted/>\n<Confidential>"+""+"</Confidential>\n<GlobalProductIdQualifier/>\n<GlobalProductId/>\n<IntendedUseBaseCode/>\n<IntendedUseSubCode/>\n<IntendedUseAddCode/>\n<IntendedUseDesc/>\n<Disclaimer>"+""+"</Disclaimer>\n<DisclaimerTypeCode>"+""+"</DisclaimerTypeCode>\n<USCSPGSeqNo/>\n<DispositionActionDate/>\n<DispositionActionTime/>\n<DispositionActionCode/>\n<NarrativeMessage/>\n<DocumentTypeCode/>\n</PG>\n<PG_APHIS>\n<DetailedDescription>"+""+"</DetailedDescription>\n<LineValue>"+""+"</LineValue>"+""+"<UseQtyForSpeciesCountry/>\n<DeclarationEntityCode/>\n<DeclarationCode/>\n<DeclarationCert>"+""+"</DeclarationCert>\n<DateSignature/>\n<ImporterAddressNo/>\n<ImporterContactNo/>\n<ImporterIndividualName>"+""+"</ImporterIndividualName>\n<ImporterPhoneNo>"+""+"</ImporterPhoneNo>\n<ImporterFaxNo/>\n<ImporterEmailAddress>"+""+"</ImporterEmailAddress>\n<APHIS_CONTAINERS>\n<ContainerNo/>\n</APHIS_CONTAINERS>\n<PERMITS>\n<PermitType/>\n<PermitTypeCode/>\n<PermitNumber/>\n<PermintDateType/>\n<PermitDate/>\n</PERMITS>\n<COMPONENTS>\n<ComponentName>"+""+"</ComponentName>\n<ComponentUom>"+""+"</ComponentUom>\n<ScientificGenusName>"+""+"</ScientificGenusName>\n<ScientificSpeciesName>"+""+"</ScientificSpeciesName>\n<CountryHarvested>"+""+"</CountryHarvested>\n<PercentReycledMaterial>"+""+"</PercentReycledMaterial>\n<ComponentQty>"+""+"</ComponentQty>\n<UnknownHarvestSrcOrSpecies/>\n<ADDL_COUNTRIES>\n<CountryHarvested/>\n</ADDL_COUNTRIES>\n</COMPONENTS>\n</PG_APHIS>\n</PG>\n<PG>\n<PGCode/>\n<Desc1Ci>"+""+"</Desc1Ci>\n<PGAgencyCode>"+""+"</PGAgencyCode>\n<PGProgramCode>"+""+"</PGProgramCode>\n<AgencyProcessingCode/>\n<ElectronicImageSubmitted/>\n<Confidential/>\n<GlobalProductIdQualifier/>\n<GlobalProductId/>\n<IntendedUseBaseCode/>\n<IntendedUseSubCode/>\n<IntendedUseAddCode/>\n<IntendedUseDesc/>\n<Disclaimer>"+""+"</Disclaimer>\n<DisclaimerTypeCode/>\n<USCSPGSeqNo/>\n<DispositionActionDate>"+""+"</DispositionActionDate>\n<DispositionActionTime>"+""+"</DispositionActionTime>\n<DispositionActionCode/>\n<NarrativeMessage/>\n<DocumentTypeCode/>\n<PG_EPA>\n<ProductCodeQualifier/>\n<ProductCode/>\n<NetWeightUOM/>\n<NetWeight/>\n<DocumentCode/>\n<EntityRoleCode>"+""+"</EntityRoleCode>\n<DeclarationCd>"+""+"</DeclarationCd>\n<DeclarationCert>"+""+"</DeclarationCert>\n<ImportCode/>\n<IsExemptFromBond/>\n<IndustryCd/>\n<OtherExemptionRegulation/>\n<TradeBrandName/>\n<EpaRegistrationNo/>\n<ForeignProducerEstNo/>\n<DomesticProducerEstNo/>\n<CertifyIndividualRoleCd/>\n<NotifyPartyRoleCd/>\n<ActiveIngredient/>\n<IngredientName/>\n<IngredientPercent/>\n<PackagingQuantity1/>\n<PackagingUomCd1/>\n<PackagingIdentifier1/>\n<PackagingQuantity2/>\n<PackagingUomCd2/>\n<PackagingIdentifier2/>\n<PackagingQuantity3/>\n<PackagingUomCd3/>\n<PackagingIdentifier3/>\n<PackagingQuantity4/>\n<PackagingUomCd4/>\n<PackagingIdentifier4/>\n<PackagingQuantity5/>\n<PackagingUomCd5/>\n<PackagingIdentifier5/>\n<PackagingQuantity6/>\n<PackagingUomCd6/>\n<PackagingIdentifier6/>\n<Model/>\n<ModelYear/>\n<ManufacturerMonthYear/>\n<ManufacturerDateLocationCd/>\n<OtherLocationDesc/>\n<EnginePowerRatingType/>\n<BodyTypeUnder1Ton/>"+""+"<BodyTypeOver1Ton/>\n<MilitaryEquipment/>\n<DriveSide/>\n<TestGroupNameNo/>\n<BondPolicyNo/>\n<BondPolicyNoDuration/>\n<VneExceptionNo/>\n<ItemIdentityQual/>\n<ItemIdentityNbr/>\n<SendPgProgramCd/>\n<DateSignature/>\n<EPA_PARTIES>\n<PartyRole>"+""+"</PartyRole>\n<PartyCustNo/>\n<PartyAddressNo/>\n<PartyContactNo/>\n<PartyCarrierCd/>\n<PartyFirmsCd/>\n<PartyMidCd/>\n<PartyNumber/>\n<PartyName/>\n<PartyAddressLine1/>\n<PartyAddressLine2/>\n<PartyCity/>\n<PartyStateProvince/>\n<PartyCountry/>\n<PartyPostalCd/>\n<PartyIndividualName>"+""+"</PartyIndividualName>\n<PartyPhoneNo>"+""+"</PartyPhoneNo>\n<PartyFaxNo/>\n<PartyEmailAddress>"+""+"</PartyEmailAddress>\n</EPA_PARTIES>\n</PG_EPA>\n</PG>\n</ProductTariff>\n</Tariff>\n</LineItem>\n"
                count = count + 1
            xml_data += "</Invoice>\n"
        record.write({'deringer_shipping_done': True})
        xml_data = "<?xml version="+str(1.0)+" encoding="+"UTF-8"+" standalone="+"yes"+"?>\n<Consolidated>\n" + xml_data + "</Consolidated>\n"
        byte_xml = bytes(xml_data, 'utf-8') 
        output = base64.b64encode(byte_xml)
        res = self.env['deringer.report.download'].create({'data':output})
        self.write({'state': 'xml_created'})
        return { 
            'type': 'ir.actions.act_window',
            'res_model': 'deringer.report.download',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'res_id': res.id,}
        
    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})
        
    def action_send_email(self):
        '''
        This function opens a window to compose an email, with the deringer template message loaded by default
        '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data.get_object_reference('hcp_deringer', 'email_template_deringer')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        lang = self.env.context.get('lang')
        template = template_id and self.env['mail.template'].browse(template_id)
        if template and template.lang:
            lang = template._render_template(template.lang, 'deringer.form', self.ids[0])
        ctx = {
            'default_model': 'deringer.form',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_deringer_as_sent': True,
            'model_description': self.name,
            'force_email': True
        }
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }
    
    #@api.multi
    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        if self.env.context.get('mark_deringer_as_sent'):
            self.filtered(lambda o: o.state == 'xml_created').with_context(tracking_disable=True).write({'state': 'sent_email'})
        return super(DeringerForm, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)
