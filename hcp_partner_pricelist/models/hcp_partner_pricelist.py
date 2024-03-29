# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import AccessError, UserError, ValidationError
from datetime import datetime, timedelta, date
# from odoo.addons.sale.models.sale import SaleOrderLine as salesline
# from odoo.addons.sale.models.sale import SaleOrderLine as salesuom
from odoo.addons.sale.models.sale_order_line import SaleOrderLine as salesline
from odoo.addons.sale.models.sale_order_line import SaleOrderLine as salesuom

# commented due to changes in version16 function
# @api.onchange('product_id')
# def product_id_change(self):
#     if not self.product_id:
#         return
#     valid_values = self.product_id.product_tmpl_id.valid_product_template_attribute_line_ids.product_template_value_ids
#     # remove the is_custom values that don't belong to this template
#     for pacv in self.product_custom_attribute_value_ids:
#         if pacv.custom_product_template_attribute_value_id not in valid_values:
#             self.product_custom_attribute_value_ids -= pacv
#
#     # remove the no_variant attributes that don't belong to this template
#     for ptav in self.product_no_variant_attribute_value_ids:
#         if ptav._origin not in valid_values:
#             self.product_no_variant_attribute_value_ids -= ptav
#
#     vals = {}
#     if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
#         vals['product_uom'] = self.product_id.uom_id
#         vals['product_uom_qty'] = self.product_uom_qty or 1.0
#
#     product = self.product_id.with_context(
#         lang=get_lang(self.env, self.order_id.partner_id.lang).code,
#         partner=self.order_id.partner_id,
#         quantity=vals.get('product_uom_qty') or self.product_uom_qty,
#         date=self.order_id.date_order,
#         pricelist=self.order_id.pricelist_id.id,
#         uom=self.product_uom.id
#     )
#     #vals.update(name=self.get_sale_order_line_multiline_description_sale(product))
#     #HEM NEW
#     vals.update(name=self.product_id.name)
#     #self.tax_id = self.order_id.partner_id.taxes_id # Added to get tax from Customer
#     self._compute_tax_id() # commented to not to derive tax from product
#
#     if self.order_id.pricelist_id and self.order_id.partner_id:
#         vals['price_unit'] = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(), product.taxes_id, self.tax_id, self.company_id)
#     #raise ValidationError(_('#######%s')%vals['price_unit'])
#
#     self.update(vals)
#     #raise ValidationError(_('#######%s')% vals)
#     title = False
#     message = False
#     result = {}
#     warning = {}
#     if product.sale_line_warn != 'no-message':
#         title = _("Warning for %s") % product.name
#         message = product.sale_line_warn_msg
#         warning['title'] = title
#         warning['message'] = message
#         result = {'warning': warning}
#         if product.sale_line_warn == 'block':
#             self.product_id = False
#
#     return result
#
# salesline.product_id_change = product_id_change
@api.depends('product_id')
def _compute_name(self):
    for line in self:
        if not line.product_id:
            continue
        if not line.order_partner_id.is_public:
            line = line.with_context(lang=line.order_partner_id.lang)
        # name = line._get_sale_order_line_multiline_description_sale()
        name = line.product_id.name
        if line.is_downpayment and not line.display_type:
            context = {'lang': line.order_partner_id.lang}
            dp_state = line._get_downpayment_state()
            if dp_state == 'draft':
                name = _("%(line_description)s (Draft)", line_description=name)
            elif dp_state == 'cancel':
                name = _("%(line_description)s (Canceled)", line_description=name)
            del context
        line.name = name



