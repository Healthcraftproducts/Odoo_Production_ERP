# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import AccessError, UserError, ValidationError

class Lead(models.Model):
    _inherit = "crm.lead"
    
    @api.model
    def create(self, vals):
        # set up context used to find the lead's Sales Team which is needed
        # to correctly set the default stage_id
        context = dict(self._context or {})
        if vals.get('type') and not self._context.get('default_type'):
            context['default_type'] = vals.get('type')
        if vals.get('team_id') and not self._context.get('default_team_id'):
            context['default_team_id'] = vals.get('team_id')

        if vals.get('user_id') and 'date_open' not in vals:
            vals['date_open'] = fields.Datetime.now()

        partner_id = vals.get('partner_id') or context.get('default_partner_id')
        onchange_values = self._onchange_partner_id_values(partner_id)
        onchange_values.update(vals)  # we don't want to overwrite any existing key
        vals = onchange_values
        if partner_id != None:
            default_stage_id = self.env.ref('hcp_partner_pricelist.stage_lead5')
            vals['stage_id'] = default_stage_id.id
        result = super(Lead, self.with_context(context)).create(vals)
        # Compute new probability for each lead separately
        result._update_probability()
    
        if result.group_code_hcp:
            result.write({'group_code_hcp': result.group_code_hcp.id})
        return result

    def write(self, vals):
        # stage change:
        if 'stage_id' in vals:
            vals['date_last_stage_update'] = fields.Datetime.now()
            stage_id = self.env['crm.stage'].browse(vals['stage_id'])
            if stage_id.is_won:
                vals.update({'probability': 100})
        # Only write the 'date_open' if no salesperson was assigned.
        if vals.get('user_id') and 'date_open' not in vals and not self.mapped('user_id'):
            vals['date_open'] = fields.Datetime.now()
        # stage change with new stage: update probability and date_closed
        if vals.get('probability', 0) >= 100 or not vals.get('active', True):
            vals['date_closed'] = fields.Datetime.now()
        elif 'probability' in vals:
            vals['date_closed'] = False
        if vals.get('user_id') and 'date_open' not in vals:
            vals['date_open'] = fields.Datetime.now()
        
        if 'partner_id' in vals:
            default_stage_id = self.env.ref('hcp_partner_pricelist.stage_lead5')
            vals['stage_id'] = default_stage_id.id
        if vals.get('partner_id') == False:
            vals['group_code_hcp'] = False
       
        write_result = super(Lead, self).write(vals)
        # Compute new automated_probability (and, eventually, probability) for each lead separately
        if self._should_update_probability(vals):
            self._update_probability()
        return write_result
    
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
                'group_code_hcp': partner.group_code_hcp.id or False,
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
    
    def action_quotation_send(self):
        ''' Opens a wizard to compose an email, with relevant mail template loaded by default '''
        self.ensure_one()
        template_id = self._find_mail_template()
        lang = self.env.context.get('lang')
        template = self.env['mail.template'].browse(template_id)
        if template.lang:
            lang = template._render_template(template.lang, 'sale.order', self.ids[0])
        ctx = {
            'default_model': 'sale.order',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'custom_layout': "mail.mail_notification_paynow",
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
     
    def _create_delivery_line(self, carrier, price_unit):
        SaleOrderLine = self.env['sale.order.line']
        if self.partner_id:
            # set delivery detail in the customer language
            carrier = carrier.with_context(lang=self.partner_id.lang)

        # Create the sales order line
        carrier_with_partner_lang = carrier.with_context(lang=self.partner_id.lang)
        if carrier_with_partner_lang.product_id.description_sale:
            so_description = '%s: %s' % (carrier_with_partner_lang.name,
                                        carrier_with_partner_lang.product_id.description_sale)
        else:
            so_description = carrier_with_partner_lang.name
        taxes_ids = self.partner_id.taxes_id.ids
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
            values['name'] += _(' (Estimated Cost: %s )') % self._format_currency_amount(price_unit)
        else:
            values['price_unit'] = price_unit
        if carrier.free_over and self.currency_id.is_zero(price_unit) :
            values['name'] += '\n' + 'Free Shipping'
        if self.order_line:
            values['sequence'] = self.order_line[-1].sequence + 1
        sol = SaleOrderLine.sudo().create(values)
        return sol   
    
    
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
        
    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return
        valid_values = self.product_id.product_tmpl_id.valid_product_template_attribute_line_ids.product_template_value_ids
        # remove the is_custom values that don't belong to this template
        for pacv in self.product_custom_attribute_value_ids:
            if pacv.custom_product_template_attribute_value_id not in valid_values:
                self.product_custom_attribute_value_ids -= pacv

        # remove the no_variant attributes that don't belong to this template
        for ptav in self.product_no_variant_attribute_value_ids:
            if ptav._origin not in valid_values:
                self.product_no_variant_attribute_value_ids -= ptav

        vals = {}
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id
            vals['product_uom_qty'] = self.product_uom_qty or 1.0

        product = self.product_id.with_context(
            lang=get_lang(self.env, self.order_id.partner_id.lang).code,
            partner=self.order_id.partner_id,
            quantity=vals.get('product_uom_qty') or self.product_uom_qty,
            date=self.order_id.date_order,
            pricelist=self.order_id.pricelist_id.id,
            uom=self.product_uom.id
        )

        vals.update(name=self.get_sale_order_line_multiline_description_sale(product))
        self.tax_id = self.order_id.partner_id.taxes_id # Added to get tax from Customer 
#         self._compute_tax_id() # commented to not to derive tax from product

        if self.order_id.pricelist_id and self.order_id.partner_id:
            vals['price_unit'] = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)
        self.update(vals)

        title = False
        message = False
        result = {}
        warning = {}
        if product.sale_line_warn != 'no-message':
            title = _("Warning for %s") % product.name
            message = product.sale_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            result = {'warning': warning}
            if product.sale_line_warn == 'block':
                self.product_id = False

        return result
    
class Opportunity2Quotation(models.TransientModel):
    _inherit = 'crm.quotation.partner'
    
    def action_apply(self):
        """ Convert lead to opportunity or merge lead and opportunity and open
            the freshly created opportunity view.
        """
        self.ensure_one()
        if self.action != 'nothing':
            self.lead_id.write({
                'partner_id': self.partner_id.id if self.action == 'exist' else self._create_partner()
            })
            self.lead_id._onchange_partner_id()    
            if self.action == 'exist':
                default_stage_id = self.env.ref('hcp_partner_pricelist.stage_lead5')
                self.lead_id.stage_id = default_stage_id
        return self.lead_id.action_new_quotation()
    
        
