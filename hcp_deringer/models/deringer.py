# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.osv import expression
import requests, json
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
from datetime import date, datetime
import logging
_logger = logging.getLogger(__name__)

class DeringerReport(models.TransientModel):
    _name = "deringer.report.download"
    _description = "Deringer Report Download"

    data = fields.Binary('File', required=True, attachment=False)
    filename = fields.Char('File Name', required=True, compute='_compute_mock_pdf_filename')

    @api.depends('data')
    def _compute_mock_pdf_filename(self):
        context = self._context
        deringer_res = self.env[context.get('active_model')].browse(int(context.get('active_id')))
        self.ensure_one()
        name = deringer_res.name + '.xml'
        self.filename = name


class DeringerForm(models.Model):
    _name = "deringer.form"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = "Deringer Form"

    name = fields.Char('Name',readonly=True, required=True, copy=False, default='New')
    date = fields.Datetime(string='Create Date', required=True, index=True, copy=False, default=fields.Datetime.now)
    partner_id = fields.Many2one('res.partner','Deringer Contact',required=1)
    invoice_ids = fields.Many2many('account.move','account_move_deringer_rel','invoice_id','deringer_id','Invoices')
    state = fields.Selection([('draft','Draft'),('xml_created','XML Generated'),('sent_email','Sent Email'),('cancel','Cancelled')],'Status', readonly=True, copy=False, default='draft')

   
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('deringer.form') or 'New'
        result = super(DeringerForm, self).create(vals)        
        return result

    #@api.multi
    def print_report_xml(self):
        # self.write({'state': 'xml_created'})
        xml_data = ''
        for record in self.invoice_ids:
            xml_data += "<Invoice>\n<Importer>HEAPRO0002</Importer>\n<Invoice_No>" +record.name +"<Invoice_No>\n<Invoice_Type>"+record.type+"</Invoice_Type>\n"
            count=1
            for line in  record.invoice_line_ids:
                xml_data += "<LineItem>\n<Description>"+line.name+"</Description>\n<LineNumber>"+str(count)+"</LineNumber>\n<TotalLineItemValue>"+str(line.price_subtotal)+"</TotalLineItemValue>\n</LineItem>\n"
                count = count + 1
            xml_data += "</Invoice>\n"
        xml_data = "<?xml version="+str(1.0)+" encoding="+"UTF-8"+" standalone="+"yes"+"?>\n<Consolidated>\n" + xml_data + "</Consolidated>\n"
        byte_xml = bytes(xml_data, 'utf-8') 
        output = base64.b64encode(byte_xml)
        res = self.env['deringer.report.download'].create({'data':output})
        context = {'res'}
        return { 
            'type': 'ir.actions.act_window',
            'res_model': 'deringer.report.download',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'res_id': res.id,}
        
    #@api.multi
    def action_cancel(self):
        self.write({'state': 'cancel'})

    #@api.multi
    def action_draft(self):
        self.write({'state': 'draft'})
        
    #@api.multi
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