# @api.onchange('product_uom', 'product_uom_qty')
# def product_uom_change(self):
#     if not self.product_uom or not self.product_id:
#         self.price_unit = 0.0
#         return
#     if self.order_id.pricelist_id and self.order_id.partner_id:
#         product = self.product_id.with_context(
#             lang=self.order_id.partner_id.lang,
#             partner=self.order_id.partner_id,
#             quantity=self.product_uom_qty,
#             date=self.order_id.date_order,
#             pricelist=self.order_id.pricelist_id.id,
#             uom=self.product_uom.id,
#             fiscal_position=self.env.context.get('fiscal_position')
#         )
#         self.price_unit = product._get_tax_included_unit_price(
#             self.company_id or self.order_id.company_id,
#             self.order_id.currency_id,
#             self.order_id.date_order,
#             'sale',
#             fiscal_position=self.order_id.fiscal_position_id,
#             product_price_unit=self._get_display_price(),
#             product_currency=self.order_id.currency_id
#         )
# salesuom.product_uom_change = product_uom_change

class Lead(models.Model):
    _inherit = "crm.lead"

    @api.model_create_multi
    def create(self, vals_list):
        # for vals in vals_list:
        # if vals.get('website'):
        #     vals['website'] = self.env['res.partner']._clean_website(vals['website'])
        leads = super(Lead, self).create(vals_list)
        if leads.group_code_hcp:
            leads.write({'group_code_hcp': leads.group_code_hcp.id})
        for lead, values in zip(leads, vals_list):
            if any(field in ['active', 'stage_id'] for field in values):
                lead._handle_won_lost(values)
        return leads

    def write(self, vals):
        if vals.get('website'):
            vals['website'] = self.env['res.partner']._clean_website(vals['website'])

        stage_updated, stage_is_won = vals.get('stage_id'), False
        # stage change: update date_last_stage_update
        if stage_updated:
            stage = self.env['crm.stage'].browse(vals['stage_id'])
            if stage.is_won:
                vals.update({'probability': 100, 'automated_probability': 100})
                stage_is_won = True
        # stage change with new stage: update probability and date_closed
        if vals.get('probability', 0) >= 100 or not vals.get('active', True):
            vals['date_closed'] = fields.Datetime.now()
        elif vals.get('probability', 0) > 0:
            vals['date_closed'] = False
        elif stage_updated and not stage_is_won and not 'probability' in vals:
            vals['date_closed'] = False

        if any(field in ['active', 'stage_id'] for field in vals):
            self._handle_won_lost(vals)

        if 'partner_id' in vals:
            default_stage_id = self.env.ref('hcp_partner_pricelist.stage_lead5')
            vals['stage_id'] = default_stage_id.id
        if vals.get('partner_id') == False:
            vals['group_code_hcp'] = False

        if not stage_is_won:
            return super(Lead, self).write(vals)

        # stage change between two won stages: does not change the date_closed
        leads_already_won = self.filtered(lambda lead: lead.stage_id.is_won)
        remaining = self - leads_already_won
        if remaining:
            result = super(Lead, remaining).write(vals)
        if leads_already_won:
            vals.pop('date_closed', False)
            result = super(Lead, leads_already_won).write(vals)
        return result

    shipment_date = fields.Date(string='Shipment Date')
    group_code_hcp = fields.Many2one('hcp.group.code', string='Group Code', readonly=True)

    def _onchange_partner_id_values(self, partner_id):
        """ returns the new values when partner_id has changed """
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            partner_name = partner.parent_id.name
            if not partner_name and partner.is_company:
                partner_name = partner.name
            return {
                'partner_name': partner_name,
                'contact_name': partner.name if not partner.is_company else False,
                'title': partner.title.id,
                'street': partner.street,
                'street2': partner.street2,
                'city': partner.city,
                'state_id': partner.state_id.id,
                'country_id': partner.country_id.id,
                'group_code_hcp': partner.hcp_group_code.id or False,
                'email_from': partner.email,
                'phone': partner.phone,
                'mobile': partner.mobile,
                'zip': partner.zip,
                'function': partner.function,
                'website': partner.website,
            }
        return {}


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    def unlink(self):
        for line in self:
            partner_pricelists = self.env['partners.pricelist.products']
            partner_pricelists_line = partner_pricelists.search([('pricelist_item_id', '=', line.id)])
            print("so_pricelists", partner_pricelists_line)
            partner_pricelists_line.unlink()
        return super(PricelistItem, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('applied_on', False):
                # Ensure item consistency for later searches.
                applied_on = values['applied_on']
                if applied_on == '3_global':
                    values.update(dict(product_id=None, product_tmpl_id=None, categ_id=None))
                elif applied_on == '2_product_category':
                    values.update(dict(product_id=None, product_tmpl_id=None))
                elif applied_on == '1_product':
                    values.update(dict(product_id=None, categ_id=None))
                elif applied_on == '0_product_variant':
                    values.update(dict(categ_id=None))

        res = super(PricelistItem, self).create(vals_list)
        partner_pricelist_res = []
        for item in res:
            if item.product_id.sale_ok == True or item.product_tmpl_id.sale_ok == True:
                partner_pricelis_products = self.env['partners.pricelist.products']
                rec = {
                    'product_id': item.product_id.id or None,
                    'product_tmpl_id': item.product_tmpl_id.id or None,
                    'applied_on': item.applied_on,
                    'pricelist_item_id': item.id,
                    'pricelist_id': item.pricelist_id.id,
                    'name': item.name,
                    'min_quantity': item.min_quantity,
                    'compute_price': item.compute_price,
                    'fixed_price': item.fixed_price or 0,
                    'percent_price': item.percent_price or 0,
                }
                partner_pricelist_res = partner_pricelis_products.create(rec)
        return res and partner_pricelist_res

    def write(self, values):
        if values.get('applied_on', False):
            # Ensure item consistency for later searches.
            applied_on = values['applied_on']
            if applied_on == '3_global':
                values.update(dict(product_id=None, product_tmpl_id=None, categ_id=None))
            elif applied_on == '2_product_category':
                values.update(dict(product_id=None, product_tmpl_id=None))
            elif applied_on == '1_product':
                values.update(dict(product_id=None, categ_id=None))
            elif applied_on == '0_product_variant':
                values.update(dict(categ_id=None))
        res = super(PricelistItem, self).write(values)
        # When the pricelist changes we need the product.template price
        # to be invalided and recomputed.
        self.flush()
        self.invalidate_cache()
        partner_pricelist_products = self.env['partners.pricelist.products']
        rec = partner_pricelist_products.search([('pricelist_item_id', '=', self.id)])
        if 'percent_price' in values:
            rec.write({
                'percent_price': values['percent_price'] or 0,
            })
        elif 'fixed_price' in values:
            rec.write({
                'fixed_price': values['fixed_price'] or 0,
            })
        elif 'min_quantity' in values:
            rec.write({
                'min_quantity': values['min_quantity'] or 0,
            })
        elif 'product_id' in values:
            rec.write({
                'product_id': values['product_id'],
            })
        elif 'product_tmpl_id' in values:
            rec.write({
                'product_tmpl_id': values['product_tmpl_id'],
            })
        elif 'applied_on' in values:
            rec.write({
                'applied_on': values['applied_on'],
            })
        elif 'pricelist_id' in values:
            rec.write({
                'pricelist_id': values['pricelist_id'],
            })
        elif 'name' in values:
            rec.write({
                'name': values['name'],
            })
        elif 'compute_price' in values:
            rec.write({
                'compute_price': values['compute_price'],
            })
        return rec and res


class PartnersPricelistProducts(models.Model):
    _name = "partners.pricelist.products"
    _description = "Partners Pricelist Products"

    name = fields.Char(string='Name')
    product_id = fields.Many2one(
        'product.product', string='Product',
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company', 'Company',
        readonly=True, related='pricelist_id.company_id', store=True
    )
    price_surcharge = fields.Float(
        'Price Surcharge', digits='Product Price',
    )
    price_discount = fields.Float(
        'Price Discount', default=0, digits=(16, 2)
    )
    compute_price = fields.Selection([
        ('fixed', 'Fixed Price'),
        ('percentage', 'Percentage (discount)'),
        ('formula', 'Formula')],
        index=True, default='fixed',
        required=True
    )
    fixed_price = fields.Float(
        'Fixed Price', digits='Product Price'
    )
    percent_price = fields.Float('Percentage Price')
    categ_id = fields.Many2one(
        'product.category', 'Product Category', ondelete='cascade',
    )
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product',
    )
    applied_on = fields.Selection([
        ('3_global', 'All Products'),
        ('2_product_category', ' Product Category'),
        ('1_product', 'Product'),
        ('0_product_variant', 'Product Variant')], "Apply On",
        default='3_global', required=True,
    )
    min_quantity = fields.Integer(
        'Min. Quantity', default=0
    )
    pricelist_id = fields.Many2one(
        'product.pricelist', 'Pricelist'
    )
    pricelist_item_id = fields.Many2one(
        'product.pricelist.item', 'Pricelist Item'
    )
    is_selected = fields.Boolean(string='Select Products', default=False)


class PartnerPricelists(models.TransientModel):
    _name = "partner.pricelists"
    _description = "Partners Pricelists"

    def _get_default_order_id(self):
        ctx = self._context
        if ctx.get('active_model') == 'sale.order':
            return self.env['sale.order'].browse(ctx.get('active_ids')[0]).id

    def _get_default_product_ids(self):
        ctx = self._context
        sale_order = self.env['sale.order'].browse(ctx.get('active_ids'))
        current_pricelist = sale_order.pricelist_id.id
        return self.env['partners.pricelist.products'].search([('pricelist_id', '=', current_pricelist)])

    def action_cancel(self):
        for line in self.products_ids:
            if line.is_selected == True:
                line.is_selected = False
        return {'type': 'ir.actions.act_window_close'}

    def add_pricelist_products(self):
        order_lines = []
        order_id = self.order_id
        taxes_id = order_id.partner_id.taxes_id
        for line in self.products_ids:
            if line.is_selected == True:
                if line.product_id:
                    product_id = line.product_id
                #                     tax = product_id.taxes_id
                else:
                    product_tmpl = line.product_tmpl_id
                    product_id = self.env['product.product'].search([('product_tmpl_id', '=', product_tmpl.id)])
                #                     tax = product_id.taxes_id
                line.is_selected = False
                order_line_values = {
                    'order_id': order_id.id,
                    'product_id': product_id.id,
                    'name': line.name,
                    'product_uom_qty': line.min_quantity,
                    'price_unit': line.fixed_price or 0,
                    'tax_id': [(6, 0, taxes_id.ids)],
                    'discount': line.percent_price or 0,
                }
                order_lines.append((0, 0, order_line_values))
            line.pricelist_item_id.min_quantity = line.min_quantity
            line.pricelist_item_id.fixed_price = line.fixed_price
            line.pricelist_item_id.percent_price = line.percent_price
        order_id.order_line = order_lines

    @api.onchange('select_all')
    def select_all_products(self):
        if self.select_all:
            for line in self.products_ids:
                line.is_selected = True
        else:
            for line in self.products_ids:
                line.is_selected = False


    products_ids = fields.Many2many(
        'partners.pricelist.products',
        string='Products',
        default=_get_default_product_ids, store=True
    )
    order_id = fields.Many2one(
        'sale.order', string='Order Reference',
        default=lambda self: self._get_default_order_id()
    )
    select_all = fields.Boolean(string='Select All', default=False)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    partner_so_pricelists_ids = fields.One2many('partner.pricelists', 'order_id', string='Order', store=True)
    so_email_status = fields.Selection([
        ('so_email_sent', 'Sale Order Email Sent')], "Email Status",
    )
    po_number = fields.Char(string='PO Number')
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', check_company=True,  # Unrequired company
        required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="If you change the pricelist, only newly added lines will be affected.", track_visibility='always')
    shipment_pay_policy = fields.Selection([('post_pay', 'Postpay'), ('pre_pay', 'Prepay')], 'Shipment Pay Policy',
                                           default='post_pay')

    def action_quotation_send(self):
        """ Opens a wizard to compose an email, with relevant mail template loaded by default """
        self.ensure_one()
        self.order_line._validate_analytic_distribution()
        lang = self.env.context.get('lang')
        mail_template = self._find_mail_template()
        if mail_template and mail_template.lang:
            lang = mail_template._render_lang(self.ids)[self.id]
        ctx = {
            'default_model': 'sale.order',
            'default_res_id': self.id,
            'default_use_template': bool(mail_template),
            'default_template_id': mail_template.id if mail_template else None,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'proforma': self.env.context.get('proforma', False),
            'force_email': True,
            'model_description': self.with_context(lang=lang).type_name,
        }
        if ctx['mark_so_as_sent'] == True and self.state in ['sale', 'done']:
            self.write({'so_email_status': 'so_email_sent'})
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def res_partner_pricelist_products(self):
        form_view_id = self.env.ref('hcp_partner_pricelist.view_partner_products_form').id
        return {
            'name': _('Customer Pricelist Products'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'partner.pricelists',
            'views': [(form_view_id, 'form')],
            'view_id': form_view_id,
            'target': 'new',
        }

    def _prepare_delivery_line_vals(self, carrier, price_unit):
        context = {}
        if self.partner_id:
            # set delivery detail in the customer language
            context['lang'] = self.partner_id.lang
            carrier = carrier.with_context(lang=self.partner_id.lang)

        # Apply fiscal position
        taxes = carrier.product_id.taxes_id.filtered(lambda t: t.company_id.id == self.company_id.id)
        taxes_ids = taxes.ids
        if self.partner_id and self.fiscal_position_id:
            taxes_ids = self.fiscal_position_id.map_tax(taxes).ids

        # Create the sales order line

        if carrier.product_id.description_sale:
            so_description = '%s: %s' % (carrier.name,
                                         carrier.product_id.description_sale)
        else:
            so_description = carrier.name
        values = {
            'order_id': self.id,
            'name': so_description,
            'product_uom_qty': 1,
            'product_uom': carrier.product_id.uom_id.id,
            'product_id': carrier.product_id.id,
            'tax_id': [(6, 0, taxes_ids)],
            'product_ship_method': True,
            'is_delivery': True,
        }
        if carrier.invoice_policy == 'real':
            values['price_unit'] = 0
            values['name'] += _(' (Estimated Cost: %s )', self._format_currency_amount(price_unit))
        else:
            values['price_unit'] = price_unit
        if carrier.free_over and self.currency_id.is_zero(price_unit):
            values['name'] += '\n' + _('Free Shipping')
        if self.order_line:
            values['sequence'] = self.order_line[-1].sequence + 1
        del context
        return values

    def _create_delivery_line(self, carrier, price_unit):
        values = self._prepare_delivery_line_vals(carrier, price_unit)
        return self.env['sale.order.line'].sudo().create(values)


class Opportunity2Quotation(models.TransientModel):
    _inherit = 'crm.quotation.partner'

    def action_apply(self):
        """ Convert lead to opportunity or merge lead and opportunity and open
            the freshly created opportunity view.
        """
        self.ensure_one()
        if self.action == 'create':
            self.lead_id._handle_partner_assignment(create_missing=True)
        elif self.action == 'exist':
            default_stage_id = self.env.ref('hcp_partner_pricelist.stage_lead5')
            self.lead_id.stage_id = default_stage_id
            self.lead_id._handle_partner_assignment(force_partner_id=self.partner_id.id, create_missing=False)
        return self.lead_id.action_new_quotation()
    
        
